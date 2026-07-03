"""SQLAlchemy models for shared pipeline configuration + extended metadata storage."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from rag_shared.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ───────────────────────────────────────────────────────────────
# ORIGINAL MODELS — required by rag_shared/*.py and query manager
# ───────────────────────────────────────────────────────────────

class RagPipeline(Base):
    """Runtime source of truth for a complete RAG pipeline (ingestion + query stages)."""
    __tablename__ = "rag_pipelines"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    stages = Column(JSON, nullable=False, default=dict)
    embedding_model = Column(String(255), nullable=True)
    chat_model = Column(String(255), nullable=True)
    reranker_model = Column(String(255), nullable=True)
    llm_params = Column(JSON, default=dict)
    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class RagPipelineAudit(Base):
    """Audit trail for pipeline configuration changes."""
    __tablename__ = "rag_pipeline_audit"

    id = Column(String, primary_key=True, default=_uuid)
    pipeline_id = Column(String(255), nullable=False, index=True)
    changed_by = Column(String(255), default="system")
    old_config = Column(JSON, default=dict)
    new_config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)


class KnowledgeSource(Base):
    """A named, persistent Qdrant collection created by an ingestion pipeline."""
    __tablename__ = "knowledge_sources"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    collection_name = Column(String(255), nullable=False)
    pipeline_id = Column(String(255), nullable=False)
    embedding_model = Column(String(255), default="")
    vector_size = Column(Integer, default=2048)
    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String(50), default="ready")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class DataConnector(Base):
    """External data source connector (Pathway-powered) — connection and file catalog only."""
    __tablename__ = "data_connectors"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    connector_type = Column(String(50), nullable=False, index=True)
    object_id = Column(String(512), nullable=False)
    credentials_path = Column(String(512), nullable=False)
    sync_mode = Column(String(50), default="static")
    pipeline_id = Column(String(255), nullable=True)
    knowledge_source_name = Column(String(255), nullable=True, index=True)
    status = Column(String(50), default="configured")
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_message = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class CollectionConnector(Base):
    """Links a vector collection (knowledge source) to one or more data connectors."""
    __tablename__ = "collection_connectors"

    id = Column(String, primary_key=True, default=_uuid)
    knowledge_source_name = Column(String(255), nullable=False, index=True)
    connector_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)


class IndexedDocument(Base):
    """Tracks connector files indexed into a vector collection for incremental sync."""
    __tablename__ = "indexed_documents"

    id = Column(String, primary_key=True, default=_uuid)
    knowledge_source_name = Column(String(255), nullable=False, index=True)
    connector_id = Column(String, nullable=False, index=True)
    connector_file_id = Column(String, nullable=False, index=True)
    external_id = Column(String(512), nullable=False)
    content_hash = Column(String(64), default="")
    chunk_count = Column(Integer, default=0)
    document_id = Column(String, nullable=True)
    indexed_at = Column(DateTime, default=_utcnow)


class ConnectorFile(Base):
    """File catalog entry synced from an external data connector."""
    __tablename__ = "connector_files"

    id = Column(String, primary_key=True, default=_uuid)
    connector_id = Column(String, nullable=False, index=True)
    external_id = Column(String(512), nullable=False)
    name = Column(String(512), nullable=False)
    mime_type = Column(String(255), default="")
    local_path = Column(String(1024), nullable=False)
    size_bytes = Column(Integer, default=0)
    synced_at = Column(DateTime, default=_utcnow)
    metadata_json = Column(JSON, default=dict)


class KnowledgeBase(Base):
    """A named group of Knowledge Sources queried together."""
    __tablename__ = "knowledge_bases"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    sources = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class PromptTemplate(Base):
    """Versioned system prompt template for agents."""
    __tablename__ = "prompt_templates"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    active_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class PromptVersion(Base):
    """A single version of a prompt template."""
    __tablename__ = "prompt_versions"

    id = Column(String, primary_key=True, default=_uuid)
    template_id = Column(String(255), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, default="")
    changelog = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


class Agent(Base):
    """A named, persistent query configuration (LLM + system prompt + knowledge target)."""
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    knowledge_base_names = Column(JSON, default=list)
    knowledge_base_name = Column(String(255), nullable=True)
    knowledge_source_name = Column(String(255), nullable=True)
    prompt_template_id = Column(String(255), nullable=True)
    prompt_version = Column(Integer, nullable=True)
    llm_model = Column(String(255), default="llama-3.3-70b-versatile")
    system_prompt = Column(
        Text,
        default="You are a helpful assistant. Answer based on the provided context.",
    )
    retrieval_strategy = Column(String(100), default="multi_collection")
    top_k = Column(Integer, default=5)
    reranking_strategy = Column(String(100), default="pass_through")
    response_strategy = Column(String(100), default="contextual_response")
    retrieval_config = Column(JSON, default=dict)
    reranking_config = Column(JSON, default=dict)
    response_config = Column(JSON, default=dict)
    query_stages = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    yaml_exported_at = Column(DateTime, nullable=True)
    yaml_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ───────────────────────────────────────────────────────────────
# NEW MODELS — Universal ingestion pipeline multi-index support
# ───────────────────────────────────────────────────────────────

class DocumentRecord(Base):
    """Store document metadata with indexing flags."""
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid)
    filename = Column(String(255), nullable=False)
    pipeline_name = Column(String(255), nullable=False)
    collection_name = Column(String(255), nullable=False, default="rag_documents")
    chunk_count = Column(Integer, default=0)
    content_preview = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)
    content_hash = Column(String(64), default="")
    created_at = Column(DateTime, default=_utcnow)

    # Indexing flags — which indexes this document was stored in
    indexed_in_vector = Column(String, default="true")
    indexed_in_sparse = Column(String, default="false")
    indexed_in_graph = Column(String, default="false")
    indexed_in_metadata = Column(String, default="true")
    indexed_in_memory = Column(String, default="false")

    # Relationship
    chunks = relationship("ChunkRecord", order_by="ChunkRecord.chunk_index", back_populates="document")


class ChunkRecord(Base):
    """Store chunk metadata, multi-granularity levels, and relationships."""
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_level = Column(String(20), default="child")  # child, parent, summary
    parent_chunk_id = Column(String, ForeignKey("chunks.id"), nullable=True)
    filename = Column(String(255))
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    # Indexing flags for this chunk
    indexed_in_vector = Column(String, default="true")
    indexed_in_sparse = Column(String, default="false")
    indexed_in_graph = Column(String, default="false")
    indexed_in_metadata = Column(String, default="true")
    indexed_in_memory = Column(String, default="false")

    # Relationships
    document = relationship("DocumentRecord", back_populates="chunks")
    parent_chunk = relationship("ChunkRecord", remote_side=[id], back_populates="child_chunks")
    child_chunks = relationship("ChunkRecord", back_populates="parent_chunk")


class CollectionIndexConfig(Base):
    """Store which indexes are enabled for each collection."""
    __tablename__ = "collection_index_configs"

    id = Column(String, primary_key=True, default=_uuid)
    collection_name = Column(String(255), nullable=False, unique=True)

    # Which indexes are enabled for this collection
    enable_vector_index = Column(String, default="true")
    enable_sparse_index = Column(String, default="false")
    enable_graph_index = Column(String, default="false")
    enable_metadata_index = Column(String, default="true")
    enable_memory_index = Column(String, default="false")

    # Configuration for each index type
    vector_index_config = Column(JSON, default=dict)   # Qdrant settings
    sparse_index_config = Column(JSON, default=dict)   # BM25 settings
    graph_index_config = Column(JSON, default=dict)    # Neo4j settings
    metadata_index_config = Column(JSON, default=dict)  # PostgreSQL settings
    memory_index_config = Column(JSON, default=dict)   # Redis settings

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_collection_name', 'collection_name'),
    )


class GraphEntityRecord(Base):
    """Mirror of Neo4j entities for tracking."""
    __tablename__ = "graph_entities"

    id = Column(String, primary_key=True, default=_uuid)
    neo4j_id = Column(String, unique=True)
    collection_name = Column(String(255), nullable=False)
    label = Column(String(50), nullable=False)  # PERSON, ORG, GPE, etc.
    name = Column(String(255), nullable=False)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index('idx_entity_name', 'name'),
        Index('idx_collection_entity', 'collection_name', 'name'),
    )


class GraphRelationRecord(Base):
    """Mirror of Neo4j relationships for tracking."""
    __tablename__ = "graph_relations"

    id = Column(String, primary_key=True, default=_uuid)
    neo4j_id = Column(String, unique=True)
    collection_name = Column(String(255), nullable=False)
    source_id = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    label = Column(String(50), nullable=False)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index('idx_relation_label', 'label'),
        Index('idx_source_target', 'source_id', 'target_id'),
    )


class SessionMemoryRecord(Base):
    """Track conversation sessions and their context."""
    __tablename__ = "session_memory"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, unique=True)
    collection_name = Column(String(255), nullable=False)
    context_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_session_id', 'session_id'),
        Index('idx_collection_session', 'collection_name', 'session_id'),
    )
