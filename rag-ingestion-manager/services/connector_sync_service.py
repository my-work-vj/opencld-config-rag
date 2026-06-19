"""Background sync for data source connectors (remote → local catalog)."""

from __future__ import annotations

import logging

from connectors.runner import run_connector_sync
from services.collection_sync_service import sync_collections_for_connector
from rag_shared.connector_repo import DataConnectorRepo
from rag_shared.db import SessionLocal as SharedSession

logger = logging.getLogger(__name__)


def is_connector_monitored(metadata_json: dict | None, sync_mode: str | None = None) -> bool:
    meta = metadata_json or {}
    if meta.get("monitor_enabled") is False:
        return False
    mode = (sync_mode or meta.get("sync_mode") or "monitor").lower()
    return mode not in ("disabled", "off")


def sync_connector(connector_id: str, *, sync_collections: bool = False) -> dict:
    try:
        result = run_connector_sync(connector_id)
        response = {
            "connector_id": connector_id,
            "status": result.get("status", "ready"),
            "files_discovered": result.get("files_discovered", 0),
            "files_synced": result.get("files_synced", 0),
            "message": result.get("message", ""),
            "errors": result.get("errors", []),
            "collections_synced": [],
        }
        if sync_collections:
            collection_results = sync_collections_for_connector(connector_id)
            response["collections_synced"] = [
                r.get("collection", "") for r in collection_results if r.get("collection")
            ]
        return response
    except Exception as exc:
        logger.exception("Connector sync failed for %s", connector_id)
        return {
            "connector_id": connector_id,
            "status": "error",
            "files_discovered": 0,
            "files_synced": 0,
            "message": str(exc),
            "errors": [str(exc)],
        }


def sync_all_monitored_connectors() -> list[dict]:
    db = SharedSession()
    try:
        records = DataConnectorRepo.list_all(db)
        connector_ids = [
            r.id for r in records if is_connector_monitored(r.metadata_json, r.sync_mode)
        ]
    finally:
        db.close()

    results = []
    for connector_id in connector_ids:
        results.append(sync_connector(connector_id))
    return results
