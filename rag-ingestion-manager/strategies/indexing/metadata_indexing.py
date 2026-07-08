"""Metadata indexing strategy — persists DocumentRecord and ChunkRecord to PostgreSQL."""

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from core.base_strategies import (
    BaseMetadataIndexingStrategy, Document, Chunk,
)
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)


def _get_db_session() -> Optional[Session]:
    """Get a local metadata DB session."""
    try:
        from core.db import SessionLocal
        return SessionLocal()
    except Exception as e:
        logger.warning("Cannot create DB session for metadata indexing: %s", e)
        return None


@StrategyRegistry.register("indexing", "metadata_indexing")
class MetadataIndexing(BaseMetadataIndexingStrategy):
    """Index document and chunk metadata into PostgreSQL (DocumentRecord + ChunkRecord tables).

    This strategy persists the full document-chunk hierarchy so that:
      - Documents reference their chunks
      - Chunks carry multi-index tracking flags (indexed_in_vector, sparse, graph, etc.)
      - Query-time tools can fetch chunk text by document or by chunk_id
    """

    def index_metadata(self, documents: list[Document], chunks: list[Chunk], **kwargs) -> None:
        """Persist documents and chunks to PostgreSQL metadata tables."""
        collection_name = kwargs.get("collection_name", "rag_documents")

        db = _get_db_session()
        if db is None:
            logger.warning("MetadataIndexing: no DB available — skipping metadata persistence")
            return

        try:
            # Build a lookup: document_id → Document
            doc_map = {doc.id: doc for doc in documents}

            # Build chunk map for parent-chunk linking
            chunk_map = {chunk.id: chunk for chunk in chunks}

            from rag_shared.models import DocumentRecord, ChunkRecord

            # Upsert documents
            for doc in documents:
                existing = (
                    db.query(DocumentRecord)
                    .filter_by(
                        filename=doc.filename or "unknown",
                        pipeline_name=kwargs.get("pipeline_name", "default"),
                        collection_name=collection_name,
                    )
                    .order_by(DocumentRecord.created_at.desc())
                    .first()
                )

                if existing:
                    record = existing
                    record.chunk_count = sum(
                        1 for c in chunks if c.document_id == doc.id
                    )
                    record.content_preview = doc.content[:200]
                    record.content_hash = kwargs.get(
                        "content_hash", record.content_hash
                    )
                else:
                    record = DocumentRecord(
                        filename=doc.filename or "unknown",
                        pipeline_name=kwargs.get("pipeline_name", "default"),
                        collection_name=collection_name,
                        chunk_count=sum(
                            1 for c in chunks if c.document_id == doc.id
                        ),
                        content_preview=doc.content[:200],
                        metadata_json=doc.metadata,
                        content_hash=kwargs.get("content_hash", ""),
                    )
                    db.add(record)

                db.flush()  # get record.id
                doc_map[doc.id] = record  # store DB id

            # Persist chunks
            for chunk in chunks:
                parent_id = None
                if chunk.parent_chunk_id and chunk.parent_chunk_id in chunk_map:
                    # Look up the parent's record in DB
                    parent_record = (
                        db.query(ChunkRecord)
                        .filter_by(id=chunk.parent_chunk_id)
                        .first()
                    )
                    if parent_record:
                        parent_id = parent_record.id

                doc_record = doc_map.get(chunk.document_id)
                if doc_record is None:
                    logger.warning(
                        "MetadataIndexing: chunk %s references unknown document %s",
                        chunk.id,
                        chunk.document_id,
                    )
                    continue
                doc_db_id = doc_record.id if hasattr(doc_record, "id") else str(doc_record)

                # Check if chunk already exists by chunk_id
                existing_chunk = (
                    db.query(ChunkRecord)
                    .filter_by(id=chunk.id)
                    .first()
                )

                if existing_chunk:
                    existing_chunk.content = chunk.content
                    existing_chunk.metadata_json = chunk.metadata
                    existing_chunk.document_id = doc_db_id
                else:
                    cr = ChunkRecord(
                        id=chunk.id,
                        document_id=doc_db_id,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        chunk_level=chunk.chunk_level,
                        parent_chunk_id=parent_id,
                        filename=chunk.filename or (
                            doc_record.filename if hasattr(doc_record, "filename") else chunk.filename
                        ),
                        metadata_json=chunk.metadata,
                    )
                    db.add(cr)

            db.commit()
            logger.info(
                f"MetadataIndexing: saved {len(documents)} docs + {len(chunks)} chunks "
                f"to PostgreSQL (collection={collection_name})"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"MetadataIndexing: DB error — {e}")
            raise
        finally:
            db.close()
