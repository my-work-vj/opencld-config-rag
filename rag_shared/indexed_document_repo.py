"""Repository for indexed connector documents per collection."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from rag_shared.models import IndexedDocument


class IndexedDocumentRepo:
    @staticmethod
    def list_for_collection(
        db: Session,
        knowledge_source_name: str,
        connector_id: str | None = None,
    ) -> list[IndexedDocument]:
        q = db.query(IndexedDocument).filter(
            IndexedDocument.knowledge_source_name == knowledge_source_name
        )
        if connector_id:
            q = q.filter(IndexedDocument.connector_id == connector_id)
        return q.order_by(IndexedDocument.indexed_at).all()

    @staticmethod
    def get_by_file_id(
        db: Session,
        knowledge_source_name: str,
        connector_file_id: str,
    ) -> IndexedDocument | None:
        return (
            db.query(IndexedDocument)
            .filter(
                IndexedDocument.knowledge_source_name == knowledge_source_name,
                IndexedDocument.connector_file_id == connector_file_id,
            )
            .first()
        )

    @staticmethod
    def upsert(
        db: Session,
        *,
        knowledge_source_name: str,
        connector_id: str,
        connector_file_id: str,
        external_id: str,
        content_hash: str,
        chunk_count: int,
        document_id: str | None,
    ) -> IndexedDocument:
        record = IndexedDocumentRepo.get_by_file_id(db, knowledge_source_name, connector_file_id)
        if record:
            record.connector_id = connector_id
            record.external_id = external_id
            record.content_hash = content_hash
            record.chunk_count = chunk_count
            record.document_id = document_id
        else:
            record = IndexedDocument(
                knowledge_source_name=knowledge_source_name,
                connector_id=connector_id,
                connector_file_id=connector_file_id,
                external_id=external_id,
                content_hash=content_hash,
                chunk_count=chunk_count,
                document_id=document_id,
            )
            db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def delete(db: Session, record_id: str) -> None:
        record = db.query(IndexedDocument).filter(IndexedDocument.id == record_id).first()
        if record:
            db.delete(record)
            db.commit()

    @staticmethod
    def delete_for_collection(db: Session, knowledge_source_name: str) -> None:
        db.query(IndexedDocument).filter(
            IndexedDocument.knowledge_source_name == knowledge_source_name
        ).delete()
        db.commit()

    @staticmethod
    def count_for_collection(db: Session, knowledge_source_name: str) -> int:
        return (
            db.query(IndexedDocument)
            .filter(IndexedDocument.knowledge_source_name == knowledge_source_name)
            .count()
        )

    @staticmethod
    def sum_chunks(db: Session, knowledge_source_name: str) -> int:
        result = (
            db.query(func.coalesce(func.sum(IndexedDocument.chunk_count), 0))
            .filter(IndexedDocument.knowledge_source_name == knowledge_source_name)
            .scalar()
        )
        return int(result or 0)
