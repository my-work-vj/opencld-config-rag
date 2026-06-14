"""Seed the shared database from YAML pipeline definitions."""

import json
import logging
from pathlib import Path

import yaml

from rag_shared.db import SessionLocal, init_pipeline_tables
from rag_shared.repo import PipelineRepo
from rag_shared.schemas import PipelineYamlDocument, StageConfig

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PIPELINES_DIR = REPO_ROOT / "pipelines"


def _parse_yaml_file(path: Path) -> PipelineYamlDocument:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) if path.suffix in (".yaml", ".yml") else json.load(f)

    pipeline = raw.get("pipeline", raw)
    stages_raw = pipeline.get("stages", {})
    stages = {
        name: StageConfig(**stage) if isinstance(stage, dict) else stage
        for name, stage in stages_raw.items()
    }

    pipeline_id = pipeline.get("id") or path.stem
    return PipelineYamlDocument(
        id=pipeline_id,
        name=pipeline.get("name", pipeline_id),
        description=pipeline.get("description", ""),
        stages=stages,
        embedding_model=pipeline.get("embedding_model"),
        chat_model=pipeline.get("chat_model"),
        reranker_model=pipeline.get("reranker_model"),
        llm_params=pipeline.get("llm_params", {}),
        status=pipeline.get("status", "active"),
    )


def seed_from_directory(pipelines_dir: Path | None = None, dry_run: bool = False) -> list[str]:
    """Load all YAML/JSON files from pipelines_dir into rag_pipelines table."""
    directory = pipelines_dir or DEFAULT_PIPELINES_DIR
    if not directory.exists():
        raise FileNotFoundError(f"Pipelines directory not found: {directory}")

    init_pipeline_tables()
    seeded: list[str] = []

    files = sorted(
        list(directory.glob("*.yaml"))
        + list(directory.glob("*.yml"))
        + list(directory.glob("*.json"))
    )

    if not files:
        logger.warning(f"No pipeline files found in {directory}")
        return seeded

    db = SessionLocal()
    try:
        for path in files:
            doc = _parse_yaml_file(path)
            if dry_run:
                logger.info(f"[dry-run] Would upsert pipeline '{doc.id}' from {path.name}")
            else:
                PipelineRepo.upsert_from_yaml(db, doc, changed_by="seed_db")
            seeded.append(doc.id)
    finally:
        db.close()

    return seeded


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Seed rag_pipelines from YAML files")
    parser.add_argument("--dir", type=Path, default=DEFAULT_PIPELINES_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ids = seed_from_directory(args.dir, dry_run=args.dry_run)
    print(f"Seeded {len(ids)} pipeline(s): {', '.join(ids)}")
