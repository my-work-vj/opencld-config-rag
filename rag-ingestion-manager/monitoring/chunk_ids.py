"""Deterministic Qdrant point IDs for connector-backed chunks."""

import hashlib
import uuid


def make_chunk_point_id(
    qdrant_collection: str,
    connector_id: str,
    external_id: str,
    chunk_index: int,
) -> str:
    """Return a stable UUID string for upsert/delete of the same logical chunk."""
    key = f"{qdrant_collection}:{connector_id}:{external_id}:{chunk_index}"
    digest = hashlib.sha256(key.encode()).digest()
    return str(uuid.UUID(bytes=digest[:16]))
