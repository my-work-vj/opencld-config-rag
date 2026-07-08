export type StageConfig = {
  strategy: string
  config: Record<string, unknown>
}

export type Pipeline = {
  id: string
  name: string
  description: string
  stages: Record<string, StageConfig>
  embedding_model?: string | null
  chat_model?: string | null
  reranker_model?: string | null
  llm_params: Record<string, unknown>
  status: string
  created_at?: string | null
  updated_at?: string | null
}

export type PipelineListResponse = {
  pipelines: Pipeline[]
  total: number
}

export type HealthResponse = {
  status: string
  llm_available: boolean
  qdrant_available: boolean
  postgres_available: boolean
  pathway_docker_ready?: boolean
  pathway_docker_message?: string
  pipeline_count: number
  collections: string[]
  knowledge_source_count?: number
  knowledge_base_count?: number
  agent_count?: number
}

export type PathwayDockerHealth = {
  docker_available: boolean
  docker_message: string
  image: string
  image_present: boolean
  container_name: string
  container_running: boolean
  container_status: string
  ready: boolean
  message: string
}

export type CollectionInfo = {
  name: string
  points_count: number
}

/** @deprecated use QdrantCollectionInfo */
export type QdrantCollectionInfo = CollectionInfo

export type StrategiesMap = Record<string, string[]>

export type LlmModels = {
  chat: string[]
  embedding: string[]
  rerank: string[]
  _fallback?: boolean
}

export type IngestRequest = {
  source: string
  source_type: 'auto' | 'text' | 'pdf' | 'web'
  pipeline: string
}

export type IngestResponse = {
  document_count: number
  chunk_count: number
  embedding_count: number
  pipeline: string
  pipeline_name: string
  collection_name: string
  status: string
  timings: Record<string, number>
}

export type QueryRequest = {
  query: string
  pipeline: string
  collection_name?: string
  top_k?: number
}

export type ChunkResult = {
  content: string
  score: number
  retrieval_method: string
  filename?: string | null
  chunk_index: number
  source_collection?: string | null
}

export type QueryResponse = {
  query: string
  pipeline: string
  pipeline_name: string
  collection_name: string
  response: string
  retrieval_method: string
  chunks: ChunkResult[]
  timings: Record<string, number>
  total_time_ms: number
}

export type CompareResult = {
  pipeline: string
  response: string
  chunk_count: number
  retrieval_method: string
  timings: Record<string, number>
}

export type CompareResponse = {
  query: string
  results: CompareResult[]
}

export type QueryLog = {
  id: number
  pipeline: string
  collection: string
  query: string
  method: string
  total_time_ms: number
  chunk_count: number
  created_at: string | null
}

export type PipelineCreateRequest = {
  id: string
  name: string
  description?: string
  stages: Record<string, StageConfig>
  embedding_model?: string
  chat_model?: string
  reranker_model?: string
  llm_params?: Record<string, unknown>
  status?: string
}

export type PipelineUpdateRequest = Partial<
  Omit<PipelineCreateRequest, 'id'>
>


// ── Index Visualization ──

export type GraphNode = {
  id: number
  labels: string[]
  properties: Record<string, unknown>
}

export type GraphEdge = {
  id: number
  source: number
  target: number
  type: string
  properties: Record<string, unknown>
}

export type GraphVisualizationResponse = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  node_count: number
  edge_count: number
  message?: string
}

export type VectorPoint = {
  id: string
  vector_dims: Record<string, unknown>
  payload: Record<string, string>
}

export type VectorVisualizationResponse = {
  available: boolean
  name: string
  points_count: number
  vectors_count: number
  status: string
  config: Record<string, unknown>
  sample_points: VectorPoint[]
  sample_count: number
  message?: string
}

export type SparseVisualizationResponse = {
  available: boolean
  name: string
  points_count: number
  sparse_config: string
  sample_sparse_entries: {
    id: string
    sparse_indices: number
    sparse_values: number
    non_zero: number
  }[]
  sample_count: number
  message?: string
}

export type MetadataDocRecord = {
  id: string | number
  filename: string
  chunk_count: string
  created_at: string
}

export type MetadataChunkRecord = {
  chunk_index: string
  token_count: string
}

export type MetadataVisualizationResponse = {
  available: boolean
  document_count: number
  chunk_count: number
  documents: Record<string, string>[]
  sample_chunks: Record<string, string>[]
  message?: string
}

export type MemoryEntry = {
  key: string
  value: string
  type: string
  ttl: number
}

export type MemoryVisualizationResponse = {
  available: boolean
  total_keys: number
  entries: MemoryEntry[]
  message?: string
}

export type IndexConfig = {
  vector: boolean
  sparse: boolean
  graph: boolean
  metadata: boolean
  memory: boolean
}

// ── Knowledge Source ──

