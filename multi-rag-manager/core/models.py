"""SQLAlchemy models for pipeline configurations and document metadata."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, JSON, Boolean
from core.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class PipelineConfig(Base):
    """Persisted pipeline configuration."""
    __tablename__ = "pipeline_configs"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    config_yaml = Column(Text, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class DocumentRecord(Base):
    """Metadata about ingested documents."""
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid)
    filename = Column(String(255), nullable=False)
    pipeline_name = Column(String(255), nullable=False)
    chunk_count = Column(Integer, default=0)
    content_preview = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)


class QueryLog(Base):
    """Log of queries and responses for observability."""
    __tablename__ = "query_logs"

    id = Column(String, primary_key=True, default=_uuid)
    pipeline_name = Column(String(255), nullable=False, index=True)
    query = Column(Text, nullable=False)
    retrieval_method = Column(String(100))
    top_k = Column(Integer, default=5)
    response = Column(Text, default="")
    retrieval_time_ms = Column(Float, default=0.0)
    reranking_time_ms = Column(Float, default=0.0)
    response_time_ms = Column(Float, default=0.0)
    total_time_ms = Column(Float, default=0.0)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
