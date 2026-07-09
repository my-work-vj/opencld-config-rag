"""Modality detection and image encoding helpers for multimodal ingestion."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif", ".svg",
})

PDF_EXTENSIONS = frozenset({".pdf"})

_IMAGE_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".svg": "image/svg+xml",
}


def is_image_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def is_pdf_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in PDF_EXTENSIONS


def detect_source_modality(path: str | Path) -> str:
    """Return coarse modality: image | pdf | text."""
    file_path = Path(path)
    if is_image_path(file_path):
        return "image"
    if is_pdf_path(file_path):
        return "pdf"
    return "text"


def mime_for_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in _IMAGE_MIME_MAP:
        return _IMAGE_MIME_MAP[suffix]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def path_to_data_url(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Image file not found: {file_path}")
    raw = file_path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    mime = mime_for_path(file_path)
    return f"data:{mime};base64,{encoded}"


def bytes_to_data_url(raw: bytes, mime: str = "image/png") -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"
