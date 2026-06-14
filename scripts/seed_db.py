#!/usr/bin/env python3
"""Seed shared rag_pipelines table from pipelines/*.yaml."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from rag_shared.seed import seed_from_directory  # noqa: E402

if __name__ == "__main__":
    ids = seed_from_directory()
    print(f"Seeded {len(ids)} pipeline(s): {', '.join(ids)}")
