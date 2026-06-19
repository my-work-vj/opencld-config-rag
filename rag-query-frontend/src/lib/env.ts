export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

/** Public URL shown in API endpoint cards (dev default matches query service). */
export const QUERY_PUBLIC_URL =
  import.meta.env.VITE_QUERY_PUBLIC_URL ?? 'http://localhost:8082/api/v1'
