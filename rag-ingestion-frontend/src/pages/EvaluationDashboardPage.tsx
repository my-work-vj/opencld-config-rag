import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import {
  BarChart4,
  RefreshCw,
  ChevronRight,
} from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { StatusDot } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import type { EvalResult } from '@/types/api'
import { INDEX_PROFILE_PLURAL } from '@/lib/terminology'

function pct(v: number | undefined | null, decimals = 0): string {
  if (v === undefined || v === null) return '—'
  return `${(v * 100).toFixed(decimals)}%`
}

function num(v: number | undefined | null): string {
  if (v === undefined || v === null) return '—'
  if (v >= 1000) return v.toLocaleString()
  return v.toFixed(2)
}

function evaluationFeedback(evalResult: EvalResult | undefined): {
  ok: boolean
  score: string
} {
  if (!evalResult) return { ok: false, score: '—' }

  const layers = evalResult.layers || evalResult.metrics || {}
  const pipeline = layers.pipeline
  const extraction = layers.extraction

  if (pipeline?.docs_per_second != null && pipeline.docs_per_second > 0 && pipeline.error_rate < 0.5) {
    const errorRate = pipeline.error_rate ?? 0
    return {
      ok: errorRate < 0.3,
      score: `${num(pipeline.total_documents)} docs, ${num(pipeline.total_chunks)} chunks, ${pct(errorRate)} errors`,
    }
  }

  if (extraction && extraction.total_documents > 0) {
    return {
      ok: extraction.error_rate < 0.3,
      score: `${num(extraction.total_documents)} docs, ${pct(extraction.error_rate)} errors`,
    }
  }

  return { ok: false, score: 'No data' }
}

export default function EvaluationDashboardPage() {
  const queryClient = useQueryClient()
  const [evaluatingName, setEvaluatingName] = useState<string | null>(null)
  const [evalResults, setEvalResults] = useState<Record<string, EvalResult>>({})

  const collectionsQuery = useQuery({
    queryKey: ['collections'],
    queryFn: api.vectorCollections,
  })

  const evaluateAll = useMutation({
    mutationFn: async (names: string[]) => {
      const results: Record<string, EvalResult> = {}
      for (const name of names) {
        try {
          results[name] = await api.evaluateCollection(name)
        } catch {
          // collection may not support evaluation
        }
      }
      return results
    },
    onSuccess: (results) => {
      setEvalResults((prev) => ({ ...prev, ...results }))
      queryClient.invalidateQueries({ queryKey: ['eval-latest'] })
    },
  })

  const collections = collectionsQuery.data?.collections ?? []
  const isLoading =
    collectionsQuery.isLoading

  const handleEvaluateSingle = async (name: string) => {
    setEvaluatingName(name)
    try {
      const result = await api.evaluateCollection(name)
      setEvalResults((prev) => ({ ...prev, [name]: result }))
    } catch {
      /* ignore */
    } finally {
      setEvaluatingName(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Evaluation Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Ingestion pipeline quality metrics across all {INDEX_PROFILE_PLURAL.toLowerCase()}
          </p>
        </div>
        <Button
          onClick={() => {
            const names = collections.map((c: any) => c.name || c.id)
            evaluateAll.mutate(names)
          }}
          disabled={evaluateAll.isPending}
        >
          <RefreshCw
            className={`mr-2 size-4 ${evaluateAll.isPending ? 'animate-spin' : ''}`}
          />
          Evaluate All
        </Button>
      </div>

      {isLoading && (
        <Card>
          <p className="py-8 text-center text-sm text-slate-500">Loading {INDEX_PROFILE_PLURAL.toLowerCase()}…</p>
        </Card>
      )}

      {!isLoading && collections.length === 0 && (
        <Card>
          <p className="py-8 text-center text-sm text-slate-500">
            No index profiles found. Create one first.
          </p>
        </Card>
      )}

      <div className="grid gap-4">
        {collections.map((col: any) => {
          const name = col.name || col.id
          const evalResult = evalResults[name]
          const feedback = evaluationFeedback(evalResult)
          const pending = evaluateAll.isPending

          return (
            <Card key={name} elevated>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <BarChart4 className="size-5 shrink-0 text-indigo-400" />
                    <Link
                      to={`/evaluation/${encodeURIComponent(name)}`}
                      className="text-base font-semibold text-slate-100 hover:text-indigo-300 transition-colors"
                    >
                      {name}
                    </Link>
                    {evalResult && (
                      <StatusDot ok={feedback.ok} />
                    )}
                  </div>

                  <div className="mt-2 flex items-center gap-4 text-sm text-slate-400">
                    <span>{feedback.score}</span>
                    {evalResult?.timestamp && (
                      <span className="text-xs text-slate-500">
                        {new Date(evalResult.timestamp).toLocaleString()}
                      </span>
                    )}
                  </div>

                  {evalResult && (
                    <div className="mt-3 flex flex-wrap gap-3">
                      <MiniMetric label="Extraction" result={evalResult.layers?.extraction?.success_rate} fmt="pct" />
                      <MiniMetric label="Chunk Size" result={evalResult.layers?.chunking?.avg_chunk_size} fmt="num" />
                      <MiniMetric label="Docs" result={evalResult.layers?.pipeline?.total_documents} fmt="num" />
                      <MiniMetric label="Error Rate" result={evalResult.layers?.pipeline?.error_rate} fmt="pct" />
                    </div>
                  )}

                  {!evalResult && !pending && (
                    <p className="mt-2 text-xs text-slate-500">No evaluation data yet</p>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleEvaluateSingle(name)}
                    disabled={pending || evaluatingName === name}
                  >
                    <RefreshCw className={`mr-1 size-3.5 ${evaluatingName === name ? 'animate-spin' : ''}`} />
                    Evaluate
                  </Button>
                  <Link
                    to={`/evaluation/${encodeURIComponent(name)}`}
                    className="flex size-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                  >
                    <ChevronRight className="size-4" />
                  </Link>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

function MiniMetric({
  label,
  result,
  fmt,
}: {
  label: string
  result: number | undefined | null
  fmt: 'pct' | 'num'
}) {
  const val = fmt === 'pct' ? pct(result) : num(result)
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-slate-800 px-2 py-1 text-xs">
      <span className="text-slate-500">{label}:</span>
      <span className="font-medium text-slate-200">{val}</span>
    </span>
  )
}
