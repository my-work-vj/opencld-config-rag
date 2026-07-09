import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, Spinner } from '@/components/ui/Feedback'
import RagStagesEditor, { IngestionModePicker, resolveStageMaps, type IngestionMode } from '@/components/RagStagesEditor'
import { IndexConfigEditor, IndexConfigBadges, DEFAULT_INDEX_CONFIG } from '@/components/IndexConfigEditor'
import type { IndexConfig } from '@/types/api'
import { 
  DEFAULT_EMBEDDING_MODEL,
  DEFAULT_INGESTION_STAGES,
} from '@/lib/stage-defaults'
import type { KnowledgeSource } from '@/types/api'
import {
  INDEX_PROFILE_PLURAL,
  INDEX_PROFILE_SINGULAR,
  indexProfilePath,
} from '@/lib/terminology'

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
  const [indexConfig, setIndexConfig] = useState<IndexConfig>(DEFAULT_INDEX_CONFIG)
  const [showAdvanced, setShowAdvanced] = useState(false)
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
      setIndexConfig(DEFAULT_INDEX_CONFIG)
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
      metadata: {
        index_config: indexConfig,
        ingestion_mode: ingestionMode,
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
          <h1 className="text-2xl font-bold tracking-tight text-white">{INDEX_PROFILE_PLURAL}</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Organize data sources into separate indexed stores. Each profile links one or more
            sources, runs the ingestion pipeline, and builds only the index types you enable
            (vector, sparse, graph, metadata, memory).
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} variant="secondary">
          <Plus className="size-4" aria-hidden="true" />
          New {INDEX_PROFILE_SINGULAR.toLowerCase()}
        </Button>
      </div>

      {showForm && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Create {INDEX_PROFILE_SINGULAR.toLowerCase()}</CardTitle>
            <CardDescription>
              Link data sources and choose which index types to build. Ingestion runs
              automatically and stays in sync when connector files change.
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
                    before creating an index profile.
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

            <IndexConfigEditor value={indexConfig} onChange={setIndexConfig} />

            <IngestionModePicker
              ingestionMode={ingestionMode}
              onChangeIngestionMode={setIngestionMode}
            />

            <div className="rounded-lg border border-slate-700/60">
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium text-slate-200 hover:bg-slate-800/50"
              >
                {showAdvanced ? (
                  <ChevronDown className="size-4 text-slate-400" aria-hidden="true" />
                ) : (
                  <ChevronRight className="size-4 text-slate-400" aria-hidden="true" />
                )}
                Advanced pipeline settings
                <span className="ml-auto text-xs font-normal text-slate-500">
                  embedding model, chunking overrides
                </span>
              </button>
              {showAdvanced && (
                <div className="border-t border-slate-700/60 p-4">
                  <RagStagesEditor
                    advancedOnly
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
                </div>
              )}
            </div>

            {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
            <Button type="submit" isLoading={createMutation.isPending}>
              Create {INDEX_PROFILE_SINGULAR.toLowerCase()}
            </Button>
          </form>
        </Card>
      )}

      {list.length === 0 ? (
        <EmptyState
          title={`No ${INDEX_PROFILE_PLURAL.toLowerCase()}`}
          description="Create an index profile to ingest selected data sources into your chosen index types."
          action={
            <Button onClick={() => setShowForm(true)}>
              Create {INDEX_PROFILE_SINGULAR.toLowerCase()}
            </Button>
          }
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
        <IndexConfigBadges config={collection.metadata?.index_config} />
      </div>
      <div className="mt-4">
        <Link to={indexProfilePath(collection.name)}>
          <Button variant="secondary" className="w-full" size="sm">
            Open profile
          </Button>
        </Link>
      </div>
    </Card>
  )
}