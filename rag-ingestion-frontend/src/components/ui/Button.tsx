import clsx from 'clsx'
import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  isLoading?: boolean
}

const variantClass: Record<Variant, string> = {
  primary:
    'bg-indigo-500 text-white hover:bg-indigo-400 active:scale-[0.98] disabled:bg-indigo-500/50',
  secondary:
    'border border-slate-600 bg-slate-800/80 text-slate-100 hover:border-slate-500 hover:bg-slate-700/80',
  ghost: 'text-slate-300 hover:bg-slate-800/80 hover:text-white',
  danger:
    'border border-red-500/40 bg-red-500/10 text-red-300 hover:bg-red-500/20',
}

const sizeClass: Record<Size, string> = {
  sm: 'h-9 min-h-9 px-3 text-sm',
  md: 'h-11 min-h-11 px-4 text-sm',
  lg: 'h-12 min-h-12 px-6 text-base',
}

export function Button({
  className,
  variant = 'primary',
  size = 'md',
  isLoading,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 ease-out',
        'disabled:cursor-not-allowed disabled:opacity-60',
        variantClass[variant],
        sizeClass[size],
        className,
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <span
          className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  )
}