export type IndexConfig = {
  vector: boolean
  sparse: boolean
  graph: boolean
  metadata: boolean
  memory: boolean
}

export type KnowledgeSource = {
  id: string
  name: string
  description: string
  collection_name: string
  embedding_model: string
  vector_size: number
  document_count: number
  chunk_count: number
  status: string
  data_connector_id?: string | null
  data_connector_ids?: string[]
  monitor_enabled?: boolean
  ingestion_stages?: Record<string, StageConfig>
  query_stages?: Record<string, StageConfig>
  chat_model?: string
  reranker_model?: string
  metadata?: {
    index_config?: IndexConfig
    ingestion_mode?: 'document_plain' | 'document_vision' | 'websites'
  }
  created_at?: string | null
}

export type CollectionListResponse = {
  collections: KnowledgeSource[]
  total: number
}

export type CreateCollectionRequest = {
  name: string
  description?: string
  collection_name?: string
  embedding_model?: string
  vector_size?: number
  chat_model?: string
  reranker_model?: string
  data_connector_id?: string
  data_connector_ids?: string[]
  stages?: Record<string, StageConfig>
  query_stages?: Record<string, StageConfig>
  metadata?: {
    index_config?: IndexConfig
    ingestion_mode?: 'document_plain' | 'document_vision' | 'websites'
  }
}

export type UpdateCollectionRequest = {
  description?: string
  embedding_model?: string
  vector_size?: number
  chat_model?: string
  reranker_model?: string
  stages?: Record<string, StageConfig>
  query_stages?: Record<string, StageConfig>
  metadata?: {
    index_config?: IndexConfig
    ingestion_mode?: 'document_plain' | 'document_vision' | 'websites'
  }
}

export type KnowledgeSourceListResponse = {
  sources: KnowledgeSource[]
}

export type CreateKnowledgeSourceRequest = {
  name: string
  description?: string
  pipeline?: string
  collection_name?: string
}

export type KnowledgeSourceIngestRequest = {
  source: string
  source_type?: 'auto' | 'text' | 'pdf' | 'web'
}

export type KnowledgeSourceIngestResponse = {
  status: string
  knowledge_source: string
  document_count: number
  chunk_count: number
  collection_name: string
  timings: Record<string, number>
}

// ── Data Connectors (Pathway) ──

export type ConnectorType = {
  id: string
  label: string
  description: string
  available: boolean
  fields: string[]
  runtime?: string
  supports_ui_upload?: boolean
}

export type DataConnector = {
  id: string
  name: string
  description: string
  connector_type: string
  object_id: string
  sync_mode: string
  status: string
  has_credentials: boolean
  supports_ui_upload?: boolean
  service_account_email?: string | null
  file_count: number
  last_sync_at?: string | null
  last_sync_message: string
  metadata_json: Record<string, unknown>
  created_at?: string | null
}

export type DataConnectorListResponse = {
  data_sources: DataConnector[]
  total: number
}

export type DataConnectorTestResponse = {
  ok: boolean
  message: string
  object_id: string
  item_count: number
  sample_items: Array<{ id?: string; name?: string; mime_type?: string }>
}

export type DataConnectorSyncResponse = {
  status: string
  message: string
  files_discovered: number
  files_synced: number
  errors: string[]
}

export type ConnectorFile = {
  id: string
  connector_id: string
  external_id: string
  name: string
  mime_type: string
  local_path: string
  size_bytes: number
  synced_at?: string | null
}

export type ConnectorFileListResponse = {
  files: ConnectorFile[]
  total: number
}

export type CreateDataConnectorInput = {
  name: string
  connector_type: string
  object_id: string
  credentials: File
  description?: string
  sync_mode?: string
}

export type SourceDocument = {
  id: string
  filename: string
  pipeline_name: string
  collection_name: string
  chunk_count: number
  content_preview?: string
  metadata?: Record<string, unknown>
  created_at?: string | null
}

export type IndexedDocument = {
  id: string
  connector_id: string
  connector_file_id: string
  external_id: string
  filename: string
  chunk_count: number
  indexed_at?: string | null
}

export type IndexedDocumentListResponse = {
  documents: IndexedDocument[]
  total: number
}

export type DataConnectorUploadResponse = {
  status: string
  message: string
  files_uploaded: number
  collections_synced: string[]
  errors: string[]
}

// ── Knowledge Base ──

export type KnowledgeBaseSource = {
  source_name: string
  collection_name: string
  vector_size: number
  embedding_model: string
}

export type KnowledgeBase = {
  id: string
  name: string
  description: string
  sources: KnowledgeBaseSource[]
  created_at?: string | null
}

export type KnowledgeBaseListResponse = {
  knowledge_bases: KnowledgeBase[]
}

export type CreateKnowledgeBaseRequest = {
  name: string
  description?: string
  source_names: string[]
}

