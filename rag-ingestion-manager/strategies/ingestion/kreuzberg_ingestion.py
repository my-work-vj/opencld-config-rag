"""Kreuzberg ingestion strategy — unified extraction for 96 file formats.

Uses the kreuzberg Rust library to extract plain text from files.
Maps to "Document (plain text only)" in the UI.
Omits tables and images — pure text extraction for downstream chunking.
"""

import os
import uuid
from pathlib import Path

import logging
from core.base_strategies import BaseIngestionStrategy, Document
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)


@StrategyRegistry.register("ingestion", "kreuzberg_ingestion")
class KreuzbergIngestion(BaseIngestionStrategy):
    """Extract plain text from files using kreuzberg (96 formats supported).
    
    Handles PDFs, Office documents, images (via OCR), HTML, and more.
    Returns only plain text content — tables, images, and formatting are omitted.
    """

    def ingest(self, source: str | list | os.PathLike, **kwargs) -> list[Document]:
        from kreuzberg import extract_file
        
        documents: list[Document] = []
        
        paths: list[Path] = []
        if isinstance(source, str):
            if os.path.isfile(source):
                paths = [Path(source)]
            elif os.path.isdir(source):
                paths = []
                for ext in self._supported_extensions():
                    paths.extend(Path(source).rglob(f"*{ext}"))
                # Also try without extension for files that might not have standard extensions
        elif isinstance(source, list):
            paths = [Path(s) if isinstance(s, str) else s for s in source]
        
        for p in paths:
            if not p.is_file():
                logger.warning("Skipping non-file: %s", p)
                continue
            try:
                result = extract_file(str(p))
                content = result.content or ""
                if not content.strip():
                    logger.warning("Empty extraction from %s", p.name)
                    continue
                
                doc = Document(
                    id=str(uuid.uuid4()),
                    content=content,
                    metadata={
                        "path": str(p),
                        "size": len(content),
                        "format": (
                            str(result.metadata.format.format_type)
                            if result.metadata and result.metadata.format
                            else p.suffix
                        ),
                        "source": "kreuzberg",
                    },
                    filename=p.name,
                )
                documents.append(doc)
                logger.debug("Extracted %d chars from %s", len(content), p.name)
            except Exception as e:
                logger.warning("kreuzberg extraction failed for %s: %s", p.name, e)
        
        return documents
    
    @staticmethod
    def _supported_extensions() -> set[str]:
        """File extensions kreuzberg can handle."""
        return {
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".txt", ".md", ".csv", ".tsv",
            ".html", ".htm", ".xml", ".json", ".yaml", ".yml",
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
            ".eml", ".msg",
            ".rtf", ".odt", ".ods", ".odp",
            ".epub", ".mobi",
            ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".rs", ".go",
        }
