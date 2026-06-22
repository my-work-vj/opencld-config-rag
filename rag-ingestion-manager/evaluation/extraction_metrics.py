"""Evaluation metrics for document extraction stage."""

from __future__ import annotations
import os
import statistics
from typing import List, Dict, Any, Tuple
from core.base_strategies import Document


def collect_extraction_stats(
    documents: List[Document],
    errors: List[Tuple[str, str]],
    durations_ms: List[float],
    file_sizes_bytes: List[int],
) -> Dict[str, Any]:
    """
    Calculate extraction quality metrics.

    Args:
        documents: List of Document objects from ingestion (successful only).
        errors: List of (filename, error_message) tuples from failed extractions.
        durations_ms: List of extraction durations in milliseconds, one per document.
        file_sizes_bytes: List of file sizes in bytes, one per document.

    Returns a dict with:
    - success_rate (float 0-1)
    - empty_extraction_rate (float 0-1)
    - avg_content_length (chars)
    - content_length_stdev (chars)
    - format_coverage (set of extensions seen)
    - error_rate (float 0-1)
    - avg_extraction_time_ms (float)
    - avg_file_size_bytes (float)
    - total_files_processed (int)
    """
    total_files = len(documents) + len(errors)
    if total_files == 0:
        return {
            "success_rate": 0.0,
            "empty_extraction_rate": 0.0,
            "avg_content_length": 0.0,
            "content_length_stdev": 0.0,
            "format_coverage": set(),
            "error_rate": 0.0,
            "avg_extraction_time_ms": 0.0,
            "avg_file_size_bytes": 0,
            "total_files_processed": 0,
        }

    content_lengths = [len(d.content) for d in documents]
    empty_count = sum(1 for length in content_lengths if length == 0)

    avg_content_length = statistics.mean(content_lengths) if content_lengths else 0.0
    content_length_stdev = statistics.stdev(content_lengths) if len(content_lengths) > 1 else 0.0

    extensions: set[str] = set()
    for d in documents:
        _, ext = os.path.splitext(d.filename or "unknown")
        extensions.add(ext.lower())
    for fname, _ in errors:
        _, ext = os.path.splitext(fname or "unknown")
        extensions.add(ext.lower())

    avg_extraction_time_ms = statistics.mean(durations_ms) if durations_ms else 0.0
    avg_file_size_bytes = statistics.mean(file_sizes_bytes) if file_sizes_bytes else 0

    successful = len(documents) - empty_count
    return {
        "success_rate": successful / total_files,
        "empty_extraction_rate": empty_count / total_files,
        "error_rate": len(errors) / total_files,
        "avg_content_length": avg_content_length,
        "content_length_stdev": content_length_stdev,
        "format_coverage": extensions,
        "avg_extraction_time_ms": avg_extraction_time_ms,
        "avg_file_size_bytes": avg_file_size_bytes,
        "total_files_processed": total_files,
    }