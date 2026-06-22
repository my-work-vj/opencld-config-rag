"""Incremental sync: mirror connector file CRUD into vector collections."""
from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from connectors.pathway.container import container_to_host_path
from connectors.google_drive import source_type_for_path
from connectors.runner import connector_supports_ui_upload, run_connector_sync
from core.db import SessionLocal
from core.models import DocumentRecord
from core.pipeline import IngestionPipeline
from monitoring.qdrant_ops import delete_connector_file_vectors
from rag_shared.collection_connector_repo import CollectionConnectorRepo
from rag_shared.collection_loader import load_collection_ingestion_config
from rag_shared.connector_file_repo import ConnectorFileRepo
from rag_shared.connector_repo import DataConnectorRepo
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.indexed_document_repo import IndexedDocumentRepo
from rag_shared.knowledge_repo import KnowledgeSourceRepo
from qdrant_client import QdrantClient
from evaluation.runner import run_evaluation

logger = logging.getLogger(__name__)

_strategies_loaded = False


def _ensure_pipeline_strategies() -> None:
    global _strategies_loaded
    if _strategies_loaded:
        return
    import strategies.ingestion  # noqa: F401
    import strategies.chunking  # noqa: F401
    import strategies.embedding  # noqa: F401
    import strategies.indexing  # noqa: F401
    _strategies_loaded = True


def file_content_hash(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8192), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_connector_file_ingest(
    knowledge_source_name: str,
    source_path: str,
    source_type: str,
    connector_metadata: dict,
) -> dict:
    """
    Ingest a single file and return metrics for evaluation.

    Returns a dict with:
        - document_count, chunk_count, document_id (as before)
        - plus evaluation data: documents, chunks, embeddings, errors, file_size_bytes, stage_timings
    """
    _ensure_pipeline_strategies()
    db = SharedSession()
    try:
        ks = KnowledgeSourceRepo.get(db, knowledge_source_name)
        KnowledgeSourceRepo.set_status(db, knowledge_source_name, "indexing")
        collection_name = ks.collection_name
        vector_size = ks.vector_size or 2048
        embedding_model = ks.embedding_model or ""
    finally:
        db.close()

    # Initialize evaluation data containers
    documents: List[Any] = []
    chunks: List[Any] = []
    embeddings: List[Any] = []
    errors: List[Tuple[str, str]] = []
    stage_timings: Dict[str, float] = {}
    file_size_bytes = os.path.getsize(source_path) if os.path.exists(source_path) else 0
    overall_start = time.time()

    try:
        shared_db = SharedSession()
        try:
            config = load_collection_ingestion_config(shared_db, knowledge_source_name)
        finally:
            shared_db.close()

        # Use kreuzberg_ingestion as the unified ingestion strategy for all document types.
        # Kreuzberg handles 96 formats (PDF, Office, images, HTML, text, etc.) — plain text only.
        config["pipeline"]["stages"]["ingestion"] = {
            "strategy": "kreuzberg_ingestion",
            "config": {},
        }

        pipeline = IngestionPipeline(config)
        ingestion_overrides: dict = {
            "strategy": "kreuzberg_ingestion",
            "config": {},
        }

        # Ingestion stage
        try:
            t0 = time.time()
            documents = pipeline.run_ingestion(source_path, **ingestion_overrides)
            stage_timings["ingestion"] = time.time() - t0
        except Exception as e:
            errors.append((source_path, f"Ingestion failed: {e}"))
            documents = []

        # Only proceed if ingestion succeeded
        if not errors:
            for doc in documents:
                doc.metadata.update(connector_metadata)
                if connector_metadata.get("filename"):
                    doc.filename = connector_metadata["filename"]

            # Chunking stage
            try:
                t0 = time.time()
                chunks = pipeline.run_chunking(documents)
                stage_timings["chunking"] = time.time() - t0
            except Exception as e:
                errors.append((source_path, f"Chunking failed: {e}"))
                chunks = []

        # Only proceed if chunking succeeded
        if not errors:
            # Embedding stage
            try:
                t0 = time.time()
                embeddings = pipeline.run_embedding(chunks)
                stage_timings["embedding"] = time.time() - t0
            except Exception as e:
                errors.append((source_path, f"Embedding failed: {e}"))
                embeddings = []

        # Only proceed if embedding succeeded
        if not errors:
            # Indexing stage
            try:
                t0 = time.time()
                pipeline.run_indexing(
                    embeddings,
                    config={
                        "collection_name": collection_name,
                        "vector_size": vector_size,
                        "model": embedding_model,
                    },
                )
                stage_timings["indexing"] = time.time() - t0
            except Exception as e:
                errors.append((source_path, f"Indexing failed: {e}"))

    except Exception as exc:
        db = SharedSession()
        try:
            KnowledgeSourceRepo.set_status(db, knowledge_source_name, "error")
        finally:
            db.close()
        raise RuntimeError(f"Ingestion failed: {exc}") from exc

    doc_count = len(documents)
    chunk_count = len(chunks)
    document_id = documents[0].id if documents else None

    try:
        local_db = SessionLocal()
        for doc in documents:
            record = DocumentRecord(
                filename=doc.filename or "unknown",
                pipeline_name=pipeline.name,
                collection_name=collection_name,
                chunk_count=len([c for c in chunks if c.document_id == doc.id]),
                content_preview=doc.content[:200],
                metadata_json={
                    **doc.metadata,
                    **connector_metadata,
                    "collection_name": knowledge_source_name,
                    "ingest_source_path": source_path,
                },
            )
            local_db.add(record)
        local_db.commit()
        local_db.close()
    except Exception as exc:
        logger.warning("Could not save document metadata: %s", exc)

    # Run evaluation on this file's ingestion
    eval_result = None
    if not errors and documents:
        sync_duration = time.time() - overall_start
        try:
            qclient = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
            )
        except Exception:
            qclient = None
        try:
            db_repo = SharedSession()
            try:
                d_cnt = IndexedDocumentRepo.count_for_collection(db_repo, knowledge_source_name)
                c_cnt = IndexedDocumentRepo.sum_chunks(db_repo, knowledge_source_name)
            finally:
                db_repo.close()
        except Exception:
            d_cnt, c_cnt = len(documents), len(chunks)
        try:
            eval_result = run_evaluation(
                collection_name=knowledge_source_name,
                documents=documents,
                chunks=chunks,
                embeddings=embeddings,
                errors=errors,
                file_sizes_bytes=[file_size_bytes] * len(documents) if documents else [],
                stage_timings=stage_timings,
                sync_result={"added": len(documents), "updated": 0, "deleted": 0, "errors": errors},
                sync_duration=sync_duration,
                db_doc_count=d_cnt,
                db_chunk_count=c_cnt,
                qdrant_client=qclient,
            )
        except Exception as eval_exc:
            logger.warning("Evaluation failed for %s: %s", source_path, eval_exc)

    # Return the original keys plus evaluation data
    result = {
        "document_count": doc_count,
        "chunk_count": chunk_count,
        "document_id": document_id,
        "collection_name": collection_name,
        # Evaluation data
        "evaluation": {
            "documents": documents,
            "chunks": chunks,
            "embeddings": embeddings,
            "errors": errors,
            "file_size_bytes": file_size_bytes,
            "stage_timings": stage_timings,
        },
        "eval_result": eval_result,
    }
    return result
