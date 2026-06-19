import { Copy, Check } from 'lucide-react'
import { useState } from 'react'
import clsx from 'clsx'

export function EndpointCard({
  label,
  method,
  url,
  body,
}: {
  label: string
  method: string
  url: string
  body?: string
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const text = body
      ? `${method} ${url}\n\n${body}`
      : `${method} ${url}`
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/40 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-slate-300">{label}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex min-h-11 min-w-11 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-700/50 hover:text-white"
          aria-label={`Copy ${label} endpoint`}
        >
          {copied ? <Check className="size-4 text-emerald-400" /> : <Copy className="size-4" />}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={clsx(
            'rounded px-2 py-0.5 font-mono text-xs font-semibold',
            method === 'GET' && 'bg-sky-500/20 text-sky-300',
            method === 'POST' && 'bg-emerald-500/20 text-emerald-300',
            method === 'PATCH' && 'bg-amber-500/20 text-amber-300',
            method === 'DELETE' && 'bg-red-500/20 text-red-300',
          )}
        >
          {method}
        </span>
        <code className="font-mono text-xs text-indigo-300 break-all">{url}</code>
      </div>
      {body && (
        <pre className="mt-3 overflow-x-auto rounded-md bg-slate-950/60 p-3 font-mono text-xs text-slate-400">
          {body}
        </pre>
      )}
    </div>
  )
}
