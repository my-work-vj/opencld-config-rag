"""Evaluation metrics for pipeline health — Qdrant cross-validation + pipeline stats."""

from __future__ import annotations
from typing import Dict, Any, Optional


def cross_validate_qdrant(
    qdrant_client,
    collection_name: str,
    db_chunk_count: int,
) -> Dict[str, Any]:
    """Compare DB chunk count against Qdrant's point count."""
    try:
        info = qdrant_client.get_collection(collection_name)
        qdrant_points = info.points_count
        mismatch = abs(qdrant_points - db_chunk_count)
        relative_mismatch = mismatch / max(qdrant_points, db_chunk_count, 1)
        return {
            "qdrant_points": qdrant_points,
            "db_chunk_count": db_chunk_count,
            "in_sync": mismatch == 0,
            "mismatch": mismatch,
            "relative_mismatch": relative_mismatch,
        }
    except Exception as exc:
        return {
            "qdrant_points": 0,
            "db_chunk_count": db_chunk_count,
            "in_sync": False,
            "mismatch": db_chunk_count,
            "relative_mismatch": 1.0,
            "error": str(exc),
        }


def collect_pipeline_stats(
    sync_result: Dict[str, Any],
    sync_duration: float,
    db_doc_count: int,
    db_chunk_count: int,
) -> Dict[str, Any]:
    """
    Collect pipeline throughput and reliability metrics.

    Args:
        sync_result: Dict with keys: added, updated, deleted, errors (list).
        sync_duration: Total time for the sync in seconds.
        db_doc_count: Total documents in the DB for the collection after sync.
        db_chunk_count: Total chunks in the DB for the collection after sync.

    Returns:
        A dict with pipeline health metrics.
    """
    added = sync_result.get("added", 0)
    updated = sync_result.get("updated", 0)
    deleted = sync_result.get("deleted", 0)
    error_list = sync_result.get("errors", [])
    total_errors = len(error_list) if isinstance(error_list, list) else error_list

    total_files_processed = added + updated + total_errors

    files_per_second = (added + updated) / sync_duration if sync_duration > 0 else 0.0
    error_rate = total_errors / total_files_processed if total_files_processed > 0 else 0.0
    chunks_per_doc = db_chunk_count / db_doc_count if db_doc_count > 0 else 0.0

    return {
        "total_files_processed": total_files_processed,
        "files_added": added,
        "files_updated": updated,
        "files_deleted": deleted,
        "total_errors": total_errors,
        "sync_duration_sec": sync_duration,
        "docs_per_second": files_per_second,
        "chunks_per_doc": chunks_per_doc,
        "total_documents": db_doc_count,
        "total_chunks": db_chunk_count,
        "error_rate": error_rate,
    }