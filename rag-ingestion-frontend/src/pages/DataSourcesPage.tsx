import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cloud, HardDrive, Plus, Server } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Label, Input, Textarea, Select } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, Spinner } from '@/components/ui/Feedback'
import type { ConnectorType, DataConnector } from '@/types/api'

const CONNECTOR_ICONS: Record<string, typeof Cloud> = {
  google_drive: Cloud,
  aws_s3: HardDrive,
}

export function DataSourcesPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [connectorType, setConnectorType] = useState('google_drive')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [objectId, setObjectId] = useState('')
  const [credentialsFile, setCredentialsFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const types = useQuery({
    queryKey: ['connector-types'],
    queryFn: async () => (await api.connectorTypes()).types,
  })

  const sources = useQuery({
    queryKey: ['data-sources'],
    queryFn: async () => (await api.dataSources()).data_sources,
    refetchInterval: 15_000,
  })

  const pathwayHealth = useQuery({
    queryKey: ['pathway-docker-health'],
    queryFn: api.pathwayDockerHealth,
    refetchInterval: 15000,
  })

  const startPathwayMutation = useMutation({
    mutationFn: api.startPathwayDocker,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pathway-docker-health'] })
    },
  })

  const createMutation = useMutation({
    mutationFn: api.createDataSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data-sources'] })
      setShowForm(false)
      resetForm()
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : 'Create failed')
    },
  })

  const resetForm = () => {
    setName('')
    setDescription('')
    setObjectId('')
    setCredentialsFile(null)
    setError(null)
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (!objectId.trim()) {
      setError('Google Drive folder ID is required')
      return
    }
    if (!credentialsFile) {
      setError('Upload credentials.json (Google service account key)')
      return
    }
    createMutation.mutate({
      name: name.trim(),
      connector_type: connectorType,
      object_id: objectId.trim(),
      credentials: credentialsFile,
      description,
    })
  }

  if (sources.isLoading || types.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  const list = sources.data ?? []
  const availableTypes = (types.data ?? []).filter((t) => t.available)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Data Sources</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Establish connectors to external systems and manage synced files. Sync runs via
            Pathway Docker (pw.io.gdrive). Index profiles link to these sources for ingestion.
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} variant="secondary">
          <Plus className="size-4" aria-hidden="true" />
          Add connector
        </Button>
      </div>

      <PathwayDockerStatus
        health={pathwayHealth.data}
        isLoading={pathwayHealth.isLoading}
        onStart={() => startPathwayMutation.mutate()}
        isStarting={startPathwayMutation.isPending}
      />

      <section aria-labelledby="connector-types-heading">
        <h2 id="connector-types-heading" className="mb-3 text-sm font-semibold text-slate-300">
          Available connectors
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(types.data ?? []).map((t) => (
            <ConnectorTypeCard key={t.id} type={t} />
          ))}
        </div>
      </section>

      {showForm && (
        <Card elevated>
          <CardHeader>
            <CardTitle>Add Google Drive connector</CardTitle>
            <CardDescription>
              Share the folder with your service account, then provide the folder ID and
              credentials.json. Uses Pathway <code className="text-indigo-300">pw.io.gdrive</code>.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ds-type">Connector type</Label>
              <Select
                id="ds-type"
                value={connectorType}
                onChange={(e) => setConnectorType(e.target.value)}
              >
                {availableTypes.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ds-name">Name *</Label>
              <Input
                id="ds-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="legal-docs-drive"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ds-object-id">Google Drive folder ID *</Label>
              <Input
                id="ds-object-id"
                value={objectId}
                onChange={(e) => setObjectId(e.target.value)}
                placeholder="1cULDv2OaViJBmOfG5WB0oWcgayNrGtVs"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ds-creds">credentials.json *</Label>
              <Input
                id="ds-creds"
                type="file"
                accept=".json,application/json"
                onChange={(e) => setCredentialsFile(e.target.files?.[0] ?? null)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ds-desc">Description</Label>
              <Textarea
                id="ds-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>
            {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
            <Button type="submit" isLoading={createMutation.isPending}>
              Create connector
            </Button>
          </form>
        </Card>
      )}

      {list.length === 0 ? (
        <EmptyState
          title="No data connectors"
          description="Add a connector to sync files from Google Drive or other external systems."
          action={<Button onClick={() => setShowForm(true)}>Add Google Drive</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((ds) => <DataSourceCard key={ds.id} connector={ds} />)}
        </div>
      )}
    </div>
  )
}

function PathwayDockerStatus({
  health,
  isLoading,
  onStart,
  isStarting,
}: {
  health?: import('@/types/api').PathwayDockerHealth
  isLoading: boolean
  onStart: () => void
  isStarting: boolean
}) {
  if (isLoading) {
    return (
      <Card elevated>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Spinner className="size-4" />
          Checking Pathway Docker…
        </div>
      </Card>
    )
  }

  const ready = health?.ready ?? false

  return (
    <Card elevated>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Server className="size-6 shrink-0 text-indigo-400" aria-hidden="true" />
          <div>
            <CardTitle className="text-base">Pathway Docker worker</CardTitle>
            <CardDescription className="mt-1">
              {health?.message ?? 'Status unknown'}
            </CardDescription>
            {health && (
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant={ready ? 'success' : 'warning'}>
                  {ready ? 'Running' : health.container_status}
                </Badge>
                <Badge variant="outline">{health.container_name}</Badge>
                {health.image_present && (
                  <Badge variant="outline">image OK</Badge>
                )}
              </div>
            )}
          </div>
        </div>
        {!ready && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onStart}
            isLoading={isStarting}
          >
            Start Pathway container
          </Button>
        )}
      </div>
    </Card>
  )
}

function ConnectorTypeCard({ type }: { type: ConnectorType }) {
  const Icon = CONNECTOR_ICONS[type.id] ?? Cloud
  return (
    <Card className={type.available ? '' : 'opacity-60'}>
      <div className="flex items-start gap-3">
        <Icon className="size-6 shrink-0 text-indigo-400" aria-hidden="true" />
        <div>
          <CardTitle className="text-sm">{type.label}</CardTitle>
          <CardDescription className="mt-1 text-xs">{type.description}</CardDescription>
          {type.available && type.runtime === 'pathway-docker' && (
            <Badge variant="outline" className="mt-2">Pathway Docker</Badge>
          )}
          {!type.available && <Badge variant="outline" className="mt-2">Coming soon</Badge>}
        </div>
      </div>
    </Card>
  )
}

function DataSourceCard({ connector }: { connector: DataConnector }) {
  const Icon = CONNECTOR_ICONS[connector.connector_type] ?? Cloud
  return (
    <Card elevated className="flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className="size-5 shrink-0 text-indigo-400" aria-hidden="true" />
          <CardTitle className="text-base">{connector.name}</CardTitle>
        </div>
        <Badge
          variant={
            connector.status === 'ready' || connector.status === 'connected'
              ? 'success'
              : connector.status === 'error'
                ? 'error'
                : 'warning'
          }
        >
          {connector.status}
        </Badge>
      </div>
      <CardDescription className="mt-2 line-clamp-2">
        {connector.description || connector.connector_type.replace('_', ' ')}
      </CardDescription>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">{connector.file_count} files</Badge>
      </div>
      <div className="mt-4">
        <Link to={`/data-sources/${connector.id}`}>
          <Button variant="secondary" className="w-full" size="sm">
            Manage files
          </Button>
        </Link>
      </div>
    </Card>
  )
}
