"""Abstract base classes for ingestion pipeline stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict

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
    # Hierarchical chunking fields
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = field(default_factory=list)
    chunk_level: str = "child"  # child, parent, summary

@dataclass
class EmbeddingVector:
    """A chunk with its embedding vector."""
    chunk: Chunk
    vector: list[float]

@dataclass
class SparseVector:
    """A chunk with its sparse (BM25) vector representation."""
    chunk: Chunk
    # Format: {term_id: weight, ...} or list of (term_id, weight) tuples
    # Using dict for sparse representation
    weights: dict[int, float] = field(default_factory=dict)

@dataclass
class GraphEntity:
    """An entity extracted for knowledge graph storage."""
    id: str
    label: str  # entity type (PERSON, ORG, etc.)
    name: str
    properties: dict[str, Any] = field(default_factory=dict)

@dataclass
class GraphRelation:
    """A relationship between entities for knowledge graph storage."""
    id: str
    source_id: str
    target_id: str
    label: str  # relationship type (WORKS_FOR, LOCATED_IN, etc.)
    properties: dict[str, Any] = field(default_factory=dict)

@dataclass
class PipelineContext:
    """Shared context passed through ingestion pipeline stages."""
    pipeline_name: str
    documents: List[Document] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    embeddings: List[EmbeddingVector] = field(default_factory=list)
    sparse_vectors: List[SparseVector] = field(default_factory=list)
    graph_entities: List[GraphEntity] = field(default_factory=list)
    graph_relations: List[GraphRelation] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

class BaseIngestionStrategy(ABC):
    @abstractmethod
    def ingest(self, source: Any, **kwargs) -> List[Document]:
        ...

class BaseChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, documents: List[Document], **kwargs) -> List[Chunk]:
        ...

class BaseEmbeddingStrategy(ABC):
    @abstractmethod
    def embed(self, chunks: List[Chunk], **kwargs) -> List[EmbeddingVector]:
        ...

class BaseSparseEmbeddingStrategy(ABC):
    @abstractmethod
    def embed_sparse(self, chunks: List[Chunk], **kwargs) -> List[SparseVector]:
        ...

class BaseIndexingStrategy(ABC):
    @abstractmethod
    def index(self, embeddings: List[EmbeddingVector], **kwargs) -> None:
        ...

class BaseSparseIndexingStrategy(ABC):
    @abstractmethod
    def index_sparse(self, sparse_vectors: List[SparseVector], **kwargs) -> None:
        ...

class BaseGraphIndexingStrategy(ABC):
    @abstractmethod
    def index_graph(self, entities: List[GraphEntity], relations: List[GraphRelation], **kwargs) -> None:
        ...

class BaseMetadataIndexingStrategy(ABC):
    @abstractmethod
    def index_metadata(self, documents: List[Document], chunks: List[Chunk], **kwargs) -> None:
        ...

class BaseMemoryIndexingStrategy(ABC):
    @abstractmethod
    def index_memory(self, session_id: str, context: dict[str, Any], **kwargs) -> None:
        ...