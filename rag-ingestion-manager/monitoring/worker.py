"""Background workers for data source and collection monitoring."""

from __future__ import annotations

import logging
import os
import threading

from services.collection_sync_service import sync_all_monitored_collections
from services.connector_sync_service import sync_all_monitored_connectors

logger = logging.getLogger(__name__)

_worker: MonitorWorker | None = None


class MonitorWorker:
    """Polls monitored data sources and collections for CRUD changes."""

    def __init__(self, interval_sec: int = 60):
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_run_at: str | None = None
        self.last_connector_results: list[dict] = []
        self.last_collection_results: list[dict] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ingestion-monitor", daemon=True)
        self._thread.start()
        logger.info("Ingestion monitor started (interval=%ss)", self.interval_sec)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                from datetime import datetime, timezone

                self.last_connector_results = sync_all_monitored_connectors()
                self.last_collection_results = sync_all_monitored_collections()
                self.last_run_at = datetime.now(timezone.utc).isoformat()
                logger.info(
                    "Monitor cycle: %d connector(s), %d collection(s)",
                    len(self.last_connector_results),
                    len(self.last_collection_results),
                )
            except Exception:
                logger.exception("Monitor cycle failed")
            self._stop.wait(self.interval_sec)


def get_monitor_worker() -> MonitorWorker | None:
    return _worker


def start_monitor() -> MonitorWorker:
    global _worker
    interval = int(os.getenv("COLLECTION_MONITOR_INTERVAL_SEC", "30"))
    if _worker is None:
        _worker = MonitorWorker(interval_sec=interval)
    _worker.start()
    return _worker


# Backward-compatible aliases
CollectionMonitorWorker = MonitorWorker
get_collection_monitor_worker = get_monitor_worker
start_collection_monitor = start_monitor
