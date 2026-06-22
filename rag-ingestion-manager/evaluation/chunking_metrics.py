"""Evaluation metrics for chunking stage."""

from __future__ import annotations
import statistics
from typing import List, Dict, Any
from core.base_strategies import Chunk


def evaluate_chunks(chunks: List[Chunk], chunking_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate chunking quality metrics.

    Args:
        chunks: List of Chunk objects produced by the chunking stage.
        chunking_config: Configuration dict for the chunking strategy (e.g., chunk_size, overlap).

    Returns:
        A dict with:
        - total_chunks (int)
        - avg_chunk_size (float)
        - chunk_size_stdev (float)
        - chunk_size_p50 (float)
        - chunk_size_p95 (float)
        - chunk_size_p99 (float)
        - chunks_per_doc (float)
        - duplicate_content_rate (float 0-1)
        - empty_chunks (int)
        - max_chunk_size (int)
        - min_chunk_size (int)
    """
    if not chunks:
        return {
            "total_chunks": 0,
            "avg_chunk_size": 0.0,
            "chunk_size_stdev": 0.0,
            "chunk_size_p50": 0.0,
            "chunk_size_p95": 0.0,
            "chunk_size_p99": 0.0,
            "chunks_per_doc": 0.0,
            "duplicate_content_rate": 0.0,
            "empty_chunks": 0,
            "max_chunk_size": 0,
            "min_chunk_size": 0,
        }

    lengths = [len(c.content) for c in chunks]
    total_chunks = len(chunks)
    empty_chunks = sum(1 for l in lengths if l == 0)

    avg_size = statistics.mean(lengths) if lengths else 0.0
    size_stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0.0
    sorted_lengths = sorted(lengths)
    p50 = sorted_lengths[int(0.5 * total_chunks)] if total_chunks > 0 else 0
    p95 = sorted_lengths[min(int(0.95 * total_chunks), total_chunks - 1)] if total_chunks > 0 else 0
    p99 = sorted_lengths[min(int(0.99 * total_chunks), total_chunks - 1)] if total_chunks > 0 else 0

    unique_doc_ids = len({c.document_id for c in chunks})
    chunks_per_doc = total_chunks / unique_doc_ids if unique_doc_ids > 0 else 0.0

    unique_chunks = len(set(c.content for c in chunks))
    duplicate_content_rate = (total_chunks - unique_chunks) / total_chunks if total_chunks > 0 else 0.0

    max_chunk_size = max(lengths) if lengths else 0
    min_chunk_size = min(lengths) if lengths else 0

    return {
        "total_chunks": total_chunks,
        "avg_chunk_size": avg_size,
        "chunk_size_stdev": size_stdev,
        "chunk_size_p50": p50,
        "chunk_size_p95": p95,
        "chunk_size_p99": p99,
        "chunks_per_doc": chunks_per_doc,
        "duplicate_content_rate": duplicate_content_rate,
        "empty_chunks": empty_chunks,
        "max_chunk_size": max_chunk_size,
        "min_chunk_size": min_chunk_size,
    }