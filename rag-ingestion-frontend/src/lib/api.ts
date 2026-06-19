import { API_BASE } from '@/lib/env'

import type {

  CollectionListResponse,

  ConnectorFileListResponse,

  ConnectorType,

  CreateCollectionRequest,

  CreateDataConnectorInput,

  CreateKnowledgeBaseRequest,

  DataConnector,

  DataConnectorListResponse,

  DataConnectorSyncResponse,
  DataConnectorTestResponse,
  DataConnectorUploadResponse,
  IndexedDocumentListResponse,

  HealthResponse,

  PathwayDockerHealth,

  IngestRequest,

  IngestResponse,

  KnowledgeBase,

  KnowledgeBaseListResponse,

  KnowledgeSource,

  KnowledgeSourceIngestRequest,

  KnowledgeSourceIngestResponse,

  QdrantCollectionInfo,

  StrategiesMap,

  UpdateCollectionRequest,
} from '@/types/api'



class ApiError extends Error {

  status: number



  constructor(status: number, message: string) {

    super(message)

    this.status = status

  }

}



async function request<T>(path: string, init?: RequestInit): Promise<T> {

  const response = await fetch(`${API_BASE}${path}`, {

    ...init,

    headers: {

      'Content-Type': 'application/json',

      ...init?.headers,

    },

  })



  if (!response.ok) {

    let detail = response.statusText

    try {

      const body = await response.json()

      detail = body.detail ?? JSON.stringify(body)

    } catch {

      /* ignore */

    }

    throw new ApiError(response.status, String(detail))

  }



  if (response.status === 204) {

    return undefined as T

  }



  return response.json() as Promise<T>

}



