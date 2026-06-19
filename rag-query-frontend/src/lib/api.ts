import { API_BASE } from '@/lib/env'
import type {
  Agent,
  AgentListResponse,
  AgentQueryRequest,
  AgentQueryResponse,
  CompareResponse,
  CollectionInfo,
  CreateAgentRequest,
  CreateKnowledgeBaseRequest,
  CreatePromptTemplateRequest,
  CreatePromptVersionRequest,
  HealthResponse,
  KnowledgeBase,
  KnowledgeBaseListResponse,
  KnowledgeSourceListResponse,
  PromptTemplateDetail,
  PromptTemplateListResponse,
  QueryLog,
  QueryRequest,
  QueryResponse,
  StrategiesMap,
  UpdateAgentRequest,
  UpdateKnowledgeBaseRequest,
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
  strategies: () => request<StrategiesMap>('/strategies'),
  collections: () => request<CollectionInfo[]>('/collections'),
  query: (body: QueryRequest) =>
    request<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  compare: (body: {
    query: string
    pipelines: string[]
    collection_name?: string
    top_k?: number
  }) =>
    request<CompareResponse>('/compare', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  logs: (limit = 50, pipeline?: string) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (pipeline) params.set('pipeline', pipeline)
    return request<QueryLog[]>(`/logs?${params}`)
  },
  knowledgeSources: () =>
    request<KnowledgeSourceListResponse>('/knowledge-sources'),
  knowledgeBases: () => request<KnowledgeBaseListResponse>('/knowledge-bases'),
  knowledgeBase: (name: string) =>
    request<KnowledgeBase>(`/knowledge-bases/${encodeURIComponent(name)}`),
  createKnowledgeBase: (body: CreateKnowledgeBaseRequest) =>
    request<KnowledgeBase>('/knowledge-bases', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateKnowledgeBase: (name: string, body: UpdateKnowledgeBaseRequest) =>
    request<KnowledgeBase>(`/knowledge-bases/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  deleteKnowledgeBase: (name: string) =>
    request<void>(`/knowledge-bases/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
  addKbSource: (kbName: string, sourceName: string) =>
    request<KnowledgeBase>(
      `/knowledge-bases/${encodeURIComponent(kbName)}/sources/${encodeURIComponent(sourceName)}`,
      { method: 'POST' },
    ),
  removeKbSource: (kbName: string, sourceName: string) =>
    request<KnowledgeBase>(
      `/knowledge-bases/${encodeURIComponent(kbName)}/sources/${encodeURIComponent(sourceName)}`,
      { method: 'DELETE' },
    ),
  agents: () => request<AgentListResponse>('/agents'),
  agent: (name: string) =>
    request<Agent>(`/agents/${encodeURIComponent(name)}`),
  createAgent: (body: CreateAgentRequest) =>
    request<Agent>('/agents', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateAgent: (name: string, body: UpdateAgentRequest) =>
    request<Agent>(`/agents/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  deleteAgent: (name: string) =>
    request<void>(`/agents/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  agentQuery: (name: string, body: AgentQueryRequest) =>
    request<AgentQueryResponse>(
      `/agents/${encodeURIComponent(name)}/query`,
      { method: 'POST', body: JSON.stringify(body) },
    ),
  seedAgents: (dryRun = false) =>
    request<{ seeded: string[]; count: number }>(
      `/agents/seed?dry_run=${dryRun}`,
      { method: 'POST' },
    ),
  promptTemplates: () => request<PromptTemplateListResponse>('/prompt-templates'),
  promptTemplate: (id: string) =>
    request<PromptTemplateDetail>(`/prompt-templates/${encodeURIComponent(id)}`),
  createPromptTemplate: (body: CreatePromptTemplateRequest) =>
    request<PromptTemplateDetail>('/prompt-templates', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  addPromptVersion: (id: string, body: CreatePromptVersionRequest) =>
    request(`/prompt-templates/${encodeURIComponent(id)}/versions`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  setActivePromptVersion: (id: string, version: number) =>
    request(`/prompt-templates/${encodeURIComponent(id)}/active-version`, {
      method: 'PUT',
      body: JSON.stringify({ version }),
    }),
  deletePromptTemplate: (id: string) =>
    request<void>(`/prompt-templates/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),
  seedPrompts: (dryRun = false) =>
    request<{ seeded: string[]; count: number }>(
      `/prompt-templates/seed?dry_run=${dryRun}`,
      { method: 'POST' },
    ),
}

export { ApiError }
