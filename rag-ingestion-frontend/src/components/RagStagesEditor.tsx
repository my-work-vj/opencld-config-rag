import {
  INGESTION_STAGE_NAMES,
  type StageConfigValue,
} from '@/lib/stage-defaults'
import {
  StageConfigEditor,
  stringifyStageConfig,
} from './StageConfigEditor'

export type IngestionMode = 'document_plain' | 'document_vision' | 'websites'

interface IngestionModePickerProps {
  ingestionMode: IngestionMode
  onChangeIngestionMode: (mode: IngestionMode) => void
}

export function IngestionModePicker({
  ingestionMode,
  onChangeIngestionMode,
}: IngestionModePickerProps) {
  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium text-slate-200">Perception mode</p>
        <p className="text-xs text-slate-500">
          Controls how files are interpreted before indexing (text, images, PDF pages).
        </p>
      </div>
      <div className="space-y-2 rounded-lg border border-slate-700/60 bg-slate-800/40 p-3">
        <label className="flex cursor-pointer items-start gap-3 rounded-md p-2 hover:bg-slate-800/80">
          <input
            type="radio"
            name="ingestion-mode"
            checked={ingestionMode === 'document_plain'}
            onChange={() => onChangeIngestionMode('document_plain')}
            className="mt-1 h-4 w-4 text-indigo-500"
          />
          <div>
            <span className="block text-sm font-medium text-slate-200">Plain text</span>
            <span className="block text-xs text-slate-500">
              Kreuzberg text extraction for documents (default).
            </span>
          </div>
        </label>
        <label className="flex cursor-pointer items-start gap-3 rounded-md p-2 hover:bg-slate-800/80">
          <input
            type="radio"
            name="ingestion-mode"
            checked={ingestionMode === 'document_vision'}
            onChange={() => onChangeIngestionMode('document_vision')}
            className="mt-1 h-4 w-4 text-indigo-500"
          />
          <div>
            <span className="block text-sm font-medium text-slate-200">Multimodal vision</span>
            <span className="block text-xs text-slate-500">
              Images and PDF pages via nvidia-embed (text, image, and text+image vectors).
            </span>
          </div>
        </label>
      </div>
    </div>
  )
}

interface RagStagesEditorProps {
  baseStages: Record<string, StageConfigValue>
  stageStrategies: Record<string, string>
  stageConfigs: Record<string, string>
  onChangeStrategies: (v: Record<string, string>) => void
  onChangeConfigs: (v: Record<string, string>) => void
  embeddingModel: string
  onChangeEmbeddingModel?: (model: string) => void
  llmModels?: { chat: string[]; embedding: string[]; rerank: string[] }
  ingestionMode: IngestionMode
  onChangeIngestionMode: (mode: IngestionMode) => void
  strategies?: Record<string, string[]>
  /** When true, only chunking/embedding overrides (modality picker hidden). */
  advancedOnly?: boolean
}

export default function RagStagesEditor({
  baseStages,
  stageStrategies,
  stageConfigs,
  onChangeStrategies,
  onChangeConfigs,
  embeddingModel,
  onChangeEmbeddingModel,
  llmModels,
  ingestionMode,
  onChangeIngestionMode,
  strategies: allStrategies,
  advancedOnly = false,
}: RagStagesEditorProps) {
  return (
    <div className="space-y-6">
      {!advancedOnly && (
        <IngestionModePicker
          ingestionMode={ingestionMode}
          onChangeIngestionMode={onChangeIngestionMode}
        />
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-200">Embedding model</label>
        <select
          className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          value={embeddingModel}
          onChange={(e) => onChangeEmbeddingModel?.(e.target.value)}
        >
          {(llmModels?.embedding ?? []).length > 0 ? (
            llmModels!.embedding.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))
          ) : (
            <option value={embeddingModel}>{embeddingModel}</option>
          )}
        </select>
        <p className="text-xs text-slate-500">
          Vector dimensions are resolved from the LiteLLM model catalog.
        </p>
      </div>

      {INGESTION_STAGE_NAMES.filter((s) => s !== 'ingestion').map((stageName) => {
        const base = baseStages[stageName]
        if (!base) return null
        const strategy = stageStrategies[stageName] || base.strategy
        const configJson = stageConfigs[stageName] ?? stringifyStageConfig(base.config)

        return (
          <StageConfigEditor
            key={stageName}
            stage={stageName}
            strategies={allStrategies?.[stageName] ?? [base.strategy]}
            strategy={strategy}
            configJson={configJson}
            onStrategyChange={(newStrategy) =>
              onChangeStrategies({ ...stageStrategies, [stageName]: newStrategy })
            }
            onConfigChange={(newConfig) =>
              onChangeConfigs({ ...stageConfigs, [stageName]: newConfig })
            }
          />
        )
      })}
    </div>
  )
}

export { resolveStageMaps } from '@/lib/stage-defaults'
