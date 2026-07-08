"""Qdrant operations — backward-compatible re-exports from index_ops."""

from monitoring.index_ops import (
    delete_connector_file_vectors,
    delete_document_from_all_indexes,
    delete_qdrant_vectors,
    ensure_collection_indexes,
    ensure_qdrant_collection,
)

__all__ = [
    "delete_connector_file_vectors",
    "delete_document_from_all_indexes",
    "delete_qdrant_vectors",
    "ensure_collection_indexes",
    "ensure_qdrant_collection",
]
