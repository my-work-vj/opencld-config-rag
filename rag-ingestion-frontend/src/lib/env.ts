export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

/** Public URL shown in API endpoint cards (dev default matches ingestion service). */
export const INGESTION_PUBLIC_URL =
  import.meta.env.VITE_INGESTION_PUBLIC_URL ?? 'http://localhost:8081/api/v1'
