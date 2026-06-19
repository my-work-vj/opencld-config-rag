"""Seed prompt templates from prompts/*.yaml."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from rag_shared.prompt_seed import seed_from_directory  # noqa: E402

if __name__ == "__main__":
    ids = seed_from_directory()
    print(f"Seeded {len(ids)} prompt template(s): {', '.join(ids)}")
