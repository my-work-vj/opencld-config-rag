import { parseStageConfig } from '@/components/StageConfigEditor'

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

/**
 * Merge base stage defaults with user overrides and model configuration.
 * Returns the resolved ingestion stages ready for the API.
 */
export function resolveStageMaps(
  baseIngestion: Record<string, StageConfigValue>,
  stageOverrides: Record<string, string>,
  configOverrides: Record<string, string>,
  models: { embeddingModel: string },
) {
  const ingestion: Record<string, StageConfigValue> = {}
  for (const stage of INGESTION_STAGE_NAMES) {
    const base = baseIngestion[stage]
    if (!base) continue
    ingestion[stage] = {
      strategy: stageOverrides[stage] ?? base.strategy,
      config: configOverrides[stage]
        ? parseStageConfig(configOverrides[stage])
        : { ...base.config },
    }
  }

  return { ingestion }
}

export const DEFAULT_EMBEDDING_MODEL = 'nvidia-embed'
