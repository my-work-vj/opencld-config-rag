"""Google Drive data source connector via Pathway Docker (pw.io.gdrive)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from connectors.base import DataSourceConnector
from connectors.pathway.container import host_to_container_path
from connectors.pathway.docker_runner import run_pathway_script

logger = logging.getLogger(__name__)

_DRIVE_ID_PATTERNS = (
    re.compile(r"drive\.google\.com/drive/folders/([a-zA-Z0-9_-]+)"),
    re.compile(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)"),
    re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)"),
)


def normalize_object_id(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ValueError("object_id is required")
    for pattern in _DRIVE_ID_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1)
    if "http://" in value or "https://" in value:
        raise ValueError(
            "Could not parse Google Drive link. Use the folder/file ID or a "
            "drive.google.com/drive/folders/… URL."
        )
    return value


def parse_credentials(credentials_path: str) -> dict[str, Any]:
    path = Path(credentials_path)
    if not path.is_file():
        raise ValueError(f"Credentials file not found: {credentials_path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") != "service_account":
        raise ValueError("credentials.json must be a Google service account key (type=service_account)")
    if not data.get("client_email"):
        raise ValueError("credentials.json is missing client_email")
    return data


def source_type_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".html", ".htm"}:
        return "web"
    return "text"


def _mime_for_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
        ".csv": "text/csv",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return mime_map.get(ext, "application/octet-stream")


def _local_external_id(connector_id: str, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()[:24]
    return f"local:{connector_id}:{digest}"


def _is_storage_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "storagequotaexceeded" in text or "storage quota" in text


class GoogleDriveConnector(DataSourceConnector):
    type_id = "google_drive"
    label = "Google Drive"
    description = "Connect and sync files from a shared folder (Pathway pw.io.gdrive via Docker)"
    fields = ["object_id", "credentials_json"]
    runtime = "pathway-docker"
    supports_ui_upload = False

    def normalize_object_id(self, raw: str) -> str:
        return normalize_object_id(raw)

    def validate_credentials(self, credentials_path: str) -> dict[str, Any]:
        return parse_credentials(credentials_path)

    def _container_credentials(self, credentials_path: str) -> str:
        return host_to_container_path(credentials_path)

    def test_connection(self, object_id: str, credentials_path: str) -> dict[str, Any]:
        object_id = self.normalize_object_id(object_id)
        creds = parse_credentials(credentials_path)
        container_creds = self._container_credentials(credentials_path)

        result = run_pathway_script(
            "gdrive_test.py",
            args=[
                "--object-id",
                object_id,
                "--credentials",
                container_creds,
                "--limit",
                "10",
            ],
        )
        result["service_account_email"] = creds["client_email"]
        if result.get("ok"):
            result["message"] = f"Connected to Google Drive as {creds['client_email']}"
        return result

    def sync_files(
        self,
        *,
        connector_id: str,
        object_id: str,
        credentials_path: str,
        files_dir: Path,
    ) -> dict[str, Any]:
        object_id = self.normalize_object_id(object_id)
        parse_credentials(credentials_path)
        files_dir.mkdir(parents=True, exist_ok=True)

        container_creds = self._container_credentials(credentials_path)
        container_out = host_to_container_path(files_dir)

        result = run_pathway_script(
            "gdrive_sync.py",
            args=[
                "--object-id",
                object_id,
                "--credentials",
                container_creds,
                "--output-dir",
                container_out,
            ],
        )
        result["object_id"] = object_id
        result["connector_id"] = connector_id
        return result

    def upload_files(
        self,
        *,
        connector_id: str,
        object_id: str,
        credentials_path: str,
        files_dir: Path,
        uploads: list[tuple[str, bytes]],
    ) -> dict[str, Any]:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload

        object_id = self.normalize_object_id(object_id)
        parse_credentials(credentials_path)
        files_dir.mkdir(parents=True, exist_ok=True)

        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        synced: list[dict[str, Any]] = []
        errors: list[str] = []
        warnings: list[str] = []

        for filename, payload in uploads:
            safe_name = Path(filename).name.replace("/", "_").replace("\\", "_")
            if not safe_name:
                errors.append("Empty filename skipped")
                continue

            dest = files_dir / safe_name
            dest.write_bytes(payload)
            mime_type = _mime_for_filename(safe_name)
            external_id = _local_external_id(connector_id, payload)
            remote_uploaded = False

            try:
                created = (
                    service.files()
                    .create(
                        body={"name": safe_name, "parents": [object_id]},
                        media_body=MediaInMemoryUpload(payload, mimetype=mime_type, resumable=True),
                        fields="id,name,mimeType,size",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                external_id = created.get("id", external_id)
                remote_uploaded = True
            except Exception as exc:
                if _is_storage_quota_error(exc):
                    warnings.append(
                        f"{safe_name}: saved locally (service accounts cannot upload to My Drive — "
                        "use a Shared Drive or upload via the UI)"
                    )
                    logger.info(
                        "GDrive remote upload skipped for %s (quota); using local catalog entry",
                        safe_name,
                    )
                else:
                    warnings.append(f"{safe_name}: remote upload failed — saved locally ({exc})")
                    logger.warning("GDrive upload failed for %s: %s", safe_name, exc)

            synced.append({
                "external_id": external_id,
                "name": safe_name,
                "mime_type": mime_type,
                "local_path": str(dest),
                "size_bytes": len(payload),
                "source": "remote" if remote_uploaded else "local",
            })

        message = f"Stored {len(synced)} file(s) in connector storage"
        if warnings:
            message += f" ({len(warnings)} remote warning(s))"

        return {
            "files_uploaded": len(synced),
            "synced_files": synced,
            "errors": errors,
            "warnings": warnings,
            "message": message,
            "object_id": object_id,
            "connector_id": connector_id,
        }


class AwsS3Connector(DataSourceConnector):
    type_id = "aws_s3"
    label = "AWS S3"
    description = "Sync objects from an S3 bucket (coming soon)"
    available = False
    fields = ["bucket", "prefix", "access_key", "secret_key"]
    runtime = "planned"

    def validate_credentials(self, credentials_path: str) -> dict[str, Any]:
        raise NotImplementedError("AWS S3 connector is not available yet")

    def test_connection(self, object_id: str, credentials_path: str) -> dict[str, Any]:
        raise NotImplementedError("AWS S3 connector is not available yet")

    def sync_files(
        self,
        *,
        connector_id: str,
        object_id: str,
        credentials_path: str,
        files_dir: Path,
    ) -> dict[str, Any]:
        raise NotImplementedError("AWS S3 connector is not available yet")
