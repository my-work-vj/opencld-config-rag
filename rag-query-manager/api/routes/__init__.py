"""Query API routes — collection and agent driven runtime config."""

import os
import time
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from core.registry import StrategyRegistry
from core.pipeline import QueryPipeline
from core.db import SessionLocal
from core.models import QueryLog
from api.models import (
    QueryRequest, QueryResponse, ChunkResult,
    CompareQueryRequest, CompareResult, CompareResponse, StatusResponse,
)
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.collection_loader import load_collection_query_config
from rag_shared.defaults import DEFAULT_QUERY_STAGES, clone_stage_map
from rag_shared.knowledge_repo import KnowledgeSourceNotFoundError
from rag_shared.strategy_options import merge_strategy_options

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)


def _load_query_config_for_request(collection_name: str | None) -> dict:
    if not collection_name:
        return {
            "pipeline": {
                "id": "inline",
                "name": "inline",
                "description": "",
                "stages": clone_stage_map(DEFAULT_QUERY_STAGES),
                "embedding_model": "",
                "chat_model": "",
                "reranker_model": "",
                "llm_params": {},
                "status": "active",
            }
        }
    db = SharedSession()
    try:
        return load_collection_query_config(db, collection_name)
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


def _build_overrides(
    base: Optional[dict],
    collection_name: Optional[str],
) -> dict:
    overrides = dict(base or {})
    if collection_name:
        overrides.setdefault("config", {})["collection_name"] = collection_name
    return overrides


@router.get("/health", response_model=StatusResponse)
async def health():
    llm_ok = qdrant_ok = pg_ok = False
    collections = []
    pipeline_count = 0
    ks_count = 0
    kb_count = 0
    agent_count = 0

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
            from rag_shared.models import Agent, KnowledgeBase, KnowledgeSource
            ks_count = db.query(KnowledgeSource).count()
            kb_count = db.query(KnowledgeBase).count()
            agent_count = db.query(Agent).count()
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
        knowledge_source_count=ks_count,
        knowledge_base_count=kb_count,
        agent_count=agent_count,
    )


@router.get("/strategies")
async def list_strategies():
    return merge_strategy_options(StrategyRegistry.list_strategies())


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


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    source_name = req.collection or req.collection_name
    config = _load_query_config_for_request(source_name)
    pipeline = QueryPipeline(config)

    ks_overrides = _build_overrides(req.knowledge_store_overrides, req.collection_name)
    retrieval_overrides = dict(req.retrieval_overrides or {})
    if req.top_k:
        retrieval_overrides.setdefault("config", {})["top_k"] = req.top_k

    t0 = time.time()
    try:
        ctx = pipeline.run(
            query=req.query,
            knowledge_store_overrides=ks_overrides,
            retrieval_overrides=retrieval_overrides,
            reranking_overrides=req.reranking_overrides,
            response_overrides=req.response_overrides,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    total_time = (time.time() - t0) * 1000
    methods = set(r.retrieval_method for r in ctx.retrieved_chunks)
    method = "+".join(sorted(methods)) if methods else "unknown"
    collection = ctx.knowledge_store.collection_name if ctx.knowledge_store else "unknown"

    chunks = [
        ChunkResult(
            content=r.chunk.content[:500],
            score=r.score,
            retrieval_method=r.retrieval_method,
            filename=r.chunk.filename or r.chunk.metadata.get("filename"),
            chunk_index=r.chunk.chunk_index,
        )
        for r in ctx.retrieved_chunks
    ]

    try:
        db = SessionLocal()
        log = QueryLog(
            pipeline_name=source_name or "inline",
            collection_name=collection,
            query=req.query,
            retrieval_method=method,
            top_k=req.top_k,
            response=ctx.response[:500],
            retrieval_time_ms=ctx.state.get("timings", {}).get("retrieval", 0) * 1000,
            reranking_time_ms=ctx.state.get("timings", {}).get("reranking", 0) * 1000,
            response_time_ms=ctx.state.get("timings", {}).get("response", 0) * 1000,
            total_time_ms=total_time,
            chunk_count=len(ctx.retrieved_chunks),
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Could not log query: {e}")

    return QueryResponse(
        query=req.query,
        pipeline=source_name or "inline",
        pipeline_name=pipeline.name,
        collection_name=collection,
        response=ctx.response,
        retrieval_method=method,
        chunks=chunks,
        timings=ctx.state.get("timings", {}),
        total_time_ms=total_time,
    )


@router.post("/compare", response_model=CompareResponse)
async def compare(req: CompareQueryRequest):
    raise HTTPException(
        status_code=410,
        detail="Pipeline comparison was removed. Create agents with different query stage configs instead.",
    )


@router.get("/logs")
async def get_logs(limit: int = 50, pipeline: Optional[str] = None):
    try:
        db = SessionLocal()
        q = db.query(QueryLog).order_by(QueryLog.created_at.desc())
        if pipeline:
            q = q.filter(QueryLog.pipeline_name == pipeline)
        logs = q.limit(limit).all()
        db.close()
        return [
            {
                "id": log.id,
                "pipeline": log.pipeline_name,
                "collection": log.collection_name,
                "query": log.query[:200],
                "method": log.retrieval_method,
                "total_time_ms": log.total_time_ms,
                "chunk_count": log.chunk_count,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    except Exception as e:
        return {"error": str(e), "logs": []}
