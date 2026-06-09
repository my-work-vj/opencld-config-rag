"""FastAPI application entry point for Multi-RAG Manager."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

# ── Must import strategies FIRST so they register with the registry ──
import strategies.ingestion    # noqa: F401
import strategies.chunking     # noqa: F401
import strategies.embedding    # noqa: F401
import strategies.indexing     # noqa: F401
import strategies.retrieval    # noqa: F401
import strategies.reranking    # noqa: F401
import strategies.response     # noqa: F401
# ──────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.db import init_db
from core.registry import StrategyRegistry
from api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("Multi-RAG Manager starting up...")
    logger.info(f"LiteLLM: {os.getenv('LITELLM_BASE_URL', 'http://localhost:4000/v1')}")
    logger.info(f"Qdrant: {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")
    logger.info(f"PostgreSQL: {os.getenv('POSTGRES_DB', 'multi_rag_manager')}")

    # Initialize database tables
    try:
        init_db()
        logger.info("PostgreSQL tables initialized")
    except Exception as e:
        logger.warning(f"PostgreSQL init failed (will retry on demand): {e}")

    # Log registered strategies
    stages = StrategyRegistry.list_strategies()
    for stage, strats in stages.items():
        logger.info(f"  Stage '{stage}': {', '.join(strats)}")

    logger.info("Multi-RAG Manager ready")
    logger.info("=" * 60)
    yield
    logger.info("Shutting down Multi-RAG Manager")


app = FastAPI(
    title="Multi-RAG Manager",
    description="A modular RAG pipeline manager with Naive, Vector, and Hybrid retrieval strategies.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the UI dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix="/api/v1")


# ──────────────────────────────────────────────
# Serve static UI
# ──────────────────────────────────────────────

ui_dir = Path(__file__).parent.parent / "ui"
if ui_dir.exists():
    app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")
    logger.info(f"Serving UI from {ui_dir}")
else:
    logger.warning(f"UI directory not found at {ui_dir}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8080"))
    logger.info(f"Starting server on port {port}")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
