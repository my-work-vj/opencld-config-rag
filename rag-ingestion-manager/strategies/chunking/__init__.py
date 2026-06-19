"""Chunking strategies."""

import uuid
from typing import Optional

from core.base_strategies import BaseChunkingStrategy, Document, Chunk
from core.registry import StrategyRegistry
from monitoring.chunk_ids import make_chunk_point_id


def _chunk_id_for(doc: Document, chunk_index: int) -> str:
    connector_id = doc.metadata.get("connector_id")
    external_id = doc.metadata.get("external_id")
    qdrant_collection = doc.metadata.get("qdrant_collection")
    if connector_id and external_id and qdrant_collection:
        return make_chunk_point_id(qdrant_collection, connector_id, external_id, chunk_index)
    return str(uuid.uuid4())


@StrategyRegistry.register("chunking", "recursive_chunking")
class RecursiveChunking(BaseChunkingStrategy):
    """Recursively split text by separators."""

    def chunk(self, documents: list[Document], **kwargs) -> list[Chunk]:
        chunk_size = kwargs.get("chunk_size", 1000)
        chunk_overlap = kwargs.get("chunk_overlap", 200)
        separators = kwargs.get("separators", ["\n\n", "\n", ". ", " ", ""])

        all_chunks = []
        for doc in documents:
            text = doc.content
            chunks = self._split_text(text, chunk_size, chunk_overlap, separators)
            for i, chunk_text in enumerate(chunks):
                all_chunks.append(Chunk(
                    id=_chunk_id_for(doc, i),
                    document_id=doc.id,
                    content=chunk_text,
                    metadata={**doc.metadata, "doc_index": i},
                    chunk_index=i,
                    filename=doc.filename,
                ))
        return all_chunks

    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int, separators: list[str]) -> list[str]:
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break

            # Try to find a separator to break at
            best_break = -1
            for sep in separators:
                pos = text.rfind(sep, start, end)
                if pos > best_break:
                    best_break = pos + len(sep) if sep else pos

            if best_break > start:
                end = best_break
            else:
                end = min(start + chunk_size, len(text))

            chunks.append(text[start:end])
            start = end - chunk_overlap if end < len(text) else len(text)

        return chunks


@StrategyRegistry.register("chunking", "fixed_size_chunking")
class FixedSizeChunking(BaseChunkingStrategy):
    """Split text into fixed-size chunks with overlap."""

    def chunk(self, documents: list[Document], **kwargs) -> list[Chunk]:
        chunk_size = kwargs.get("chunk_size", 512)
        chunk_overlap = kwargs.get("chunk_overlap", 50)

        all_chunks = []
        for doc in documents:
            text = doc.content
            chunks = []
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunks.append(text[start:end])
                if end == len(text):
                    break
                start = end - chunk_overlap

            for i, chunk_text in enumerate(chunks):
                all_chunks.append(Chunk(
                    id=_chunk_id_for(doc, i),
                    document_id=doc.id,
                    content=chunk_text,
                    metadata={**doc.metadata, "chunk_size": chunk_size},
                    chunk_index=i,
                    filename=doc.filename,
                ))
        return all_chunks
