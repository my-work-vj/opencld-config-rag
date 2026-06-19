"""Repository for collection ↔ data connector links."""

from sqlalchemy.orm import Session

from rag_shared.models import CollectionConnector


class CollectionConnectorRepo:
    @staticmethod
    def link(db: Session, knowledge_source_name: str, connector_id: str) -> CollectionConnector:
        existing = (
            db.query(CollectionConnector)
            .filter(
                CollectionConnector.knowledge_source_name == knowledge_source_name,
                CollectionConnector.connector_id == connector_id,
            )
            .first()
        )
        if existing:
            return existing
        record = CollectionConnector(
            knowledge_source_name=knowledge_source_name,
            connector_id=connector_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def link_many(db: Session, knowledge_source_name: str, connector_ids: list[str]) -> list[CollectionConnector]:
        records = []
        for connector_id in connector_ids:
            records.append(CollectionConnectorRepo.link(db, knowledge_source_name, connector_id))
        return records

    @staticmethod
    def list_connector_ids(db: Session, knowledge_source_name: str) -> list[str]:
        rows = (
            db.query(CollectionConnector)
            .filter(CollectionConnector.knowledge_source_name == knowledge_source_name)
            .order_by(CollectionConnector.created_at)
            .all()
        )
        return [r.connector_id for r in rows]

    @staticmethod
    def list_monitored_collection_names(db: Session) -> list[str]:
        rows = db.query(CollectionConnector.knowledge_source_name).distinct().all()
        return [r[0] for r in rows]

    @staticmethod
    def list_collection_names_for_connector(db: Session, connector_id: str) -> list[str]:
        rows = (
            db.query(CollectionConnector.knowledge_source_name)
            .filter(CollectionConnector.connector_id == connector_id)
            .distinct()
            .all()
        )
        return [r[0] for r in rows]

    @staticmethod
    def delete_for_collection(db: Session, knowledge_source_name: str) -> None:
        db.query(CollectionConnector).filter(
            CollectionConnector.knowledge_source_name == knowledge_source_name
        ).delete()
        db.commit()

    @staticmethod
    def ensure_legacy_links(db: Session, knowledge_source_name: str, metadata_json: dict | None) -> list[str]:
        """Migrate single data_connector_id metadata into junction rows."""
        meta = metadata_json or {}
        ids = list(meta.get("data_connector_ids") or [])
        legacy = meta.get("data_connector_id")
        if legacy and legacy not in ids:
            ids.insert(0, legacy)
        for connector_id in ids:
            CollectionConnectorRepo.link(db, knowledge_source_name, connector_id)
        return ids
