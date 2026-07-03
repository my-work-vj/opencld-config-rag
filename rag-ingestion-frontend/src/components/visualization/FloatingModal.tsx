import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'

interface FloatingModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
}

export function FloatingModal({ isOpen, onClose, title, children }: FloatingModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
    >
      <div className="relative max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-slate-600 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-700 px-6 py-4">
          <h2 className="text-xl font-bold text-white">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="overflow-auto p-6 max-h-[calc(90vh-80px)]">
          {children}
        </div>
      </div>
    </div>
  )
}
