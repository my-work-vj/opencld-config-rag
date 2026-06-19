import clsx from 'clsx'
import type { InputHTMLAttributes, LabelHTMLAttributes } from 'react'

export function Label({
  className,
  children,
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={clsx('text-sm font-medium text-slate-300', className)}
      {...props}
    >
      {children}
    </label>
  )
}

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={clsx(
        'h-11 min-h-11 w-full rounded-lg border border-slate-600 bg-slate-800/80 px-3 text-sm text-slate-100',
        'placeholder:text-slate-500 transition-colors duration-200',
        'hover:border-slate-500 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30',
        className,
      )}
      {...props}
    />
  )
}

export function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={clsx(
        'min-h-[88px] w-full rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-2 text-sm text-slate-100',
        'placeholder:text-slate-500 transition-colors duration-200 resize-y',
        'hover:border-slate-500 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30',
        className,
      )}
      {...props}
    />
  )
}

export function Select({
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={clsx(
        'h-11 min-h-11 w-full rounded-lg border border-slate-600 bg-slate-800/80 px-3 text-sm text-slate-100',
        'transition-colors duration-200',
        'hover:border-slate-500 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}
