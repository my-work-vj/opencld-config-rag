"""Shared database connection for pipeline configuration."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")
load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_USER = os.getenv("POSTGRES_USER", "llmproxy")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "your-strong-password")
DB_NAME = os.getenv("POSTGRES_DB", "rag_platform")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_pipeline_tables():
    """Create shared pipeline tables."""
    from rag_shared.models import RagPipeline, RagPipelineAudit  # noqa: F401
    Base.metadata.create_all(bind=engine)
