"""Abstract base classes for ingestion pipeline stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Document:
    """A single document to be processed through the ingestion pipeline."""
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    filename: Optional[str] = None


@dataclass
class Chunk:
    """A chunk of a document after the chunking stage."""
    id: str
    document_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    filename: Optional[str] = None


@dataclass
class EmbeddingVector:
    """A chunk with its embedding vector."""
    chunk: Chunk
    vector: list[float]


@dataclass
class PipelineContext:
    """Shared context passed through ingestion pipeline stages."""
    pipeline_name: str
    documents: list[Document] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    embeddings: list[EmbeddingVector] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)


class BaseIngestionStrategy(ABC):
    @abstractmethod
    def ingest(self, source: Any, **kwargs) -> list[Document]:
        ...


class BaseChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, documents: list[Document], **kwargs) -> list[Chunk]:
        ...


class BaseEmbeddingStrategy(ABC):
    @abstractmethod
    def embed(self, chunks: list[Chunk], **kwargs) -> list[EmbeddingVector]:
        ...


class BaseIndexingStrategy(ABC):
    @abstractmethod
    def index(self, embeddings: list[EmbeddingVector], **kwargs) -> None:
        ...
