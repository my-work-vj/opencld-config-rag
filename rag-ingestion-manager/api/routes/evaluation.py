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

    Triggers a sync-evaluation cycle and stores the report.
    """
    if not _collection_exists(name):
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")

    import time
    from services.collection_sync_service import sync_collection

    t0 = time.time()
    try:
        result = sync_collection(name)
        duration = time.time() - t0
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")

    # Run retrieval evaluation if requested
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
                    host=os.getenv("QDRANT_HOST", "localhost"),
                    port=int(os.getenv("QDRANT_PORT", "6333")),
                )
                retrieval_result = evaluate_retrieval(
                    collection_name=name,
                    test_questions=[{"question": q.question, "ground_truth": q.ground_truth} for q in questions],
                    qdrant_client=qclient,
                )
        except Exception as exc:
            logger.warning("Retrieval eval failed for '%s': %s", name, exc)

    # Build the full evaluation result
    eval_result = {
        "collection_name": name,
        "timestamp": t0,
        "layers": {
            "extraction": result.get("evaluation", {}).get("layers", {}).get("extraction", {}),
            "chunking": result.get("evaluation", {}).get("layers", {}).get("chunking", {}),
            "embedding": result.get("evaluation", {}).get("layers", {}).get("embedding", {}),
            "pipeline": result,
            "retrieval": retrieval_result,
        },
    }

    # Check thresholds
    threshold_result = check_thresholds(eval_result)

    # Store report
    report_path = _store_report(eval_result)

    return {
        "collection": name,
        "status": result.get("status", "unknown"),
        "sync_duration_sec": round(duration, 3),
        "added": result.get("added", 0),
        "updated": result.get("updated", 0),
        "deleted": result.get("deleted", 0),
        "unchanged": result.get("unchanged", 0),
        "errors": result.get("errors", []),
        "thresholds": threshold_result,
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
        threshold_result = check_thresholds(data)
        return threshold_result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Threshold check failed: {exc}")