def _recalculate_collection_counts(db, knowledge_source_name: str) -> None:
    doc_count = IndexedDocumentRepo.count_for_collection(db, knowledge_source_name)
    chunk_count = IndexedDocumentRepo.sum_chunks(db, knowledge_source_name)
    record = KnowledgeSourceRepo.get(db, knowledge_source_name)
    record.document_count = doc_count
    record.chunk_count = chunk_count
    record.status = "ready"
    db.commit()


def sync_collection(knowledge_source_name: str) -> dict:
    """Sync all linked connectors and reconcile indexed vectors with connector catalogs."""
    _ensure_pipeline_strategies()
    db = SharedSession()
    try:
        ks = KnowledgeSourceRepo.get(db, knowledge_source_name)
        connector_ids = CollectionConnectorRepo.ensure_legacy_links(
            db, knowledge_source_name, ks.metadata_json
        )
        qdrant_collection = ks.collection_name
        if not connector_ids:
            return {
                "collection": knowledge_source_name,
                "status": "skipped",
                "message": "No linked data sources",
            }
        KnowledgeSourceRepo.set_status(db, knowledge_source_name, "syncing")
    finally:
        db.close()

    stats = {
        "collection": knowledge_source_name,
        "status": "success",
        "added": 0,
        "updated": 0,
        "deleted": 0,
        "unchanged": 0,
        "errors": [],
        "connectors_synced": [],
    }

    for connector_id in connector_ids:
        try:
            sync_result = run_connector_sync(connector_id)
            stats["connectors_synced"].append(
                {"connector_id": connector_id, "files_synced": sync_result.get("files_synced", 0)}
            )
        except Exception as exc:
            stats["errors"].append(f"connector {connector_id} sync: {exc}")
            logger.exception("Connector sync failed for %s", connector_id)

        db = SharedSession()
        try:
            connector_record = DataConnectorRepo.get(db, connector_id)
            allow_local_uploads = connector_supports_ui_upload(connector_record.connector_type)
            files = ConnectorFileRepo.list_for_connector(db, connector_id)
            if not allow_local_uploads:
                files = [f for f in files if not f.external_id.startswith("local:")]
            indexed = IndexedDocumentRepo.list_for_collection(db, knowledge_source_name, connector_id)
            indexed_by_file_id = {r.connector_file_id: r for r in indexed}
            current_file_ids = {f.id for f in files}

            for record in indexed:
                if record.connector_file_id not in current_file_ids:
                    delete_connector_file_vectors(
                        qdrant_collection, record.connector_id, record.external_id
                    )
                    IndexedDocumentRepo.delete(db, record.id)
                    stats["deleted"] += 1

            for connector_file in files:
                host_path = container_to_host_path(connector_file.local_path)
                path = Path(host_path)
                if not path.is_file():
                    continue

                content_hash = file_content_hash(path)
                existing = indexed_by_file_id.get(connector_file.id)

                if existing and existing.content_hash == content_hash and existing.chunk_count > 0:
                    stats["unchanged"] += 1
                    continue

                if existing:
                    delete_connector_file_vectors(
                        qdrant_collection, existing.connector_id, existing.external_id
                    )
                    IndexedDocumentRepo.delete(db, existing.id)
                    stats["updated"] += 1
                else:
                    stats["added"] += 1

                connector_metadata = {
                    "connector_id": connector_id,
                    "connector_file_id": connector_file.id,
                    "external_id": connector_file.external_id,
                    "filename": connector_file.name,
                    "qdrant_collection": qdrant_collection,
                }

                try:
                    source_type = source_type_for_path(path)
                    result = _run_connector_file_ingest(
                        knowledge_source_name,
                        str(path),
                        source_type,
                        connector_metadata,
                    )
                    IndexedDocumentRepo.upsert(
                        db,
                        knowledge_source_name=knowledge_source_name,
                        connector_id=connector_id,
                        connector_file_id=connector_file.id,
                        external_id=connector_file.external_id,
                        content_hash=content_hash,
                        chunk_count=result["chunk_count"],
                        document_id=result.get("document_id"),
                    )
                except Exception as exc:
                    stats["errors"].append(f"{connector_file.name}: {exc}")
                    logger.exception("Ingest failed for %s", connector_file.name)

            _recalculate_collection_counts(db, knowledge_source_name)
        finally:
            db.close()

    if stats["errors"]:
        stats["status"] = "partial"
        db = SharedSession()
        try:
            KnowledgeSourceRepo.set_status(db, knowledge_source_name, "error")
        finally:
            db.close()
    else:
        db = SharedSession()
        try:
            _recalculate_collection_counts(db, knowledge_source_name)
            doc_count = IndexedDocumentRepo.count_for_collection(db, knowledge_source_name)
            if doc_count == 0:
                stats["message"] = "Collection ready — no documents in linked data sources yet"
            else:
                stats["message"] = f"Synced {doc_count} document(s) into collection"
        finally:
            db.close()

    return stats


def sync_collections_for_connector(connector_id: str) -> list[dict]:
    """Reconcile all collections linked to a connector after catalog changes."""
    db = SharedSession()
    try:
        names = CollectionConnectorRepo.list_collection_names_for_connector(db, connector_id)
    finally:
        db.close()

    results = []
    for name in names:
        try:
            results.append(sync_collection(name))
        except Exception as exc:
            logger.exception("Collection sync failed for %s", name)
            results.append({"collection": name, "status": "error", "message": str(exc)})
    return results


def sync_all_monitored_collections() -> list[dict]:
    db = SharedSession()
    try:
        names = CollectionConnectorRepo.list_monitored_collection_names(db)
    finally:
        db.close()

    results = []
    for name in names:
        try:
            results.append(sync_collection(name))
        except Exception as exc:
            logger.exception("Collection sync failed for %s", name)
            results.append({"collection": name, "status": "error", "message": str(exc)})
    return results