export const api = {

  health: () => request<HealthResponse>('/health'),

  pathwayDockerHealth: () => request<PathwayDockerHealth>('/connectors/pathway/health'),

  startPathwayDocker: () =>
    request<PathwayDockerHealth>('/connectors/pathway/start', { method: 'POST' }),

  strategies: () => request<StrategiesMap>('/strategies'),

  qdrantCollections: () => request<QdrantCollectionInfo[]>('/qdrant/collections'),

  vectorCollections: () => request<CollectionListResponse>('/collections'),

  vectorCollection: (name: string) =>

    request<KnowledgeSource>(`/collections/${encodeURIComponent(name)}`),

  createVectorCollection: (body: CreateCollectionRequest) =>

    request<KnowledgeSource>('/collections', {

      method: 'POST',

      body: JSON.stringify(body),

    }),

  updateVectorCollection: (name: string, body: UpdateCollectionRequest) =>
    request<KnowledgeSource>(`/collections/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  syncVectorCollection: (name: string) =>
    request<Record<string, unknown>>(
      `/collections/${encodeURIComponent(name)}/sync`,
      { method: 'POST' },
    ),

  collectionMonitorStatus: () =>
    request<{
      running: boolean
      interval_sec: number | null
      last_run_at: string | null
      last_results: Record<string, unknown>[]
    }>('/collections/monitor/status'),

  deleteVectorCollection: (name: string, deleteVectors = false) =>

    request<void>(

      `/collections/${encodeURIComponent(name)}?delete_collection_vectors=${deleteVectors}`,

      { method: 'DELETE' },

    ),

  ingestCollectionFromConnector: (name: string, fileIds: string[] = []) =>

    request<{

      status: string

      files_processed: number

      document_count: number

      chunk_count: number

      errors: string[]

    }>(`/collections/${encodeURIComponent(name)}/ingest-from-connector`, {

      method: 'POST',

      body: JSON.stringify({ file_ids: fileIds }),

    }),

  ingestKnowledgeSource: (name: string, body: KnowledgeSourceIngestRequest) =>

    request<KnowledgeSourceIngestResponse>(

      `/knowledge-sources/${encodeURIComponent(name)}/ingest`,

      { method: 'POST', body: JSON.stringify(body) },

    ),

  collectionDocuments: (name: string) =>

    request<IndexedDocumentListResponse>(

      `/collections/${encodeURIComponent(name)}/documents`,

    ),

  uploadDataSourceFiles: async (connectorId: string, files: File[]) => {
    const form = new FormData()
    for (const file of files) {
      form.append('files', file)
    }
    const response = await fetch(
      `${API_BASE}/data-sources/${encodeURIComponent(connectorId)}/upload`,
      { method: 'POST', body: form },
    )
    if (!response.ok) {
      let detail = response.statusText
      try {
        const body = await response.json()
        detail = body.detail ?? JSON.stringify(body)
      } catch {
        /* ignore */
      }
      throw new ApiError(response.status, String(detail))
    }
    return response.json() as Promise<DataConnectorUploadResponse>
  },

  ingest: (body: IngestRequest) =>

    request<IngestResponse>('/ingest', {

      method: 'POST',

      body: JSON.stringify(body),

    }),

  knowledgeBases: () => request<KnowledgeBaseListResponse>('/knowledge-bases'),

  knowledgeBase: (name: string) =>

    request<KnowledgeBase>(`/knowledge-bases/${encodeURIComponent(name)}`),

  createKnowledgeBase: (body: CreateKnowledgeBaseRequest) =>

    request<KnowledgeBase>('/knowledge-bases', {

      method: 'POST',

      body: JSON.stringify(body),

    }),

  deleteKnowledgeBase: (name: string) =>

    request<void>(`/knowledge-bases/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  addKbCollection: (kbName: string, collectionName: string) =>

    request<KnowledgeBase>(

      `/knowledge-bases/${encodeURIComponent(kbName)}/collections/${encodeURIComponent(collectionName)}`,

      { method: 'POST' },

    ),

  removeKbCollection: (kbName: string, collectionName: string) =>

    request<KnowledgeBase>(

      `/knowledge-bases/${encodeURIComponent(kbName)}/collections/${encodeURIComponent(collectionName)}`,

      { method: 'DELETE' },

    ),

  connectorTypes: () =>

    request<{ types: ConnectorType[] }>('/connectors/types'),

  dataSources: () => request<DataConnectorListResponse>('/data-sources'),

  dataSource: (id: string) =>

    request<DataConnector>(`/data-sources/${encodeURIComponent(id)}`),

  dataSourceFiles: (id: string) =>

    request<ConnectorFileListResponse>(

      `/data-sources/${encodeURIComponent(id)}/files`,

    ),

  deleteDataSourceFile: (connectorId: string, fileId: string) =>

    request<void>(

      `/data-sources/${encodeURIComponent(connectorId)}/files/${encodeURIComponent(fileId)}`,

      { method: 'DELETE' },

    ),

  createDataSource: async (input: CreateDataConnectorInput) => {

    const form = new FormData()

    form.append('name', input.name)

    form.append('connector_type', input.connector_type)

    form.append('object_id', input.object_id)

    form.append('credentials', input.credentials)

    form.append('description', input.description ?? '')

    form.append('sync_mode', input.sync_mode ?? 'monitor')

    const response = await fetch(`${API_BASE}/data-sources`, {

      method: 'POST',

      body: form,

    })

    if (!response.ok) {

      let detail = response.statusText

      try {

        const body = await response.json()

        detail = body.detail ?? JSON.stringify(body)

      } catch {

        /* ignore */

      }

      throw new ApiError(response.status, String(detail))

    }

    return response.json() as Promise<DataConnector>

  },

  deleteDataSource: (id: string) =>

    request<void>(`/data-sources/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  testDataSource: (id: string) =>

    request<DataConnectorTestResponse>(

      `/data-sources/${encodeURIComponent(id)}/test`,

      { method: 'POST' },

    ),

  syncDataSource: (id: string) =>

    request<DataConnectorSyncResponse>(

      `/data-sources/${encodeURIComponent(id)}/sync`,

      { method: 'POST' },

    ),

}



export { ApiError }


