"""Base types for modular data source connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConnectorTypeInfo:
    id: str
    label: str
    description: str
    available: bool
    fields: list[str]
    runtime: str = "pathway-docker"
    supports_ui_upload: bool = True


class DataSourceConnector(ABC):
    """CRUD operations for a single connector type (connection + file catalog sync)."""

    type_id: str
    label: str
    description: str
    available: bool = True
    fields: list[str]
    runtime: str = "pathway-docker"
    supports_ui_upload: bool = True

    def type_info(self) -> ConnectorTypeInfo:
        return ConnectorTypeInfo(
            id=self.type_id,
            label=self.label,
            description=self.description,
            available=self.available,
            fields=self.fields,
            runtime=self.runtime,
            supports_ui_upload=self.supports_ui_upload,
        )

    def normalize_object_id(self, raw: str) -> str:
        return (raw or "").strip()

    @abstractmethod
    def validate_credentials(self, credentials_path: str) -> dict[str, Any]:
        """Validate stored credentials file."""

    @abstractmethod
    def test_connection(self, object_id: str, credentials_path: str) -> dict[str, Any]:
        """Lightweight connectivity check."""

    @abstractmethod
    def sync_files(
        self,
        *,
        connector_id: str,
        object_id: str,
        credentials_path: str,
        files_dir: Path,
    ) -> dict[str, Any]:
        """Discover and download files into files_dir. Returns sync summary."""

    def upload_files(
        self,
        *,
        connector_id: str,
        object_id: str,
        credentials_path: str,
        files_dir: Path,
        uploads: list[tuple[str, bytes]],
    ) -> dict[str, Any]:
        """Upload files to remote source and local connector storage."""
        raise NotImplementedError(f"Upload not supported for connector type: {self.type_id}")
