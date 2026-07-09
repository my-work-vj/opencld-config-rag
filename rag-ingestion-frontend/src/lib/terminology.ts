/** User-facing labels for Universal RAG Ingestion Knowledge (API still uses /collections). */

export const PRODUCT_TITLE = 'Universal RAG Ingestion Knowledge'
export const PRODUCT_SUBTITLE = 'Ingestion Manager'

export const INDEX_PROFILE_SINGULAR = 'Index profile'
export const INDEX_PROFILE_PLURAL = 'Index profiles'
export const KNOWLEDGE_BASE_SINGULAR = 'Knowledge base'
export const KNOWLEDGE_BASE_PLURAL = 'Knowledge bases'

export const INDEX_PROFILES_PATH = '/index-profiles'
export const KNOWLEDGE_BASES_PATH = '/knowledge-bases'

export const indexProfilePath = (name: string) =>
  `${INDEX_PROFILES_PATH}/${encodeURIComponent(name)}`

export const ingestionModeLabel = (mode?: string) => {
  if (mode === 'document_vision') return 'Vision (text + images + PDF pages)'
  if (mode === 'websites') return 'Websites'
  return 'Plain text'
}