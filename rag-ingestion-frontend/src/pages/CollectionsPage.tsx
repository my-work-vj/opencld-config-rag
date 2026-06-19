import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Plus } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, Spinner } from '@/components/ui/Feedback'
import { RagStagesEditor, resolveStageMaps } from '@/components/RagStagesEditor'
import {
  DEFAULT_CHAT_MODEL,
  DEFAULT_EMBEDDING_MODEL,
  DEFAULT_INGESTION_STAGES,
  DEFAULT_QUERY_STAGES,
  DEFAULT_RERANKER_MODEL,
} from '@/lib/stage-defaults'
import type { KnowledgeSource } from '@/types/api'

export function CollectionsPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState(DEFAULT_EMBEDDING_MODEL)
  const [chatModel, setChatModel] = useState(DEFAULT_CHAT_MODEL)
  const [rerankerModel, setRerankerModel] = useState(DEFAULT_RERANKER_MODEL)
  const [vectorSize, setVectorSize] = useState(2048)
  const [selectedDataConnectorIds, setSelectedDataConnectorIds] = useState<string[]>([])
  const [stageStrategies, setStageStrategies] = useState<Record<string, string>>({})
  const [stageConfigs, setStageConfigs] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  const collections = useQuery({
    queryKey: ['vector-collections'],
    queryFn: async () => (await api.vectorCollections()).collections,
  })

  const strategies = useQuery({
    queryKey: ['strategies'],
    queryFn: api.strategies,
  })

  const dataSources = useQuery({
    queryKey: ['data-sources'],
    queryFn: async () => (await api.dataSources()).data_sources,
  })

  const resolvedStages = useMemo(
    () =>
      resolveStageMaps(
        DEFAULT_INGESTION_STAGES,
        DEFAULT_QUERY_STAGES,
        stageStrategies,
        stageConfigs,
        { embeddingModel, vectorSize, chatModel, rerankerModel },
      ),
    [stageStrategies, stageConfigs, embeddingModel, vectorSize, chatModel, rerankerModel],
  )

  const createMutation = useMutation({
    mutationFn: api.createVectorCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vector-collections'] })
      setShowForm(false)
      setName('')
      setDescription('')
      setSelectedDataConnectorIds([])
      setStageStrategies({})
      setStageConfigs({})
      setError(null)
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Create failed')
    },
  })

  const handleToggleDataSource = (connectorId: string) => {
    setSelectedDataConnectorIds((prev) =>
      prev.includes(connectorId)
        ? prev.filter((id) => id !== connectorId)
        : [...prev, connectorId],
    )
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (selectedDataConnectorIds.length === 0) {
      setError('Select at least one data source')
      return
    }
    createMutation.mutate({
      name: name.trim(),
      description,
      embedding_model: embeddingModel,
      vector_size: vectorSize,
      chat_model: chatModel,
      reranker_model: rerankerModel,
      data_connector_ids: selectedDataConnectorIds,
      stages: Object.fromEntries(
        Object.entries(resolvedStages.ingestion).map(([s, cfg]) => [s, cfg]),
      ),
      query_stages: Object.fromEntries(
        Object.entries(resolvedStages.query).map(([s, cfg]) => [s, cfg]),
      ),
    })
  }

  if (collections.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  const list = collections.data ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Collections</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Configure ingestion and query stages, link data sources, and build a monitored Qdrant
            collection end to end.
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} variant="secondary">
          <Plus className="size-4" aria-hidden="true" />
          New collection
        </Button>
      </div>

      {showForm && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Create vector collection</CardTitle>
            <CardDescription>
              Select strategies for every stage from ingestion through querying.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleCreate} className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="col-name">Name *</Label>
                <Input
                  id="col-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="finance-docs"
                  required
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label>Data sources *</Label>
                {(dataSources.data ?? []).length === 0 ? (
                  <p className="text-xs text-slate-500">
                    <Link to="/data-sources" className="text-indigo-400 hover:underline">
                      Add a data source
                    </Link>{' '}
                    before creating a collection.
                  </p>
                ) : (
                  <ul className="max-h-40 space-y-2 overflow-y-auto rounded-lg border border-slate-700/60 p-3">
                    {(dataSources.data ?? []).map((d) => (
                      <li key={d.id}>
                        <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                          <input
                            type="checkbox"
                            checked={selectedDataConnectorIds.includes(d.id)}
                            onChange={() => handleToggleDataSource(d.id)}
                            className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                          />
                          <span className="truncate">{d.name}</span>
                          <span className="text-xs text-slate-500">({d.file_count} files)</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="col-desc">Description</Label>
              <Textarea
                id="col-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label htmlFor="col-embed">Embedding model</Label>
                <Input
                  id="col-embed"
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="col-chat">Chat model</Label>
                <Input
                  id="col-chat"
                  value={chatModel}
                  onChange={(e) => setChatModel(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="col-rerank">Reranker model</Label>
                <Input
                  id="col-rerank"
                  value={rerankerModel}
                  onChange={(e) => setRerankerModel(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="col-dim">Vector size</Label>
                <Input
                  id="col-dim"
                  type="number"
                  min={128}
                  max={8192}
                  value={vectorSize}
                  onChange={(e) => setVectorSize(Number(e.target.value))}
                />
              </div>
            </div>
            <RagStagesEditor
              strategies={strategies.data ?? {}}
              ingestionStages={resolvedStages.ingestion}
              queryStages={resolvedStages.query}
              stageOverrides={stageStrategies}
              configOverrides={stageConfigs}
              onStrategyChange={(stage, strategy) =>
                setStageStrategies((s) => ({ ...s, [stage]: strategy }))
              }
              onConfigChange={(stage, configJson) =>
                setStageConfigs((c) => ({ ...c, [stage]: configJson }))
              }
            />
            {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
            <Button type="submit" isLoading={createMutation.isPending}>
              Create collection
            </Button>
          </form>
        </Card>
      )}

      {list.length === 0 ? (
        <EmptyState
          title="No collections"
          description="Create a collection with full ingestion and query stage configuration."
          action={<Button onClick={() => setShowForm(true)}>Create collection</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((c) => <CollectionCard key={c.id} collection={c} />)}
        </div>
      )}
    </div>
  )
}

function CollectionCard({ collection }: { collection: KnowledgeSource }) {
  return (
    <Card elevated className="flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Database className="size-5 text-indigo-400 shrink-0" aria-hidden="true" />
          <CardTitle className="text-base">{collection.name}</CardTitle>
        </div>
        <Badge variant={collection.status === 'ready' ? 'success' : 'warning'}>
          {collection.status}
        </Badge>
      </div>
      <CardDescription className="mt-2 line-clamp-2">
        {collection.description || collection.collection_name}
      </CardDescription>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">{collection.embedding_model}</Badge>
        <Badge variant="outline">{collection.document_count} docs</Badge>
        <Badge variant="outline">{collection.chunk_count} chunks</Badge>
        {collection.monitor_enabled && (
          <Badge variant="outline">monitored</Badge>
        )}
      </div>
      <div className="mt-4">
        <Link to={`/collections/${encodeURIComponent(collection.name)}`}>
          <Button variant="secondary" className="w-full" size="sm">
            Open collection
          </Button>
        </Link>
      </div>
    </Card>
  )
}
