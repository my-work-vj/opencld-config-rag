"""SQLAlchemy models for shared pipeline configuration."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, JSON

from rag_shared.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class RagPipeline(Base):
    """Runtime source of truth for a complete RAG pipeline (ingestion + query stages)."""
    __tablename__ = "rag_pipelines"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    stages = Column(JSON, nullable=False, default=dict)
    embedding_model = Column(String(255), nullable=True)
    chat_model = Column(String(255), nullable=True)
    reranker_model = Column(String(255), nullable=True)
    llm_params = Column(JSON, default=dict)
    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class RagPipelineAudit(Base):
    """Audit trail for pipeline configuration changes."""
    __tablename__ = "rag_pipeline_audit"

    id = Column(String, primary_key=True, default=_uuid)
    pipeline_id = Column(String(255), nullable=False, index=True)
    changed_by = Column(String(255), default="system")
    old_config = Column(JSON, default=dict)
    new_config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
