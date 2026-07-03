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
    """Create shared pipeline and knowledge tables + ingestion metadata tables."""
    from rag_shared.models import (
        Agent,
        ChunkRecord,
        CollectionConnector,
        CollectionIndexConfig,
        ConnectorFile,
        DataConnector,
        DocumentRecord,
        GraphEntityRecord,
        GraphRelationRecord,
        IndexedDocument,
        KnowledgeBase,
        KnowledgeSource,
        PromptTemplate,
        PromptVersion,
        RagPipeline,
        RagPipelineAudit,
        SessionMemoryRecord,
    )
    Base.metadata.create_all(bind=engine)
    _migrate_agent_columns()


def _migrate_agent_columns():
    """Add new agent columns and migrate legacy single-KB data."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "agents" not in insp.get_table_names():
        return

    existing = {c["name"] for c in insp.get_columns("agents")}
    alters = []
    new_cols = {
        "knowledge_base_names": "JSONB DEFAULT '[]'::jsonb",
        "prompt_template_id": "VARCHAR(255)",
        "prompt_version": "INTEGER",
        "response_strategy": "VARCHAR(100) DEFAULT 'contextual_response'",
        "query_stages": "JSONB DEFAULT '{}'::jsonb",
        "yaml_exported_at": "TIMESTAMP WITH TIME ZONE",
        "yaml_hash": "VARCHAR(64)",
    }
    for col, typedef in new_cols.items():
        if col not in existing:
            alters.append(f"ADD COLUMN {col} {typedef}")

    if alters:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE agents {', '.join(alters)}"))

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE agents
                SET knowledge_base_names = jsonb_build_array(knowledge_base_name)
                WHERE knowledge_base_name IS NOT NULL
                  AND (knowledge_base_names IS NULL
                       OR knowledge_base_names = '[]'::jsonb
                       OR knowledge_base_names = 'null'::jsonb)
                """
            )
        )
