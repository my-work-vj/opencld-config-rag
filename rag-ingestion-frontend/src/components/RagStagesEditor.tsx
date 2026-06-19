import {
  INGESTION_STAGE_NAMES,
  QUERY_STAGE_NAMES,
  STAGE_LABELS,
  type StageConfigValue,
} from '@/lib/stage-defaults'
import {
  StageConfigEditor,
  parseStageConfig,
  stringifyStageConfig,
} from '@/components/StageConfigEditor'

type StrategiesMap = Record<string, string[]>

type RagStagesEditorProps = {
  strategies: StrategiesMap
  ingestionStages: Record<string, StageConfigValue>
  queryStages: Record<string, StageConfigValue>
  stageOverrides: Record<string, string>
  configOverrides: Record<string, string>
  onStrategyChange: (stage: string, strategy: string) => void
  onConfigChange: (stage: string, configJson: string) => void
}

export function RagStagesEditor({
  strategies,
  ingestionStages,
  queryStages,
  stageOverrides,
  configOverrides,
  onStrategyChange,
  onConfigChange,
}: RagStagesEditorProps) {
  const renderSection = (
    title: string,
    description: string,
    stageNames: readonly string[],
    stages: Record<string, StageConfigValue>,
  ) => (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-slate-300">{title}</h3>
      <p className="mb-3 text-xs text-slate-500">{description}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {stageNames.map((stage) => (
          <StageConfigEditor
            key={stage}
            stage={STAGE_LABELS[stage] ?? stage}
            strategies={strategies[stage] ?? []}
            strategy={stageOverrides[stage] ?? stages[stage]?.strategy ?? ''}
            configJson={
              configOverrides[stage] ??
              stringifyStageConfig(stages[stage]?.config ?? {})
            }
            onStrategyChange={(strategy) => onStrategyChange(stage, strategy)}
            onConfigChange={(configJson) => onConfigChange(stage, configJson)}
          />
        ))}
      </div>
    </div>
  )

  return (
    <div className="space-y-8">
      {renderSection(
        'Ingestion stages',
        'How documents are parsed, chunked, embedded, and written to Qdrant.',
        INGESTION_STAGE_NAMES,
        ingestionStages,
      )}
      {renderSection(
        'Query stages',
        'How chunks are retrieved, reranked, and turned into answers at query time.',
        QUERY_STAGE_NAMES,
        queryStages,
      )}
    </div>
  )
}

export function resolveStageMaps(
  baseIngestion: Record<string, StageConfigValue>,
  baseQuery: Record<string, StageConfigValue>,
  stageOverrides: Record<string, string>,
  configOverrides: Record<string, string>,
  models: { embeddingModel: string; vectorSize: number; chatModel: string; rerankerModel: string },
) {
  const ingestion: Record<string, StageConfigValue> = {}
  for (const stage of INGESTION_STAGE_NAMES) {
    const base = baseIngestion[stage]
    ingestion[stage] = {
      strategy: stageOverrides[stage] ?? base.strategy,
      config: configOverrides[stage]
        ? parseStageConfig(configOverrides[stage])
        : { ...base.config },
    }
  }
  ingestion.embedding.config.model = models.embeddingModel
  ingestion.indexing.config.model = models.embeddingModel
  ingestion.indexing.config.vector_size = models.vectorSize

  const query: Record<string, StageConfigValue> = {}
  for (const stage of QUERY_STAGE_NAMES) {
    const base = baseQuery[stage]
    query[stage] = {
      strategy: stageOverrides[stage] ?? base.strategy,
      config: configOverrides[stage]
        ? parseStageConfig(configOverrides[stage])
        : { ...base.config },
    }
  }
  query.response.config.model = models.chatModel
  query.reranking.config.model = models.rerankerModel

  return { ingestion, query }
}
