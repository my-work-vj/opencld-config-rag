"""SQLAlchemy models for ingestion metadata."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from core.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid)
    filename = Column(String(255), nullable=False)
    pipeline_name = Column(String(255), nullable=False)
    collection_name = Column(String(255), nullable=False, default="rag_documents")
    chunk_count = Column(Integer, default=0)
    content_preview = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
