import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Cloud, Database, Eye, GitBranch, MemoryStick, Settings2, Table, Trash2, Upload, Waves } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { AUTO_SYNC_POLL_MS, syncPollInterval } from '@/lib/poll'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Select } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'
import RagStagesEditor, { resolveStageMaps, type IngestionMode } from '@/components/RagStagesEditor'
import {
  DEFAULT_EMBEDDING_MODEL,
  DEFAULT_INGESTION_STAGES,
} from '@/lib/stage-defaults'
import { stringifyStageConfig } from '@/components/StageConfigEditor'
import { FloatingModal } from '@/components/visualization/FloatingModal'
import { GraphVisualization } from '@/components/visualization/GraphVisualization'
import {
  MemoryVisualization,
  MetadataVisualization,
  SparseVisualization,
  VectorVisualization,
} from '@/components/visualization/IndexVisualizations'

export function CollectionDetailPage() {
  const { name } = useParams<{ name: string }>()
  const decodedName = decodeURIComponent(name ?? '')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedConnectorId, setSelectedConnectorId] = useState('')
  const [pickedFiles, setPickedFiles] = useState<File[]>([])
  const [uploadResult, setUploadResult] = useState<string | null>(null)
  const [editingStages, setEditingStages] = useState(false)
  const [stageSaveMessage, setStageSaveMessage] = useState<string | null>(null)
  const [embeddingModel, setEmbeddingModel] = useState(DEFAULT_EMBEDDING_MODEL)
  const [stageStrategies, setStageStrategies] = useState<Record<string, string>>({})
  const [stageConfigs, setStageConfigs] = useState<Record<string, string>>({})
  const [ingestionMode, setIngestionMode] = useState<IngestionMode>('document_plain')
  const [vizModal, setVizModal] = useState<string | null>(null)
  const [vizError, setVizError] = useState<string | null>(null)

  const llmModels = useQuery({
    queryKey: ['llm-models'],
    queryFn: api.llmModels,
    refetchInterval: 60_000,
  })

  const strategies = useQuery({
    queryKey: ['strategies'],
    queryFn: api.strategies,
  })

  const collection = useQuery({
    queryKey: ['vector-collection', decodedName],
    queryFn: () => api.vectorCollection(decodedName),
    enabled: Boolean(decodedName),
    refetchInterval: (q: { state: { data: { status: string } | undefined } }) =>
      syncPollInterval(q.state.data?.status),
  })

  const documents = useQuery({
    queryKey: ['collection-docs', decodedName],
    queryFn: async () => (await api.collectionDocuments(decodedName)).documents,
    enabled: Boolean(decodedName),
    refetchInterval: syncPollInterval(collection.data?.status),
  })

  const dataSources = useQuery({
    queryKey: ['data-sources'],
    queryFn: async () => (await api.dataSources()).data_sources,
    refetchInterval: AUTO_SYNC_POLL_MS,
  })

  const connectorIds = collection.data?.data_connector_ids ?? []
  const legacyConnectorId = collection.data?.data_connector_id
  const linkedConnectorIds = useMemo(() => {
    const ids = [...connectorIds]
    if (legacyConnectorId && !ids.includes(legacyConnectorId)) {
      ids.unshift(legacyConnectorId)
    }
    return ids
  }, [connectorIds, legacyConnectorId])

  const linkedDataSources = useMemo(
    () => (dataSources.data ?? []).filter((d) => linkedConnectorIds.includes(d.id)),
    [dataSources.data, linkedConnectorIds],
  )

  const uploadableDataSources = useMemo(
    () => linkedDataSources.filter((ds) => ds.supports_ui_upload !== false),
    [linkedDataSources],
  )

  const driveOnlyDataSources = useMemo(
    () => linkedDataSources.filter((ds) => ds.supports_ui_upload === false),
    [linkedDataSources],
  )

  const uploadMutation = useMutation({
    mutationFn: () => api.uploadDataSourceFiles(selectedConnectorId, pickedFiles),
    onSuccess: (data) => {
      const warn =
        data.errors.length > 0
          ? ` Note: ${data.errors[0]}`
          : ''
      setUploadResult(
        `Uploaded ${data.files_uploaded} file(s). Indexing ${data.collections_synced.length} collection(s)…${warn}`,
      )
      setPickedFiles([])
      if (fileInputRef.current) fileInputRef.current.value = ''
      queryClient.invalidateQueries({ queryKey: ['vector-collection', decodedName] })
      queryClient.invalidateQueries({ queryKey: ['collection-docs', decodedName] })
      queryClient.invalidateQueries({ queryKey: ['vector-collections'] })
      queryClient.invalidateQueries({ queryKey: ['data-sources'] })
    },
    onError: (err) => {
      setUploadResult(err instanceof ApiError ? err.message : 'Upload failed')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteVectorCollection(decodedName),
    onSuccess: () => navigate('/collections'),
  })

  const updateStagesMutation = useMutation({
    mutationFn: (body: Parameters<typeof api.updateVectorCollection>[1]) =>
      api.updateVectorCollection(decodedName, body),
    onSuccess: () => {
      setStageSaveMessage('Stage configuration saved')
      setEditingStages(false)
      queryClient.invalidateQueries({ queryKey: ['vector-collection', decodedName] })
    },
    onError: (err) => {
      setStageSaveMessage(err instanceof ApiError ? err.message : 'Save failed')
    },
  })

  const c = collection.data
  const ingestionStages = c?.ingestion_stages ?? DEFAULT_INGESTION_STAGES

  useEffect(() => {
    if (!c) return
    setEmbeddingModel(c.embedding_model || DEFAULT_EMBEDDING_MODEL)
    const strategiesMap: Record<string, string> = {}
    const configsMap: Record<string, string> = {}
    const allStages = {
      ...(c.ingestion_stages ?? DEFAULT_INGESTION_STAGES),
    }
    for (const [stage, cfg] of Object.entries(allStages)) {
      if (cfg?.strategy) strategiesMap[stage] = cfg.strategy
      if (cfg?.config) configsMap[stage] = stringifyStageConfig(cfg.config)
    }
    setStageStrategies(strategiesMap)
    setStageConfigs(configsMap)
  }, [c?.name, c?.embedding_model])

  const resolvedStages = useMemo(
    () =>
      resolveStageMaps(
        ingestionStages,
        stageStrategies,
        stageConfigs,
        { embeddingModel },
      ),
    [
      ingestionStages,
      stageStrategies,
      stageConfigs,
      embeddingModel,
    ],
  )

  // ── Viz query — fetches from whichever endpoint the modal needs ──
  const vizQuery = useQuery({
    queryKey: ['collection-viz', decodedName, vizModal],
    queryFn: async () => {
      setVizError(null)
      switch (vizModal) {
        case 'graph':
          return { kind: 'graph' as const, data: await api.visualizeGraph(decodedName) }
        case 'vector':
          return { kind: 'vector' as const, data: await api.visualizeVectors(decodedName) }
        case 'sparse':
          return { kind: 'sparse' as const, data: await api.visualizeSparse(decodedName) }
        case 'metadata':
          return { kind: 'metadata' as const, data: await api.visualizeMetadata(decodedName) }
        case 'memory':
          return { kind: 'memory' as const, data: await api.visualizeMemory(decodedName) }
        default:
          throw new Error(`Unknown viz type: ${vizModal}`)
      }
    },
    enabled: Boolean(vizModal),
    retry: 1,
    staleTime: 30_000,
  })

  const handleCloseViz = () => {
    setVizModal(null)
    setVizError(null)
  }

  const vizTitle =
    vizModal === 'graph' ? 'Graph Visualization' :
    vizModal === 'vector' ? 'Dense Vector Index' :
    vizModal === 'sparse' ? 'Sparse Vector Index' :
    vizModal === 'metadata' ? 'Metadata Index' :
    vizModal === 'memory' ? 'Memory Store' : 'Index Visualization'

  if (collection.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  if (collection.isError || !collection.data) {
    return (
      <div className="space-y-4 text-center py-20">
        <p className="text-red-400">Collection not found: {decodedName}</p>
        <Link to="/collections">
          <Button variant="secondary">Back to collections</Button>
        </Link>
      </div>
    )
  }

  if (!c) {
    return null
  }

  const docList = documents.data ?? []
  const activeConnectorId = selectedConnectorId || uploadableDataSources[0]?.id || ''
  const hasDriveOnlySources =
    linkedDataSources.length > 0 && uploadableDataSources.length === 0

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    setPickedFiles(files)
    setUploadResult(null)
  }

  const handleSaveStages = () => {
    updateStagesMutation.mutate({
      embedding_model: embeddingModel,
      stages: Object.fromEntries(
        Object.entries(resolvedStages.ingestion).map(([s, cfg]) => [s, cfg]),
      ),
    })
  }

  const handleUpload = () => {
    if (!activeConnectorId) {
      setUploadResult('Select a data source')
      return
    }
    if (pickedFiles.length === 0) {
      setUploadResult('Choose at least one file')
      return
    }
    uploadMutation.mutate()
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link
          to="/collections"
          className="flex min-h-11 min-w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800/80 hover:text-white"
          aria-label="Back to collections"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <div className="flex items-center gap-3">
          <Database className="size-7 text-indigo-400" aria-hidden="true" />
          <div>
            <h1 className="text-2xl font-bold text-white">{c.name}</h1>
            <p className="font-mono text-sm text-indigo-300">{c.collection_name}</p>
          </div>
        </div>
        <Badge variant={c.status === 'ready' ? 'success' : 'outline'}>{c.status}</Badge>
        {c.monitor_enabled && <Badge variant="outline">auto-sync</Badge>}
        <Button
          variant="danger"
          size="sm"
          onClick={() => deleteMutation.mutate()}
          isLoading={deleteMutation.isPending}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>

      <p className="text-sm text-slate-400">{c.description}</p>

      <div className="grid gap-3 sm:grid-cols-3 text-sm">
        <Stat label="Embedding" value={c.embedding_model || '—'} />
        <Stat label="Documents" value={String(c.document_count)} />
        <Stat label="Chunks" value={String(c.chunk_count)} />
      </div>

      <Card elevated>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Settings2 className="size-5 text-indigo-400" aria-hidden="true" />
                Ingestion stage configuration
              </CardTitle>
              <CardDescription>
                Configure the document source type and chunking strategy. Embedding is handled
                automatically via LiteLLM.
              </CardDescription>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setEditingStages((v) => !v)}
            >
              {editingStages ? 'Cancel' : 'Edit stages'}
            </Button>
          </div>
        </CardHeader>
        {editingStages ? (
          <div className="space-y-6">
            <RagStagesEditor
              baseStages={ingestionStages}
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
            <Button onClick={handleSaveStages} isLoading={updateStagesMutation.isPending}>
              Save configuration
            </Button>
            {stageSaveMessage && (
              <p className="text-sm text-slate-400" role="status">{stageSaveMessage}</p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {Object.entries(ingestionStages).map(([stage, cfg]) => (
                <Badge key={`ing-${stage}`} variant="outline">
                  {stage}: {cfg.strategy}
                </Badge>
              ))}
            </div>
            {/* ── Index Visualization Buttons ── */}
            {c?.metadata?.index_config && (
              <div className="mt-4 border-t border-slate-700 pt-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Index visualizations
                </p>
                <div className="flex flex-wrap gap-2">
                  {c.metadata.index_config.graph && (
                    <button
                      onClick={() => setVizModal('graph')}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-700 bg-cyan-900/30 px-3 py-1.5 text-xs font-medium text-cyan-300 transition-colors hover:bg-cyan-800/50 hover:text-cyan-200"
                    >
                      <GitBranch className="size-3.5" />
                      Graph
                    </button>
                  )}
                  {c.metadata.index_config.vector && (
                    <button
                      onClick={() => setVizModal('vector')}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-blue-700 bg-blue-900/30 px-3 py-1.5 text-xs font-medium text-blue-300 transition-colors hover:bg-blue-800/50 hover:text-blue-200"
                    >
                      <Waves className="size-3.5" />
                      Dense Vectors
                    </button>
                  )}
                  {c.metadata.index_config.sparse && (
                    <button
                      onClick={() => setVizModal('sparse')}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-violet-700 bg-violet-900/30 px-3 py-1.5 text-xs font-medium text-violet-300 transition-colors hover:bg-violet-800/50 hover:text-violet-200"
                    >
                      <Waves className="size-3.5" />
                      Sparse Vectors
                    </button>
                  )}
                  {c.metadata.index_config.metadata && (
                    <button
                      onClick={() => setVizModal('metadata')}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-700 bg-emerald-900/30 px-3 py-1.5 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-800/50 hover:text-emerald-200"
                    >
                      <Table className="size-3.5" />
                      Metadata
                    </button>
                  )}
                  {c.metadata.index_config.memory && (
                    <button
                      onClick={() => setVizModal('memory')}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-amber-700 bg-amber-900/30 px-3 py-1.5 text-xs font-medium text-amber-300 transition-colors hover:bg-amber-800/50 hover:text-amber-200"
                    >
                      <MemoryStick className="size-3.5" />
                      Memory
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {linkedDataSources.length > 0 && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Linked data sources</CardTitle>
            <CardDescription>
              Monitored continuously — remote changes are synced and indexed automatically.
            </CardDescription>
          </CardHeader>
          <ul className="flex flex-wrap gap-2">
            {linkedDataSources.map((ds) => (
              <li key={ds.id}>
                <Link to={`/data-sources/${ds.id}`}>
                  <Badge variant="outline" className="hover:border-indigo-400">
                    {ds.name} ({ds.file_count} files)
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {hasDriveOnlySources && (
        <Card elevated>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cloud className="size-5 text-indigo-400" aria-hidden="true" />
              Google Drive sync
            </CardTitle>
            <CardDescription>
              Upload, update, or delete files directly in the linked Google Drive folder. Changes
              are detected automatically and indexed into this collection.
            </CardDescription>
          </CardHeader>
          <ul className="flex flex-wrap gap-2">
            {driveOnlyDataSources.map((ds) => (
              <li key={ds.id}>
                <Link to={`/data-sources/${ds.id}`}>
                  <Badge variant="outline" className="hover:border-indigo-400">
                    {ds.name}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {uploadableDataSources.length > 0 && (
      <Card elevated>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="size-5 text-indigo-400" aria-hidden="true" />
            Upload documents
          </CardTitle>
          <CardDescription>
            Upload files to a linked data source. The connector and collection update automatically.
          </CardDescription>
        </CardHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="upload-connector">Data source</Label>
              <Select
                id="upload-connector"
                value={activeConnectorId}
                onChange={(e) => setSelectedConnectorId(e.target.value)}
              >
                {uploadableDataSources.map((ds) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name} ({ds.connector_type})
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="upload-files">Files</Label>
              <input
                ref={fileInputRef}
                id="upload-files"
                type="file"
                multiple
                accept=".pdf,.txt,.md,.html,.htm,.doc,.docx,.csv"
                onChange={handleFileChange}
                className="block w-full text-sm text-slate-400 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-500"
              />
              {pickedFiles.length > 0 && (
                <p className="text-xs text-slate-500">
                  {pickedFiles.length} file(s) selected:{' '}
                  {pickedFiles.map((f) => f.name).join(', ')}
                </p>
              )}
            </div>
            <Button
              onClick={handleUpload}
              isLoading={uploadMutation.isPending}
              disabled={pickedFiles.length === 0}
            >
              Upload &amp; index
            </Button>
            {uploadResult && (
              <p className="text-sm text-slate-400" role="status">{uploadResult}</p>
            )}
          </div>
      </Card>
      )}

      {linkedDataSources.length === 0 && (
      <Card elevated>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="size-5 text-indigo-400" aria-hidden="true" />
            Upload documents
          </CardTitle>
        </CardHeader>
          <p className="text-sm text-slate-500">
            No linked data sources.{' '}
            <Link to="/data-sources" className="text-indigo-400 hover:underline">
              Create a data source
            </Link>{' '}
            and link it when creating this collection.
          </p>
      </Card>
      )}

      <Card elevated>
        <CardHeader>
          <CardTitle>Indexed documents</CardTitle>
          <CardDescription>
            {docList.length} indexed · collection reports {c.document_count} docs / {c.chunk_count}{' '}
            chunks
          </CardDescription>
        </CardHeader>
        {documents.isLoading ? (
          <Spinner className="mx-auto" />
        ) : docList.length === 0 ? (
          <p className="text-sm text-slate-500">
            {hasDriveOnlySources
              ? 'No documents indexed yet. Add files to the linked Google Drive folder — indexing runs automatically.'
              : 'No documents indexed yet. Upload files or add them to a linked data source — indexing runs automatically.'}
          </p>
        ) : (
          <ul className="space-y-2">
            {docList.map((doc) => (
              <li
                key={doc.id}
                className="rounded-lg border border-slate-700/60 bg-slate-800/40 px-3 py-2 text-sm"
              >
                <span className="font-medium text-slate-200">{doc.filename}</span>
                <span className="ml-2 text-slate-500">{doc.chunk_count} chunks</span>
                {doc.indexed_at && (
                  <span className="ml-2 text-xs text-slate-600">
                    {new Date(doc.indexed_at).toLocaleString()}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── Index Visualization Floating Modal ── */}
      <FloatingModal isOpen={Boolean(vizModal)} onClose={handleCloseViz} title={vizTitle}>
        {vizQuery.isLoading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}
        {vizQuery.isError && (
          <div className="py-8 text-center">
            <p className="text-red-400">Failed to load visualization data</p>
            <p className="mt-1 text-sm text-slate-500">{(vizQuery.error as Error)?.message}</p>
          </div>
        )}
        {vizQuery.data?.kind === 'graph' && (
          <GraphVisualization data={vizQuery.data.data as any} />
        )}
        {vizQuery.data?.kind === 'vector' && (
          <VectorVisualization data={vizQuery.data.data as any} />
        )}
        {vizQuery.data?.kind === 'sparse' && (
          <SparseVisualization data={vizQuery.data.data as any} />
        )}
        {vizQuery.data?.kind === 'metadata' && (
          <MetadataVisualization data={vizQuery.data.data as any} />
        )}
        {vizQuery.data?.kind === 'memory' && (
          <MemoryVisualization data={vizQuery.data.data as any} />
        )}
      </FloatingModal>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-800/50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm font-medium text-slate-200">{value}</p>
    </div>
  )
}
