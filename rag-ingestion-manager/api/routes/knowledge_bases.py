"""Knowledge Base API routes — cluster collections for query retrieval."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from rag_shared.db import SessionLocal as SharedSession
from rag_shared.knowledge_repo import (
    KnowledgeBaseNotFoundError,
    KnowledgeBaseRepo,
    KnowledgeSourceNotFoundError,
)
from rag_shared.schemas import (
    CreateKnowledgeBaseRequest,
    KnowledgeBaseInfo,
    KnowledgeBaseList,
    UpdateKnowledgeBaseRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)

THRESHOLD_PASS_RATIO = 0.9  # 90% of evaluation thresholds must pass


def _get_report_dir() -> Path:
    """Get the eval_reports directory relative to this file."""
    return Path(__file__).resolve().parent.parent / "eval_reports"


def _validate_evaluation_for_kb(collection_name: str) -> None:
    """Check if a collection's latest evaluation meets the threshold bar.

    Raises HTTPException with a descriptive message if the check fails.
    """
    import os
    from evaluation.reporter import _latest_report

    # 1. Find latest report
    coll_dir = _get_report_dir() / collection_name
    latest = _latest_report(collection_name)
    if not latest or not latest.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Collection '{collection_name}' has no evaluation. "
                "Run evaluation first (Evaluation → click Evaluate on this collection), "
                "then add it to a knowledge base."
            ),
        )

    # 2. Read thresholds from the report
    try:
        with open(latest) as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cannot read evaluation report for '{collection_name}': {exc}",
        )

    thresholds = report.get("thresholds", {})
    summary = thresholds.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)

    if total == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Collection '{collection_name}' has an evaluation report but no thresholds "
                "were computed. Run evaluation again to regenerate metrics."
            ),
        )

    ratio = passed / total if total > 0 else 0
    if ratio < THRESHOLD_PASS_RATIO:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Collection '{collection_name}' evaluation thresholds: {passed}/{total} "
                f"passed ({ratio:.0%}). At least {THRESHOLD_PASS_RATIO:.0%} required "
                f"to add to a knowledge base. Fix the failing metrics and re-evaluate."
            ),
        )

    logger.info(
        "Collection '%s' threshold check OK: %d/%d passed (%.0f%% ≥ %.0f%% threshold)",
        collection_name, passed, total, ratio * 100, THRESHOLD_PASS_RATIO * 100,
    )


def _kb_info(record) -> KnowledgeBaseInfo:
    return KnowledgeBaseInfo(
        id=record.id,
        name=record.name,
        description=record.description or "",
        sources=record.sources or [],
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.post("/knowledge-bases", response_model=KnowledgeBaseInfo, status_code=201)
async def create_knowledge_base(req: CreateKnowledgeBaseRequest):
    # Validate each collection has passing evaluations
    if req.source_names:
        for coll_name in req.source_names:
            _validate_evaluation_for_kb(coll_name)

    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.create(db, req)
        return _kb_info(record)
    except (ValueError, KnowledgeSourceNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()


@router.get("/knowledge-bases", response_model=KnowledgeBaseList)
async def list_knowledge_bases():
    db = SharedSession()
    try:
        records = KnowledgeBaseRepo.list_all(db)
        return KnowledgeBaseList(knowledge_bases=[_kb_info(r) for r in records])
    finally:
        db.close()


@router.get("/knowledge-bases/{name}", response_model=KnowledgeBaseInfo)
async def get_knowledge_base(name: str):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.get(db, name)
        return _kb_info(record)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.put("/knowledge-bases/{name}", response_model=KnowledgeBaseInfo)
async def update_knowledge_base(name: str, req: UpdateKnowledgeBaseRequest):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.update(db, name, req)
        return _kb_info(record)
    except (KnowledgeBaseNotFoundError, KnowledgeSourceNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()


@router.delete("/knowledge-bases/{name}", status_code=204)
async def delete_knowledge_base(name: str):
    db = SharedSession()
    try:
        KnowledgeBaseRepo.delete(db, name)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/knowledge-bases/{kb_name}/collections/{collection_name}", response_model=KnowledgeBaseInfo)
async def add_collection_to_kb(kb_name: str, collection_name: str):
    _validate_evaluation_for_kb(collection_name)

    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.add_source(db, kb_name, collection_name)
        return _kb_info(record)
    except (KnowledgeBaseNotFoundError, KnowledgeSourceNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()


@router.delete("/knowledge-bases/{kb_name}/collections/{collection_name}", response_model=KnowledgeBaseInfo)
async def remove_collection_from_kb(kb_name: str, collection_name: str):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.remove_source(db, kb_name, collection_name)
        return _kb_info(record)
    except (KnowledgeBaseNotFoundError, KnowledgeSourceNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()
