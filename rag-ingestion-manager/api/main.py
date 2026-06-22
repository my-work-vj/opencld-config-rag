"""FastAPI entry point for RAG Ingestion Manager."""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(_REPO_ROOT / ".env")

import strategies.ingestion   # noqa: F401
import strategies.chunking    # noqa: F401
import strategies.embedding   # noqa: F401
import strategies.indexing    # noqa: F401

import connectors  # noqa: F401 — register data source connector types

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.db import init_db
from core.registry import StrategyRegistry
from api.routes import router as api_router
from api.routes.collections import router as collections_router
from api.routes.data_connectors import router as data_connectors_router
from api.routes.knowledge_bases import router as knowledge_bases_router
from api.routes.knowledge_sources import router as knowledge_sources_router
from api.routes.evaluation import router as evaluation_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("RAG Ingestion Manager starting (hybrid config: DB runtime)")
    logger.info(f"PostgreSQL DB: {os.getenv('POSTGRES_DB', 'rag_platform')}")
    logger.info(f"LiteLLM: {os.getenv('LITELLM_BASE_URL', 'http://localhost:4000/v1')}")
    logger.info(f"Qdrant: {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")
    logger.info(f"Pathway Docker image: {os.getenv('PATHWAY_DOCKER_IMAGE', 'pathwaycom/pathway:latest')}")

    try:
        init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.warning(f"Database init failed: {e}")

    try:
        from connectors.pathway.docker_runner import bootstrap_pathway
        pw = bootstrap_pathway()
        logger.info(
            "Pathway Docker: %s (container=%s, running=%s)",
            pw.get("message"),
            pw.get("container_name"),
            pw.get("container_running"),
        )
    except Exception as e:
        logger.warning(f"Pathway Docker not ready: {e}")

    try:
        from monitoring.worker import start_monitor
        start_monitor()
    except Exception as e:
        logger.warning(f"Collection monitor not started: {e}")

    for stage, strats in StrategyRegistry.list_strategies().items():
        logger.info(f"  Stage '{stage}': {', '.join(strats)}")

    logger.info("Collections use inline stage config stored per collection")
    logger.info("=" * 60)
    yield
    logger.info("Shutting down RAG Ingestion Manager")


app = FastAPI(
    title="RAG Ingestion Manager",
    description="Ingestion service with per-collection stage configuration.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(knowledge_sources_router, prefix="/api/v1")
app.include_router(collections_router, prefix="/api/v1")
app.include_router(knowledge_bases_router, prefix="/api/v1")
app.include_router(data_connectors_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8081"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
