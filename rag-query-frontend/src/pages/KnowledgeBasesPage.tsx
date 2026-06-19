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
import type { KnowledgeBase } from '@/types/api'

export function KnowledgeBasesPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const bases = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: async () => {
      const res = await api.knowledgeBases()
      return res.knowledge_bases
    },
  })

  const sources = useQuery({
    queryKey: ['knowledge-sources'],
    queryFn: async () => {
      const res = await api.knowledgeSources()
      return res.sources
    },
  })

  const createMutation = useMutation({
    mutationFn: api.createKnowledgeBase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setShowForm(false)
      setName('')
      setDescription('')
      setSelectedSources([])
      setError(null)
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Create failed')
    },
  })

  const handleToggleSource = (sourceName: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceName)
        ? prev.filter((s) => s !== sourceName)
        : [...prev, sourceName],
    )
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    createMutation.mutate({
      name: name.trim(),
      description,
      source_names: selectedSources,
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
          <p className="mt-1 text-sm text-slate-400">
            Group multiple knowledge sources for multi-collection retrieval (:8082).
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
              Select one or more sources to search together at query time.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="kb-name">Name *</Label>
              <Input
                id="kb-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="finance-kb"
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
              <Label>Sources</Label>
              {(sources.data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">
                  No sources yet.{' '}
                  <Link to="/sources" className="text-indigo-400 hover:underline">
                    Create a source
                  </Link>
                </p>
              ) : (
                <ul className="space-y-2 rounded-lg border border-slate-700/60 p-3">
                  {sources.data?.map((s) => (
                    <li key={s.id}>
                      <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedSources.includes(s.name)}
                          onChange={() => handleToggleSource(s.name)}
                          className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                        />
                        {s.name}
                        <span className="text-slate-500">({s.collection_name})</span>
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
          description="Create a knowledge base to combine multiple indexed sources."
          action={
            <Button onClick={() => setShowForm(true)}>Create knowledge base</Button>
          }
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
  return (
    <Card elevated className="flex flex-col">
      <div className="flex items-start gap-2">
        <BookOpen className="size-5 text-indigo-400 shrink-0" aria-hidden="true" />
        <CardTitle className="text-base">{base.name}</CardTitle>
      </div>
      <CardDescription className="mt-2 line-clamp-2">
        {base.description || 'No description'}
      </CardDescription>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">{base.sources.length} sources</Badge>
        {base.sources.slice(0, 3).map((s) => (
          <Badge key={s.source_name} variant="outline">{s.source_name}</Badge>
        ))}
        {base.sources.length > 3 && (
          <Badge variant="outline">+{base.sources.length - 3}</Badge>
        )}
      </div>
      <div className="mt-4">
        <Link to={`/knowledge-bases/${encodeURIComponent(base.name)}`}>
          <Button variant="secondary" className="w-full" size="sm">
            Manage sources
          </Button>
        </Link>
      </div>
    </Card>
  )
}
