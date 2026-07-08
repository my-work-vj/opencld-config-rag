"""Pydantic schemas for pipeline configuration validation."""

from datetime import datetime
from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class IndexType(str, Enum):
    """Types of indexes that can be enabled for a collection."""
    VECTOR = "vector"
    SPARSE = "sparse"
    GRAPH = "graph"
    METADATA = "metadata"
    MEMORY = "memory"


# ── Index Configuration Schemas ──


class CollectionIndexConfigBase(BaseModel):
    """Base configuration for collection index settings."""
    collection_name: str = Field(..., description="Name of the collection")


class CollectionIndexConfigResponse(CollectionIndexConfigBase):
    """Response model for collection index configuration."""
    enable_vector_index: bool = Field(default=True, description="Enable dense vector indexing (Qdrant)")
    enable_sparse_index: bool = Field(default=False, description="Enable sparse/BMI25 indexing (Qdrant)")
    enable_graph_index: bool = Field(default=False, description="Enable graph indexing (Neo4j)")
    enable_metadata_index: bool = Field(default=True, description="Enable metadata indexing (PostgreSQL)")
    enable_memory_index: bool = Field(default=False, description="Enable memory indexing (Redis)")
    
    # Configuration objects for each index type
    vector_index_config: dict[str, Any] = Field(default_factory=dict, description="Qdrant-specific configuration")
    sparse_index_config: dict[str, Any] = Field(default_factory=dict, description="BMI25/sparse configuration")
    graph_index_config: dict[str, Any] = Field(default_factory=dict, description="Neo4j-specific configuration")
    metadata_index_config: dict[str, Any] = Field(default_factory=dict, description="PostgreSQL-specific configuration")
    memory_index_config: dict[str, Any] = Field(default_factory=dict, description="Redis-specific configuration")


class CollectionIndexConfigUpdate(BaseModel):
    """Update model for collection index configuration."""
    enable_vector_index: Optional[bool] = Field(None, description="Enable/disable dense vector indexing")
    enable_sparse_index: Optional[bool] = Field(None, description="Enable/disable sparse/BMI25 indexing")
    enable_graph_index: Optional[bool] = Field(None, description="Enable/disable graph indexing")
    enable_metadata_index: Optional[bool] = Field(None, description="Enable/disable metadata indexing")
    enable_memory_index: Optional[bool] = Field(None, description="Enable/disable memory indexing")
    
    # Configuration objects - partial updates allowed
    vector_index_config: Optional[dict[str, Any]] = Field(None, description="Qdrant-specific configuration updates")
    sparse_index_config: Optional[dict[str, Any]] = Field(None, description="BMI25/sparse configuration updates")
    graph_index_config: Optional[dict[str, Any]] = Field(None, description="Neo4j-specific configuration updates")
    metadata_index_config: Optional[dict[str, Any]] = Field(None, description="PostgreSQL-specific configuration updates")
    memory_index_config: Optional[dict[str, Any]] = Field(None, description="Redis-specific configuration updates")


# ── Pipeline Schemas —— (rest of the file remains the same)


class StageConfig(BaseModel):
    strategy: str
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineYamlDocument(BaseModel):
    """Validates a unified pipeline YAML file before seeding the database."""
    id: str
    name: str
    description: str = ""
    stages: dict[str, StageConfig]
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"

    @field_validator("stages")
    @classmethod
    def stages_not_empty(cls, value: dict[str, StageConfig]) -> dict[str, StageConfig]:
        if not value:
            raise ValueError("stages must not be empty")
        return value


class PipelineCreateRequest(BaseModel):
    """Create a pipeline via API (UI-driven)."""
    id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$", min_length=1, max_length=255)
    name: str
    description: str = ""
    stages: dict[str, StageConfig]
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class PipelineUpdateRequest(BaseModel):
    """Partial update of a pipeline."""
    name: Optional[str] = None
    description: Optional[str] = None
    stages: Optional[dict[str, StageConfig]] = None
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class PipelineResponse(BaseModel):
    id: str
    name: str
    description: str
    stages: dict[str, Any]
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PipelineListResponse(BaseModel):
    pipelines: list[PipelineResponse]
    total: int


# ── Knowledge Source ——


class CreateKnowledgeSourceRequest(BaseModel):
    name: str = Field(..., description="Unique name for this Knowledge Source")
    description: str = Field("", description="Human-readable description")
    pipeline: str = Field("inline", description="Deprecated — use collection on /collections instead")
    collection_name: Optional[str] = Field(
        None, description="Qdrant collection name; defaults to slugified source name"
    )


class KnowledgeSourceIngestRequest(BaseModel):
    source: str = Field(..., description="File path, directory, URL, or raw text")
    source_type: str = Field("auto", description="auto | text | pdf | web")


