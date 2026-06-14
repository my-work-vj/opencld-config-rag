"""Indexing strategies — Qdrant vector store."""

import os
import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from dotenv import load_dotenv

from core.base_strategies import BaseIndexingStrategy, EmbeddingVector
from core.registry import StrategyRegistry

load_dotenv()
logger = logging.getLogger(__name__)


class QdrantStore:
    """Singleton Qdrant client."""
    _instance: Optional["QdrantStore"] = None

    def __init__(self):
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        self.client = QdrantClient(host=host, port=port)
        logger.info(f"Connected to Qdrant at {host}:{port}")

    @classmethod
    def get(cls) -> "QdrantStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


@StrategyRegistry.register("indexing", "qdrant_indexing")
class QdrantIndexing(BaseIndexingStrategy):
    """Index and search using Qdrant vector store."""

    def __init__(self, **kwargs):
        self.store = QdrantStore.get()
        self.client = self.store.client

    def _ensure_collection(self, collection_name: str, vector_size: int, distance: str, recreate: bool = False):
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
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=dist),
            )
            logger.info(f"Created Qdrant collection '{collection_name}' (size={vector_size}, distance={distance})")

    def index(self, embeddings: list[EmbeddingVector], **kwargs) -> None:
        collection = kwargs.get("collection_name", "rag_documents")
        vector_size = kwargs.get("vector_size", 768)
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
                "filename": ev.chunk.filename or ev.chunk.metadata.get("filename", ""),
                **{k: v for k, v in ev.chunk.metadata.items() if isinstance(v, (str, int, float, bool))},
            }
            point = PointStruct(
                id=ev.chunk.id,
                vector=ev.vector,
                payload=payload,
            )
            points.append(point)

        if points:
            self.client.upsert(collection_name=collection, points=points)
            logger.info(f"Indexed {len(points)} points into '{collection}'")
