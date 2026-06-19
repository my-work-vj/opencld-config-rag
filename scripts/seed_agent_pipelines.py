"""Seed agent pipelines from agent_pipelines/*.yaml."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from rag_shared.agent_yaml import seed_from_directory  # noqa: E402
from rag_shared.db import SessionLocal, init_pipeline_tables  # noqa: E402

if __name__ == "__main__":
    init_pipeline_tables()
    db = SessionLocal()
    try:
        ids = seed_from_directory(db)
        print(f"Seeded {len(ids)} agent pipeline(s): {', '.join(ids)}")
    finally:
        db.close()
