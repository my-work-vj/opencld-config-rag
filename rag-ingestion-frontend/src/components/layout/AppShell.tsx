import {
  Activity,
  BookOpen,
  Cloud,
  Database,
  Home,
  Sparkles,
  BarChart4,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import clsx from 'clsx'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatusDot } from '@/components/ui/Badge'

const navItems = [
  { to: '/', label: 'Welcome', icon: Home, end: true },
  { to: '/data-sources', label: 'Data Sources', icon: Cloud },
  { to: '/collections', label: 'Collections', icon: Database },
  { to: '/evaluation', label: 'Evaluation', icon: BarChart4 },
  { to: '/knowledge-bases', label: 'Knowledge Bases', icon: BookOpen },
]

export function AppShell() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30000,
  })

  const isHealthy = health.data?.status === 'healthy'

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <aside
        className="glass z-40 flex flex-col border-b border-slate-700/60 lg:fixed lg:inset-y-0 lg:w-64 lg:border-b-0 lg:border-r"
        aria-label="Main navigation"
      >
        <div className="flex items-center gap-2 border-b border-slate-700/60 px-5 py-4 lg:py-5">
          <div className="flex size-9 items-center justify-center rounded-lg bg-indigo-500/20">
            <Sparkles className="size-5 text-indigo-400" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">OpenCLD RAG</p>
            <p className="text-xs text-slate-400">Ingestion Manager</p>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto p-2 lg:flex-col lg:space-y-1 lg:p-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                clsx(
                  'flex min-h-11 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors duration-200 lg:gap-3',
                  isActive
                    ? 'bg-indigo-500/15 text-indigo-300'
                    : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-100',
                )
              }
            >
              <item.icon className="size-5 shrink-0" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden border-t border-slate-700/60 p-4 lg:block">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-2">
              <Activity className="size-3.5" aria-hidden="true" />
              Ingestion :8081
            </span>
            <StatusDot ok={isHealthy} />
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col lg:pl-64">
        <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
