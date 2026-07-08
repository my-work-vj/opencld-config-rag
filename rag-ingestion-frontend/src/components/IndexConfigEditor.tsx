import type { IndexConfig } from '@/types/api'

export const DEFAULT_INDEX_CONFIG: IndexConfig = {
  vector: true,
  sparse: false,
  graph: false,
  metadata: true,
  memory: false,
}

export function normalizeIndexConfig(raw?: Partial<IndexConfig> | null): IndexConfig {
  return {
    vector: raw?.vector ?? DEFAULT_INDEX_CONFIG.vector,
    sparse: raw?.sparse ?? DEFAULT_INDEX_CONFIG.sparse,
    graph: raw?.graph ?? DEFAULT_INDEX_CONFIG.graph,
    metadata: raw?.metadata ?? DEFAULT_INDEX_CONFIG.metadata,
    memory: raw?.memory ?? DEFAULT_INDEX_CONFIG.memory,
  }
}

type IndexConfigEditorProps = {
  value: IndexConfig
  onChange: (next: IndexConfig) => void
  disabled?: boolean
}

const INDEX_OPTIONS: {
  key: keyof IndexConfig
  label: string
  hint: string
}[] = [
  { key: 'vector', label: 'Vector (Qdrant)', hint: 'Dense embeddings' },
  { key: 'sparse', label: 'Sparse (BM25)', hint: 'Keyword matching' },
  { key: 'graph', label: 'Graph (Neo4j)', hint: 'Entity relationships' },
  { key: 'metadata', label: 'Metadata (PostgreSQL)', hint: 'Document & chunk records' },
  { key: 'memory', label: 'Memory (Redis)', hint: 'Per-document catalog' },
]

export function IndexConfigEditor({ value, onChange, disabled }: IndexConfigEditorProps) {
  const handleToggle = (key: keyof IndexConfig, checked: boolean) => {
    onChange({ ...value, [key]: checked })
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium text-slate-200">Index types</p>
        <p className="text-xs text-slate-500">
          Enable or disable indexes at any time. Saving triggers re-indexing for linked files.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {INDEX_OPTIONS.map(({ key, label, hint }) => (
          <label
            key={key}
            className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-700/60 bg-slate-800/40 p-3 text-sm text-slate-300"
          >
            <input
              type="checkbox"
              checked={Boolean(value[key])}
              onChange={(e) => handleToggle(key, e.target.checked)}
              disabled={disabled}
              className="mt-0.5 rounded border-slate-600 bg-slate-800 text-indigo-500"
            />
            <span>
              <span className="block font-medium text-slate-200">{label}</span>
              <span className="block text-xs text-slate-500">{hint}</span>
            </span>
          </label>
        ))}
      </div>
    </div>
  )
}

export function IndexConfigBadges({ config }: { config?: Partial<IndexConfig> | null }) {
  if (!config) return null
  const items: { key: keyof IndexConfig; label: string; className?: string }[] = [
    { key: 'vector', label: 'Vector' },
    { key: 'sparse', label: 'Sparse', className: 'border-violet-700 text-violet-300' },
    { key: 'graph', label: 'Graph', className: 'border-cyan-700 text-cyan-300' },
    { key: 'metadata', label: 'Meta' },
    { key: 'memory', label: 'Memory', className: 'border-amber-700 text-amber-300' },
  ]
  return (
    <>
      {items
        .filter(({ key }) => config[key])
        .map(({ key, label, className }) => (
          <span
            key={key}
            className={`inline-flex items-center rounded-full border border-slate-600 px-2 py-0.5 text-xs text-slate-300 ${className ?? ''}`}
          >
            {label}
          </span>
        ))}
    </>
  )
}
