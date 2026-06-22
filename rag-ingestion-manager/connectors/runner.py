"""Sync orchestration for data connectors — modular registry + file catalog."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from connectors.pathway.container import container_to_host_path, copy_files_from_container
from connectors import ConnectorRegistry
from connectors.registry import ConnectorNotFoundError
from rag_shared.connector_file_repo import ConnectorFileRepo
from rag_shared.connector_repo import DataConnectorNotFoundError, DataConnectorRepo
from rag_shared.db import SessionLocal as SharedSession

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONNECTORS_DIR = Path(os.getenv("CONNECTORS_DATA_DIR", _REPO_ROOT / "data" / "connectors"))


def _connector_files_dir(connector_id: str) -> Path:
    return _CONNECTORS_DIR / connector_id / "files"


def list_connector_types() -> list[dict]:
    return [
        {
            "id": t.id,
            "label": t.label,
            "description": t.description,
            "available": t.available,
            "fields": t.fields,
            "runtime": t.runtime,
            "supports_ui_upload": t.supports_ui_upload,
        }
        for t in ConnectorRegistry.list_types()
    ]


def connector_supports_ui_upload(connector_type: str) -> bool:
    try:
        return ConnectorRegistry.get(connector_type).supports_ui_upload
    except ConnectorNotFoundError:
        return True


def _resolve_object_id(db, record, connector) -> str:
    normalized = connector.normalize_object_id(record.object_id)
    if normalized != record.object_id:
        record.object_id = normalized
        db.commit()
        db.refresh(record)
        logger.info("Normalized object_id for connector %s", record.id)
    return normalized


def run_connector_test(connector_id: str) -> dict:
    db = SharedSession()
    try:
        record = DataConnectorRepo.get(db, connector_id)
        connector = ConnectorRegistry.get(record.connector_type)
        if not connector.available:
            return {"ok": False, "message": f"Connector type not available: {record.connector_type}"}
        object_id = _resolve_object_id(db, record, connector)
        result = connector.test_connection(object_id, record.credentials_path)
        if result.get("ok"):
            DataConnectorRepo.mark_synced(
                db,
                connector_id,
                status="connected",
                message=result.get("message", "Connected"),
                metadata_patch={
                    "service_account_email": result.get("service_account_email"),
                    "runtime": connector.runtime,
                },
            )
        return result
    finally:
        db.close()


def run_connector_sync(connector_id: str) -> dict:
    db = SharedSession()
    try:
        record = DataConnectorRepo.get(db, connector_id)
        connector = ConnectorRegistry.get(record.connector_type)
        if not connector.available:
            raise ValueError(f"Connector type not available: {record.connector_type}")
        object_id = _resolve_object_id(db, record, connector)
        credentials_path = record.credentials_path
        DataConnectorRepo.set_status(db, connector_id, "syncing", "Syncing via Pathway Docker")
    finally:
        db.close()

    files_dir = _connector_files_dir(connector_id)

    try:
        result = connector.sync_files(
            connector_id=connector_id,
            object_id=object_id,
            credentials_path=credentials_path,
            files_dir=files_dir,
        )
        # Copy synced files from container (Windows fs) to WSL host path
        copy_files_from_container(connector_id, files_dir)
        db = SharedSession()
        try:
            if result.get("object_id"):
                record = DataConnectorRepo.get(db, connector_id)
                if record.object_id != result["object_id"]:
                    record.object_id = result["object_id"]
                    db.commit()

            synced_items = result.get("synced_files", [])
            normalized_items = []
            for item in synced_items:
                entry = dict(item)
                if entry.get("local_path"):
                    entry["local_path"] = container_to_host_path(entry["local_path"])
                normalized_items.append(entry)
            ConnectorFileRepo.sync_catalog(
                db,
                connector_id,
                normalized_items,
                keep_local_uploads=connector.supports_ui_upload,
            )

            status = "ready" if not result.get("errors") else "error"
            DataConnectorRepo.mark_synced(
                db,
                connector_id,
                status=status,
                message=result.get("message", "Sync completed"),
                metadata_patch={
                    "last_files_discovered": result.get("files_discovered", 0),
                    "last_files_synced": result.get("files_synced", 0),
                    "runtime": connector.runtime,
                },
            )
        finally:
            db.close()
        result["status"] = status
        return result
    except Exception as exc:
        db = SharedSession()
        try:
            DataConnectorRepo.set_status(db, connector_id, "error", str(exc))
        finally:
            db.close()
        raise


def upload_connector_files(connector_id: str, uploads: list[tuple[str, bytes]]) -> dict:
    """Upload files to a connector (remote + local catalog)."""
    db = SharedSession()
    try:
        record = DataConnectorRepo.get(db, connector_id)
        connector = ConnectorRegistry.get(record.connector_type)
        if not connector.available:
            raise ValueError(f"Connector type not available: {record.connector_type}")
        if not connector.supports_ui_upload:
            raise ValueError(
                f"UI upload is not supported for {record.connector_type}. "
                "Add or update files directly in the remote source."
            )
        object_id = _resolve_object_id(db, record, connector)
        credentials_path = record.credentials_path
        DataConnectorRepo.set_status(db, connector_id, "uploading", "Uploading files")
    finally:
        db.close()

    files_dir = _connector_files_dir(connector_id)

    try:
        result = connector.upload_files(
            connector_id=connector_id,
            object_id=object_id,
            credentials_path=credentials_path,
            files_dir=files_dir,
            uploads=uploads,
        )
        db = SharedSession()
        try:
            synced_items = result.get("synced_files", [])
            for item in synced_items:
                entry = dict(item)
                if entry.get("local_path"):
                    entry["local_path"] = container_to_host_path(entry["local_path"])
                ConnectorFileRepo.upsert_file(
                    db,
                    connector_id=connector_id,
                    external_id=entry["external_id"],
                    name=entry["name"],
                    mime_type=entry.get("mime_type", ""),
                    local_path=entry["local_path"],
                    size_bytes=entry.get("size_bytes", 0),
                )
            uploaded = result.get("files_uploaded", 0)
            if uploaded > 0 and not result.get("errors"):
                status = "ready"
            elif uploaded > 0:
                status = "partial"
            else:
                status = "error"
            DataConnectorRepo.mark_synced(
                db,
                connector_id,
                status=status,
                message=result.get("message", "Upload completed"),
                metadata_patch={
                    "last_files_uploaded": uploaded,
                    "last_upload_warnings": result.get("warnings", []),
                },
            )
        finally:
            db.close()
        result["status"] = status
        return result
    except Exception as exc:
        db = SharedSession()
        try:
            DataConnectorRepo.set_status(db, connector_id, "error", str(exc))
        finally:
            db.close()
        raise
