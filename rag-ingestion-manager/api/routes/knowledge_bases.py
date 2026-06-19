"""Knowledge Base API routes — cluster collections for query retrieval."""

import logging

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
