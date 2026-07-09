import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, Cloud, Database, Layers, Zap } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'
import {
  INDEX_PROFILES_PATH,
  INDEX_PROFILE_PLURAL,
  KNOWLEDGE_BASES_PATH,
  PRODUCT_TITLE,
} from '@/lib/terminology'

const flowSteps = [
  {
    step: '1',
    title: 'Data sources',
    description: 'Connect Google Drive or upload files. Pathway syncs content into the ingestion pipeline.',
    icon: Cloud,
    to: '/data-sources',
  },
  {
    step: '2',
    title: INDEX_PROFILE_PLURAL,
    description:
      'Choose index types (vector, sparse, graph, metadata, memory) and perception mode. Each profile builds its own index store.',
    icon: Database,
    to: INDEX_PROFILES_PATH,
  },
  {
    step: '3',
    title: 'Knowledge bases',
    description:
      'Group profiles into clusters. Query agents and RAG Builder use the index catalog to pick retrieval strategies.',
    icon: BookOpen,
    to: KNOWLEDGE_BASES_PATH,
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
          <Badge className="mb-4">RAG-as-a-Service · Ingestion</Badge>
          <h1 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-4xl">
            {PRODUCT_TITLE}
          </h1>
          <p className="mt-4 text-base leading-relaxed text-slate-400 sm:text-lg">
            Industry-standard ingestion flow: connectors → multimodal parsing → multi-index storage →
            knowledge base grouping. Same data source can feed multiple index profiles with different
            recipes.
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
              to={INDEX_PROFILES_PATH}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-600 px-5 text-sm font-medium text-slate-200 transition-colors hover:border-slate-500 hover:bg-slate-800/80"
            >
              Build index profiles
            </Link>
          </div>
        </div>
        <Zap className="absolute -right-4 -top-4 size-32 text-indigo-500/10" aria-hidden="true" />
      </section>

      <section aria-labelledby="flow-heading">
        <h2 id="flow-heading" className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-200">
          <Layers className="size-5 text-indigo-400" aria-hidden="true" />
          Universal RAG pipeline
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {flowSteps.map((item) => (
            <Link key={item.step} to={item.to} className="group">
              <Card
                elevated
                className="h-full transition-all duration-200 group-hover:border-indigo-500/40"
              >
                <div className="mb-3 flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-bold text-indigo-300">
                    {item.step}
                  </span>
                  <item.icon className="size-5 text-indigo-400" aria-hidden="true" />
                </div>
                <CardTitle className="text-base">{item.title}</CardTitle>
                <CardDescription className="mt-2">{item.description}</CardDescription>
              </Card>
            </Link>
          ))}
        </div>
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
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Stat label="Status" value={health.data?.status ?? 'unknown'} />
              <Stat label={INDEX_PROFILE_PLURAL} value={String(health.data?.knowledge_source_count ?? 0)} />
              <Stat label="Knowledge bases" value={String(health.data?.knowledge_base_count ?? 0)} />
              <Stat label="Qdrant" value={health.data?.qdrant_available ? 'up' : 'down'} />
            </div>
          </Card>
        )}
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
