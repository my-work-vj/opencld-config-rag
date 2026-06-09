"""API Routes."""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv

from core.registry import StrategyRegistry
from core.pipeline import RAGPipeline
from core.db import SessionLocal, init_db
from core.models import PipelineConfig, DocumentRecord, QueryLog
from api.models import (
    PipelineInfo, PipelineList, IngestRequest, IngestResponse,
    QueryRequest, QueryResponse, ChunkResult,
    StrategyInfo, CompareQueryRequest, CompareResult, CompareResponse,
    StatusResponse,
)

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Utility: load pipeline config from file
# ──────────────────────────────────────────────

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def _load_pipeline_config(name: str) -> dict:
    """Load a pipeline config from the config directory."""
    candidates = [
        CONFIG_DIR / f"{name}.yaml",
        CONFIG_DIR / f"{name}.yml",
        CONFIG_DIR / f"{name}.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                if path.suffix == ".json":
                    return json.load(f)
                return yaml.safe_load(f)
    raise HTTPException(status_code=404, detail=f"Pipeline config '{name}' not found. Available: {list_available_pipelines()}")


def list_available_pipelines() -> list[str]:
    """List all available pipeline config files."""
    configs = []
    for ext in ("*.yaml", "*.yml", "*.json"):
        for p in CONFIG_DIR.glob(ext):
            configs.append(p.stem)
    return sorted(configs)


# ──────────────────────────────────────────────
# Health / Status
# ──────────────────────────────────────────────

@router.get("/health", response_model=StatusResponse)
async def health():
    """Check health of all connected services."""
    llm_ok = False
    qdrant_ok = False
    pg_ok = False
    pipeline_count = 0
    doc_count = 0

    # Check LiteLLM
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

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
        qc.get_collections()
        qdrant_ok = True
    except Exception:
        pass

    # Check PostgreSQL
    try:
        from sqlalchemy import text
        from core.db import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            pg_ok = True
    except Exception:
        pass

    # Count pipelines
    pipeline_count = len(list_available_pipelines())

    return StatusResponse(
        status="healthy" if all([llm_ok, qdrant_ok, pg_ok]) else "degraded",
        llm_available=llm_ok,
        qdrant_available=qdrant_ok,
        postgres_available=pg_ok,
        pipeline_count=pipeline_count,
        document_count=doc_count,
    )


# ──────────────────────────────────────────────
# Pipeline Management
# ──────────────────────────────────────────────

@router.get("/pipelines", response_model=PipelineList)
async def list_pipelines():
    """List all available pipeline configurations."""
    names = list_available_pipelines()
    pipelines = []
    for name in names:
        config = _load_pipeline_config(name)
        p = config.get("pipeline", {})
        pipelines.append(PipelineInfo(
            name=p.get("name", name),
            description=p.get("description", ""),
            stages=p.get("stages", {}),
        ))
    return PipelineList(pipelines=pipelines)


@router.get("/pipelines/{name}", response_model=PipelineInfo)
async def get_pipeline(name: str):
    """Get details of a specific pipeline."""
    config = _load_pipeline_config(name)
    p = config.get("pipeline", {})
    return PipelineInfo(
        name=p.get("name", name),
        description=p.get("description", ""),
        stages=p.get("stages", {}),
    )


# ──────────────────────────────────────────────
# Strategies
# ──────────────────────────────────────────────

@router.get("/strategies")
async def list_strategies():
    """List all registered strategies grouped by stage."""
    return StrategyRegistry.list_strategies()


# ──────────────────────────────────────────────
# Ingestion
# ──────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    """Ingest documents and index them using the specified pipeline."""
    config = _load_pipeline_config(req.pipeline)
    pipeline = RAGPipeline(config)

    source = req.source
    if req.source_type == "pdf":
        ingestion_config = {"ingestion": {"strategy": "pdf_ingestion", "config": {}}}
        config["pipeline"]["stages"].update(ingestion_config)
    elif req.source_type == "web":
        ingestion_config = {"ingestion": {"strategy": "web_ingestion", "config": {}}}
        config["pipeline"]["stages"].update(ingestion_config)

    try:
        ctx = pipeline.run_ingestion_pipeline(source=source)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    # Log to PostgreSQL
    try:
        from core.db import SessionLocal
        db = SessionLocal()
        for doc in ctx.documents:
            record = DocumentRecord(
                filename=doc.filename or "unknown",
                pipeline_name=pipeline.name,
                chunk_count=len([c for c in ctx.chunks if c.document_id == doc.id]),
                content_preview=doc.content[:200],
                metadata_json=doc.metadata,
            )
            db.add(record)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Could not save to PostgreSQL: {e}")

    return IngestResponse(
        document_count=len(ctx.documents),
        chunk_count=len(ctx.chunks),
        embedding_count=len(ctx.embeddings),
        pipeline=pipeline.name,
        status="success",
    )


# ──────────────────────────────────────────────
# Query
# ──────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Run a query through a pipeline and return the response."""
    config = _load_pipeline_config(req.pipeline)
    pipeline = RAGPipeline(config)

    retrieval_overrides = req.retrieval_overrides or {}
    if req.top_k:
        retrieval_overrides.setdefault("config", {})["top_k"] = req.top_k

    t0 = time.time()
    try:
        ctx = pipeline.run_query_only(
            query=req.query,
            retrieval_overrides=retrieval_overrides,
            reranking_overrides=req.reranking_overrides,
            response_overrides=req.response_overrides,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    total_time = (time.time() - t0) * 1000

    # Determine retrieval method from the result
    methods = set(r.retrieval_method for r in ctx.retrieved_chunks)
    method = "+".join(sorted(methods)) if methods else "unknown"

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

    # Log query
    try:
        db = SessionLocal()
        log = QueryLog(
            pipeline_name=pipeline.name,
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
        pipeline=pipeline.name,
        response=ctx.response,
        retrieval_method=method,
        chunks=chunks,
        timings=ctx.state.get("timings", {}),
        total_time_ms=total_time,
    )


# ──────────────────────────────────────────────
# Compare — run same query across multiple pipelines
# ──────────────────────────────────────────────

@router.post("/compare", response_model=CompareResponse)
async def compare(req: CompareQueryRequest):
    """Run the same query across multiple pipelines side-by-side."""
    results = []
    for pipeline_name in req.pipelines:
        try:
            config = _load_pipeline_config(pipeline_name)
            pipeline = RAGPipeline(config)
            t0 = time.time()
            ctx = pipeline.run_query_only(
                query=req.query,
                retrieval_overrides={"config": {"top_k": req.top_k}},
            )
            elapsed = (time.time() - t0) * 1000

            methods = set(r.retrieval_method for r in ctx.retrieved_chunks)
            method = "+".join(sorted(methods))

            results.append(CompareResult(
                pipeline=pipeline_name,
                response=ctx.response,
                chunk_count=len(ctx.retrieved_chunks),
                retrieval_method=method,
                timings={**ctx.state.get("timings", {}), "total_ms": elapsed},
            ))
        except Exception as e:
            results.append(CompareResult(
                pipeline=pipeline_name,
                response=f"Error: {e}",
                chunk_count=0,
                retrieval_method="error",
                timings={},
            ))

    return CompareResponse(query=req.query, results=results)


# ──────────────────────────────────────────────
# Query Logs
# ──────────────────────────────────────────────

@router.get("/logs")
async def get_logs(limit: int = 50, pipeline: Optional[str] = None):
    """Retrieve recent query logs."""
    try:
        db = SessionLocal()
        query = db.query(QueryLog).order_by(QueryLog.created_at.desc())
        if pipeline:
            query = query.filter(QueryLog.pipeline_name == pipeline)
        logs = query.limit(limit).all()
        db.close()
        return [
            {
                "id": log.id,
                "pipeline": log.pipeline_name,
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
