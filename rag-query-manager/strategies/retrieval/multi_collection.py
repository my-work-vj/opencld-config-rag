"""Multi-collection dense retrieval across multiple Qdrant collections."""

import hashlib
import logging
import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from core.base_strategies import (
    BaseKnowledgeStoreStrategy,
    BaseRetrievalStrategy,
    Chunk,
    KnowledgeStoreHandle,
    RetrievedChunk,
)
from core.registry import StrategyRegistry
from strategies.embedding import LiteLLMClient

load_dotenv()
logger = logging.getLogger(__name__)


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


@StrategyRegistry.register("retrieval", "multi_collection")
class MultiCollectionRetrieval(BaseRetrievalStrategy):
    """Search multiple Qdrant collections and merge results by score."""

    def __init__(self, **kwargs):
        self.collections = kwargs.get("collections", [])
        self.embed_client = LiteLLMClient.get_client().client
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        self.client = QdrantClient(host=host, port=port)

    def _embed_query(self, query: str, model: str) -> list[float]:
        resp = self.embed_client.embeddings.create(
            model=model,
            input=[query],
            extra_body={"input_type": "query", "encoding_format": "float"},
        )
        return resp.data[0].embedding

    def _search_collection(
        self,
        query: str,
        collection_name: str,
        embedding_model: str,
        per_collection_k: int,
    ) -> list[RetrievedChunk]:
        existing = [c.name for c in self.client.get_collections().collections]
        if collection_name not in existing:
            logger.warning(
                f"[MultiCollection] Collection '{collection_name}' not found — skipping"
            )
            return []

        query_vec = self._embed_query(query, embedding_model)
        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vec,
            limit=per_collection_k,
        ).points

        chunks: list[RetrievedChunk] = []
        for point in results:
            payload = point.payload or {}
            chunk = _payload_to_chunk(payload, str(point.id))
            chunk.metadata["source_collection"] = collection_name
            chunks.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=point.score,
                    retrieval_method="multi_collection",
                )
            )
        return chunks

    def retrieve(
        self,
        query: str,
        store: KnowledgeStoreHandle,
        knowledge_store_strategy: BaseKnowledgeStoreStrategy,
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        collections = kwargs.get("collections") or self.collections
        if not collections:
            logger.warning("[MultiCollection] No collections configured")
            return []

        per_collection_k = max(top_k * 2, top_k)
        all_results: list[RetrievedChunk] = []

        for coll in collections:
            collection_name = coll.get("collection_name")
            embedding_model = coll.get("embedding_model") or os.getenv(
                "EMBEDDING_MODEL", "nvidia-embed"
            )
            if not collection_name:
                continue
            try:
                all_results.extend(
                    self._search_collection(
                        query, collection_name, embedding_model, per_collection_k
                    )
                )
            except Exception as e:
                logger.warning(
                    f"[MultiCollection] Search failed for '{collection_name}': {e}"
                )

        all_results.sort(key=lambda r: r.score, reverse=True)

        seen_hashes: set[str] = set()
        deduped: list[RetrievedChunk] = []
        for item in all_results:
            content_hash = hashlib.sha256(item.chunk.content.encode()).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            deduped.append(item)
            if len(deduped) >= top_k:
                break

        logger.info(
            f"[MultiCollection] Merged {len(all_results)} → {len(deduped)} chunks "
            f"from {len(collections)} collections"
        )
        return deduped
