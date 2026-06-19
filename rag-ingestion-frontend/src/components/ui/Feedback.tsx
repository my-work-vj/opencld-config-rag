import clsx from 'clsx'

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        'size-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-400',
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <p className="text-lg font-medium text-slate-200">{title}</p>
      <p className="max-w-md text-sm text-slate-400">{description}</p>
      {action}
    </div>
  )
}
