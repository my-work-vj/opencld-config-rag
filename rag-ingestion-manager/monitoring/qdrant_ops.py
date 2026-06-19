"""Qdrant operations for collection sync (delete by connector file identity)."""

import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector, VectorParams, Distance

logger = logging.getLogger(__name__)


def _client() -> QdrantClient:
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )


def ensure_qdrant_collection(
    collection_name: str,
    vector_size: int = 2048,
    distance: str = "Cosine",
) -> None:
    """Create an empty Qdrant collection if it does not exist."""
    client = _client()
    distance_map = {
        "Cosine": Distance.COSINE,
        "Dot": Distance.DOT,
        "Euclid": Distance.EUCLID,
    }
    dist = distance_map.get(distance, Distance.COSINE)
    existing = {c.name for c in client.get_collections().collections}
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=dist),
        )
        logger.info("Created empty Qdrant collection '%s' (size=%s)", collection_name, vector_size)


def delete_connector_file_vectors(
    qdrant_collection: str,
    connector_id: str,
    external_id: str,
) -> None:
    """Remove all vector points for a connector file from a Qdrant collection."""
    client = _client()
    try:
        client.delete(
            collection_name=qdrant_collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="connector_id", match=MatchValue(value=connector_id)),
                        FieldCondition(key="external_id", match=MatchValue(value=external_id)),
                    ]
                )
            ),
        )
        logger.info(
            "Deleted vectors for connector %s external_id %s in %s",
            connector_id,
            external_id,
            qdrant_collection,
        )
    except Exception as exc:
        logger.warning(
            "Could not delete vectors for %s/%s in %s: %s",
            connector_id,
            external_id,
            qdrant_collection,
            exc,
        )
