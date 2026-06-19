"""Run Pathway connector scripts inside the official Pathway Docker image."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from connectors.pathway.container import container_name, ensure_container_running

logger = logging.getLogger(__name__)

_SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"


def _docker_timeout() -> int:
    import os
    return int(os.getenv("PATHWAY_DOCKER_TIMEOUT_SEC", "900"))


def _parse_json_output(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise RuntimeError("Pathway container produced no output")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"Pathway container did not return JSON: {text[:500]}")
    return json.loads(text[start:end + 1])


def run_pathway_script(
    script_name: str,
    *,
    args: list[str],
) -> dict[str, Any]:
    """
    Execute a script in the long-running Pathway container via docker exec.

    Paths in args must be container paths (e.g. /data/connectors/{id}/credentials.json).
    """
    ensure_container_running()

    script_path = _SCRIPTS_DIR / script_name
    if not script_path.is_file():
        raise RuntimeError(f"Pathway script not found: {script_path}")

    name = container_name()
    cmd: list[str] = ["docker", "exec", name, "python", f"/scripts/{script_name}"]
    cmd.extend(args)

    logger.info("Pathway exec: %s %s", name, script_name)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=_docker_timeout(),
        check=False,
    )

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Pathway script failed (exit {result.returncode}): {detail[:2000]}"
        )

    if result.stderr:
        logger.debug("Pathway stderr: %s", result.stderr[:1000])

    return _parse_json_output(result.stdout)


def bootstrap_pathway() -> dict[str, Any]:
    """Pull image (if missing) and ensure the Pathway container is running."""
    from connectors.pathway.container import get_status, pull_image

    status = get_status()
    if status.docker_available and not status.image_present:
        pull_image()
    final = ensure_container_running()
    return final.as_dict()
