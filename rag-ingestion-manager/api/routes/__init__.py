"""Ingestion API routes — runtime loads pipeline config from shared DB."""

import os
import logging

from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from core.registry import StrategyRegistry
from core.pipeline import IngestionPipeline
from core.db import SessionLocal, init_db
from core.models import DocumentRecord
from api.models import IngestRequest, IngestResponse, StatusResponse
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.loader import load_ingestion_config
from rag_shared.repo import PipelineNotFoundError, PipelineRepo

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)


def _load_pipeline_config(pipeline_id: str) -> dict:
    db = SharedSession()
    try:
        return load_ingestion_config(db, pipeline_id)
    except PipelineNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.get("/health", response_model=StatusResponse)
async def health():
    llm_ok = qdrant_ok = pg_ok = False
    collections = []
    pipeline_count = 0

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
            api_key=os.getenv("LITELLM_API_KEY", "sk-vj"),
        )
        client.models.list()
        llm_ok = True
    except Exception:
        pass

    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
        collections = [c.name for c in qc.get_collections().collections]
        qdrant_ok = True
    except Exception:
        pass

    try:
        from sqlalchemy import text
        from core.db import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            pg_ok = True
        db = SharedSession()
        try:
            pipeline_count = len(PipelineRepo.list_all(db))
        finally:
            db.close()
    except Exception:
        pass

    return StatusResponse(
        status="healthy" if all([llm_ok, qdrant_ok, pg_ok]) else "degraded",
        llm_available=llm_ok,
        qdrant_available=qdrant_ok,
        postgres_available=pg_ok,
        pipeline_count=pipeline_count,
        collections=collections,
    )


@router.get("/strategies")
async def list_strategies():
    return StrategyRegistry.list_strategies()


@router.get("/collections")
async def list_collections():
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
        cols = qc.get_collections().collections
        return [
            {"name": c.name, "points_count": qc.get_collection(c.name).points_count}
            for c in cols
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    config = _load_pipeline_config(req.pipeline)

    if req.source_type == "pdf":
        config["pipeline"]["stages"]["ingestion"] = {
            "strategy": "pdf_ingestion", "config": {},
        }
    elif req.source_type == "web":
        config["pipeline"]["stages"]["ingestion"] = {
            "strategy": "web_ingestion", "config": {},
        }

    pipeline = IngestionPipeline(config)
    try:
        ctx = pipeline.run(source=req.source)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    collection_name = ctx.state.get("collection_name", "rag_documents")

    try:
        db = SessionLocal()
        for doc in ctx.documents:
            record = DocumentRecord(
                filename=doc.filename or "unknown",
                pipeline_name=pipeline.name,
                collection_name=collection_name,
                chunk_count=len([c for c in ctx.chunks if c.document_id == doc.id]),
                content_preview=doc.content[:200],
                metadata_json=doc.metadata,
            )
            db.add(record)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Could not save document metadata: {e}")

    return IngestResponse(
        document_count=len(ctx.documents),
        chunk_count=len(ctx.chunks),
        embedding_count=len(ctx.embeddings),
        pipeline=req.pipeline,
        pipeline_name=pipeline.name,
        collection_name=collection_name,
        status="success",
        timings=ctx.state.get("timings", {}),
    )
