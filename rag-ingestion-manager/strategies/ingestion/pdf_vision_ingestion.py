"""PDF vision ingestion — rasterize pages for multimodal embedding (industry page-as-image pattern)."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from core.base_strategies import BaseIngestionStrategy, Document
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)


@StrategyRegistry.register("ingestion", "pdf_vision_ingestion")
class PdfVisionIngestion(BaseIngestionStrategy):
    """
    Render PDF pages as images and extract per-page text for text_image embeddings.

    Aligns with managed RAG multimodal parsing (page-as-image + text) used by
    Bedrock Knowledge Bases and similar RAG-as-a-Service offerings.
    """

    def ingest(self, source: str | Path, **kwargs) -> list[Document]:
        path = Path(source)
        if not path.is_file():
            raise ValueError(f"pdf_vision_ingestion expects a file path, got: {source}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"pdf_vision_ingestion only supports PDF files: {path}")

        try:
            import fitz  # pymupdf
        except ImportError as exc:
            raise RuntimeError(
                "pdf_vision_ingestion requires pymupdf. Install with: pip install pymupdf"
            ) from exc

        zoom = float(kwargs.get("page_zoom", 2.0))
        max_pages = int(kwargs.get("max_pages", 0))  # 0 = all pages

        documents: list[Document] = []
        temp_dir = Path(tempfile.mkdtemp(prefix="pdf-vision-"))
        pdf = fitz.open(path)

        try:
            page_count = pdf.page_count
            limit = page_count if max_pages <= 0 else min(page_count, max_pages)

            for page_index in range(limit):
                page = pdf.load_page(page_index)
                matrix = fitz.Matrix(zoom, zoom)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                page_path = temp_dir / f"{path.stem}_page_{page_index + 1}.png"
                pixmap.save(str(page_path))

                page_text = (page.get_text() or "").strip()
                modality = "text_image" if page_text else "image"

                documents.append(
                    Document(
                        id=str(uuid.uuid4()),
                        content=page_text or f"{path.stem} page {page_index + 1}",
                        metadata={
                            "modality": modality,
                            "image_path": str(page_path),
                            "mime_type": "image/png",
                            "page_number": page_index + 1,
                            "page_count": page_count,
                            "source_pdf": str(path.resolve()),
                            "path": str(page_path),
                        },
                        filename=f"{path.name}#page{page_index + 1}",
                    )
                )

            logger.info(
                "PdfVisionIngestion: %s → %d page document(s) in %s",
                path.name,
                len(documents),
                temp_dir,
            )
            return documents
        finally:
            pdf.close()