export type UpdateKnowledgeBaseRequest = {
  description?: string
  source_names?: string[]
}

// ── Prompt Template ──

export type PromptVersion = {
  version: number
  system_prompt: string
  user_prompt_template?: string
  changelog?: string
  created_at?: string | null
}

export type PromptTemplateSummary = {
  id: string
  name: string
  description: string
  active_version: number
  active_system_prompt: string
  version_count: number
  created_at?: string | null
}

export type PromptTemplateDetail = {
  id: string
  name: string
  description: string
  active_version: number
  versions: PromptVersion[]
  created_at?: string | null
}

export type PromptTemplateListResponse = {
  templates: PromptTemplateSummary[]
}

export type CreatePromptTemplateRequest = {
  id: string
  name: string
  description?: string
  system_prompt: string
  user_prompt_template?: string
  changelog?: string
}

export type CreatePromptVersionRequest = {
  system_prompt: string
  user_prompt_template?: string
  changelog?: string
}

// ── Agent ──

export type Agent = {
  id: string
  name: string
  description: string
  knowledge_base_names: string[]
  knowledge_base_name?: string | null
  knowledge_source_name?: string | null
  prompt_template_id?: string | null
  prompt_version?: number | null
  llm_model: string
  system_prompt: string
  retrieval_strategy: string
  top_k: number
  reranking_strategy: string
  response_strategy: string
  retrieval_config: Record<string, unknown>
  reranking_config: Record<string, unknown>
  response_config: Record<string, unknown>
  query_stages: Record<string, unknown>
  is_active: boolean
  yaml_exported_at?: string | null
  yaml_hash?: string | null
  created_at?: string | null
}

export type AgentListResponse = {
  agents: Agent[]
}

export type CreateAgentRequest = {
  name: string
  description?: string
  knowledge_base_names?: string[]
  knowledge_base_name?: string
  knowledge_source_name?: string
  prompt_template_id?: string
  prompt_version?: number
  llm_model?: string
  system_prompt?: string
  retrieval_strategy?: string
  top_k?: number
  reranking_strategy?: string
  response_strategy?: string
  retrieval_config?: Record<string, unknown>
  reranking_config?: Record<string, unknown>
  response_config?: Record<string, unknown>
  query_stages?: Record<string, unknown>
  is_active?: boolean
}

export type UpdateAgentRequest = Partial<CreateAgentRequest>

// ── Evaluation / Metrics ──

export type ExtractionMetrics = {
  total_documents: number
  success_rate: number
  error_rate: number
  avg_content_length: number
  content_length_stdev: number
  format_coverage: Record<string, number>
  avg_extraction_time_ms: number
  avg_file_size_bytes: number
  empty_extraction_rate?: number
}

export type ChunkingMetrics = {
  total_chunks: number
  avg_chunk_size: number
  chunk_size_stdev: number
  chunks_per_doc: number
  duplicate_content_rate: number
  empty_chunks: number
  p50: number
  p95: number
  p99: number
}

export type EmbeddingMetrics = {
  total_embeddings: number
  embedding_dimensions: number
  avg_vector_norm: number
  norm_stdev: number
  avg_cosine_similarity: number
  dimension_utilization: number
  zero_vector_rate: number
}

export type PipelineHealthMetrics = {
  status: string
  total_documents: number
  total_chunks: number
  docs_per_second: number | null
  error_rate: number
  files_added?: number
  files_updated?: number
  files_deleted?: number
}

export type RetrievalMetrics = {
  total_questions: number
  avg_faithfulness: number
  avg_answer_relevancy: number
  avg_context_precision: number
  avg_context_recall: number
  avg_noise_sensitivity: number
  thresholds_passed: number
  thresholds_total: number
}

export type EvalMetrics = {
  extraction?: ExtractionMetrics
  chunking?: ChunkingMetrics
  embedding?: EmbeddingMetrics
  pipeline?: PipelineHealthMetrics
  retrieval?: RetrievalMetrics
}

export type EvalResult = {
  collection_name: string
  timestamp: string
  status?: string
  metrics: EvalMetrics
  layers: EvalMetrics
  summary?: EvalMetrics
}

export type ThresholdCheckResult = {
  layer: string
  metric: string
  value: number
  threshold: { min?: number | null; max?: number | null } | number | string
  passed: boolean
}

export type ThresholdReport = {
  summary: { passed: number; failed: number; total: number }
  all_passed: boolean
  results: ThresholdCheckResult[]
}

export type EvaluationListResponse = {
  reports: string[]
  total: number
}

export type AgentQueryRequest = {
  query: string
  top_k?: number
}

export type AgentQueryResponse = {
  query: string
  agent_name: string
  knowledge_target: string
  sources_searched: string[]
  response: string
  retrieval_method: string
  chunks: ChunkResult[]
  timings: Record<string, number>
  total_time_ms: number
}
