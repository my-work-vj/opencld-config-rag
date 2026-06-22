export const INGESTION_STAGE_NAMES = [
  'ingestion',
  'chunking',
] as const

export const STAGE_LABELS: Record<string, string> = {
  ingestion: 'Ingestion',
  chunking: 'Chunking',
}

export type StageConfigValue = {
  strategy: string
  config: Record<string, unknown>
}

export const DEFAULT_INGESTION_STAGES: Record<string, StageConfigValue> = {
  ingestion: { strategy: 'kreuzberg_ingestion', config: {} },
  chunking: {
    strategy: 'recursive_chunking',
    config: { chunk_size: 512, chunk_overlap: 50 },
  },
}

export const DEFAULT_EMBEDDING_MODEL = 'nvidia-embed'
