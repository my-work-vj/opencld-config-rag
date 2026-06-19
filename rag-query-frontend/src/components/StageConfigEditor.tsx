import { useState } from 'react'
import { Label, Select, Textarea } from '@/components/ui/Field'

type StageConfigEditorProps = {
  stage: string
  strategies: string[]
  strategy: string
  configJson: string
  onStrategyChange: (strategy: string) => void
  onConfigChange: (configJson: string) => void
  configError?: string | null
}

export function StageConfigEditor({
  stage,
  strategies,
  strategy,
  configJson,
  onStrategyChange,
  onConfigChange,
  configError,
}: StageConfigEditorProps) {
  const [localError, setLocalError] = useState<string | null>(null)

  const handleConfigBlur = () => {
    try {
      JSON.parse(configJson || '{}')
      setLocalError(null)
    } catch {
      setLocalError('Invalid JSON')
    }
  }

  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/30 p-4 space-y-3">
      <p className="text-sm font-medium text-slate-200 capitalize">{stage}</p>
      <div className="space-y-2">
        <Label htmlFor={`${stage}-strategy`}>Strategy</Label>
        <Select
          id={`${stage}-strategy`}
          value={strategy}
          onChange={(e) => onStrategyChange(e.target.value)}
        >
          {strategies.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${stage}-config`}>Config (JSON)</Label>
        <Textarea
          id={`${stage}-config`}
          value={configJson}
          onChange={(e) => onConfigChange(e.target.value)}
          onBlur={handleConfigBlur}
          rows={4}
          className="font-mono text-xs"
        />
        {(localError || configError) && (
          <p className="text-sm text-red-400" role="alert">{localError || configError}</p>
        )}
      </div>
    </div>
  )
}

export function parseStageConfig(json: string): Record<string, unknown> {
  return JSON.parse(json || '{}') as Record<string, unknown>
}

export function stringifyStageConfig(config: Record<string, unknown>): string {
  return JSON.stringify(config ?? {}, null, 2)
}
