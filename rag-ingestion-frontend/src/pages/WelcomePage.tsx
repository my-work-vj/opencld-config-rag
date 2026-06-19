import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, Cloud, Database, Zap } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'

const features = [
  {
    icon: Cloud,
    title: 'Data Sources',
    description: 'Connect Google Drive and manage synced files via Pathway connectors.',
    to: '/data-sources',
  },
  {
    icon: Database,
    title: 'Collections',
    description:
      'Configure every RAG stage — ingestion through querying — and build monitored vector collections.',
    to: '/collections',
  },
  {
    icon: BookOpen,
    title: 'Knowledge Bases',
    description: 'Cluster collections for query agents in the query service.',
    to: '/knowledge-bases',
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
          <Badge className="mb-4">Ingestion service · port 8081</Badge>
          <h1 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Connect data, configure RAG stages, build collections
          </h1>
          <p className="mt-4 text-base leading-relaxed text-slate-400 sm:text-lg">
            Data sources sync files. Collections define ingestion and query strategies end to end.
            Knowledge bases group collections for agents.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to="/data-sources"
              className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-indigo-500 px-5 text-sm font-medium text-white transition-colors hover:bg-indigo-400"
            >
              Connect data sources
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <Link
              to="/collections"
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-600 px-5 text-sm font-medium text-slate-200 transition-colors hover:border-slate-500 hover:bg-slate-800/80"
            >
              Build collections
            </Link>
          </div>
        </div>
        <Zap className="absolute -right-4 -top-4 size-32 text-indigo-500/10" aria-hidden="true" />
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
              <CardTitle>Ingestion service</CardTitle>
              <CardDescription>Port 8081</CardDescription>
            </CardHeader>
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <Stat label="Status" value={health.data?.status ?? 'unknown'} />
              <Stat label="Collections" value={String(health.data?.knowledge_source_count ?? 0)} />
              <Stat label="Qdrant" value={health.data?.qdrant_available ? 'up' : 'down'} />
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
                className="h-full transition-all duration-200 group-hover:border-indigo-500/40"
              >
                <f.icon className="mb-3 size-8 text-indigo-400" aria-hidden="true" />
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
