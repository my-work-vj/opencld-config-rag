"""FastAPI entry point for RAG Query Manager."""

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

import strategies.knowledge_store  # noqa: F401
import strategies.retrieval        # noqa: F401
import strategies.reranking        # noqa: F401
import strategies.response         # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.db import init_db
from core.registry import StrategyRegistry
from api.routes import router as api_router
from rag_shared.routes import create_pipeline_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("RAG Query Manager starting (hybrid config: DB runtime)")
    logger.info(f"PostgreSQL DB: {os.getenv('POSTGRES_DB', 'rag_platform')}")
    logger.info(f"LiteLLM: {os.getenv('LITELLM_BASE_URL', 'http://localhost:4000/v1')}")
    logger.info(f"Qdrant: {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")

    try:
        init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.warning(f"Database init failed: {e}")

    for stage, strats in StrategyRegistry.list_strategies().items():
        logger.info(f"  Stage '{stage}': {', '.join(strats)}")

    logger.info("Run scripts/seed_db.py to load pipelines/*.yaml into DB")
    logger.info("=" * 60)
    yield
    logger.info("Shutting down RAG Query Manager")


app = FastAPI(
    title="RAG Query Manager",
    description="Query pipeline with hybrid YAML seed + database runtime config.",
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

app.include_router(create_pipeline_router(), prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")

ui_dir = Path(__file__).parent.parent / "ui"
if ui_dir.exists():
    app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8082"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
