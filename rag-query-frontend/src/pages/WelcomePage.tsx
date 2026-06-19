import { Link } from 'react-router-dom'
import { ArrowRight, Bot, FileText, Zap } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'

const features = [
  {
    icon: FileText,
    title: 'Prompt Manager',
    description: 'Versioned system prompts for agents.',
    to: '/prompts',
  },
  {
    icon: Bot,
    title: 'Agents',
    description: 'Query agents with knowledge bases, prompts, and retrieval strategies.',
    to: '/agents',
  },
]

export function WelcomePage() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
  })

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-2xl border border-slate-700/60 glass p-8 sm:p-10">
        <div className="relative z-10 max-w-2xl">
          <Badge className="mb-4">Query service · port 8082</Badge>
          <h1 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Query indexed content with RAG agents
          </h1>
          <p className="mt-4 text-base leading-relaxed text-slate-400 sm:text-lg">
            Collections define ingestion and query stages in the ingestion service. Here you wire
            agents to knowledge bases, prompts, and optional query overrides.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to="/agents"
              className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-indigo-500 px-5 text-sm font-medium text-white transition-colors hover:bg-indigo-400"
            >
              Manage agents
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <Link
              to="/prompts"
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-600 px-5 text-sm font-medium text-slate-200 transition-colors hover:border-slate-500 hover:bg-slate-800/80"
            >
              Manage prompts
            </Link>
          </div>
        </div>
        <Zap
          className="absolute -right-4 -top-4 size-32 text-indigo-500/10"
          aria-hidden="true"
        />
      </section>

      <section aria-labelledby="status-heading">
        <h2 id="status-heading" className="mb-4 text-lg font-semibold text-slate-200">
          Service status
        </h2>
        {health.isLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : (
          <Card elevated>
            <CardHeader>
              <CardTitle>Query service</CardTitle>
              <CardDescription>Port 8082 — retrieve, rerank, respond</CardDescription>
            </CardHeader>
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <Stat label="Status" value={health.data?.status ?? 'unknown'} />
              <Stat label="Bases" value={String(health.data?.knowledge_base_count ?? 0)} />
              <Stat label="Agents" value={String(health.data?.agent_count ?? 0)} />
              <Stat label="LiteLLM" value={health.data?.llm_available ? 'OK' : 'Down'} />
              <Stat label="Qdrant" value={health.data?.qdrant_available ? 'OK' : 'Down'} />
            </div>
          </Card>
        )}
      </section>

      <section aria-labelledby="features-heading">
        <h2 id="features-heading" className="mb-4 text-lg font-semibold text-slate-200">
          Get started
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <Link key={f.to} to={f.to} className="group">
              <Card
                elevated
                className="h-full transition-all duration-200 group-hover:border-indigo-500/40 group-hover:shadow-indigo-500/10"
              >
                <f.icon
                  className="mb-3 size-8 text-indigo-400 transition-transform duration-200 group-hover:scale-105"
                  aria-hidden="true"
                />
                <CardTitle className="text-base">{f.title}</CardTitle>
                <CardDescription className="mt-2">{f.description}</CardDescription>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-800/50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-medium text-slate-200">{value}</p>
    </div>
  )
}
