import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Plus } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, Spinner } from '@/components/ui/Feedback'
import { AggregatedIndexBadges } from '@/components/KbCatalogBadges'
import type { KnowledgeBase } from '@/types/api'
import {
  INDEX_PROFILES_PATH,
  INDEX_PROFILE_PLURAL,
  INDEX_PROFILE_SINGULAR,
} from '@/lib/terminology'

export function KnowledgeBasesPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedCollections, setSelectedCollections] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const bases = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: async () => (await api.knowledgeBases()).knowledge_bases,
    refetchInterval: 15_000,
  })

  const collections = useQuery({
    queryKey: ['vector-collections'],
    queryFn: async () => (await api.vectorCollections()).collections,
    refetchInterval: 15_000,
  })

  const createMutation = useMutation({
    mutationFn: api.createKnowledgeBase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setShowForm(false)
      setName('')
      setDescription('')
      setSelectedCollections([])
      setError(null)
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Create failed')
    },
  })

  const handleToggleCollection = (collectionName: string) => {
    setSelectedCollections((prev) =>
      prev.includes(collectionName)
        ? prev.filter((n) => n !== collectionName)
        : [...prev, collectionName],
    )
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (selectedCollections.length === 0) {
      setError(`Select at least one ${INDEX_PROFILE_SINGULAR.toLowerCase()}`)
      return
    }
    createMutation.mutate({
      name: name.trim(),
      description,
      source_names: selectedCollections,
    })
  }

  if (bases.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  const list = bases.data ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Knowledge Bases</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Knowledge clusters group one or more index profiles. Only knowledge bases connect
            to retrieval and query pipelines — not individual profiles.
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} variant="secondary">
          <Plus className="size-4" aria-hidden="true" />
          New knowledge base
        </Button>
      </div>

      {showForm && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Create knowledge base</CardTitle>
            <CardDescription>
              Select index profiles to search together at query time via agents.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="kb-name">Name *</Label>
              <Input
                id="kb-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="company-kb"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="kb-desc">Description</Label>
              <Textarea
                id="kb-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label>{INDEX_PROFILE_PLURAL} *</Label>
              {(collections.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">
                  No index profiles yet.{' '}
                  <Link to={INDEX_PROFILES_PATH} className="text-indigo-400 hover:underline">
                    Create an index profile
                  </Link>
                </p>
              ) : (
                <ul className="space-y-2 rounded-lg border border-slate-700/60 p-3">
                  {collections.data?.map((col) => (
                    <li key={col.id}>
                      <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                        <input
                          type="checkbox"
                          checked={selectedCollections.includes(col.name)}
                          onChange={() => handleToggleCollection(col.name)}
                          className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                        />
                        {col.name}
                        <span className="text-slate-500">({col.collection_name})</span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
            <Button type="submit" isLoading={createMutation.isPending}>
              Create knowledge base
            </Button>
          </form>
        </Card>
      )}

      {list.length === 0 ? (
        <EmptyState
          title="No knowledge bases"
          description={`Create a knowledge base cluster from your indexed ${INDEX_PROFILE_PLURAL.toLowerCase()}.`}
          action={<Button onClick={() => setShowForm(true)}>Create knowledge base</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((kb) => <KbCard key={kb.id} base={kb} />)}
        </div>
      )}
    </div>
  )
}

function KbCard({ base }: { base: KnowledgeBase }) {
  const aggregated = Array.from(
    new Set(base.sources.flatMap((s) => s.enabled_indexes ?? [])),
  ).sort()

  return (
    <Card elevated className="flex flex-col">
      <div className="flex items-start gap-2">
        <BookOpen className="size-5 text-indigo-400 shrink-0" aria-hidden="true" />
        <CardTitle className="text-base">{base.name}</CardTitle>
      </div>
      <CardDescription className="mt-2 line-clamp-2">
        {base.description || 'Knowledge cluster'}
      </CardDescription>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">{base.sources.length} profiles</Badge>
        {base.sources.slice(0, 3).map((s) => (
          <Badge key={s.source_name} variant="outline">{s.source_name}</Badge>
        ))}
      </div>
      {aggregated.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs text-slate-500">Indexes in cluster</p>
          <AggregatedIndexBadges indexes={aggregated} />
        </div>
      )}
      <div className="mt-4">
        <Link to={`/knowledge-bases/${encodeURIComponent(base.name)}`}>
          <Button variant="secondary" className="w-full" size="sm">
            Manage cluster
          </Button>
        </Link>
      </div>
    </Card>
  )
}
