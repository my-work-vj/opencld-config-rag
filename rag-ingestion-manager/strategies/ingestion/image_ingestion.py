"""Ingest standalone image files for multimodal embedding (Path B)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from core.base_strategies import BaseIngestionStrategy, Document
from core.registry import StrategyRegistry
from services.modality import is_image_path, mime_for_path

logger = logging.getLogger(__name__)


@StrategyRegistry.register("ingestion", "image_ingestion")
class ImageIngestion(BaseIngestionStrategy):
    """Produce one image document per file for nvidia-embed multimodal vectors."""

    def ingest(self, source: str | Path, **kwargs) -> list[Document]:
        path = Path(source)
        if not path.is_file():
            raise ValueError(f"Image ingestion expects a file path, got: {source}")

        if not is_image_path(path):
            raise ValueError(f"image_ingestion does not support file type: {path.suffix}")

        stat = path.stat()
        doc = Document(
            id=str(uuid.uuid4()),
            content=path.stem or path.name,
            metadata={
                "modality": "image",
                "image_path": str(path.resolve()),
                "mime_type": mime_for_path(path),
                "path": str(path),
                "size": stat.st_size,
            },
            filename=path.name,
        )
        logger.info("ImageIngestion: prepared %s (%s bytes)", path.name, stat.st_size)
        return [doc]
