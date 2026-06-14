"""SQLAlchemy models for query observability."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Integer, DateTime
from core.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(String, primary_key=True, default=_uuid)
    pipeline_name = Column(String(255), nullable=False, index=True)
    collection_name = Column(String(255), nullable=False, default="rag_documents")
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
