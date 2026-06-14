"""Knowledge store strategies — connect to vector/knowledge backends."""

import os
import logging
from typing import Optional

from qdrant_client import QdrantClient
from dotenv import load_dotenv

from core.base_strategies import (
    BaseKnowledgeStoreStrategy,
    KnowledgeStoreHandle,
    Chunk,
    RetrievedChunk,
)
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


def _payload_to_chunk(payload: dict, point_id: str = "") -> Chunk:
    return Chunk(
        id=payload.get("chunk_id", point_id),
        document_id=payload.get("document_id", ""),
        content=payload.get("content", ""),
        metadata={
            k: v for k, v in payload.items()
            if k not in ("chunk_id", "document_id", "content", "chunk_index", "filename")
        },
        chunk_index=payload.get("chunk_index", 0),
        filename=payload.get("filename"),
    )


@StrategyRegistry.register("knowledge_store", "qdrant_store")
class QdrantKnowledgeStore(BaseKnowledgeStoreStrategy):
    """Connect to a Qdrant collection for retrieval."""

    def __init__(self, **kwargs):
        self.store = QdrantStore.get()
        self.client = self.store.client

    def connect(self, **kwargs) -> KnowledgeStoreHandle:
        collection_name = kwargs.get("collection_name", "rag_documents")
        validate = kwargs.get("validate", True)

        if validate:
            collections = [c.name for c in self.client.get_collections().collections]
            if collection_name not in collections:
                raise ValueError(
                    f"Qdrant collection '{collection_name}' not found. "
                    f"Available: {collections}"
                )
            info = self.client.get_collection(collection_name)
            logger.info(
                f"Knowledge store ready: '{collection_name}' "
                f"({info.points_count} points)"
            )

        return KnowledgeStoreHandle(
            store_type="qdrant",
            collection_name=collection_name,
            config=kwargs,
        )

    def search(
        self,
        query_vector: list[float],
        store: KnowledgeStoreHandle,
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        score_threshold = kwargs.get("score_threshold")
        search_params = {
            "collection_name": store.collection_name,
            "query": query_vector,
            "limit": top_k,
        }
        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        results = self.client.query_points(**search_params).points
        chunks = []
        for r in results:
            payload = r.payload or {}
            chunk = _payload_to_chunk(payload)
            chunks.append(RetrievedChunk(chunk=chunk, score=r.score, retrieval_method="vector"))
        return chunks

    def scroll_chunks(
        self,
        store: KnowledgeStoreHandle,
        limit: int = 10000,
        **kwargs,
    ) -> list[Chunk]:
        try:
            info = self.client.get_collection(store.collection_name)
            total = info.points_count
            if total == 0:
                return []

            scroll_limit = min(limit, total)
            scroll_result = self.client.scroll(
                collection_name=store.collection_name,
                limit=scroll_limit,
                with_payload=True,
            )
            chunks = []
            for point in scroll_result[0]:
                payload = point.payload or {}
                chunks.append(_payload_to_chunk(payload, str(point.id)))
            return chunks
        except Exception as e:
            logger.warning(f"Could not scroll chunks from Qdrant: {e}")
            return []

    def list_collections(self) -> list[str]:
        return [c.name for c in self.client.get_collections().collections]
