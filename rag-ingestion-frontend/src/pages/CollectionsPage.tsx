import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Plus } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea, Select } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, Spinner } from '@/components/ui/Feedback'
import RagStagesEditor, { resolveStageMaps, type IngestionMode } from '@/components/RagStagesEditor'
import { 
  DEFAULT_EMBEDDING_MODEL,
  DEFAULT_INGESTION_STAGES,
} from '@/lib/stage-defaults'
import type { KnowledgeSource } from '@/types/api'

export function CollectionsPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState(DEFAULT_EMBEDDING_MODEL)
  const [selectedDataConnectorIds, setSelectedDataConnectorIds] = useState<string[]>([])
  const [stageStrategies, setStageStrategies] = useState<Record<string, string>>({})
  const [stageConfigs, setStageConfigs] = useState<Record<string, string>>({})
  const [ingestionMode, setIngestionMode] = useState<IngestionMode>('document_plain')
  // NEW: Index configuration state
  const [enableVectorIndex, setEnableVectorIndex] = useState(true)
  const [enableSparseIndex, setEnableSparseIndex] = useState(false)
  const [enableGraphIndex, setEnableGraphIndex] = useState(false)
  const [enableMetadataIndex, setEnableMetadataIndex] = useState(true)
  const [enableMemoryIndex, setEnableMemoryIndex] = useState(false)
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

  const llmModels = useQuery({
    queryKey: ['llm-models'],
    queryFn: api.llmModels,
    refetchInterval: 60_000,
  })

  const resolvedStages = useMemo(
    () =>
      resolveStageMaps(
        DEFAULT_INGESTION_STAGES,
        stageStrategies,
        stageConfigs,
        { embeddingModel },
      ),
    [stageStrategies, stageConfigs, embeddingModel],
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
      setIngestionMode('document_plain')
      // Reset index config
      setEnableVectorIndex(true)
      setEnableSparseIndex(false)
      setEnableGraphIndex(false)
      setEnableMetadataIndex(true)
      setEnableMemoryIndex(false)
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
      data_connector_ids: selectedDataConnectorIds,
      stages: Object.fromEntries(
        Object.entries(resolvedStages.ingestion).map(([s, cfg]) => [s, cfg]),
      ),
      // NEW: Include index configuration in the metadata
      metadata: {
        index_config: {
          vector: enableVectorIndex,
          sparse: enableSparseIndex,
          graph: enableGraphIndex,
          metadata: enableMetadataIndex,
          memory: enableMemoryIndex,
        },
      },
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
            Configure ingestion stages, link data sources, and build a monitored Qdrant
            collection end to end. Now with configurable index types for flexible RAG strategies.
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
              Link one or more data sources and choose your embedding model and document source
              type. The ingestion pipeline handles chunking, embedding, and indexing automatically
              via LiteLLM. Configure which index types to enable for this collection.
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

            {/* NEW: Index Configuration Section */}
            <div className="border-t pt-4">
              <Label className="font-medium text-slate-300">Index Configuration</Label>
              <div className="grid gap-4 sm:grid-cols-3 mt-2">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="enable-vector"
                    checked={enableVectorIndex}
                    onChange={(e) => setEnableVectorIndex(e.target.checked)}
                    className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                  />
                  <span className="text-sm font-medium">Vector (Qdrant)</span>
                  <span className="text-xs text-slate-500">Dense embeddings</span>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="enable-sparse"
                    checked={enableSparseIndex}
                    onChange={(e) => setEnableSparseIndex(e.target.checked)}
                    className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                  />
                  <span className="text-sm font-medium">Sparse (BM25)</span>
                  <span className="text-xs text-slate-500">Keyword matching</span>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="enable-graph"
                    checked={enableGraphIndex}
                    onChange={(e) => setEnableGraphIndex(e.target.checked)}
                    className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                  />
                  <span className="text-sm font-medium">Graph (Neo4j)</span>
                  <span className="text-xs text-slate-500">Entity relationships</span>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="enable-metadata"
                    checked={enableMetadataIndex}
                    onChange={(e) => setEnableMetadataIndex(e.target.checked)}
                    className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                  />
                  <span className="text-sm font-medium">Metadata (PostgreSQL)</span>
                  <span className="text-xs text-slate-500">Document/chunk metadata</span>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="enable-memory"
                    checked={enableMemoryIndex}
                    onChange={(e) => setEnableMemoryIndex(e.target.checked)}
                    className="rounded border-slate-600 bg-slate-800 text-indigo-500"
                  />
                  <span className="text-sm font-medium">Memory (Redis)</span>
                  <span className="text-xs text-slate-500">Session context</span>
                </div>
              </div>
            </div>

            <RagStagesEditor
              baseStages={DEFAULT_INGESTION_STAGES}
              stageStrategies={stageStrategies}
              stageConfigs={stageConfigs}
              onChangeStrategies={setStageStrategies}
              onChangeConfigs={setStageConfigs}
              embeddingModel={embeddingModel}
              onChangeEmbeddingModel={setEmbeddingModel}
              llmModels={llmModels.data}
              ingestionMode={ingestionMode}
              onChangeIngestionMode={setIngestionMode}
              strategies={strategies.data}
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
          description="Create a collection with full ingestion stage configuration."
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
        {/* NEW: Show index configuration badge */}
        {collection.metadata?.index_config && (
          <>
            {collection.metadata.index_config.vector && <Badge variant="outline" className="mr-1">Vector</Badge>}
            {collection.metadata.index_config.sparse && <Badge variant="outline" className="mr-1" style={{ backgroundColor: '#8b5cf6' }}>Sparse</Badge>}
            {collection.metadata.index_config.graph && <Badge variant="outline" className="mr-1" style={{ backgroundColor: '#06b6d4' }}>Graph</Badge>}
            {collection.metadata.index_config.metadata && <Badge variant="outline" className="mr-1">Meta</Badge>}
            {collection.metadata.index_config.memory && <Badge variant="outline" className="mr-1" style={{ backgroundColor: '#f59e0b' }}>Memory</Badge>}
          </>
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