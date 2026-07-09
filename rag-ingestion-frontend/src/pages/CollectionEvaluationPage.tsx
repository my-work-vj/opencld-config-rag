import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import {
  ArrowLeft,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  Scissors,
  Layers,
  Activity,
  Search,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

function pct(v: number | undefined | null, decimals = 1): string {
  if (v === undefined || v === null) return '—'
  return `${(v * 100).toFixed(decimals)}%`
}

function num(v: number | undefined | null): string {
  if (v === undefined || v === null) return '—'
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function formatThreshold(t: { value: number | null | undefined; threshold: { min?: number | null; max?: number | null } | number | string | null | undefined }): string {
  if (t.value === undefined || t.value === null) return '—'
  const val = num(t.value)
  const th = t.threshold
  if (typeof th === 'number') return `${val} vs ${th}`
  if (typeof th === 'string') return `${val} vs ${th}`
  if (th && typeof th === 'object') {
    if (th.min != null && th.max != null) return `${val} [${th.min}–${th.max}]`
    if (th.min != null) return `${val} ≥ ${th.min}`
    if (th.max != null) return `${val} ≤ ${th.max}`
  }
  return val
}

function MetricRow({ label, value, good, bad }: { label: string; value: string; good?: boolean; bad?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800 py-2 last:border-0">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={`text-sm font-medium ${good ? 'text-emerald-400' : bad ? 'text-red-400' : 'text-slate-200'}`}>
        {value}
      </span>
    </div>
  )
}

function LayerCard({ icon, title, children, status }: { icon: React.ReactNode; title: string; children: React.ReactNode; status?: 'pass' | 'fail' | 'unknown' }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="text-indigo-400">{icon}</span>
          <CardTitle>{title}</CardTitle>
          {status === 'pass' && <CheckCircle2 className="ml-auto size-4 text-emerald-400" />}
          {status === 'fail' && <XCircle className="ml-auto size-4 text-red-400" />}
          {status === 'unknown' && <AlertTriangle className="ml-auto size-4 text-amber-400" />}
        </div>
      </CardHeader>
      {children}
    </Card>
  )
}

export default function CollectionEvaluationPage() {
  const { name } = useParams<{ name: string }>()
  const decodedName = name ? decodeURIComponent(name) : ''

  const latestQuery = useQuery({
    queryKey: ['eval-latest', decodedName],
    queryFn: () => api.latestEvaluation(decodedName),
    enabled: !!decodedName,
  })

  const thresholdsQuery = useQuery({
    queryKey: ['eval-thresholds', decodedName],
    queryFn: () => api.evaluationThresholds(decodedName),
    enabled: !!decodedName,
  })

  const evalResult = latestQuery.data
  const thresholds = thresholdsQuery.data
  const layers = evalResult?.layers || evalResult?.metrics || {}
  const extraction = layers.extraction
  const chunking = layers.chunking
  const embedding = layers.embedding
  const pipeline = layers.pipeline
  const retrieval = layers.retrieval

  const handleReevaluate = async () => {
    await api.evaluateCollection(decodedName)
    latestQuery.refetch()
    thresholdsQuery.refetch()
  }

  const totalThresholds = thresholds?.summary?.total ?? 0
  const passedThresholds = thresholds?.summary?.passed ?? 0
  const allPassed = thresholds?.all_passed ?? true

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/evaluation"
            className="flex size-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-slate-100"
          >
            <ArrowLeft className="size-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">{decodedName}</h1>
            <p className="mt-1 text-sm text-slate-400">
              Ingestion Pipeline Quality —{' '}
              {evalResult?.timestamp
                ? new Date(evalResult.timestamp).toLocaleString()
                : 'No data'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {totalThresholds > 0 && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-500">Thresholds:</span>
              {allPassed ? (
                <span className="flex items-center gap-1 text-emerald-400">
                  <CheckCircle2 className="size-4" /> {passedThresholds}/{totalThresholds} passed
                </span>
              ) : (
                <span className="flex items-center gap-1 text-red-400">
                  <XCircle className="size-4" /> {passedThresholds}/{totalThresholds} passed
                </span>
              )}
            </div>
          )}
          <Button variant="secondary" size="sm" onClick={handleReevaluate} disabled={latestQuery.isFetching}>
            <RefreshCw className={`mr-1 size-3.5 ${latestQuery.isFetching ? 'animate-spin' : ''}`} />
            Re-Evaluate
          </Button>
        </div>
      </div>

      {latestQuery.isLoading && (
        <Card><p className="py-8 text-center text-sm text-slate-500">Loading evaluation…</p></Card>
      )}

      {latestQuery.isError && (
        <Card>
          <div className="flex items-center gap-2 py-4 text-amber-400">
            <AlertTriangle className="size-4" />
            <p className="text-sm">No evaluation data yet. Click "Re-Evaluate" to run the pipeline.</p>
          </div>
        </Card>
      )}

      {evalResult && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Layer 1: Extraction */}
          {extraction && (
            <LayerCard
              icon={<FileText className="size-4" />}
              title="Layer 1: Extraction"
              status={extraction.error_rate < 0.3 ? 'pass' : extraction.error_rate > 0 ? 'fail' : 'unknown'}
            >
              <div className="space-y-0">
                <MetricRow label="Documents" value={num(extraction.total_documents)} />
                <MetricRow label="Success Rate" value={pct(extraction.success_rate)} good={extraction.success_rate > 0.8} bad={extraction.success_rate < 0.5} />
                <MetricRow label="Error Rate" value={pct(extraction.error_rate)} good={extraction.error_rate < 0.2} bad={extraction.error_rate > 0.4} />
                <MetricRow label="Avg Content Length" value={num(extraction.avg_content_length)} />
                <MetricRow label="Avg File Size" value={`${num(extraction.avg_file_size_bytes)} B`} />
                {extraction.avg_extraction_time_ms != null && (
                  <MetricRow label="Avg Extraction Time" value={`${num(extraction.avg_extraction_time_ms)} ms`} />
                )}
              </div>
            </LayerCard>
          )}

          {/* Layer 2: Chunking */}
          {chunking && (
            <LayerCard
              icon={<Scissors className="size-4" />}
              title="Layer 2: Chunking"
              status={chunking.duplicate_content_rate < 0.2 ? 'pass' : 'fail'}
            >
              <div className="space-y-0">
                <MetricRow label="Total Chunks" value={num(chunking.total_chunks)} />
                <MetricRow label="Avg Chunk Size" value={num(chunking.avg_chunk_size)} />
                <MetricRow label="Chunks per Document" value={num(chunking.chunks_per_doc)} />
                <MetricRow label="Duplicate Rate" value={pct(chunking.duplicate_content_rate)} good={chunking.duplicate_content_rate < 0.1} bad={chunking.duplicate_content_rate > 0.3} />
                <MetricRow label="p50" value={num(chunking.p50)} />
                <MetricRow label="p95" value={num(chunking.p95)} />
                <MetricRow label="p99" value={num(chunking.p99)} />
              </div>
            </LayerCard>
          )}

          {/* Layer 3: Embedding */}
          {embedding && (
            <LayerCard
              icon={<Layers className="size-4" />}
              title="Layer 3: Embedding"
              status={embedding.zero_vector_rate < 0.1 ? 'pass' : embedding.zero_vector_rate > 0 ? 'fail' : 'unknown'}
            >
              <div className="space-y-0">
                <MetricRow label="Total Embeddings" value={num(embedding.total_embeddings)} />
                <MetricRow label="Dimensions" value={num(embedding.embedding_dimensions)} />
                <MetricRow label="Avg Norm" value={num(embedding.avg_vector_norm)} />
                <MetricRow label="Zero Vector Rate" value={pct(embedding.zero_vector_rate)} good={embedding.zero_vector_rate < 0.05} bad={embedding.zero_vector_rate > 0.2} />
                <MetricRow label="Dim Utilization" value={pct(embedding.dimension_utilization)} good={embedding.dimension_utilization > 0.5} bad={embedding.dimension_utilization < 0.2} />
                <MetricRow label="Avg Cosine Sim" value={num(embedding.avg_cosine_similarity)} />
              </div>
            </LayerCard>
          )}

          {/* Layer 4: Pipeline Health */}
          {pipeline && (
            <LayerCard
              icon={<Activity className="size-4" />}
              title="Layer 4: Pipeline Health"
              status={pipeline.status === 'success' ? 'pass' : pipeline.status === 'partial' ? 'fail' : 'unknown'}
            >
              <div className="space-y-0">
                <MetricRow label="Status" value={pipeline.status} good={pipeline.status === 'success'} bad={pipeline.status === 'partial'} />
                <MetricRow label="Total Documents" value={num(pipeline.total_documents)} />
                <MetricRow label="Total Chunks" value={num(pipeline.total_chunks)} />
                <MetricRow label="Error Rate" value={pct(pipeline.error_rate)} good={pipeline.error_rate < 0.2} bad={pipeline.error_rate > 0.4} />
                <MetricRow label="Docs/second" value={pipeline.docs_per_second != null ? num(pipeline.docs_per_second) : '—'} />
              </div>
            </LayerCard>
          )}

          {/* Layer 5: Retrieval */}
          {retrieval && (
            <LayerCard
              icon={<Search className="size-4" />}
              title="Layer 5: Retrieval Quality"
              status={retrieval.avg_faithfulness > 0.7 ? 'pass' : retrieval.avg_faithfulness > 0 ? 'fail' : 'unknown'}
            >
              <div className="space-y-0">
                <MetricRow label="Test Questions" value={num(retrieval.total_questions)} />
                <MetricRow label="Faithfulness" value={pct(retrieval.avg_faithfulness)} good={retrieval.avg_faithfulness > 0.8} bad={retrieval.avg_faithfulness < 0.5} />
                <MetricRow label="Answer Relevancy" value={pct(retrieval.avg_answer_relevancy)} good={retrieval.avg_answer_relevancy > 0.8} bad={retrieval.avg_answer_relevancy < 0.5} />
                <MetricRow label="Context Precision" value={pct(retrieval.avg_context_precision)} good={retrieval.avg_context_precision > 0.8} bad={retrieval.avg_context_precision < 0.5} />
                <MetricRow label="Context Recall" value={pct(retrieval.avg_context_recall)} good={retrieval.avg_context_recall > 0.8} bad={retrieval.avg_context_recall < 0.5} />
              </div>
            </LayerCard>
          )}
        </div>
      )}

      {/* Threshold Results */}
      {thresholds && thresholds.results && thresholds.results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Threshold Check</CardTitle>
            <CardDescription>
              {allPassed ? 'All thresholds passed ✓' : `${thresholds.summary.failed} thresholds failed`}
            </CardDescription>
          </CardHeader>
          <div className="space-y-0">
            {thresholds.results.map((t, i) => (
              <div key={i} className="flex items-center justify-between border-b border-slate-800 py-2 last:border-0">
                <div className="flex items-center gap-2">
                  {t.passed ? (
                    <CheckCircle2 className="size-4 text-emerald-400" />
                  ) : (
                    <XCircle className="size-4 text-red-400" />
                  )}
                  <span className="text-sm text-slate-300">
                    {t.layer}.{t.metric}
                  </span>
                </div>
                <span className="text-sm text-slate-400">
                  {formatThreshold(t)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
