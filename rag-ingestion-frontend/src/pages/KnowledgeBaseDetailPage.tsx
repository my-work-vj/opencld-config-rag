import { useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2, CheckCircle2, AlertTriangle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import {
  INDEX_PROFILES_PATH,
  INDEX_PROFILE_PLURAL,
  INDEX_PROFILE_SINGULAR,
  indexProfilePath,
  ingestionModeLabel,
} from '@/lib/terminology'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Select } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'
import { AggregatedIndexBadges, ProfileCatalogRow } from '@/components/KbCatalogBadges'
import { IndexConfigBadges } from '@/components/IndexConfigEditor'

export function KnowledgeBaseDetailPage() {
  const { name } = useParams<{ name: string }>()
  const decodedName = decodeURIComponent(name ?? '')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [addCollection, setAddCollection] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const base = useQuery({
    queryKey: ['knowledge-base', decodedName],
    queryFn: () => api.knowledgeBase(decodedName),
    enabled: Boolean(decodedName),
  })

  const catalog = useQuery({
    queryKey: ['knowledge-base-catalog', decodedName],
    queryFn: () => api.knowledgeBaseIndexCatalog(decodedName),
    enabled: Boolean(decodedName),
  })

  const allCollections = useQuery({
    queryKey: ['vector-collections'],
    queryFn: async () => (await api.vectorCollections()).collections,
  })

  // Fetch evaluation status for the currently selected collection
  const evalStatus = useQuery({
    queryKey: ['eval-latest', addCollection],
    queryFn: () => api.latestEvaluation(addCollection),
    enabled: Boolean(addCollection),
    retry: false,
    staleTime: 30_000,
  })

  const addMutation = useMutation({
    mutationFn: (collectionName: string) => api.addKbCollection(decodedName, collectionName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', decodedName] })
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setAddCollection('')
      setActionError(null)
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : 'Add failed')
    },
  })

  const removeMutation = useMutation({
    mutationFn: (collectionName: string) => api.removeKbCollection(decodedName, collectionName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', decodedName] })
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setActionError(null)
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : 'Remove failed')
    },
  })

  const deleteKbMutation = useMutation({
    mutationFn: () => api.deleteKnowledgeBase(decodedName),
    onSuccess: () => navigate('/knowledge-bases'),
  })

  if (base.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  if (base.isError || !base.data) {
    return (
      <div className="space-y-4 text-center py-20">
        <p className="text-red-400">Knowledge base not found: {decodedName}</p>
        <Link to="/knowledge-bases">
          <Button variant="secondary">Back to knowledge bases</Button>
        </Link>
      </div>
    )
  }

  const kb = base.data
  const linkedNames = new Set(kb.sources.map((s) => s.source_name))
  const availableToAdd = (allCollections.data ?? []).filter((c) => !linkedNames.has(c.name))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link
          to="/knowledge-bases"
          className="flex min-h-11 min-w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800/80 hover:text-white"
          aria-label="Back to knowledge bases"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">{kb.name}</h1>
          <p className="text-sm text-slate-400">{kb.description}</p>
        </div>
        <Badge variant="outline" className="ml-auto">{kb.sources.length} profiles</Badge>
        <Button
          variant="danger"
          size="sm"
          onClick={() => deleteKbMutation.mutate()}
          isLoading={deleteKbMutation.isPending}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>

      <Card elevated>
        <CardHeader>
          <CardTitle>Index catalog</CardTitle>
          <CardDescription>
            Live snapshot for RAG Builder — aggregated indexes and modalities across profiles.
          </CardDescription>
        </CardHeader>
        {catalog.isLoading ? (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        ) : catalog.data ? (
          <div className="space-y-4">
            <div>
              <p className="mb-2 text-xs text-slate-500">Aggregated indexes</p>
              <AggregatedIndexBadges indexes={catalog.data.aggregated_indexes} />
            </div>
            {catalog.data.modalities.length > 0 && (
              <div>
                <p className="mb-2 text-xs text-slate-500">Modalities</p>
                <div className="flex flex-wrap gap-1.5">
                  {catalog.data.modalities.map((m) => (
                    <Badge key={m} variant="outline" className="text-xs">{m}</Badge>
                  ))}
                </div>
              </div>
            )}
            <ul className="space-y-2">
              {catalog.data.profiles.map((p) => (
                <ProfileCatalogRow key={p.source_name} profile={p} />
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Catalog unavailable.</p>
        )}
      </Card>

      <Card elevated>
        <CardHeader>
          <CardTitle>{INDEX_PROFILE_PLURAL} in this cluster</CardTitle>
          <CardDescription>
            Query agents attach to knowledge bases — not individual index profiles.
          </CardDescription>
        </CardHeader>
        {kb.sources.length === 0 ? (
          <p className="text-sm text-slate-500">No index profiles linked yet.</p>
        ) : (
          <ul className="space-y-2">
            {kb.sources.map((s) => (
              <li
                key={s.source_name}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-800/40 px-3 py-2"
              >
                <div className="min-w-0 text-sm">
                  <Link
                    to={indexProfilePath(s.source_name)}
                    className="font-medium text-indigo-300 hover:underline"
                  >
                    {s.source_name}
                  </Link>
                  <span className="ml-2 font-mono text-xs text-slate-500">{s.collection_name}</span>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <IndexConfigBadges config={s.index_config} />
                    {s.ingestion_mode && (
                      <Badge variant="outline" className="text-xs">
                        {ingestionModeLabel(s.ingestion_mode)}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {s.embedding_model} · dim {s.vector_size}
                    {s.document_count != null && ` · ${s.document_count} docs`}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeMutation.mutate(s.source_name)}
                  isLoading={removeMutation.isPending}
                  aria-label={`Remove ${s.source_name}`}
                >
                  <Trash2 className="size-4 text-red-400" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card elevated>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="size-5 text-indigo-400" aria-hidden="true" />
            Add index profile
          </CardTitle>
        </CardHeader>
        {availableToAdd.length === 0 ? (
          <p className="text-sm text-slate-500">
            All index profiles are linked or none exist.{' '}
            <Link to={INDEX_PROFILES_PATH} className="text-indigo-400 hover:underline">
              Create an index profile
            </Link>
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[200px] flex-1 space-y-2">
              <Label htmlFor="add-collection">{INDEX_PROFILE_SINGULAR}</Label>
              <Select
                id="add-collection"
                value={addCollection}
                onChange={(e) => setAddCollection(e.target.value)}
              >
                <option value="">Select index profile…</option>
                {availableToAdd.map((c) => (
                  <option key={c.id} value={c.name}>{c.name}</option>
                ))}
              </Select>
            </div>
            {/* Evaluation status for selected collection */}
            {addCollection && evalStatus.isLoading && (
              <span className="text-xs text-slate-500">Checking evaluation…</span>
            )}
            {addCollection && evalStatus.isError && (
              <p className="mt-1 flex items-center gap-1 text-xs text-amber-400">
                <AlertTriangle className="size-3.5" />
                <span>No evaluation yet. Run Evaluate on this index profile first.</span>
              </p>
            )}
            {addCollection && evalStatus.data && (
              <p className="mt-1 flex items-center gap-1 text-xs text-emerald-400">
                <CheckCircle2 className="size-3.5" />
                <span>Thresholds OK — ready to add</span>
              </p>
            )}
            <Button
              onClick={() => addCollection && addMutation.mutate(addCollection)}
              disabled={!addCollection}
              isLoading={addMutation.isPending}
            >
              Add index profile
            </Button>
          </div>
        )}
        {actionError && <p className="mt-2 text-sm text-red-400" role="alert">{actionError}</p>}
      </Card>
    </div>
  )
}
