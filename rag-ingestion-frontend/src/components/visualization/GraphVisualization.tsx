import { useEffect, useRef } from 'react'
import type { GraphVisualizationResponse } from '@/types/api'

interface NodePos {
  id: number
  x: number
  y: number
  vx: number
  vy: number
  label: string
  properties: Record<string, unknown>
}

interface EdgePos {
  source: number
  target: number
  type: string
}

interface GraphVisualizationProps {
  data: GraphVisualizationResponse
}

const NODE_COLORS = [
  '#ef4444', // red
  '#3b82f6', // blue
  '#10b981', // emerald
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#84cc16', // lime
]

export function GraphVisualization({ data }: GraphVisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || data.nodes.length === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const parent = canvas.parentElement
    if (!parent) return

    const width = parent.clientWidth
    const height = 500
    canvas.width = width
    canvas.height = height

    // Create nodes with initial positions
    const nodes: NodePos[] = data.nodes.map((n, i) => ({
      id: n.id,
      x: Math.random() * width * 0.8 + width * 0.1,
      y: Math.random() * height * 0.8 + height * 0.1,
      vx: 0,
      vy: 0,
      label: n.properties.name as string || n.labels[0] || 'Node',
      properties: n.properties,
    }))

    const edges: EdgePos[] = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
    }))

    const nodeMap = new Map(nodes.map((n) => [n.id, n]))
    let animationFrame: number
    let isRunning = true

    function applyForce() {
      if (!isRunning) return

      // Repulsion (Coulomb)
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x
          const dy = nodes[j].y - nodes[i].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = 2000 / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          nodes[i].vx -= fx
          nodes[i].vy -= fy
          nodes[j].vx += fx
          nodes[j].vy += fy
        }
      }

      // Spring attraction (Hooke's law)
      for (const edge of edges) {
        const src = nodeMap.get(edge.source)
        const tgt = nodeMap.get(edge.target)
        if (!src || !tgt) continue
        const dx = tgt.x - src.x
        const dy = tgt.y - src.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (dist - 100) * 0.001
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        src.vx += fx
        src.vy += fy
        tgt.vx -= fx
        tgt.vy -= fy
      }

      // Center gravity
      for (const node of nodes) {
        node.vx += (width / 2 - node.x) * 0.0003
        node.vy += (height / 2 - node.y) * 0.0003
      }

      // Apply velocity and damping
      for (const node of nodes) {
        node.vx *= 0.9
        node.vy *= 0.9
        node.x += node.vx
        node.y += node.vy

        // Keep within bounds
        node.x = Math.max(30, Math.min(width - 30, node.x))
        node.y = Math.max(30, Math.min(height - 30, node.y))
      }

      // Render
      ctx.clearRect(0, 0, width, height)

      // Draw edges
      for (const edge of edges) {
        const src = nodeMap.get(edge.source)
        const tgt = nodeMap.get(edge.target)
        if (!src || !tgt) continue
        ctx.beginPath()
        ctx.moveTo(src.x, src.y)
        ctx.lineTo(tgt.x, tgt.y)
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.3)'
        ctx.lineWidth = 1
        ctx.stroke()
      }

      // Draw nodes
      nodes.forEach((node, i) => {
        const color = NODE_COLORS[i % NODE_COLORS.length]

        // Node shadow
        ctx.beginPath()
        ctx.arc(node.x, node.y, 18, 0, Math.PI * 2)
        ctx.fillStyle = `${color}30`
        ctx.fill()

        // Node circle
        ctx.beginPath()
        ctx.arc(node.x, node.y, 12, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.fill()
        ctx.strokeStyle = '#1e293b'
        ctx.lineWidth = 2
        ctx.stroke()

        // Label
        ctx.font = '12px sans-serif'
        ctx.fillStyle = '#e2e8f0'
        ctx.textAlign = 'center'
        ctx.fillText(node.label.slice(0, 20), node.x, node.y + 30)
      })

      animationFrame = requestAnimationFrame(applyForce)
    }

    applyForce()

    return () => {
      isRunning = false
      cancelAnimationFrame(animationFrame)
    }
  }, [data])

  if (data.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-slate-400">
        <p>{data.message || 'No graph data available for this collection.'}</p>
        <p className="mt-2 text-sm text-slate-500">Ingest documents with graph indexing enabled to see relationships.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 text-sm text-slate-300">
        <div className="flex items-center gap-2">
          <span className="inline-block size-3 rounded-full bg-emerald-500" />
          <span>Nodes: {data.node_count}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block size-3 rounded-full bg-blue-500" />
          <span>Edges: {data.edge_count}</span>
        </div>
      </div>
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 overflow-hidden">
        <canvas
          ref={canvasRef}
          className="w-full cursor-grab active:cursor-grabbing"
          style={{ height: 500 }}
        />
      </div>
      <p className="text-xs text-slate-500">Force-directed graph layout powered by HTML5 Canvas</p>
    </div>
  )
}