class KnowledgeSourceInfo(BaseModel):
    id: str
    name: str
    description: str
    collection_name: str
    embedding_model: str
    vector_size: int
    document_count: int
    chunk_count: int
    status: str
    data_connector_id: Optional[str] = None
    data_connector_ids: list[str] = Field(default_factory=list)
    monitor_enabled: bool = False
    ingestion_stages: dict[str, Any] = Field(default_factory=dict)
    query_stages: dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[dict[str, Any]] = None
    chat_model: str = ""
    reranker_model: str = ""
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CollectionList(BaseModel):
    collections: list[KnowledgeSourceInfo]
    total: int


class CreateCollectionRequest(BaseModel):
    """Create a vector collection with ingestion stage configuration."""
    name: str = Field(..., description="Unique collection name")
    description: str = Field("", description="Human-readable description")
    collection_name: Optional[str] = Field(None, description="Qdrant collection name")
    embedding_model: str = Field("nvidia-embed", description="Embedding model for indexing")
    vector_size: int = Field(2048, description="Vector dimension")
    data_connector_id: Optional[str] = Field(None, description="Legacy single linked data source")
    data_connector_ids: list[str] = Field(
        default_factory=list,
        description="Linked data source connectors (monitored after create)",
    )
    stages: dict[str, StageConfig] = Field(
        default_factory=dict,
        description="ingestion, chunking, embedding, indexing stage configs",
    )
    query_stages: dict[str, StageConfig] = Field(
        default_factory=dict,
        description="knowledge_store, retrieval, reranking, response stage configs",
    )
    metadata: Optional[dict[str, Any]] = Field(
        None,
        description="Extra metadata (e.g., index_config)",
    )
    chat_model: str = Field("llama-3.3-70b-versatile", description="LLM for response stage")
    reranker_model: str = Field("rerank-english-v3.0", description="Reranker model")


class UpdateCollectionRequest(BaseModel):
    """Update collection metadata and RAG stage configuration."""
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    vector_size: Optional[int] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    stages: Optional[dict[str, StageConfig]] = Field(
        None,
        description="ingestion, chunking, embedding, indexing stage configs",
    )
    query_stages: Optional[dict[str, StageConfig]] = Field(
        None,
        description="knowledge_store, retrieval, reranking, response stage configs",
    )
    metadata: Optional[dict[str, Any]] = Field(
        None,
        description="Extra metadata (e.g., index_config)",
    )


class CollectionIngestFromConnectorRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list, description="Connector file IDs; empty = all")


class ConnectorFileInfo(BaseModel):
    id: str
    connector_id: str
    external_id: str
    name: str
    mime_type: str
    local_path: str
    size_bytes: int
    synced_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ConnectorFileList(BaseModel):
    files: list[ConnectorFileInfo]
    total: int


class IndexedDocumentInfo(BaseModel):
    id: str
    connector_id: str
    connector_file_id: str
    external_id: str
    filename: str
    chunk_count: int
    indexed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class IndexedDocumentList(BaseModel):
    documents: list[IndexedDocumentInfo]
    total: int


class DataConnectorUploadResponse(BaseModel):
    status: str
    message: str
    files_uploaded: int = 0
    collections_synced: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class KnowledgeSourceList(BaseModel):
    sources: list[KnowledgeSourceInfo]
    total: int


# ── Data Connectors (Pathway-powered external sources) ——


class ConnectorTypeInfo(BaseModel):
    id: str
    label: str
    description: str
    available: bool = True
    fields: list[str] = Field(default_factory=list)
    runtime: str = "pathway-docker"
    supports_ui_upload: bool = True


class ConnectorTypeList(BaseModel):
    types: list[ConnectorTypeInfo]


class DataConnectorInfo(BaseModel):
    id: str
    name: str
    description: str
    connector_type: str
    object_id: str
    sync_mode: str
    status: str
    has_credentials: bool = True
    supports_ui_upload: bool = True
    service_account_email: Optional[str] = None
    file_count: int = 0
    last_sync_at: Optional[str] = None
    last_sync_message: str = ""
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class DataConnectorSyncResponse(BaseModel):
    status: str
    message: str
    files_discovered: int = 0
    files_synced: int = 0
    errors: list[str] = Field(default_factory=list)


class DataConnectorList(BaseModel):
    data_sources: list[DataConnectorInfo]
    total: int


class DataConnectorTestResponse(BaseModel):
    ok: bool
    message: str
    object_id: str
    item_count: int = 0
    sample_items: list[dict[str, Any]] = Field(default_factory=list)


# ── Knowledge Base ——


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., description="Unique name, e.g. 'company-kb'")
    description: str = Field("", description="Human-readable description")
    source_names: list[str] = Field(..., description="Existing Knowledge Source names")


class UpdateKnowledgeBaseRequest(BaseModel):
    description: Optional[str] = None
    source_names: Optional[list[str]] = None


