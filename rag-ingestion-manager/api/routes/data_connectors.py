"""Data connector API routes — connection and file catalog only."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from connectors.google_drive import parse_credentials
from connectors.pathway.container import container_name
from connectors.registry import ConnectorNotFoundError, ConnectorRegistry
from connectors.runner import (
    connector_supports_ui_upload,
    list_connector_types,
    run_connector_sync,
    run_connector_test,
    upload_connector_files,
)
from services.collection_sync_service import sync_collections_for_connector
from services.connector_sync_service import sync_connector
from rag_shared.connector_file_repo import ConnectorFileRepo
from rag_shared.connector_repo import DataConnectorNotFoundError, DataConnectorRepo
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.schemas import (
    ConnectorFileInfo,
    ConnectorFileList,
    ConnectorTypeInfo,
    ConnectorTypeList,
    DataConnectorInfo,
    DataConnectorList,
    DataConnectorSyncResponse,
    DataConnectorTestResponse,
    DataConnectorUploadResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONNECTORS_DIR = Path(os.getenv("CONNECTORS_DATA_DIR", _REPO_ROOT / "data" / "connectors"))


def _connectors_root() -> Path:
    root = _CONNECTORS_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sync_credentials_to_container(connector_id: str, cred_path: Path) -> None:
    """Copy credentials into the Pathway container (WSL→Docker Desktop cross-filesystem)."""
    import subprocess
    docker_host = os.environ.get("DOCKER_HOST", "").strip()
    env = {**os.environ, "DOCKER_HOST": docker_host} if docker_host else None
    name = container_name()
    try:
        subprocess.run(
            ["docker", "exec", name, "mkdir", "-p", f"/data/connectors/{connector_id}"],
            capture_output=True, timeout=30, env=env,
        )
        result = subprocess.run(
            ["docker", "cp", str(cred_path), f"{name}:/data/connectors/{connector_id}/credentials.json"],
            capture_output=True, timeout=30, env=env,
        )
        if result.returncode == 0:
            logger.info("Synced credentials to Pathway container %s", name)
        else:
            logger.warning("Failed to copy credentials to container: %s", (result.stderr or result.stdout).strip())
    except Exception as exc:
        logger.warning("Could not sync credentials to Pathway container: %s", exc)


def _to_info(record, file_count: int = 0) -> DataConnectorInfo:
    meta = record.metadata_json or {}
    return DataConnectorInfo(
        id=record.id,
        name=record.name,
        description=record.description or "",
        connector_type=record.connector_type,
        object_id=record.object_id,
        sync_mode=record.sync_mode or "monitor",
        status=record.status or "configured",
        has_credentials=bool(record.credentials_path and Path(record.credentials_path).is_file()),
        supports_ui_upload=connector_supports_ui_upload(record.connector_type),
        service_account_email=meta.get("service_account_email"),
        file_count=file_count,
        last_sync_at=record.last_sync_at.isoformat() if record.last_sync_at else None,
        last_sync_message=record.last_sync_message or "",
        metadata_json=meta,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


def _file_info(record) -> ConnectorFileInfo:
    return ConnectorFileInfo(
        id=record.id,
        connector_id=record.connector_id,
        external_id=record.external_id,
        name=record.name,
        mime_type=record.mime_type or "",
        local_path=record.local_path,
        size_bytes=record.size_bytes or 0,
        synced_at=record.synced_at.isoformat() if record.synced_at else None,
    )


@router.get("/connectors/types", response_model=ConnectorTypeList)
async def list_connector_types_route():
    return ConnectorTypeList(types=[ConnectorTypeInfo(**t) for t in list_connector_types()])


@router.get("/data-sources", response_model=DataConnectorList)
async def list_data_sources():
    db = SharedSession()
    try:
        records = DataConnectorRepo.list_all(db)
        items = [
            _to_info(r, ConnectorFileRepo.count_for_connector(db, r.id))
            for r in records
        ]
        return DataConnectorList(data_sources=items, total=len(items))
    finally:
        db.close()


@router.get("/data-sources/{connector_id}", response_model=DataConnectorInfo)
async def get_data_source(connector_id: str):
    db = SharedSession()
    try:
        record = DataConnectorRepo.get(db, connector_id)
        count = ConnectorFileRepo.count_for_connector(db, connector_id)
        return _to_info(record, count)
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.get("/data-sources/{connector_id}/files", response_model=ConnectorFileList)
async def list_data_source_files(connector_id: str):
    db = SharedSession()
    try:
        DataConnectorRepo.get(db, connector_id)
        records = ConnectorFileRepo.list_for_connector(db, connector_id)
        files = [_file_info(r) for r in records]
        return ConnectorFileList(files=files, total=len(files))
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.delete("/data-sources/{connector_id}/files/{file_id}", status_code=204)
async def delete_data_source_file(connector_id: str, file_id: str):
    db = SharedSession()
    try:
        DataConnectorRepo.get(db, connector_id)
        record = ConnectorFileRepo.get(db, file_id)
        if not record or record.connector_id != connector_id:
            raise HTTPException(status_code=404, detail="File not found")
        ConnectorFileRepo.delete_file(db, file_id)
        _trigger_background_collection_syncs(connector_id)
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


def _trigger_background_collection_syncs(connector_id: str) -> None:
    def _run() -> None:
        try:
            sync_collections_for_connector(connector_id)
        except Exception as exc:
            logger.warning("Collection sync after connector change failed for %s: %s", connector_id, exc)

    thread = threading.Thread(
        target=_run,
        name=f"collection-sync-{connector_id}",
        daemon=True,
    )
    thread.start()


def _trigger_background_connector_bootstrap(connector_id: str) -> None:
    """Test connection and pull initial file catalog after create."""

    def _run() -> None:
        try:
            run_connector_test(connector_id)
        except Exception as exc:
            logger.warning("Connector test after create failed for %s: %s", connector_id, exc)
        try:
            sync_connector(connector_id, sync_collections=True)
        except Exception as exc:
            logger.warning("Connector sync after create failed for %s: %s", connector_id, exc)

    thread = threading.Thread(
        target=_run,
        name=f"connector-bootstrap-{connector_id}",
        daemon=True,
    )
    thread.start()


@router.post("/data-sources", response_model=DataConnectorInfo, status_code=201)
async def create_data_source(
    name: str = Form(...),
    connector_type: str = Form("google_drive"),
    object_id: str = Form(...),
    credentials: UploadFile = File(...),
    description: str = Form(""),
    sync_mode: str = Form("monitor"),
):
    if connector_type != "google_drive":
        raise HTTPException(status_code=400, detail="Only google_drive connector is available")

    try:
        connector = ConnectorRegistry.get(connector_type)
    except ConnectorNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not connector.available:
        raise HTTPException(status_code=400, detail=f"Connector not available: {connector_type}")

    try:
        object_id = connector.normalize_object_id(object_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw = await credentials.read()
    try:
        creds_data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="credentials must be valid JSON") from exc

    if creds_data.get("type") != "service_account":
        raise HTTPException(status_code=400, detail="credentials.json must be a service account key")

    db = SharedSession()
    try:
        record = DataConnectorRepo.create(
            db,
            name=name.strip(),
            description=description,
            connector_type=connector_type,
            object_id=object_id,
            credentials_path="",
            pipeline_id=None,
            sync_mode=sync_mode or "monitor",
            knowledge_source_name=None,
            metadata_json={
                "service_account_email": creds_data.get("client_email"),
                "monitor_enabled": True,
            },
        )

        cred_dir = _connectors_root() / record.id
        cred_dir.mkdir(parents=True, exist_ok=True)
        cred_path = cred_dir / "credentials.json"
        cred_path.write_bytes(raw)
        parse_credentials(str(cred_path))

        # Sync credentials into Pathway container (WSL→Docker Desktop cross-fs)
        _sync_credentials_to_container(record.id, cred_path)

        record.credentials_path = str(cred_path)
        db.commit()
        db.refresh(record)
        info = _to_info(record, 0)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        db.close()

    _trigger_background_connector_bootstrap(record.id)
    return info


@router.delete("/data-sources/{connector_id}", status_code=204)
async def delete_data_source(connector_id: str):
    db = SharedSession()
    try:
        record = DataConnectorRepo.get(db, connector_id)
        cred_dir = _connectors_root() / record.id
        ConnectorFileRepo.delete_for_connector(db, connector_id)
        DataConnectorRepo.delete(db, connector_id)
        if cred_dir.exists():
            shutil.rmtree(cred_dir, ignore_errors=True)
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/data-sources/{connector_id}/test", response_model=DataConnectorTestResponse)
async def test_data_source(connector_id: str):
    try:
        result = run_connector_test(connector_id)
        return DataConnectorTestResponse(
            ok=result.get("ok", False),
            message=result.get("message", ""),
            object_id=result.get("object_id", ""),
            item_count=result.get("item_count", 0),
            sample_items=result.get("sample_items", []),
        )
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        db = SharedSession()
        try:
            DataConnectorRepo.set_status(db, connector_id, "error", str(exc))
        finally:
            db.close()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/data-sources/{connector_id}/upload", response_model=DataConnectorUploadResponse)
async def upload_data_source_files(
    connector_id: str,
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploads: list[tuple[str, bytes]] = []
    for upload in files:
        raw = await upload.read()
        if not raw:
            continue
        uploads.append((upload.filename or "upload.bin", raw))

    if not uploads:
        raise HTTPException(status_code=400, detail="All uploaded files were empty")

    db = SharedSession()
    try:
        record = DataConnectorRepo.get(db, connector_id)
        if not connector_supports_ui_upload(record.connector_type):
            raise HTTPException(
                status_code=400,
                detail=(
                    "UI upload is disabled for Google Drive. "
                    "Add, update, or remove files directly in the linked Drive folder — "
                    "changes sync automatically."
                ),
            )
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()

    try:
        result = upload_connector_files(connector_id, uploads)
        _trigger_background_collection_syncs(connector_id)
        db = SharedSession()
        try:
            from rag_shared.collection_connector_repo import CollectionConnectorRepo
            collection_names = CollectionConnectorRepo.list_collection_names_for_connector(db, connector_id)
        finally:
            db.close()
        uploaded = result.get("files_uploaded", 0)
        if uploaded == 0:
            raise HTTPException(
                status_code=400,
                detail="; ".join(result.get("errors") or ["Upload failed"]),
            )
        return DataConnectorUploadResponse(
            status=result.get("status", "ready"),
            message=result.get("message", "Upload complete"),
            files_uploaded=uploaded,
            collections_synced=collection_names,
            errors=[*result.get("errors", []), *result.get("warnings", [])],
        )
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/data-sources/{connector_id}/sync", response_model=DataConnectorSyncResponse)
async def sync_data_source(connector_id: str):
    try:
        result = sync_connector(connector_id, sync_collections=True)
        return DataConnectorSyncResponse(
            status=result.get("status", "ready"),
            message=result.get("message", ""),
            files_discovered=result.get("files_discovered", 0),
            files_synced=result.get("files_synced", 0),
            errors=result.get("errors", []),
        )
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
