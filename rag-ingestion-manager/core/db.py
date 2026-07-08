"""Database — shared pipeline DB + local ingestion metadata tables."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from rag_shared.db import engine, SessionLocal, Base, init_pipeline_tables  # noqa: E402

__all__ = ["engine", "SessionLocal", "Base", "init_pipeline_tables"]

def init_db():
    init_pipeline_tables()
    from rag_shared.models import DocumentRecord  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_ingestion_metadata_columns()


def _migrate_ingestion_metadata_columns() -> None:
    """Add columns introduced after initial deployments (idempotent)."""
    from sqlalchemy import text

    statements = [
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64) DEFAULT ''",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS indexed_in_vector BOOLEAN DEFAULT FALSE",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS indexed_in_sparse BOOLEAN DEFAULT FALSE",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS indexed_in_graph BOOLEAN DEFAULT FALSE",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS indexed_in_metadata BOOLEAN DEFAULT FALSE",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS indexed_in_memory BOOLEAN DEFAULT FALSE",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

