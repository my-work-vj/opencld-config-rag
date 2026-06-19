export const INGESTION_STAGE_NAMES = [
  'ingestion',
  'chunking',
  'embedding',
  'indexing',
] as const

export const QUERY_STAGE_NAMES = [
  'knowledge_store',
  'retrieval',
  'reranking',
  'response',
] as const

export const ALL_STAGE_NAMES = [...INGESTION_STAGE_NAMES, ...QUERY_STAGE_NAMES] as const

export const STAGE_LABELS: Record<string, string> = {
  ingestion: 'Ingestion',
  chunking: 'Chunking',
  embedding: 'Embedding',
  indexing: 'Indexing',
  knowledge_store: 'Knowledge store',
  retrieval: 'Retrieval',
  reranking: 'Reranking',
  response: 'Response',
}

export type StageConfigValue = {
  strategy: string
  config: Record<string, unknown>
}

export const DEFAULT_INGESTION_STAGES: Record<string, StageConfigValue> = {
  ingestion: { strategy: 'pdf_ingestion', config: {} },
  chunking: {
    strategy: 'recursive_chunking',
    config: { chunk_size: 512, chunk_overlap: 50 },
  },
  embedding: { strategy: 'litellm_embedding', config: { model: 'nvidia-embed' } },
  indexing: {
    strategy: 'qdrant_indexing',
    config: { vector_size: 2048, model: 'nvidia-embed' },
  },
}

export const DEFAULT_QUERY_STAGES: Record<string, StageConfigValue> = {
  knowledge_store: {
    strategy: 'qdrant_store',
    config: { validate: true },
  },
  retrieval: {
    strategy: 'vector_rag',
    config: { top_k: 5, top_k_rerank: 10, query_rewrite: true, use_hyde: true },
  },
  reranking: {
    strategy: 'litellm_reranking',
    config: { model: 'rerank-english-v3.0', top_k: 5 },
  },
  response: {
    strategy: 'contextual_response',
    config: {
      model: 'llama-3.3-70b-versatile',
      temperature: 0.3,
      max_tokens: 2048,
    },
  },
}

export const DEFAULT_CHAT_MODEL = 'llama-3.3-70b-versatile'
export const DEFAULT_RERANKER_MODEL = 'rerank-english-v3.0'
export const DEFAULT_EMBEDDING_MODEL = 'nvidia-embed'
