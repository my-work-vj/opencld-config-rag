"""REST API endpoints for evaluation — trigger, list, and inspect results."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from rag_shared.db import SessionLocal as SharedSession
from rag_shared.knowledge_repo import KnowledgeSourceRepo

from evaluation.reporter import store_result as _store_report, _latest_report
from evaluation.thresholds import check_thresholds

logger = logging.getLogger(__name__)
router = APIRouter()


def _eval_reports_dir() -> Path:
    """Get the reports directory, creating it if needed."""
    reports = Path(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "eval_reports",
    ))
    reports.mkdir(parents=True, exist_ok=True)
    return reports


def _collection_exists(name: str) -> bool:
    """Check if a collection exists in the DB."""
    db = SharedSession()
    try:
        try:
            ks = KnowledgeSourceRepo.get(db, name)
            return ks is not None
        except Exception:
            return False
    finally:
        db.close()


@router.post("/collections/{name}/evaluate")
async def evaluate_collection(
    name: str,
    run_retrieval: bool = False,
):
    """
    Run evaluation on a collection (Layers 1-4, optionally Layer 5 retrieval).

    First syncs to ensure data is current, then evaluates the stored data
    from Qdrant and the DB.
    """
    if not _collection_exists(name):
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")

    import time
    from services.collection_sync_service import sync_collection
    from services.evaluation_service import evaluate_collection_from_storage

    t0 = time.time()

    # Step 1: Sync to make sure data is current
    try:
        sync_collection(name)
    except Exception as exc:
        logger.warning("Sync before evaluation failed for '%s': %s", name, exc)
        # Continue anyway — we can evaluate whatever is in Qdrant

    # Step 2: Evaluate stored data from Qdrant + DB
    try:
        eval_result = evaluate_collection_from_storage(name)
        duration = time.time() - t0
        eval_result["sync_duration_sec"] = round(duration, 3)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}")

    # Step 3: Run retrieval evaluation if requested
    retrieval_result = None
    if run_retrieval:
        try:
            from evaluation.test_data import GoldenTestSet
            from evaluation.retrieval_eval import evaluate_retrieval
            from qdrant_client import QdrantClient

            ts = GoldenTestSet(name)
            questions = ts.get_questions()
            if questions:
                qclient = QdrantClient(
                    host=os.getenv("QDRANT_HOST", "host.docker.internal"),
                    port=int(os.getenv("QDRANT_PORT", "6333")),
                )
                retrieval_result = evaluate_retrieval(
                    collection_name=name,
                    test_questions=[{"question": q.question, "ground_truth": q.ground_truth} for q in questions],
                    qdrant_client=qclient,
                )
                if retrieval_result:
                    eval_result.setdefault("layers", {})["retrieval"] = retrieval_result
        except Exception as exc:
            logger.warning("Retrieval eval failed for '%s': %s", name, exc)

    # Step 4: Return result (the report was already stored in evaluate...from_storage)
    report_path = eval_result.get("report_path", "")

    return {
        "collection": name,
        "status": "success",
        "duration_sec": round(duration, 3),
        "layers": eval_result.get("layers", {}),
        "thresholds": eval_result.get("thresholds", {}),
        "retrieval_evaluated": retrieval_result is not None,
        "report_path": report_path,
    }


@router.get("/collections/{name}/evaluations")
async def list_evaluations(name: str):
    """List evaluation report files for a collection."""
    coll_dir = _eval_reports_dir() / name
    if not coll_dir.exists():
        return {"collection": name, "reports": []}

    reports = sorted(coll_dir.glob("eval_*.json"), reverse=True)
    report_list = []
    for rp in reports:
        try:
            with open(rp) as f:
                data = json.load(f)
            ts = data.get("timestamp", 0)
            layers = data.get("layers", {})
            report_list.append({
                "filename": rp.name,
                "timestamp": ts,
                "status": layers.get("pipeline", {}).get("status", "unknown"),
                "has_retrieval": layers.get("retrieval") is not None,
            })
        except Exception:
            pass

    return {
        "collection": name,
        "count": len(report_list),
        "reports": report_list,
    }


@router.get("/collections/{name}/evaluations/latest")
async def get_latest_evaluation(name: str):
    """Get the most recent evaluation report for a collection."""
    latest = _latest_report(name)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No evaluation reports found for '{name}'")

    try:
        with open(latest) as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Cannot read report: {exc}")


@router.get("/collections/{name}/evaluations/latest/thresholds")
async def get_latest_thresholds(name: str):
    """Get the threshold check for the latest evaluation."""
    from evaluation.reporter import _latest_report

    latest = _latest_report(name)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No evaluation reports found for '{name}'")

    try:
        with open(latest) as f:
            data = json.load(f)
        thresholds = data.get("thresholds", {})

        # Normalize results to flat array if it's still nested (old reports)
        results = thresholds.get("results", {})
        if isinstance(results, dict):
            flat = []
            failures = thresholds.get("failures", [])
            for layer_name, metrics in results.items():
                if isinstance(metrics, dict):
                    for metric_name, check in metrics.items():
                        if isinstance(check, dict):
                            flat.append({
                                "layer": layer_name,
                                "metric": metric_name,
                                "value": check.get("value"),
                                "threshold": check.get("threshold", {}),
                                "passed": check.get("passed", False),
                            })
            thresholds["results"] = flat
            thresholds["summary"] = {
                "total": len(flat),
                "passed": sum(1 for r in flat if r["passed"]),
                "failed": sum(1 for r in flat if not r["passed"]),
            }
            thresholds["all_passed"] = len(failures) == 0

        return thresholds
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Threshold check failed: {exc}")
