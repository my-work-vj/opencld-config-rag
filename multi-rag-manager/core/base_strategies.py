"""Abstract base classes for all RAG pipeline stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


# ──────────────────────────────────────────
# Data Types
# ──────────────────────────────────────────

@dataclass
class Document:
    """A single document to be processed through the RAG pipeline."""
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
class RetrievedChunk:
    """A chunk returned from retrieval with relevance score."""
    chunk: Chunk
    score: float
    retrieval_method: str = "vector"


@dataclass
class PipelineContext:
    """Shared context passed through all pipeline stages."""
    pipeline_name: str
    documents: list[Document] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    embeddings: list[EmbeddingVector] = field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    query: str = ""
    rewritten_query: str = ""
    response: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────
# Abstract Base Strategies
# ──────────────────────────────────────────

class BaseIngestionStrategy(ABC):
    """Ingest raw documents from various sources."""

    @abstractmethod
    def ingest(self, source: Any, **kwargs) -> list[Document]:
        """Ingest documents from a source."""
        ...


class BaseChunkingStrategy(ABC):
    """Split documents into chunks."""

    @abstractmethod
    def chunk(self, documents: list[Document], **kwargs) -> list[Chunk]:
        """Split documents into smaller chunks."""
        ...


class BaseEmbeddingStrategy(ABC):
    """Generate embeddings for chunks."""

    @abstractmethod
    def embed(self, chunks: list[Chunk], **kwargs) -> list[EmbeddingVector]:
        """Generate embedding vectors for chunks."""
        ...


class BaseIndexingStrategy(ABC):
    """Store embeddings in a vector index."""

    @abstractmethod
    def index(self, embeddings: list[EmbeddingVector], **kwargs) -> None:
        """Index embedding vectors."""
        ...

    @abstractmethod
    def search(self, query_vector: list[float], top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        """Search the index for similar vectors."""
        ...


class BaseRetrievalStrategy(ABC):
    """Retrieve relevant context for a query."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        """Retrieve relevant chunks for the given query."""
        ...


class BaseRerankingStrategy(ABC):
    """Re-rank retrieved chunks for better relevance."""

    @abstractmethod
    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        """Re-rank retrieved chunks."""
        ...


class BaseResponseStrategy(ABC):
    """Generate a response from retrieved context."""

    @abstractmethod
    def generate(self, query: str, context_chunks: list[RetrievedChunk], **kwargs) -> str:
        """Generate a response based on query and retrieved context."""
        ...
