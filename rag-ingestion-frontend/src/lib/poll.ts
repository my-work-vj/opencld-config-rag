/** Polling interval for auto-synced ingestion UI (ms). */
export const AUTO_SYNC_POLL_MS = 15_000

export const ACTIVE_SYNC_POLL_MS = 5_000

export function syncPollInterval(status?: string): number | false {
  if (!status) return AUTO_SYNC_POLL_MS
  if (status === 'syncing' || status === 'indexing' || status === 'uploading') {
    return ACTIVE_SYNC_POLL_MS
  }
  return AUTO_SYNC_POLL_MS
}
