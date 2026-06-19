import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Plus } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { StageConfigEditor, parseStageConfig, stringifyStageConfig } from '@/components/StageConfigEditor'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, Spinner } from '@/components/ui/Feedback'
import type { Agent } from '@/types/api'

const DEFAULT_RETRIEVAL = { top_k: 10 }
const DEFAULT_RERANKING = { top_k: 5 }
const DEFAULT_RESPONSE = { temperature: 0.3, max_tokens: 2048 }

export function AgentsPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedKbs, setSelectedKbs] = useState<string[]>([])
  const [promptTemplateId, setPromptTemplateId] = useState('')
  const [promptVersion, setPromptVersion] = useState<number | ''>('')
  const [llmModel, setLlmModel] = useState('llama-3.3-70b-versatile')
  const [retrievalStrategy, setRetrievalStrategy] = useState('multi_collection')
  const [rerankingStrategy, setRerankingStrategy] = useState('pass_through')
  const [responseStrategy, setResponseStrategy] = useState('contextual_response')
  const [retrievalConfigJson, setRetrievalConfigJson] = useState(stringifyStageConfig(DEFAULT_RETRIEVAL))
  const [rerankingConfigJson, setRerankingConfigJson] = useState(stringifyStageConfig(DEFAULT_RERANKING))
  const [responseConfigJson, setResponseConfigJson] = useState(stringifyStageConfig(DEFAULT_RESPONSE))
  const [error, setError] = useState<string | null>(null)

  const agents = useQuery({
    queryKey: ['agents'],
    queryFn: async () => (await api.agents()).agents,
  })

  const bases = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: async () => (await api.knowledgeBases()).knowledge_bases,
  })

  const prompts = useQuery({
    queryKey: ['prompt-templates'],
    queryFn: async () => (await api.promptTemplates()).templates,
  })

  const queryStrategies = useQuery({
    queryKey: ['strategies', 'query'],
    queryFn: api.strategies,
  })

  const retrievalOptions = queryStrategies.data?.retrieval ?? ['multi_collection']
  const rerankingOptions = queryStrategies.data?.reranking ?? ['pass_through']
  const responseOptions = queryStrategies.data?.response ?? ['contextual_response']

  const createMutation = useMutation({
    mutationFn: api.createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setShowForm(false)
      setName('')
      setDescription('')
      setSelectedKbs([])
      setError(null)
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Create failed')
    },
  })

  const handleToggleKb = (kbName: string) => {
    setSelectedKbs((prev) =>
      prev.includes(kbName) ? prev.filter((k) => k !== kbName) : [...prev, kbName],
    )
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (selectedKbs.length === 0) {
      setError('Select at least one knowledge base')
      return
    }
    try {
      const retrieval_config = parseStageConfig(retrievalConfigJson)
      const reranking_config = parseStageConfig(rerankingConfigJson)
      const response_config = { ...parseStageConfig(responseConfigJson), model: llmModel }
      const top_k = Number(retrieval_config.top_k ?? 5)

      createMutation.mutate({
        name: name.trim(),
        description,
        knowledge_base_names: selectedKbs,
        prompt_template_id: promptTemplateId || undefined,
        prompt_version: promptVersion === '' ? undefined : Number(promptVersion),
        llm_model: llmModel,
        retrieval_strategy: retrievalStrategy,
        top_k,
        reranking_strategy: rerankingStrategy,
        response_strategy: responseStrategy,
        retrieval_config,
        reranking_config,
        response_config,
        query_stages: {
          retrieval: { strategy: retrievalStrategy, config: retrieval_config },
          reranking: { strategy: rerankingStrategy, config: reranking_config },
          response: { strategy: responseStrategy, config: response_config },
        },
      })
    } catch {
      setError('Invalid JSON in stage config')
    }
  }

  if (agents.isLoading) {
    return <div className="flex justify-center py-20"><Spinner /></div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">RAG Agents</h1>
          <p className="mt-1 text-sm text-slate-400">
            Agent pipelines with prompts, knowledge bases, and query strategies. Auto-exported to agent_pipelines/*.yaml.
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} variant="secondary">
          <Plus className="size-4" /> New agent
        </Button>
      </div>

      {showForm && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Create RAG agent pipeline</CardTitle>
          </CardHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="agent-name">Name *</Label>
                <Input id="agent-name" value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="agent-llm">LLM model</Label>
                <Input id="agent-llm" value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-desc">Description</Label>
              <Textarea id="agent-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
            </div>

            <div className="space-y-2">
              <Label>Knowledge bases *</Label>
              <ul className="space-y-2 rounded-lg border border-slate-700/60 p-3 max-h-40 overflow-y-auto">
                {(bases.data ?? []).map((kb) => (
                  <li key={kb.id}>
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="checkbox" checked={selectedKbs.includes(kb.name)} onChange={() => handleToggleKb(kb.name)} className="rounded border-slate-600" />
                      {kb.name} <span className="text-slate-500">({kb.sources.length} sources)</span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="prompt-template">Prompt template</Label>
                <select id="prompt-template" value={promptTemplateId} onChange={(e) => setPromptTemplateId(e.target.value)} className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm">
                  <option value="">Inline only (use resolved prompt)</option>
                  {(prompts.data ?? []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name} (v{p.active_version})</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="prompt-version">Pin version (optional)</Label>
                <Input id="prompt-version" type="number" min={1} value={promptVersion} onChange={(e) => setPromptVersion(e.target.value ? Number(e.target.value) : '')} />
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <StageConfigEditor stage="retrieval" strategies={retrievalOptions} strategy={retrievalStrategy} configJson={retrievalConfigJson} onStrategyChange={setRetrievalStrategy} onConfigChange={setRetrievalConfigJson} />
              <StageConfigEditor stage="reranking" strategies={rerankingOptions} strategy={rerankingStrategy} configJson={rerankingConfigJson} onStrategyChange={setRerankingStrategy} onConfigChange={setRerankingConfigJson} />
              <StageConfigEditor stage="response" strategies={responseOptions} strategy={responseStrategy} configJson={responseConfigJson} onStrategyChange={setResponseStrategy} onConfigChange={setResponseConfigJson} />
            </div>

            {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
            <Button type="submit" isLoading={createMutation.isPending}>Create agent</Button>
          </form>
        </Card>
      )}

      {(agents.data ?? []).length === 0 ? (
        <EmptyState title="No agents" description="Create an agent pipeline." action={<Button onClick={() => setShowForm(true)}>Create agent</Button>} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(agents.data ?? []).map((a) => <AgentCard key={a.id} agent={a} />)}
        </div>
      )}
    </div>
  )
}

function AgentCard({ agent }: { agent: Agent }) {
  const kbs = agent.knowledge_base_names?.length ? agent.knowledge_base_names : (agent.knowledge_base_name ? [agent.knowledge_base_name] : [])
  return (
    <Card elevated className="flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bot className="size-5 text-indigo-400" />
          <CardTitle className="text-base">{agent.name}</CardTitle>
        </div>
        <Badge variant={agent.is_active ? 'success' : 'outline'}>{agent.is_active ? 'active' : 'inactive'}</Badge>
      </div>
      <CardDescription className="mt-2 line-clamp-2">{agent.description || 'No description'}</CardDescription>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">{kbs.length} KB(s)</Badge>
        {agent.prompt_template_id && <Badge variant="outline">prompt: {agent.prompt_template_id}</Badge>}
        <Badge variant="outline">{agent.llm_model}</Badge>
      </div>
      <div className="mt-4">
        <Link to={`/agents/${encodeURIComponent(agent.name)}`}>
          <Button variant="secondary" className="w-full" size="sm">Configure & query</Button>
        </Link>
      </div>
    </Card>
  )
}
