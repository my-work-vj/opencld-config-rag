"""Route connector files to ingestion/chunking strategies based on modality."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.modality import detect_source_modality, is_image_path, is_pdf_path

IMAGE_INGESTION_OVERRIDE = {"strategy": "image_ingestion", "config": {}}
IMAGE_CHUNKING_OVERRIDE = {"strategy": "image_chunking", "config": {}}
PDF_VISION_INGESTION_OVERRIDE = {"strategy": "pdf_vision_ingestion", "config": {}}
PDF_VISION_CHUNKING_OVERRIDE = {"strategy": "image_chunking", "config": {}}


def resolve_pipeline_overrides(
    path: str | Path,
    ingestion_mode: str = "document_plain",
    source_type: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Return (ingestion_overrides, chunking_overrides) for universal multimodal routing.

    document_vision:
      - standalone images → image_ingestion + image_chunking
      - PDFs → pdf_vision_ingestion (page raster + text) + image_chunking
    """
    if ingestion_mode != "document_vision":
        return None, None

    file_path = Path(path)
    modality = source_type or detect_source_modality(file_path)

    if is_image_path(file_path) or modality == "image":
        return IMAGE_INGESTION_OVERRIDE, IMAGE_CHUNKING_OVERRIDE

    if is_pdf_path(file_path) or modality == "pdf":
        return PDF_VISION_INGESTION_OVERRIDE, PDF_VISION_CHUNKING_OVERRIDE

    return None, None
