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

