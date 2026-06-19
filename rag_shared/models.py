"""SQLAlchemy models for shared pipeline configuration."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text

from rag_shared.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


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
