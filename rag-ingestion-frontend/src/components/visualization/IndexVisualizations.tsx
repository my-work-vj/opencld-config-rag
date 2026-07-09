import type { VectorVisualizationResponse, SparseVisualizationResponse, MetadataVisualizationResponse, MemoryVisualizationResponse } from '@/types/api'

export function VectorVisualization({ data }: { data: VectorVisualizationResponse }) {
  if (!data.available) {
    return (
      <div className="py-8 text-center text-slate-400">
        <p>{data.message || 'Vector index not available for this profile.'}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Points" value={data.points_count.toLocaleString()} />
        <StatCard label="Vectors" value={data.vectors_count.toLocaleString()} />
        <StatCard label="Status" value={data.status} />
        <StatCard label="Samples" value={data.sample_count.toString()} />
      </div>

      {data.sample_points.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Sample Points</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-left text-slate-400">
                  <th className="pb-2 pr-4">ID</th>
                  <th className="pb-2 pr-4">Vector Dims</th>
                  <th className="pb-2">Payload Preview</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {data.sample_points.map((p) => (
                  <tr key={p.id} className="text-slate-300">
                    <td className="py-2 pr-4 font-mono text-xs text-slate-400">{p.id}</td>
                    <td className="py-2 pr-4 font-mono text-xs">
                      {Object.entries(p.vector_dims).map(([k, v]) => (
                        <div key={k} className="text-slate-500">
                          {k}: {typeof weightedString(v)}
                        </div>
                      ))}
                    </td>
                    <td className="py-2 text-slate-400 text-xs">
                      {Object.entries(p.payload).slice(0, 3).map(([k, v]) => (
                        <div key={k} className="truncate max-w-xs">{k}: {v}</div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export function SparseVisualization({ data }: { data: SparseVisualizationResponse }) {
  if (!data.available) {
    return (
      <div className="py-8 text-center text-slate-400">
        <p>{data.message || 'Sparse vector index not available for this profile.'}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <StatCard label="Points" value={data.points_count.toLocaleString()} />
        <StatCard label="Sparse Config" value={data.sparse_config} />
        <StatCard label="Samples" value={data.sample_count.toString()} />
      </div>

      {data.sample_sparse_entries.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Sparse Entries</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-left text-slate-400">
                  <th className="pb-2 pr-4">ID</th>
                  <th className="pb-2 pr-4">Non-zero Count</th>
                  <th className="pb-2">Metrics</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {data.sample_sparse_entries.map((entry) => (
                  <tr key={entry.id} className="text-slate-300">
                    <td className="py-2 pr-4 font-mono text-xs text-slate-400">{entry.id}</td>
                    <td className="py-2 pr-4 text-emerald-400 font-medium">{entry.non_zero}</td>
                    <td className="py-2 text-xs text-slate-500">
                      indices: {entry.sparse_indices}, values: {entry.sparse_values}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export function MetadataVisualization({ data }: { data: MetadataVisualizationResponse }) {
  if (!data.available) {
    return (
      <div className="py-8 text-center text-slate-400">
        <p>{data.message || 'Metadata not available for this profile.'}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <StatCard label="Documents" value={data.document_count.toLocaleString()} />
        <StatCard label="Chunks" value={data.chunk_count.toLocaleString()} />
        <StatCard label="Recent Docs" value={data.documents.length.toString()} />
      </div>

      {data.documents.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Recent Documents</h3>
          <div className="space-y-2">
            {data.documents.map((doc, i) => (
              <div key={i} className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 text-sm">
                {Object.entries(doc).map(([k, v]) => (
                  <div key={k} className="text-slate-300">
                    <span className="text-slate-500 text-xs uppercase tracking-wide">{k}: </span>
                    <span className={k === 'filename' ? 'font-medium' : ''}>{v}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function MemoryVisualization({ data }: { data: MemoryVisualizationResponse }) {
  if (!data.available) {
    return (
      <div className="py-8 text-center text-slate-400">
        <p>{data.message || 'Memory store not available for this profile.'}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Total Keys" value={data.total_keys.toLocaleString()} />
        <StatCard label="Entries" value={data.entries.length.toString()} />
      </div>

      {data.entries.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Memory Entries</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-left text-slate-400">
                  <th className="pb-2 pr-4">Key</th>
                  <th className="pb-2 pr-4">Type</th>
                  <th className="pb-2">Value Preview</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {data.entries.map((entry, i) => (
                  <tr key={i} className="text-slate-300">
                    <td className="py-2 pr-4 font-mono text-xs text-slate-400 max-w-[200px] truncate">{entry.key}</td>
                    <td className="py-2 pr-4 text-xs"><span className="rounded bg-slate-800 px-1.5 py-0.5">{entry.type}</span></td>
                    <td className="py-2 text-xs text-slate-500 max-w-md truncate">{entry.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3">
      <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  )
}

function weightedString(val: unknown): string {
  if (typeof val === 'object' && val !== null) {
    if ('length' in val && 'preview' in val) {
      const v = val as { length: number; preview: number[] }
      return `${v.length} dims, [${v.preview.join(', ')}...]`
    }
    return JSON.stringify(val).slice(0, 50)
  }
  return String(val)
}
