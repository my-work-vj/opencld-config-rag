"""Seed prompt templates from prompts/*.yaml."""

import logging
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from rag_shared.db import SessionLocal, init_pipeline_tables
from rag_shared.prompt_repo import PromptTemplateRepo

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPTS_DIR = REPO_ROOT / "prompts"


def _parse_prompt_file(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw.get("prompt_template", raw)


def seed_from_directory(
    db: Session | None = None,
    directory: Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    folder = directory or DEFAULT_PROMPTS_DIR
    if not folder.exists():
        logger.warning(f"Prompts directory not found: {folder}")
        return []

    own_session = db is None
    if own_session:
        init_pipeline_tables()
        db = SessionLocal()

    seeded: list[str] = []
    try:
        for path in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
            doc = _parse_prompt_file(path)
            template_id = doc.get("id") or path.stem
            if dry_run:
                logger.info(f"[dry-run] Would upsert prompt '{template_id}' from {path.name}")
                seeded.append(template_id)
                continue
            PromptTemplateRepo.upsert_from_yaml(db, doc)
            seeded.append(template_id)
    finally:
        if own_session and db:
            db.close()

    return seeded


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Seed prompt templates from YAML")
    parser.add_argument("--dir", type=Path, default=DEFAULT_PROMPTS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ids = seed_from_directory(directory=args.dir, dry_run=args.dry_run)
    print(f"Seeded {len(ids)} prompt template(s): {', '.join(ids)}")
