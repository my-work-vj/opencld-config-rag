import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Cloud, Trash2, Zap } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { AUTO_SYNC_POLL_MS, syncPollInterval } from '@/lib/poll'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Feedback'

export function DataSourceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [actionError, setActionError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<string | null>(null)

  const connector = useQuery({
    queryKey: ['data-source', id],
    queryFn: () => api.dataSource(id!),
    enabled: Boolean(id),
    refetchInterval: (q) => syncPollInterval(q.state.data?.status),
  })

  const files = useQuery({
    queryKey: ['data-source-files', id],
    queryFn: () => api.dataSourceFiles(id!),
    enabled: Boolean(id),
    refetchInterval: syncPollInterval(connector.data?.status) || AUTO_SYNC_POLL_MS,
  })

  const testMutation = useMutation({
    mutationFn: () => api.testDataSource(id!),
    onSuccess: (data) => {
      setTestResult(`${data.message} — ${data.item_count} remote item(s)`)
      setActionError(null)
      queryClient.invalidateQueries({ queryKey: ['data-source', id] })
    },
    onError: (err) => {
      setTestResult(null)
      setActionError(err instanceof ApiError ? err.message : 'Test failed')
    },
  })

  const deleteFileMutation = useMutation({
    mutationFn: (fileId: string) => api.deleteDataSourceFile(id!, fileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data-source-files', id] })
      queryClient.invalidateQueries({ queryKey: ['data-source', id] })
      queryClient.invalidateQueries({ queryKey: ['vector-collections'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteDataSource(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data-sources'] })
      window.location.href = '/data-sources'
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : 'Delete failed')
    },
  })

  const handleDelete = () => {
    if (!window.confirm('Delete this connector and all synced files?')) return
    deleteMutation.mutate()
  }

  if (connector.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  if (connector.isError || !connector.data) {
    return (
      <div className="space-y-4 text-center py-20">
        <p className="text-red-400">Connector not found</p>
        <Link to="/data-sources">
          <Button variant="secondary">Back to data sources</Button>
        </Link>
      </div>
    )
  }

  const ds = connector.data
  const meta = ds.metadata_json ?? {}
  const fileList = files.data?.files ?? []
  const isMonitored = ds.sync_mode === 'monitor' || meta.monitor_enabled !== false
  const isDriveSource = ds.supports_ui_upload === false

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link
          to="/data-sources"
          className="flex min-h-11 min-w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-800/80 hover:text-white"
          aria-label="Back to data sources"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <div className="flex items-center gap-3">
          <Cloud className="size-7 text-indigo-400" aria-hidden="true" />
          <div>
            <h1 className="text-2xl font-bold text-white">{ds.name}</h1>
            <p className="font-mono text-sm text-indigo-300">{ds.connector_type}</p>
          </div>
        </div>
        <Badge variant={ds.status === 'ready' ? 'success' : 'outline'}>{ds.status}</Badge>
        {isMonitored && <Badge variant="outline">auto-sync</Badge>}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card elevated>
          <CardHeader>
            <CardTitle>Connection</CardTitle>
          </CardHeader>
          <dl className="grid gap-3 text-sm">
            <Row label="Remote folder ID" value={ds.object_id} mono />
            <Row label="Service account" value={ds.service_account_email ?? '—'} />
            <Row label="Credentials" value={ds.has_credentials ? 'Stored' : 'Missing'} />
            {typeof meta.object_name === 'string' && meta.object_name && (
              <Row label="Remote name" value={meta.object_name} />
            )}
          </dl>
        </Card>

        <Card elevated>
          <CardHeader>
            <CardTitle>Sync status</CardTitle>
            <CardDescription>
              This connector is monitored in the background. Remote changes sync automatically
              and linked collections are re-indexed.
            </CardDescription>
          </CardHeader>
          <dl className="grid gap-3 text-sm mb-4">
            <Row label="Last sync" value={ds.last_sync_at ?? 'Pending first sync'} />
            <Row label="Files on disk" value={String(ds.file_count)} />
            <Row label="Message" value={ds.last_sync_message || '—'} />
          </dl>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="secondary"
              onClick={() => testMutation.mutate()}
              isLoading={testMutation.isPending}
            >
              <Zap className="size-4" aria-hidden="true" />
              Test connection
            </Button>
            <Button
              variant="secondary"
              onClick={handleDelete}
              isLoading={deleteMutation.isPending}
              className="text-red-400"
            >
              <Trash2 className="size-4" aria-hidden="true" />
              Delete
            </Button>
          </div>
          {actionError && <p className="mt-3 text-sm text-red-400" role="alert">{actionError}</p>}
          {testResult && <p className="mt-3 text-sm text-emerald-400" role="status">{testResult}</p>}
        </Card>
      </div>

      <Card elevated>
        <CardHeader>
          <CardTitle>Synced files</CardTitle>
          <CardDescription>
            {isDriveSource
              ? 'Read-only mirror of your Google Drive folder — add, update, or remove files in Drive to sync.'
              : 'Files in this connector — updates propagate to linked collections automatically.'}
          </CardDescription>
        </CardHeader>
        {files.isLoading ? (
          <Spinner className="mx-auto" />
        ) : fileList.length === 0 ? (
          <p className="text-sm text-slate-500">
            {isDriveSource
              ? 'No files synced yet. Add files to the linked Google Drive folder — changes are detected automatically.'
              : 'No files yet. Upload from a linked collection or add files to the remote source.'}
          </p>
        ) : (
          <ul className="space-y-2">
            {fileList.map((f) => (
              <li
                key={f.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-800/40 px-3 py-2 text-sm"
              >
                <div className="min-w-0">
                  <p className="font-medium text-slate-200 truncate">{f.name}</p>
                  <p className="text-xs text-slate-500">
                    {(f.size_bytes / 1024).toFixed(1)} KB · {f.mime_type || 'unknown'}
                  </p>
                </div>
                {!isDriveSource && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => deleteFileMutation.mutate(f.id)}
                  isLoading={deleteFileMutation.isPending}
                  aria-label={`Remove ${f.name}`}
                >
                  <Trash2 className="size-4 text-red-400" />
                </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className={mono ? 'font-mono text-slate-200 break-all' : 'text-slate-200'}>{value}</dd>
    </div>
  )
}
