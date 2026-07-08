"""Route connector files to ingestion/chunking strategies based on modality."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.modality import is_image_path

IMAGE_INGESTION_OVERRIDE = {"strategy": "image_ingestion", "config": {}}
IMAGE_CHUNKING_OVERRIDE = {"strategy": "image_chunking", "config": {}}


def resolve_pipeline_overrides(
    path: str | Path,
    ingestion_mode: str = "document_plain",
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Return (ingestion_overrides, chunking_overrides) for multimodal Path B routing.

    document_vision: standalone images use image ingestion + one chunk per image.
    """
    if ingestion_mode != "document_vision":
        return None, None

    file_path = Path(path)
    if not is_image_path(file_path):
        return None, None

    return IMAGE_INGESTION_OVERRIDE, IMAGE_CHUNKING_OVERRIDE
