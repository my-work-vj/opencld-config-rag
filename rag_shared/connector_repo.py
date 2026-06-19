"""Repository for Pathway-powered data connectors."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from rag_shared.models import DataConnector
from rag_shared.schemas import CreateKnowledgeSourceRequest


class DataConnectorNotFoundError(Exception):
    pass


class DataConnectorRepo:
    @staticmethod
    def list_all(db: Session) -> list[DataConnector]:
        return db.query(DataConnector).order_by(DataConnector.created_at.desc()).all()

    @staticmethod
    def get(db: Session, connector_id: str) -> DataConnector:
        record = db.query(DataConnector).filter(DataConnector.id == connector_id).first()
        if not record:
            raise DataConnectorNotFoundError(f"Data connector not found: {connector_id}")
        return record

    @staticmethod
    def get_by_name(db: Session, name: str) -> DataConnector:
        record = db.query(DataConnector).filter(DataConnector.name == name).first()
        if not record:
            raise DataConnectorNotFoundError(f"Data connector not found: {name}")
        return record

    @staticmethod
    def create(
        db: Session,
        *,
        name: str,
        description: str,
        connector_type: str,
        object_id: str,
        credentials_path: str,
        pipeline_id: str | None,
        sync_mode: str,
        knowledge_source_name: str | None,
        metadata_json: dict | None = None,
    ) -> DataConnector:
        existing = db.query(DataConnector).filter(DataConnector.name == name).first()
        if existing:
            raise ValueError(f"Data connector already exists: {name}")

        record = DataConnector(
            name=name,
            description=description,
            connector_type=connector_type,
            object_id=object_id.strip(),
            credentials_path=credentials_path,
            pipeline_id=pipeline_id,
            sync_mode=sync_mode,
            knowledge_source_name=knowledge_source_name,
            status="configured",
            metadata_json=metadata_json or {},
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def delete(db: Session, connector_id: str) -> None:
        record = DataConnectorRepo.get(db, connector_id)
        db.delete(record)
        db.commit()

    @staticmethod
    def set_status(
        db: Session,
        connector_id: str,
        status: str,
        message: str = "",
    ) -> DataConnector:
        record = DataConnectorRepo.get(db, connector_id)
        record.status = status
        if message:
            record.last_sync_message = message
        record.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def mark_synced(
        db: Session,
        connector_id: str,
        *,
        status: str,
        message: str,
        metadata_patch: dict | None = None,
    ) -> DataConnector:
        record = DataConnectorRepo.get(db, connector_id)
        record.status = status
        record.last_sync_at = datetime.now(timezone.utc)
        record.last_sync_message = message
        if metadata_patch:
            merged = dict(record.metadata_json or {})
            merged.update(metadata_patch)
            record.metadata_json = merged
        record.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def link_knowledge_source(db: Session, connector_id: str, ks_name: str) -> DataConnector:
        record = DataConnectorRepo.get(db, connector_id)
        record.knowledge_source_name = ks_name
        db.commit()
        db.refresh(record)
        return record


def ensure_knowledge_source_for_connector(
    db: Session,
    *,
    ks_name: str,
    pipeline_id: str,
    description: str,
) -> str:
    """Create a knowledge source if missing; return its name."""
    from rag_shared.knowledge_repo import KnowledgeSourceNotFoundError, KnowledgeSourceRepo

    try:
        KnowledgeSourceRepo.get(db, ks_name)
        return ks_name
    except KnowledgeSourceNotFoundError:
        pass

    req = CreateKnowledgeSourceRequest(
        name=ks_name,
        description=description,
        pipeline=pipeline_id,
    )
    record = KnowledgeSourceRepo.create(db, req)
    db.commit()
    return record.name
