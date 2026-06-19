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
  pipeline_count: number
  collections: string[]
  knowledge_source_count?: number
  knowledge_base_count?: number
  agent_count?: number
}

export type CollectionInfo = {
  name: string
  points_count: number
}

export type StrategiesMap = Record<string, string[]>

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
  collection?: string
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

// ── Knowledge Source ──

export type KnowledgeSource = {
  id: string
  name: string
  description: string
  collection_name: string
  pipeline_id: string
  embedding_model: string
  vector_size: number
  document_count: number
  chunk_count: number
  status: string
  created_at?: string | null
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

export type SourceDocument = {
  id: string
  filename: string
  pipeline_name: string
  collection_name: string
  chunk_count: number
  content_preview: string
  metadata: Record<string, unknown>
  created_at: string | null
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
