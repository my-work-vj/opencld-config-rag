"""Indexing strategies — Qdrant vector store."""

import os
import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, SearchRequest,
)
from dotenv import load_dotenv

from core.base_strategies import BaseIndexingStrategy, Chunk, EmbeddingVector, RetrievedChunk
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

    def search(self, query_vector: list[float], top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        collection = kwargs.get("collection_name", "rag_documents")
        score_threshold = kwargs.get("score_threshold")

        search_params = {
            "collection_name": collection,
            "query": query_vector,
            "limit": top_k,
        }
        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        results = self.client.query_points(**search_params).points

        chunks = []
        for r in results:
            payload = r.payload or {}
            chunk = Chunk(
                id=payload.get("chunk_id", ""),
                document_id=payload.get("document_id", ""),
                content=payload.get("content", ""),
                metadata={k: v for k, v in payload.items() if k not in ("chunk_id", "document_id", "content", "chunk_index", "filename")},
                chunk_index=payload.get("chunk_index", 0),
                filename=payload.get("filename"),
            )
            chunks.append(RetrievedChunk(chunk=chunk, score=r.score, retrieval_method="vector"))

        return chunks
