import { useState } from 'react'
import {
  INGESTION_STAGE_NAMES,
  STAGE_LABELS,
  type StageConfigValue,
} from '@/lib/stage-defaults'
import {
  StageConfigEditor,
  parseStageConfig,
  stringifyStageConfig,
} from './StageConfigEditor'

export type IngestionMode = 'document_plain' | 'document_vision' | 'websites'

interface RagStagesEditorProps {
  baseStages: Record<string, StageConfigValue>
  stageStrategies: Record<string, string>
  stageConfigs: Record<string, string>
  onChangeStrategies: (v: Record<string, string>) => void
  onChangeConfigs: (v: Record<string, string>) => void
  onChangeStages?: (stages: Record<string, StageConfigValue>) => void
  /** Currently selected embedding model */
  embeddingModel: string
  onChangeEmbeddingModel?: (model: string) => void
  /** Available LLM models from LiteLLM proxy */
  llmModels?: { chat: string[]; embedding: string[]; rerank: string[] }
  /** Currently selected ingestion mode */
  ingestionMode: IngestionMode
  onChangeIngestionMode: (mode: IngestionMode) => void
  /** Available strategies keyed by stage name */
  strategies?: Record<string, string[]>
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
}: RagStagesEditorProps) {
  return (
    <div className="space-y-6">
      {/* ── Embedding model picker ── */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700">
          Embedding model
        </label>
        <select
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
        <p className="text-xs text-gray-500">
          Vector size is derived automatically from the selected model
        </p>
      </div>

      {/* ── Document Source — two clickable cards ── */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-700">
          Document source
        </label>

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => onChangeIngestionMode('document_plain')}
            className={`rounded-xl border-2 p-4 text-left transition-all ${
              ingestionMode.startsWith('document')
                ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300'
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <span className="block text-sm font-semibold text-gray-800">
              📄 Document
            </span>
            <span className="mt-1 block text-xs text-gray-500">
              PDF, DOCX, images &amp; more
            </span>
          </button>

          <button
            type="button"
            onClick={() => onChangeIngestionMode('websites')}
            className={`rounded-xl border-2 p-4 text-left transition-all ${
              ingestionMode === 'websites'
                ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300'
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <span className="block text-sm font-semibold text-gray-800">
              🌐 Websites
            </span>
            <span className="mt-1 block text-xs text-gray-500">
              Extract content from URLs
            </span>
          </button>
        </div>

        {/* Radio buttons when Document is selected */}
        {ingestionMode.startsWith('document') && (
          <div className="ml-1 space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-3">
            <label className="flex items-start gap-3 rounded-md p-2 hover:bg-white transition-colors cursor-pointer">
              <input
                type="radio"
                name="doc-subtype"
                checked={ingestionMode === 'document_plain'}
                onChange={() => onChangeIngestionMode('document_plain')}
                className="mt-1 h-4 w-4 text-blue-600"
              />
              <div>
                <span className="block text-sm font-medium text-gray-800">
                  Plain text only
                </span>
                <span className="block text-xs text-gray-500">
                  Extracts readable text, ignores tables &amp; images (active)
                </span>
              </div>
            </label>

            <label className="flex items-start gap-3 rounded-md p-2 hover:bg-white transition-colors cursor-pointer">
              <input
                type="radio"
                name="doc-subtype"
                checked={ingestionMode === 'document_vision'}
                onChange={() => onChangeIngestionMode('document_vision')}
                className="mt-1 h-4 w-4 text-blue-600"
              />
              <div>
                <span className="block text-sm font-medium text-gray-800">
                  Image &amp; graph understanding
                </span>
                <span className="block text-xs text-gray-500">
                  Standalone images use multimodal embeddings via nvidia-embed (Path B)
                </span>
              </div>
            </label>
          </div>
        )}

        {/* URL textbox when Websites is selected */}
        {ingestionMode === 'websites' && (
          <div className="space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-3">
            <textarea
              placeholder="Enter one URL per line to extract content from"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={3}
              disabled
            />
            <button
              type="button"
              disabled
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white opacity-50 cursor-not-allowed"
            >
              Extract data
            </button>
            <p className="text-xs text-gray-400">
              Website extraction is planned for future implementation
            </p>
          </div>
        )}
      </div>

      {/* ── Ingestion stages (only chunking shown) ── */}
      {INGESTION_STAGE_NAMES.filter((s) => s !== 'ingestion').map(
        (stageName) => {
          const base = baseStages[stageName]
          if (!base) return null
          const strategy = stageStrategies[stageName] || base.strategy
          const configJson =
            stageConfigs[stageName] ?? stringifyStageConfig(base.config)

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
        },
      )}
    </div>
  )
}

export { resolveStageMaps } from '@/lib/stage-defaults'
