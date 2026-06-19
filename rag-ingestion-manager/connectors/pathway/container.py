"""Manage the long-running Pathway Docker container for data source sync."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_INGESTION_ROOT = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _INGESTION_ROOT.parent
_COMPOSE_FILE = _REPO_ROOT / "docker-compose.yml"
_DEFAULT_IMAGE = "pathwaycom/pathway:latest"
_CONTAINER_MOUNT = "/data/connectors"


def container_name() -> str:
    return os.getenv("PATHWAY_CONTAINER_NAME", "opncld-rag-pathway").strip() or "opncld-rag-pathway"


def docker_image() -> str:
    return os.getenv("PATHWAY_DOCKER_IMAGE", _DEFAULT_IMAGE).strip() or _DEFAULT_IMAGE


def connectors_host_dir() -> Path:
    raw = os.getenv("CONNECTORS_DATA_DIR", str(_INGESTION_ROOT / "data" / "connectors"))
    path = Path(raw)
    if not path.is_absolute():
        path = (_INGESTION_ROOT / path).resolve()
    return path


def host_to_container_path(host_path: str | Path) -> str:
    """Map a host connector file path to the path inside the Pathway container."""
    host = Path(host_path).resolve()
    root = connectors_host_dir().resolve()
    try:
        rel = host.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            f"Connector path {host} is outside CONNECTORS_DATA_DIR ({root}). "
            "Set CONNECTORS_DATA_DIR to match the docker-compose volume mount."
        ) from exc
    return f"{_CONTAINER_MOUNT}/{rel.as_posix()}"


def container_to_host_path(container_path: str | Path) -> str:
    """Map a Pathway container path back to the host CONNECTORS_DATA_DIR path."""
    raw = str(container_path).replace("\\", "/")
    prefix = f"{_CONTAINER_MOUNT}/"
    if raw.startswith(prefix):
        rel = raw[len(prefix):]
        return str((connectors_host_dir() / rel).resolve())
    path = Path(container_path)
    if path.is_file():
        return str(path.resolve())
    return str(path)


@dataclass
class PathwayDockerStatus:
    docker_available: bool
    docker_message: str
    image: str
    image_present: bool
    container_name: str
    container_running: bool
    container_status: str
    ready: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "docker_available": self.docker_available,
            "docker_message": self.docker_message,
            "image": self.image,
            "image_present": self.image_present,
            "container_name": self.container_name,
            "container_running": self.container_running,
            "container_status": self.container_status,
            "ready": self.ready,
            "message": self.message,
        }


def _run(cmd: list[str], timeout: int = 120, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        cwd=cwd,
    )


def check_docker() -> tuple[bool, str]:
    try:
        result = _run(["docker", "version"], timeout=30)
    except FileNotFoundError:
        return False, "Docker is not installed or not on PATH"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "Docker is not running").strip()
    return True, "Docker is available"


def check_image_present(image: str) -> bool:
    result = _run(["docker", "image", "inspect", image], timeout=30)
    return result.returncode == 0


def get_container_state(name: str) -> tuple[bool, str]:
    result = _run(
        ["docker", "inspect", "-f", "{{.State.Status}}", name],
        timeout=30,
    )
    if result.returncode != 0:
        return False, "not_created"
    status = (result.stdout or "").strip() or "unknown"
    return status == "running", status


def get_status() -> PathwayDockerStatus:
    image = docker_image()
    name = container_name()
    docker_ok, docker_msg = check_docker()
    image_present = check_image_present(image) if docker_ok else False
    running, container_status = get_container_state(name) if docker_ok else (False, "unknown")

    if not docker_ok:
        message = docker_msg
    elif not image_present:
        message = f"Pathway image not found locally: {image}. Run: docker pull {image}"
    elif not running:
        message = f"Pathway container '{name}' is not running"
    else:
        message = f"Pathway container '{name}' is running"

    ready = docker_ok and image_present and running

    return PathwayDockerStatus(
        docker_available=docker_ok,
        docker_message=docker_msg,
        image=image,
        image_present=image_present,
        container_name=name,
        container_running=running,
        container_status=container_status,
        ready=ready,
        message=message,
    )


def pull_image() -> None:
    docker_ok, msg = check_docker()
    if not docker_ok:
        raise RuntimeError(msg)
    image = docker_image()
    logger.info("Pulling Pathway image %s", image)
    result = _run(["docker", "pull", image], timeout=900)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docker pull failed").strip())


def ensure_container_running() -> PathwayDockerStatus:
    """Start the Pathway container if needed. Returns current status."""
    status = get_status()
    if not status.docker_available:
        raise RuntimeError(status.docker_message)

    name = container_name()

    if status.container_running:
        return status

    # Try start existing container
    start_result = _run(["docker", "start", name], timeout=60)
    if start_result.returncode == 0:
        logger.info("Started existing Pathway container %s", name)
        return get_status()

    if not status.image_present:
        pull_image()

    if not _COMPOSE_FILE.is_file():
        raise RuntimeError(f"docker-compose.yml not found at {_COMPOSE_FILE}")

    logger.info("Creating Pathway container via docker compose")
    compose_result = _run(
        [
            "docker",
            "compose",
            "-f",
            str(_COMPOSE_FILE),
            "up",
            "-d",
            "pathway",
        ],
        timeout=300,
        cwd=str(_REPO_ROOT),
    )
    if compose_result.returncode != 0:
        detail = (compose_result.stderr or compose_result.stdout or "").strip()
        raise RuntimeError(f"Failed to start Pathway container: {detail}")

    final = get_status()
    if not final.container_running:
        raise RuntimeError(final.message)
    return final


def stop_container() -> None:
    name = container_name()
    _run(["docker", "stop", name], timeout=60)

