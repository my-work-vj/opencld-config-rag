"""Ensure repo root is on sys.path so rag_shared can be imported from subprojects."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def ensure_repo_root_on_path() -> Path:
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return _REPO_ROOT
