"""Qdrant dense vector indexing strategy — stores EmbeddingVector chunks as Qdrant points."""

import os
import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
)

from core.base_strategies import BaseIndexingStrategy, EmbeddingVector
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)


class QdrantStore:
    """Singleton Qdrant client shared across indexing strategies."""
    _instance: Optional["QdrantStore"] = None

    def __init__(self):
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        self.client = QdrantClient(host=host, port=port)
        logger.info(f"QdrantStore: connected to {host}:{port}")

    @classmethod
    def get(cls) -> "QdrantStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


@StrategyRegistry.register("indexing", "qdrant_indexing")
class QdrantIndexing(BaseIndexingStrategy):
    """Index dense embedding vectors into a Qdrant collection."""

    def __init__(self, **kwargs):
        self.store = QdrantStore.get()
        self.client = self.store.client

    def _ensure_collection(self, collection_name: str, vector_size: int,
                           distance: str = "Cosine", recreate: bool = False):
        distance_map = {
            "Cosine": Distance.COSINE,
            "Dot": Distance.DOT,
            "Euclid": Distance.EUCLID,
        }
        dist = distance_map.get(distance, Distance.COSINE)

        if recreate:
            try:
                self.client.delete_collection(collection_name)
            except Exception:
                pass

        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name not in collections:
            # Enable both dense + sparse vectors at creation time so the
            # QdrantSparseIndexing strategy can write without recreating the collection
            from qdrant_client.models import SparseVectorParams, SparseIndexParams
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=dist),
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=SparseIndexParams()
                    )
                },
            )
            logger.info(
                f"Created Qdrant dense+sparse collection '{collection_name}' "
                f"(size={vector_size}, distance={distance})"
            )

    def index(self, embeddings: list[EmbeddingVector], **kwargs) -> None:
        """Store dense embedding vectors."""
        collection = kwargs.get("collection_name", "rag_documents")
        vector_size = kwargs.get("vector_size", 2048)
        distance = kwargs.get("distance", "Cosine")
        recreate = kwargs.get("recreate", False)

        self._ensure_collection(collection, vector_size, distance, recreate)

        points = []
        for ev in embeddings:
            payload = {
                "chunk_id": ev.chunk.id,
                "document_id": ev.chunk.document_id,
                "content": ev.chunk.content,
                "chunk_index": ev.chunk.chunk_index,
                "chunk_level": ev.chunk.chunk_level,
                "filename": ev.chunk.filename or "",
                "parent_chunk_id": ev.chunk.parent_chunk_id or "",
            }
            # Add metadata fields that are simple types
            for k, v in ev.chunk.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    payload[k] = v

            points.append(PointStruct(
                id=ev.chunk.id,
                vector=ev.vector,
                payload=payload,
            ))

        if points:
            self.client.upsert(collection_name=collection, points=points)
            logger.info(f"QdrantIndexing: upserted {len(points)} dense points into '{collection}'")
