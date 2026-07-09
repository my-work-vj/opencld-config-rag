import { Badge } from '@/components/ui/Badge'
import { IndexConfigBadges } from '@/components/IndexConfigEditor'
import { ingestionModeLabel } from '@/lib/terminology'
import type { KnowledgeBaseSource } from '@/types/api'

const INDEX_LABELS: Record<string, string> = {
  vector: 'Vector',
  sparse: 'Sparse',
  graph: 'Graph',
  metadata: 'Metadata',
  memory: 'Memory',
}

export function AggregatedIndexBadges({ indexes }: { indexes: string[] }) {
  if (!indexes.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {indexes.map((idx) => (
        <Badge key={idx} variant="outline" className="text-xs">
          {INDEX_LABELS[idx] ?? idx}
        </Badge>
      ))}
    </div>
  )
}

export function ProfileCatalogRow({ profile }: { profile: KnowledgeBaseSource }) {
  return (
    <li className="rounded-lg border border-slate-700/60 bg-slate-800/40 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-slate-200">{profile.source_name}</p>
          <p className="font-mono text-xs text-slate-500">{profile.collection_name}</p>
        </div>
        {profile.status && profile.status !== 'ready' && (
          <Badge variant="outline" className="text-amber-300 border-amber-700">
            {profile.status}
          </Badge>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <IndexConfigBadges config={profile.index_config} />
        {profile.ingestion_mode && (
          <Badge variant="outline" className="text-xs">
            {ingestionModeLabel(profile.ingestion_mode)}
          </Badge>
        )}
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {profile.embedding_model} · dim {profile.vector_size}
        {profile.document_count != null && ` · ${profile.document_count} docs`}
        {profile.modalities?.length ? ` · ${profile.modalities.join(', ')}` : ''}
      </p>
    </li>
  )
}
