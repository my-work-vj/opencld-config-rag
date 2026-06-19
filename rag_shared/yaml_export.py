"""YAML export utilities for prompts and agent pipelines."""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPTS_DIR = REPO_ROOT / "prompts"
DEFAULT_AGENT_PIPELINES_DIR = REPO_ROOT / "agent_pipelines"


def _export_enabled() -> bool:
    return os.getenv("YAML_EXPORT_ENABLED", "true").lower() in ("1", "true", "yes")


def _hash_doc(doc: dict) -> str:
    payload = json.dumps(doc, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _write_yaml(path: Path, doc: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return _hash_doc(doc)


def export_prompt_template(
    template_id: str,
    name: str,
    description: str,
    active_version: int,
    versions: list[dict],
    output_dir: Path | None = None,
) -> tuple[str | None, datetime | None]:
    if not _export_enabled():
        return None, None
    directory = output_dir or DEFAULT_PROMPTS_DIR
    doc = {
        "prompt_template": {
            "id": template_id,
            "name": name,
            "description": description,
            "active_version": active_version,
            "versions": versions,
        }
    }
    path = directory / f"{template_id}.yaml"
    yaml_hash = _write_yaml(path, doc)
    exported_at = datetime.now(timezone.utc)
    logger.info(f"Exported prompt template to {path}")
    return yaml_hash, exported_at


def export_agent_pipeline(
    agent_doc: dict,
    output_dir: Path | None = None,
) -> tuple[str | None, datetime | None]:
    if not _export_enabled():
        return None, None
    directory = output_dir or DEFAULT_AGENT_PIPELINES_DIR
    agent_id = agent_doc.get("id") or agent_doc.get("name")
    doc = {"agent_pipeline": agent_doc}
    path = directory / f"{agent_id}.yaml"
    yaml_hash = _write_yaml(path, doc)
    exported_at = datetime.now(timezone.utc)
    logger.info(f"Exported agent pipeline to {path}")
    return yaml_hash, exported_at