class KnowledgeBaseInfo(BaseModel):
    id: str
    name: str
    description: str
    sources: list[dict]
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class KnowledgeBaseList(BaseModel):
    knowledge_bases: list[KnowledgeBaseInfo]


# ── Prompt Template ——


class CreatePromptTemplateRequest(BaseModel):
    id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$", min_length=1, max_length=255)
    name: str
    description: str = ""
    system_prompt: str
    user_prompt_template: str = ""
    changelog: str = "Initial version"


class CreatePromptVersionRequest(BaseModel):
    system_prompt: str
    user_prompt_template: str = ""
    changelog: str = ""


class SetActiveVersionRequest(BaseModel):
    version: int


class PromptVersionInfo(BaseModel):
    version: int
    system_prompt: str
    user_prompt_template: str = ""
    changelog: str = ""
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class PromptTemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    active_version: int
    active_system_prompt: str = ""
    version_count: int = 0
    created_at: Optional[str] = None


class PromptTemplateDetail(BaseModel):
    id: str
    name: str
    description: str
    active_version: int
    versions: list[PromptVersionInfo]
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class PromptTemplateList(BaseModel):
    templates: list[PromptTemplateSummary]


# ── Agent ——


class CreateAgentRequest(BaseModel):
    name: str = Field(..., description="Unique agent name")
    description: str = Field("", description="Human-readable description")
    knowledge_base_names: list[str] = Field(
        default_factory=list, description="One or more Knowledge Bases"
    )
    knowledge_base_name: Optional[str] = Field(None, description="Deprecated: single KB")
    knowledge_source_name: Optional[str] = Field(None, description="Deprecated: single source")
    prompt_template_id: Optional[str] = Field(None, description="Prompt template id")
    prompt_version: Optional[int] = Field(None, description="Pin prompt version; omit for active")
    llm_model: str = Field("llama-3.3-70b-versatile", description="LiteLLM model name")
    system_prompt: Optional[str] = Field(
        None,
        description="Inline system prompt (used when no prompt_template_id)",
    )
    retrieval_strategy: str = Field("multi_collection", description="Retrieval strategy")
    top_k: int = Field(5, description="Number of chunks to retrieve")
    reranker_strategy: str = Field("pass_through", description="Reranking strategy name")
    response_strategy: str = Field("contextual_response", description="Response strategy name")
    retrieval_config: Optional[dict[str, Any]] = Field(default_factory=dict)
    reranker_config: Optional[dict[str, Any]] = Field(default_factory=dict)
    response_config: Optional[dict[str, Any]] = Field(default_factory=dict)
    query_stages: Optional[dict[str, Any]] = Field(default_factory=dict)
    is_active: bool = True


class UpdateAgentRequest(BaseModel):
    description: Optional[str] = None
    knowledge_base_names: Optional[list[str]] = None
    knowledge_base_name: Optional[str] = None
    knowledge_source_name: Optional[str] = None
    prompt_template_id: Optional[str] = None
    prompt_version: Optional[int] = None
    llm_model: Optional[str] = None
    system_prompt: Optional[str] = None
    retrieval_strategy: Optional[str] = None
    top_k: Optional[int] = None
    reranker_strategy: Optional[str] = None
    response_strategy: Optional[str] = None
    retrieval_config: Optional[dict[str, Any]] = None
    reranker_config: Optional[dict[str, Any]] = None
    response_config: Optional[dict[str, Any]] = None
    query_stages: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    knowledge_base_names: list[str] = Field(default_factory=list)
    knowledge_base_name: Optional[str] = None
    knowledge_source_name: Optional[str] = None
    prompt_template_id: Optional[str] = None
    prompt_version: Optional[int] = None
    llm_model: str
    system_prompt: str
    retrieval_strategy: str
    top_k: int
    reranker_strategy: str = "pass_through"
    response_strategy: str = "contextual_response"
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    reranker_config: dict[str, Any] = Field(default_factory=dict)
    response_config: dict[str, Any] = Field(default_factory=dict)
    query_stages: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    yaml_exported_at: Optional[str] = None
    yaml_hash: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class AgentList(BaseModel):
    agents: list[AgentInfo]


class ChunkResult(BaseModel):
    content: str
    score: float
    retrieval_method: str
    filename: Optional[str] = None
    chunk_index: int = 0
    source_collection: Optional[str] = None


class AgentQueryRequest(BaseModel):
    query: str = Field(..., description="The user query")
    top_k: Optional[int] = Field(None, description="Override agent's top_k")
    stream: bool = Field(False, description="Stream response (not yet implemented)")


class AgentQueryResponse(BaseModel):
    query: str
    agent_name: str
    knowledge_target: str
    sources_searched: list[str]
    response: str
    retrieval_method: str
    timings: dict[str, float]
    total_time_ms: float
    chunks: list[ChunkResult]