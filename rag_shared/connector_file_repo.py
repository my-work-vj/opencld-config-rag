"""Repository for connector file catalog."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from rag_shared.models import ConnectorFile


class ConnectorFileRepo:
    @staticmethod
    def list_for_connector(db: Session, connector_id: str) -> list[ConnectorFile]:
        return (
            db.query(ConnectorFile)
            .filter(ConnectorFile.connector_id == connector_id)
            .order_by(ConnectorFile.name)
            .all()
        )

    @staticmethod
    def count_for_connector(db: Session, connector_id: str) -> int:
        return (
            db.query(ConnectorFile)
            .filter(ConnectorFile.connector_id == connector_id)
            .count()
        )

    @staticmethod
    def get(db: Session, file_id: str) -> ConnectorFile | None:
        return db.query(ConnectorFile).filter(ConnectorFile.id == file_id).first()

    @staticmethod
    def upsert_file(
        db: Session,
        *,
        connector_id: str,
        external_id: str,
        name: str,
        mime_type: str,
        local_path: str,
        size_bytes: int,
    ) -> ConnectorFile:
        record = (
            db.query(ConnectorFile)
            .filter(
                ConnectorFile.connector_id == connector_id,
                ConnectorFile.external_id == external_id,
            )
            .first()
        )
        if record:
            record.name = name
            record.mime_type = mime_type
            record.local_path = local_path
            record.size_bytes = size_bytes
            record.synced_at = datetime.now(timezone.utc)
        else:
            record = ConnectorFile(
                connector_id=connector_id,
                external_id=external_id,
                name=name,
                mime_type=mime_type,
                local_path=local_path,
                size_bytes=size_bytes,
            )
            db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def sync_catalog(
        db: Session,
        connector_id: str,
        synced_items: list[dict],
        *,
        keep_local_uploads: bool = True,
    ) -> list[str]:
        """Upsert synced files and remove catalog entries no longer present remotely.

        Returns connector_file ids removed from the catalog.
        """
        synced_ids = {item["external_id"] for item in synced_items}
        existing = ConnectorFileRepo.list_for_connector(db, connector_id)
        removed_file_ids: list[str] = []

        for item in synced_items:
            ConnectorFileRepo.upsert_file(
                db,
                connector_id=connector_id,
                external_id=item["external_id"],
                name=item["name"],
                mime_type=item.get("mime_type", ""),
                local_path=item["local_path"],
                size_bytes=item.get("size_bytes", 0),
            )

        for record in existing:
            if record.external_id not in synced_ids:
                if record.external_id.startswith("local:") and keep_local_uploads:
                    continue
                removed_file_ids.append(record.id)
                ConnectorFileRepo.delete_file(db, record.id)

        return removed_file_ids

    @staticmethod
    def delete_for_connector(db: Session, connector_id: str) -> None:
        db.query(ConnectorFile).filter(ConnectorFile.connector_id == connector_id).delete()
        db.commit()

    @staticmethod
    def delete_file(db: Session, file_id: str) -> ConnectorFile | None:
        record = db.query(ConnectorFile).filter(ConnectorFile.id == file_id).first()
        if not record:
            return None
        path = Path(record.local_path)
        if path.is_file():
            path.unlink(missing_ok=True)
        db.delete(record)
        db.commit()
        return record
