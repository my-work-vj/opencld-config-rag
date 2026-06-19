"""Ingestion API routes — collection-driven runtime config."""

import os
import logging

from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from core.registry import StrategyRegistry
from core.pipeline import IngestionPipeline
from core.db import SessionLocal, init_db
from core.models import DocumentRecord
from api.models import IngestRequest, IngestResponse, PathwayDockerHealthResponse, StatusResponse
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.collection_loader import load_collection_ingestion_config
from rag_shared.defaults import DEFAULT_INGESTION_STAGES, clone_stage_map
from rag_shared.knowledge_repo import KnowledgeSourceNotFoundError, KnowledgeSourceRepo
from rag_shared.strategy_options import merge_strategy_options

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=StatusResponse)
async def health():
    llm_ok = qdrant_ok = pg_ok = False
    collections = []
    pipeline_count = 0
    ks_count = 0

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
            from rag_shared.models import KnowledgeSource
            ks_count = db.query(KnowledgeSource).count()
        finally:
            db.close()
    except Exception:
        pass

    pathway_ready = False
    pathway_message = ""
    try:
        from connectors.pathway.container import get_status
        pw_status = get_status()
        pathway_ready = pw_status.ready
        pathway_message = pw_status.message
    except Exception as exc:
        pathway_message = str(exc)

    core_ok = all([llm_ok, qdrant_ok, pg_ok])
    overall = "healthy" if core_ok and pathway_ready else "degraded"

    return StatusResponse(
        status=overall,
        llm_available=llm_ok,
        qdrant_available=qdrant_ok,
        postgres_available=pg_ok,
        pathway_docker_ready=pathway_ready,
        pathway_docker_message=pathway_message,
        pipeline_count=pipeline_count,
        collections=collections,
        knowledge_source_count=ks_count,
        knowledge_base_count=0,
        agent_count=0,
    )


@router.get("/connectors/pathway/health", response_model=PathwayDockerHealthResponse)
async def pathway_docker_health():
    from connectors.pathway.container import get_status
    status = get_status()
    return PathwayDockerHealthResponse(**status.as_dict())


@router.post("/connectors/pathway/start", response_model=PathwayDockerHealthResponse)
async def pathway_docker_start():
    from connectors.pathway.docker_runner import bootstrap_pathway
    result = bootstrap_pathway()
    return PathwayDockerHealthResponse(**result)


@router.get("/strategies")
async def list_strategies():
    return merge_strategy_options(StrategyRegistry.list_strategies())


@router.get("/qdrant/collections")
async def list_qdrant_collections():
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
    db = SharedSession()
    try:
        if req.collection:
            config = load_collection_ingestion_config(db, req.collection)
        else:
            config = {
                "pipeline": {
                    "id": "inline",
                    "name": "inline",
                    "description": "",
                    "stages": clone_stage_map(DEFAULT_INGESTION_STAGES),
                    "embedding_model": "",
                    "chat_model": "",
                    "reranker_model": "",
                    "llm_params": {},
                    "status": "active",
                }
            }
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()

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
        pipeline=req.collection or "inline",
        pipeline_name=pipeline.name,
        collection_name=collection_name,
        status="success",
        timings=ctx.state.get("timings", {}),
    )
