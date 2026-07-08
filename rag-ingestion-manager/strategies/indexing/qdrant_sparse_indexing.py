"""Qdrant sparse vector indexing strategy — stores BM25 sparse vectors alongside dense vectors."""

import os
import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    SparseVectorParams, SparseIndexParams, PointStruct,
)

from core.base_strategies import BaseSparseIndexingStrategy, SparseVector
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)


@StrategyRegistry.register("indexing", "qdrant_sparse_indexing")
class QdrantSparseIndexing(BaseSparseIndexingStrategy):
    """Index BM25 sparse vectors into a Qdrant collection's sparse vector named 'sparse'."""

    def __init__(self, **kwargs):
        from .qdrant_indexing import QdrantStore
        self.store = QdrantStore.get()
        self.client = self.store.client

    def _ensure_sparse_collection(self, collection_name: str, recreate: bool = False):
        """Ensure the collection has sparse vectors enabled.
        
        The collection is already created by QdrantIndexing with both dense and sparse
        vector support. This method only validates that sparse config exists.
        """
        if recreate:
            try:
                self.client.delete_collection(collection_name)
            except Exception:
                pass

        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name in collections:
            # Verify sparse config exists (set by QdrantIndexing at creation time)
            info = self.client.get_collection(collection_name)
            if info.config.params.sparse_vectors:
                return
            logger.warning(
                f"Collection '{collection_name}' has no sparse vectors config — "
                f"sparse indexing will be skipped"
            )
            return

        # Rare edge-case: collection doesn't exist yet (e.g. direct call without dense indexer)
        from qdrant_client.models import VectorParams, Distance
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE),  # placeholder
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams()
                )
            },
        )
        logger.info(f"Enabled sparse vectors on Qdrant collection '{collection_name}'")

    def index_sparse(self, sparse_vectors: list[SparseVector], **kwargs) -> None:
        """Store BM25 sparse vectors in Qdrant's sparse vector named 'sparse'."""
        collection = kwargs.get("collection_name", "rag_documents")
        recreate = kwargs.get("recreate", False)

        self._ensure_sparse_collection(collection, recreate)

        points = []
        for sv in sparse_vectors:
            if not sv.weights:
                continue

            # Qdrant sparse vector format: indices + values
            indices = sorted(sv.weights.keys())
            values = [float(sv.weights[i]) for i in indices]

            payload = {
                "chunk_id": sv.chunk.id,
                "document_id": sv.chunk.document_id,
                "content": sv.chunk.content,
                "chunk_index": sv.chunk.chunk_index,
                "chunk_level": sv.chunk.chunk_level,
                "filename": sv.chunk.filename or "",
            }
            for key in ("connector_id", "external_id", "connector_file_id", "qdrant_collection"):
                if key in sv.chunk.metadata:
                    payload[key] = sv.chunk.metadata[key]

            points.append(PointStruct(
                id=sv.chunk.id,
                vector={
                    "sparse": {
                        "indices": indices,
                        "values": values,
                    }
                },
                payload=payload,
            ))

        if points:
            self.client.upsert(collection_name=collection, points=points)
            logger.info(
                f"QdrantSparseIndexing: upserted {len(points)} sparse points into '{collection}'"
            )
