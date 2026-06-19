"""Knowledge Source API routes — ingestion manager."""

import logging
import os

from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv
from qdrant_client import QdrantClient

from core.pipeline import IngestionPipeline
from core.db import SessionLocal
from core.models import DocumentRecord
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.knowledge_repo import (
    KnowledgeSourceNotFoundError,
    KnowledgeSourceRepo,
)
from rag_shared.collection_loader import load_collection_ingestion_config
from rag_shared.defaults import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_INGESTION_STAGES,
    DEFAULT_QUERY_STAGES,
    DEFAULT_VECTOR_SIZE,
    INLINE_PIPELINE_ID,
    clone_stage_map,
)
from rag_shared.schemas import (
    CreateKnowledgeSourceRequest,
    KnowledgeSourceIngestRequest,
    KnowledgeSourceInfo,
    KnowledgeSourceList,
)

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_info(record) -> KnowledgeSourceInfo:
    meta = record.metadata_json or {}
    return KnowledgeSourceInfo(
        id=record.id,
        name=record.name,
        description=record.description or "",
        collection_name=record.collection_name,
        embedding_model=record.embedding_model or "",
        vector_size=record.vector_size or 2048,
        document_count=record.document_count or 0,
        chunk_count=record.chunk_count or 0,
        status=record.status or "ready",
        ingestion_stages=meta.get("ingestion_stages") or {},
        query_stages=meta.get("query_stages") or {},
        chat_model=meta.get("chat_model") or "",
        reranker_model=meta.get("reranker_model") or "",
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.post("/knowledge-sources", response_model=KnowledgeSourceInfo, status_code=201)
async def create_knowledge_source(req: CreateKnowledgeSourceRequest):
    db = SharedSession()
    try:
        record = KnowledgeSourceRepo.create(db, req)
        meta = dict(record.metadata_json or {})
        meta.setdefault("ingestion_stages", clone_stage_map(DEFAULT_INGESTION_STAGES))
        meta.setdefault("query_stages", clone_stage_map(DEFAULT_QUERY_STAGES))
        record.metadata_json = meta
        record.pipeline_id = INLINE_PIPELINE_ID
        record.embedding_model = DEFAULT_EMBEDDING_MODEL
        record.vector_size = DEFAULT_VECTOR_SIZE
        db.commit()
        db.refresh(record)
        return _to_info(record)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


@router.get("/knowledge-sources", response_model=KnowledgeSourceList)
async def list_knowledge_sources():
    db = SharedSession()
    try:
        records = KnowledgeSourceRepo.list_all(db)
        return KnowledgeSourceList(sources=[_to_info(r) for r in records])
    finally:
        db.close()


@router.get("/knowledge-sources/{name}", response_model=KnowledgeSourceInfo)
async def get_knowledge_source(name: str):
    db = SharedSession()
    try:
        record = KnowledgeSourceRepo.get(db, name)
        return _to_info(record)
    except KnowledgeSourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.delete("/knowledge-sources/{name}", status_code=204)
async def delete_knowledge_source(
    name: str,
    delete_collection: bool = Query(False),
):
    db = SharedSession()
    try:
        record = KnowledgeSourceRepo.get(db, name)
        collection_name = record.collection_name
        KnowledgeSourceRepo.delete(db, name)
    except KnowledgeSourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()

    if delete_collection:
        try:
            qc = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
            )
            qc.delete_collection(collection_name)
        except Exception as e:
            logger.warning(f"Could not delete Qdrant collection '{collection_name}': {e}")


@router.post("/knowledge-sources/{name}/ingest")
async def ingest_knowledge_source(name: str, req: KnowledgeSourceIngestRequest):
    db = SharedSession()
    try:
        ks = KnowledgeSourceRepo.get(db, name)
        collection_name = ks.collection_name
        ks_name = ks.name
        KnowledgeSourceRepo.set_status(db, name, "indexing")
    except KnowledgeSourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()

    try:
        shared_db = SharedSession()
        try:
            config = load_collection_ingestion_config(shared_db, ks_name)
        finally:
            shared_db.close()

        if req.source_type == "pdf":
            config["pipeline"]["stages"]["ingestion"] = {
                "strategy": "pdf_ingestion",
                "config": {},
            }
        elif req.source_type == "web":
            config["pipeline"]["stages"]["ingestion"] = {
                "strategy": "web_ingestion",
                "config": {},
            }

        pipeline = IngestionPipeline(config)
        ctx = pipeline.run(
            source=req.source,
            indexing_overrides={"config": {"collection_name": collection_name}},
        )
    except Exception as e:
        db = SharedSession()
        try:
            KnowledgeSourceRepo.set_status(db, ks_name, "error")
        finally:
            db.close()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    doc_count = len(ctx.documents)
    chunk_count = len(ctx.chunks)

    db = SharedSession()
    try:
        KnowledgeSourceRepo.increment_counts(db, ks_name, doc_count, chunk_count, status="ready")
    finally:
        db.close()

    try:
        local_db = SessionLocal()
        for doc in ctx.documents:
            record = DocumentRecord(
                filename=doc.filename or "unknown",
                pipeline_name=pipeline.name,
                collection_name=collection_name,
                chunk_count=len([c for c in ctx.chunks if c.document_id == doc.id]),
                content_preview=doc.content[:200],
                metadata_json={
                    **doc.metadata,
                    "knowledge_source_name": ks_name,
                },
            )
            local_db.add(record)
        local_db.commit()
        local_db.close()
    except Exception as e:
        logger.warning(f"Could not save document metadata: {e}")

    return {
        "status": "success",
        "knowledge_source": ks_name,
        "document_count": doc_count,
        "chunk_count": chunk_count,
        "collection_name": collection_name,
        "timings": ctx.state.get("timings", {}),
    }


@router.get("/knowledge-sources/{name}/documents")
async def list_knowledge_source_documents(name: str):
    db_shared = SharedSession()
    try:
        ks = KnowledgeSourceRepo.get(db_shared, name)
    except KnowledgeSourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db_shared.close()

    try:
        db = SessionLocal()
        records = (
            db.query(DocumentRecord)
            .filter(DocumentRecord.collection_name == ks.collection_name)
            .order_by(DocumentRecord.created_at.desc())
            .all()
        )
        db.close()
        return [
            {
                "id": r.id,
                "filename": r.filename,
                "pipeline_name": r.pipeline_name,
                "collection_name": r.collection_name,
                "chunk_count": r.chunk_count,
                "content_preview": r.content_preview,
                "metadata": r.metadata_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
