import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, Spinner } from '@/components/ui/Feedback'
import type { PromptTemplateSummary } from '@/types/api'

export function PromptsPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful RAG assistant.')
  const [error, setError] = useState<string | null>(null)

  const templates = useQuery({
    queryKey: ['prompt-templates'],
    queryFn: async () => {
      const res = await api.promptTemplates()
      return res.templates
    },
  })

  const createMutation = useMutation({
    mutationFn: api.createPromptTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompt-templates'] })
      setShowForm(false)
      setId('')
      setName('')
      setDescription('')
      setError(null)
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Create failed')
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!id.trim() || !name.trim()) {
      setError('ID and name are required')
      return
    }
    createMutation.mutate({
      id: id.trim(),
      name: name.trim(),
      description,
      system_prompt: systemPrompt,
    })
  }

  if (templates.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  const list = templates.data ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Prompt Manager</h1>
          <p className="mt-1 text-sm text-slate-400">
            Versioned system prompts for RAG agents. Exported to prompts/*.yaml on save.
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} variant="secondary">
          <Plus className="size-4" aria-hidden="true" />
          New template
        </Button>
      </div>

      {showForm && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Create prompt template</CardTitle>
            <CardDescription>Creates version 1 automatically.</CardDescription>
          </CardHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="pt-id">ID *</Label>
                <Input id="pt-id" value={id} onChange={(e) => setId(e.target.value)} placeholder="finance_assistant" required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pt-name">Name *</Label>
                <Input id="pt-name" value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pt-desc">Description</Label>
              <Textarea id="pt-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pt-prompt">System prompt (v1)</Label>
              <Textarea id="pt-prompt" value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={5} />
            </div>
            {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
            <Button type="submit" isLoading={createMutation.isPending}>Create template</Button>
          </form>
        </Card>
      )}

      {list.length === 0 ? (
        <EmptyState
          title="No prompt templates"
          description="Create a template to use in agent pipelines."
          action={<Button onClick={() => setShowForm(true)}>Create template</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((t) => <PromptCard key={t.id} template={t} />)}
        </div>
      )}
    </div>
  )
}

function PromptCard({ template }: { template: PromptTemplateSummary }) {
  return (
    <Card elevated className="flex flex-col">
      <div className="flex items-start gap-2">
        <FileText className="size-5 text-indigo-400 shrink-0" aria-hidden="true" />
        <CardTitle className="text-base">{template.name}</CardTitle>
      </div>
      <p className="mt-1 font-mono text-xs text-indigo-300">{template.id}</p>
      <CardDescription className="mt-2 line-clamp-2">{template.description || 'No description'}</CardDescription>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">v{template.active_version} active</Badge>
        <Badge variant="outline">{template.version_count} versions</Badge>
      </div>
      <div className="mt-4">
        <Link to={`/prompts/${encodeURIComponent(template.id)}`}>
          <Button variant="secondary" className="w-full" size="sm">Manage versions</Button>
        </Link>
      </div>
    </Card>
  )
}
