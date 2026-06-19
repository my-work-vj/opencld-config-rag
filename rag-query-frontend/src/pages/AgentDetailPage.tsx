import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, MessageSquare, Save, Trash2 } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { QUERY_PUBLIC_URL } from '@/lib/env'
import { StageConfigEditor, parseStageConfig, stringifyStageConfig } from '@/components/StageConfigEditor'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Feedback'
import { EndpointCard } from '@/components/EndpointCard'
import type { AgentQueryResponse } from '@/types/api'

export function AgentDetailPage() {
  const { name } = useParams<{ name: string }>()
  const decodedName = decodeURIComponent(name ?? '')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [description, setDescription] = useState('')
  const [selectedKbs, setSelectedKbs] = useState<string[]>([])
  const [promptTemplateId, setPromptTemplateId] = useState('')
  const [promptVersion, setPromptVersion] = useState<number | ''>('')
  const [llmModel, setLlmModel] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [retrievalStrategy, setRetrievalStrategy] = useState('multi_collection')
  const [rerankingStrategy, setRerankingStrategy] = useState('pass_through')
  const [responseStrategy, setResponseStrategy] = useState('contextual_response')
  const [retrievalConfigJson, setRetrievalConfigJson] = useState('{}')
  const [rerankingConfigJson, setRerankingConfigJson] = useState('{}')
  const [responseConfigJson, setResponseConfigJson] = useState('{}')
  const [queryText, setQueryText] = useState('')
  const [result, setResult] = useState<AgentQueryResponse | null>(null)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveOk, setSaveOk] = useState(false)

  const agent = useQuery({
    queryKey: ['agent', decodedName],
    queryFn: () => api.agent(decodedName),
    enabled: Boolean(decodedName),
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

  useEffect(() => {
    if (!agent.data) return
    const a = agent.data
    setDescription(a.description)
    setSelectedKbs(a.knowledge_base_names?.length ? a.knowledge_base_names : (a.knowledge_base_name ? [a.knowledge_base_name] : []))
    setPromptTemplateId(a.prompt_template_id ?? '')
    setPromptVersion(a.prompt_version ?? '')
    setLlmModel(a.llm_model)
    setIsActive(a.is_active)
    setRetrievalStrategy(a.retrieval_strategy)
    setRerankingStrategy(a.reranking_strategy)
    setResponseStrategy(a.response_strategy || 'contextual_response')
    setRetrievalConfigJson(stringifyStageConfig(a.retrieval_config ?? {}))
    setRerankingConfigJson(stringifyStageConfig(a.reranking_config ?? {}))
    setResponseConfigJson(stringifyStageConfig(a.response_config ?? {}))
  }, [agent.data])

  const updateMutation = useMutation({
    mutationFn: () => {
      const retrieval_config = parseStageConfig(retrievalConfigJson)
      const reranking_config = parseStageConfig(rerankingConfigJson)
      const response_config = { ...parseStageConfig(responseConfigJson), model: llmModel }
      return api.updateAgent(decodedName, {
        description,
        knowledge_base_names: selectedKbs,
        prompt_template_id: promptTemplateId || undefined,
        prompt_version: promptVersion === '' ? undefined : Number(promptVersion),
        llm_model: llmModel,
        is_active: isActive,
        retrieval_strategy: retrievalStrategy,
        top_k: Number(retrieval_config.top_k ?? 5),
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
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent', decodedName] })
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setSaveOk(true)
      setSaveError(null)
      setTimeout(() => setSaveOk(false), 3000)
    },
    onError: (err) => {
      setSaveError(err instanceof ApiError ? err.message : 'Save failed')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteAgent(decodedName),
    onSuccess: () => navigate('/agents'),
  })

  const queryMutation = useMutation({
    mutationFn: (query: string) => api.agentQuery(decodedName, { query }),
    onSuccess: (data) => { setResult(data); setQueryError(null) },
    onError: (err) => { setResult(null); setQueryError(err instanceof ApiError ? err.message : 'Query failed') },
  })

  if (agent.isLoading) return <div className="flex justify-center py-20"><Spinner /></div>
  if (agent.isError || !agent.data) {
    return (
      <div className="space-y-4 text-center py-20">
        <p className="text-red-400">Agent not found</p>
        <Link to="/agents"><Button variant="secondary">Back</Button></Link>
      </div>
    )
  }

  const a = agent.data
  const retrievalOptions = queryStrategies.data?.retrieval ?? ['multi_collection']
  const rerankingOptions = queryStrategies.data?.reranking ?? ['pass_through']
  const responseOptions = queryStrategies.data?.response ?? ['contextual_response']

  const handleToggleKb = (kbName: string) => {
    setSelectedKbs((prev) => prev.includes(kbName) ? prev.filter((k) => k !== kbName) : [...prev, kbName])
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link to="/agents" className="flex min-h-11 min-w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800/80" aria-label="Back">
          <ArrowLeft className="size-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">{a.name}</h1>
          {a.yaml_exported_at && <p className="text-xs text-slate-500">YAML exported {new Date(a.yaml_exported_at).toLocaleString()}</p>}
        </div>
        <label className="ml-auto flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Active
        </label>
        <Button variant="danger" size="sm" onClick={() => deleteMutation.mutate()} isLoading={deleteMutation.isPending}>
          <Trash2 className="size-4" />
        </Button>
      </div>

      <Card elevated>
        <CardHeader><CardTitle>Configuration</CardTitle></CardHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Description</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          <div className="space-y-2">
            <Label>Knowledge bases</Label>
            <ul className="space-y-2 rounded-lg border border-slate-700/60 p-3 max-h-32 overflow-y-auto">
              {(bases.data ?? []).map((kb) => (
                <li key={kb.id}>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={selectedKbs.includes(kb.name)} onChange={() => handleToggleKb(kb.name)} />
                    {kb.name}
                  </label>
                </li>
              ))}
            </ul>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Prompt template</Label>
              <select value={promptTemplateId} onChange={(e) => setPromptTemplateId(e.target.value)} className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm">
                <option value="">None</option>
                {(prompts.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Prompt version</Label>
              <Input type="number" value={promptVersion} onChange={(e) => setPromptVersion(e.target.value ? Number(e.target.value) : '')} />
            </div>
            <div className="space-y-2">
              <Label>LLM model</Label>
              <Input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <StageConfigEditor stage="retrieval" strategies={retrievalOptions} strategy={retrievalStrategy} configJson={retrievalConfigJson} onStrategyChange={setRetrievalStrategy} onConfigChange={setRetrievalConfigJson} />
            <StageConfigEditor stage="reranking" strategies={rerankingOptions} strategy={rerankingStrategy} configJson={rerankingConfigJson} onStrategyChange={setRerankingStrategy} onConfigChange={setRerankingConfigJson} />
            <StageConfigEditor stage="response" strategies={responseOptions} strategy={responseStrategy} configJson={responseConfigJson} onStrategyChange={setResponseStrategy} onConfigChange={setResponseConfigJson} />
          </div>
          {saveError && <p className="text-sm text-red-400">{saveError}</p>}
          {saveOk && <p className="text-sm text-emerald-400">Saved and exported to agent_pipelines/{a.name}.yaml</p>}
          <Button onClick={() => updateMutation.mutate()} isLoading={updateMutation.isPending}>
            <Save className="size-4" /> Save agent
          </Button>
        </div>
      </Card>

      <Card elevated>
        <CardHeader><CardTitle>API</CardTitle></CardHeader>
        <EndpointCard label="Agent query" method="POST" url={`${QUERY_PUBLIC_URL}/agents/${encodeURIComponent(a.name)}/query`} body={JSON.stringify({ query: 'Your question' }, null, 2)} />
      </Card>

      <Card elevated>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><MessageSquare className="size-5 text-indigo-400" /> Test query</CardTitle>
        </CardHeader>
        <div className="space-y-3">
          <Textarea value={queryText} onChange={(e) => setQueryText(e.target.value)} rows={3} placeholder="Ask a question..." />
          <Button onClick={() => queryMutation.mutate(queryText)} disabled={!queryText.trim()} isLoading={queryMutation.isPending}>Run query</Button>
          {queryError && <p className="text-sm text-red-400">{queryError}</p>}
        </div>
      </Card>

      {result && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Response</CardTitle>
            <CardDescription>{result.retrieval_method} · {result.total_time_ms.toFixed(0)}ms</CardDescription>
          </CardHeader>
          <p className="text-sm text-slate-200 whitespace-pre-wrap">{result.response}</p>
        </Card>
      )}
    </div>
  )
}
