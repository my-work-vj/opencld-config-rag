"""Abstract base classes for query pipeline stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Chunk:
    """A knowledge chunk retrieved from a vector store."""
    id: str
    document_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    filename: Optional[str] = None


@dataclass
class RetrievedChunk:
    """A chunk returned from retrieval with relevance score."""
    chunk: Chunk
    score: float
    retrieval_method: str = "vector"


@dataclass
class KnowledgeStoreHandle:
    """Connection handle produced by a knowledge store strategy."""
    store_type: str
    collection_name: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Shared context passed through query pipeline stages."""
    pipeline_name: str
    query: str = ""
    knowledge_store: Optional[KnowledgeStoreHandle] = None
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    response: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)


class BaseKnowledgeStoreStrategy(ABC):
    @abstractmethod
    def connect(self, **kwargs) -> KnowledgeStoreHandle:
        """Connect to and validate a knowledge store."""

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        store: KnowledgeStoreHandle,
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        """Vector search against the connected store."""

    @abstractmethod
    def scroll_chunks(
        self,
        store: KnowledgeStoreHandle,
        limit: int = 10000,
        **kwargs,
    ) -> list[Chunk]:
        """Load chunks from the store (e.g. for BM25 indexing)."""


class BaseRetrievalStrategy(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        store: KnowledgeStoreHandle,
        knowledge_store_strategy: BaseKnowledgeStoreStrategy,
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        ...


class BaseRerankingStrategy(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        ...


class BaseResponseStrategy(ABC):
    @abstractmethod
    def generate(
        self,
        query: str,
        context_chunks: list[RetrievedChunk],
        **kwargs,
    ) -> str:
        ...
