"""One chunk per image document — no text splitting."""

from __future__ import annotations

import uuid

from core.base_strategies import BaseChunkingStrategy, Chunk, Document
from core.registry import StrategyRegistry


@StrategyRegistry.register("chunking", "image_chunking")
class ImageChunking(BaseChunkingStrategy):
    """Create a single retrieval chunk per image document."""

    def chunk(self, documents: list[Document], **kwargs) -> list[Chunk]:
        chunks: list[Chunk] = []
        for doc in documents:
            metadata = dict(doc.metadata or {})
            metadata.setdefault("modality", "image")
            chunks.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc.id,
                    content=doc.content or doc.filename or "image",
                    metadata=metadata,
                    chunk_index=0,
                    chunk_level="image",
                    filename=doc.filename,
                )
            )
        return chunks
