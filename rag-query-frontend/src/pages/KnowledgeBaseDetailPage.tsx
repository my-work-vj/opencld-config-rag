import { useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { QUERY_PUBLIC_URL } from '@/lib/env'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Select } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'
import { EndpointCard } from '@/components/EndpointCard'

export function KnowledgeBaseDetailPage() {
  const { name } = useParams<{ name: string }>()
  const decodedName = decodeURIComponent(name ?? '')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [addSource, setAddSource] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const base = useQuery({
    queryKey: ['knowledge-base', decodedName],
    queryFn: () => api.knowledgeBase(decodedName),
    enabled: Boolean(decodedName),
  })

  const allSources = useQuery({
    queryKey: ['knowledge-sources'],
    queryFn: async () => {
      const res = await api.knowledgeSources()
      return res.sources
    },
  })

  const addMutation = useMutation({
    mutationFn: (sourceName: string) => api.addKbSource(decodedName, sourceName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', decodedName] })
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setAddSource('')
      setActionError(null)
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : 'Add failed')
    },
  })

  const removeMutation = useMutation({
    mutationFn: (sourceName: string) => api.removeKbSource(decodedName, sourceName),
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
  const availableToAdd = (allSources.data ?? []).filter((s) => !linkedNames.has(s.name))
  const kbUrl = `${QUERY_PUBLIC_URL}/knowledge-bases/${encodeURIComponent(kb.name)}`

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
        <Badge variant="outline" className="ml-auto">{kb.sources.length} sources</Badge>
        <Button variant="danger" size="sm" onClick={() => deleteKbMutation.mutate()} isLoading={deleteKbMutation.isPending}>
          <Trash2 className="size-4" />
        </Button>
      </div>

      <Card elevated>
        <CardHeader>
          <CardTitle>API endpoint</CardTitle>
        </CardHeader>
        <EndpointCard label="Knowledge base" method="GET" url={kbUrl} />
      </Card>

      <Card elevated>
        <CardHeader>
          <CardTitle>Linked sources</CardTitle>
          <CardDescription>
            Agents attached to this base search all linked collections via multi_collection retrieval.
          </CardDescription>
        </CardHeader>
        {kb.sources.length === 0 ? (
          <p className="text-sm text-slate-500">No sources linked yet.</p>
        ) : (
          <ul className="space-y-2">
            {kb.sources.map((s) => (
              <li
                key={s.source_name}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-800/40 px-3 py-2"
              >
                <div className="min-w-0 text-sm">
                  <span className="font-medium text-slate-200">{s.source_name}</span>
                  <span className="ml-2 font-mono text-xs text-slate-500">{s.collection_name}</span>
                  <p className="text-xs text-slate-500">{s.embedding_model} · dim {s.vector_size}</p>
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
            Add source
          </CardTitle>
        </CardHeader>
        {availableToAdd.length === 0 ? (
          <p className="text-sm text-slate-500">
            All sources are linked or none exist.{' '}
            <Link to="/sources" className="text-indigo-400 hover:underline">Create a source</Link>
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 space-y-2 min-w-[200px]">
              <Label htmlFor="add-source">Source</Label>
              <Select
                id="add-source"
                value={addSource}
                onChange={(e) => setAddSource(e.target.value)}
              >
                <option value="">Select source…</option>
                {availableToAdd.map((s) => (
                  <option key={s.id} value={s.name}>{s.name}</option>
                ))}
              </Select>
            </div>
            <Button
              onClick={() => addSource && addMutation.mutate(addSource)}
              disabled={!addSource}
              isLoading={addMutation.isPending}
            >
              Add source
            </Button>
          </div>
        )}
        {actionError && <p className="mt-2 text-sm text-red-400" role="alert">{actionError}</p>}
      </Card>
    </div>
  )
}
