import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'

export function PromptDetailPage() {
  const { id } = useParams<{ id: string }>()
  const decodedId = decodeURIComponent(id ?? '')
  const queryClient = useQueryClient()
  const [systemPrompt, setSystemPrompt] = useState('')
  const [userPromptTemplate, setUserPromptTemplate] = useState('')
  const [changelog, setChangelog] = useState('')
  const [error, setError] = useState<string | null>(null)

  const template = useQuery({
    queryKey: ['prompt-template', decodedId],
    queryFn: () => api.promptTemplate(decodedId),
    enabled: Boolean(decodedId),
  })

  const addVersionMutation = useMutation({
    mutationFn: () =>
      api.addPromptVersion(decodedId, {
        system_prompt: systemPrompt,
        user_prompt_template: userPromptTemplate,
        changelog,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompt-template', decodedId] })
      queryClient.invalidateQueries({ queryKey: ['prompt-templates'] })
      setChangelog('')
      setError(null)
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Failed to add version')
    },
  })

  const setActiveMutation = useMutation({
    mutationFn: (version: number) => api.setActivePromptVersion(decodedId, version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompt-template', decodedId] })
      queryClient.invalidateQueries({ queryKey: ['prompt-templates'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deletePromptTemplate(decodedId),
    onSuccess: () => {
      window.location.href = '/prompts'
    },
  })

  if (template.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  if (template.isError || !template.data) {
    return (
      <div className="space-y-4 text-center py-20">
        <p className="text-red-400">Template not found: {decodedId}</p>
        <Link to="/prompts"><Button variant="secondary">Back</Button></Link>
      </div>
    )
  }

  const t = template.data

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link to="/prompts" className="flex min-h-11 min-w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800/80 hover:text-white" aria-label="Back">
          <ArrowLeft className="size-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">{t.name}</h1>
          <p className="font-mono text-sm text-indigo-300">{t.id}</p>
        </div>
        <Badge className="ml-auto">Active: v{t.active_version}</Badge>
        <Button variant="danger" size="sm" onClick={() => deleteMutation.mutate()} isLoading={deleteMutation.isPending}>
          <Trash2 className="size-4" /> Delete
        </Button>
      </div>

      <p className="text-sm text-slate-400">{t.description}</p>

      <Card elevated>
        <CardHeader>
          <CardTitle>Versions</CardTitle>
          <CardDescription>{t.versions.length} version(s)</CardDescription>
        </CardHeader>
        <ul className="space-y-3">
          {t.versions.map((v) => (
            <li key={v.version} className="rounded-lg border border-slate-700/60 bg-slate-800/40 p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-200">Version {v.version}</span>
                {v.version === t.active_version ? (
                  <Badge variant="success">active</Badge>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => setActiveMutation.mutate(v.version)} isLoading={setActiveMutation.isPending}>
                    Set active
                  </Button>
                )}
              </div>
              {v.changelog && <p className="mt-1 text-xs text-slate-500">{v.changelog}</p>}
              <p className="mt-2 text-sm text-slate-400 whitespace-pre-wrap line-clamp-4">{v.system_prompt}</p>
            </li>
          ))}
        </ul>
      </Card>

      <Card elevated>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="size-5 text-indigo-400" /> New version
          </CardTitle>
        </CardHeader>
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="new-system">System prompt</Label>
            <Textarea id="new-system" value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={5} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-user">User prompt template (optional, use {'{context}'} and {'{query}'})</Label>
            <Textarea id="new-user" value={userPromptTemplate} onChange={(e) => setUserPromptTemplate(e.target.value)} rows={3} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="changelog">Changelog</Label>
            <Textarea id="changelog" value={changelog} onChange={(e) => setChangelog(e.target.value)} rows={2} />
          </div>
          {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
          <Button onClick={() => addVersionMutation.mutate()} disabled={!systemPrompt.trim()} isLoading={addVersionMutation.isPending}>
            Add version
          </Button>
        </div>
      </Card>
    </div>
  )
}
