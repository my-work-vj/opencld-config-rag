"""Vector collection API — embedding, chunking, indexing configuration."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.db import SessionLocal
from core.models import DocumentRecord
from core.pipeline import IngestionPipeline
from rag_shared.collection_connector_repo import CollectionConnectorRepo
from rag_shared.collection_loader import load_collection_ingestion_config
from rag_shared.connector_file_repo import ConnectorFileRepo
from rag_shared.connector_repo import DataConnectorNotFoundError, DataConnectorRepo
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.indexed_document_repo import IndexedDocumentRepo
from rag_shared.knowledge_repo import KnowledgeSourceNotFoundError, KnowledgeSourceRepo
from rag_shared.models import KnowledgeSource
from rag_shared.schemas import (
    CollectionIngestFromConnectorRequest,
    CollectionList,
    CreateCollectionRequest,
    IndexedDocumentInfo,
    IndexedDocumentList,
    KnowledgeSourceInfo,
    UpdateCollectionRequest,
)
from rag_shared.slug import slugify_name
from rag_shared.defaults import (
    DEFAULT_INGESTION_STAGES,
    DEFAULT_QUERY_STAGES,
    INLINE_PIPELINE_ID,
    clone_stage_map,
)
from rag_shared.constants import INGESTION_STAGES, QUERY_STAGES

from connectors.google_drive import source_type_for_path
from connectors.pathway.container import container_to_host_path
from monitoring.qdrant_ops import delete_connector_file_vectors, ensure_qdrant_collection
from services.collection_sync_service import sync_collection, _run_connector_file_ingest, file_content_hash

router = APIRouter()
logger = logging.getLogger(__name__)


def _stage_dict_from_request(stage_map: dict) -> dict:
    return {
        name: {"strategy": cfg.strategy, "config": dict(cfg.config or {})}
        for name, cfg in stage_map.items()
    }


def _resolve_connector_ids(req: CreateCollectionRequest) -> list[str]:
    ids = list(req.data_connector_ids or [])
    if req.data_connector_id and req.data_connector_id not in ids:
        ids.insert(0, req.data_connector_id)
    return ids


def _collection_info(record: KnowledgeSource, db) -> KnowledgeSourceInfo:
    meta = record.metadata_json or {}
    ingestion_stages = meta.get("ingestion_stages") or {}
    query_stages = meta.get("query_stages") or {}
    connector_ids = CollectionConnectorRepo.ensure_legacy_links(db, record.name, meta)
    return KnowledgeSourceInfo(
        id=record.id,
        name=record.name,
        description=record.description or "",
        collection_name=record.collection_name,
        embedding_model=record.embedding_model or "",
        vector_size=record.vector_size or 2048,
        document_count=record.document_count or 0,
        chunk_count=record.chunk_count or 0,
        status=record.status or "ready",
        data_connector_id=connector_ids[0] if connector_ids else meta.get("data_connector_id"),
        data_connector_ids=connector_ids,
        monitor_enabled=bool(connector_ids),
        ingestion_stages=ingestion_stages,
        query_stages=query_stages,
        chat_model=meta.get("chat_model") or "",
        reranker_model=meta.get("reranker_model") or "",
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


def _build_ingestion_stages(req: CreateCollectionRequest, collection_name: str) -> dict:
    stages = clone_stage_map(DEFAULT_INGESTION_STAGES)
    for stage_name, cfg in _stage_dict_from_request(req.stages or {}).items():
        if stage_name in INGESTION_STAGES:
            stages[stage_name] = cfg
    stages["embedding"]["config"]["model"] = req.embedding_model
    stages["indexing"]["config"]["collection_name"] = collection_name
    stages["indexing"]["config"]["vector_size"] = req.vector_size
    stages["indexing"]["config"]["model"] = req.embedding_model
    return stages


def _build_query_stages(req: CreateCollectionRequest, collection_name: str) -> dict:
    stages = clone_stage_map(DEFAULT_QUERY_STAGES)
    for stage_name, cfg in _stage_dict_from_request(req.query_stages or {}).items():
        if stage_name in QUERY_STAGES:
            stages[stage_name] = cfg
    stages["knowledge_store"]["config"]["collection_name"] = collection_name
    stages["response"]["config"]["model"] = req.chat_model
    stages["reranking"]["config"]["model"] = req.reranker_model
    return stages


def _trigger_background_sync(collection_name: str) -> None:
    thread = threading.Thread(
        target=sync_collection,
        args=(collection_name,),
        name=f"sync-{collection_name}",
        daemon=True,
    )
    thread.start()


@router.get("/collections", response_model=CollectionList)
async def list_collections():
    db = SharedSession()
    try:
        records = KnowledgeSourceRepo.list_all(db)
        items = [_collection_info(r, db) for r in records]
        return CollectionList(collections=items, total=len(items))
    finally:
        db.close()


@router.get("/collections/monitor/status")
async def collection_monitor_status():
    from monitoring.worker import get_monitor_worker

    worker = get_monitor_worker()
    if not worker:
        return {
            "running": False,
            "interval_sec": None,
            "last_run_at": None,
            "connectors": [],
            "collections": [],
        }
    return {
        "running": worker._thread is not None and worker._thread.is_alive(),
        "interval_sec": worker.interval_sec,
        "last_run_at": worker.last_run_at,
        "connectors": worker.last_connector_results,
        "collections": worker.last_collection_results,
        "last_results": worker.last_collection_results,
    }


@router.get("/collections/{name}/documents", response_model=IndexedDocumentList)
async def list_collection_indexed_documents(name: str):
    db = SharedSession()
    try:
        KnowledgeSourceRepo.get(db, name)
        indexed = IndexedDocumentRepo.list_for_collection(db, name)
        documents: list[IndexedDocumentInfo] = []
        for record in indexed:
            connector_file = ConnectorFileRepo.get(db, record.connector_file_id)
            filename = connector_file.name if connector_file else record.external_id
            documents.append(
                IndexedDocumentInfo(
                    id=record.id,
                    connector_id=record.connector_id,
                    connector_file_id=record.connector_file_id,
                    external_id=record.external_id,
                    filename=filename,
                    chunk_count=record.chunk_count or 0,
                    indexed_at=record.indexed_at.isoformat() if record.indexed_at else None,
                )
            )
        return IndexedDocumentList(documents=documents, total=len(documents))
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.get("/collections/{name}", response_model=KnowledgeSourceInfo)
async def get_collection(name: str):
    db = SharedSession()
    try:
        record = KnowledgeSourceRepo.get(db, name)
        return _collection_info(record, db)
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/collections", response_model=KnowledgeSourceInfo, status_code=201)
async def create_collection(req: CreateCollectionRequest):
    connector_ids = _resolve_connector_ids(req)
    if not connector_ids:
        raise HTTPException(
            status_code=400,
            detail="Select at least one data source to create a monitored collection",
        )

    db = SharedSession()
    try:
        if db.query(KnowledgeSource).filter(KnowledgeSource.name == req.name).first():
            raise HTTPException(status_code=409, detail=f"Collection '{req.name}' already exists")

        for connector_id in connector_ids:
            DataConnectorRepo.get(db, connector_id)

        collection_name = req.collection_name or slugify_name(req.name)
        ingestion_stages = _build_ingestion_stages(req, collection_name)
        query_stages = _build_query_stages(req, collection_name)
        meta = {
            "data_connector_id": connector_ids[0],
            "data_connector_ids": connector_ids,
            "ingestion_stages": ingestion_stages,
            "query_stages": query_stages,
            "embedding_model": req.embedding_model,
            "chat_model": req.chat_model,
            "reranker_model": req.reranker_model,
            "vector_size": req.vector_size,
            "monitor_enabled": True,
        }

        record = KnowledgeSource(
            name=req.name,
            description=req.description,
            collection_name=collection_name,
            pipeline_id=INLINE_PIPELINE_ID,
            embedding_model=req.embedding_model,
            vector_size=req.vector_size,
            status="ready",
            document_count=0,
            chunk_count=0,
            metadata_json=meta,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        CollectionConnectorRepo.link_many(db, req.name, connector_ids)

        try:
            ensure_qdrant_collection(collection_name, vector_size=req.vector_size)
        except Exception as exc:
            logger.warning("Could not pre-create Qdrant collection '%s': %s", collection_name, exc)

        info = _collection_info(record, db)
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()

    _trigger_background_sync(req.name)
    return info


@router.patch("/collections/{name}", response_model=KnowledgeSourceInfo)
async def update_collection(name: str, req: UpdateCollectionRequest):
    db = SharedSession()
    try:
        record = KnowledgeSourceRepo.get(db, name)
        meta = dict(record.metadata_json or {})

        if req.description is not None:
            record.description = req.description
        if req.embedding_model is not None:
            record.embedding_model = req.embedding_model
            meta["embedding_model"] = req.embedding_model
        if req.vector_size is not None:
            record.vector_size = req.vector_size
            meta["vector_size"] = req.vector_size
        if req.chat_model is not None:
            meta["chat_model"] = req.chat_model
        if req.reranker_model is not None:
            meta["reranker_model"] = req.reranker_model

        if req.stages is not None:
            current = meta.get("ingestion_stages") or clone_stage_map(DEFAULT_INGESTION_STAGES)
            for stage_name, cfg in _stage_dict_from_request(req.stages).items():
                if stage_name in INGESTION_STAGES:
                    current[stage_name] = cfg
            current["embedding"]["config"]["model"] = record.embedding_model
            current["indexing"]["config"]["collection_name"] = record.collection_name
            current["indexing"]["config"]["vector_size"] = record.vector_size
            current["indexing"]["config"]["model"] = record.embedding_model
            meta["ingestion_stages"] = current

        if req.query_stages is not None:
            current = meta.get("query_stages") or clone_stage_map(DEFAULT_QUERY_STAGES)
            for stage_name, cfg in _stage_dict_from_request(req.query_stages).items():
                if stage_name in QUERY_STAGES:
                    current[stage_name] = cfg
            current["knowledge_store"]["config"]["collection_name"] = record.collection_name
            chat_model = meta.get("chat_model") or req.chat_model
            reranker_model = meta.get("reranker_model") or req.reranker_model
            if chat_model:
                current["response"]["config"]["model"] = chat_model
            if reranker_model:
                current["reranking"]["config"]["model"] = reranker_model
            meta["query_stages"] = current

        record.metadata_json = meta
        db.commit()
        db.refresh(record)
        return _collection_info(record, db)
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/collections/{name}/sync")
async def sync_collection_endpoint(name: str):
    try:
        return sync_collection(name)
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/collections/{name}", status_code=204)
async def delete_collection(name: str, delete_collection_vectors: bool = False):
    db = SharedSession()
    try:
        record = KnowledgeSourceRepo.get(db, name)
        collection_name = record.collection_name
        connector_ids = CollectionConnectorRepo.list_connector_ids(db, name)
        indexed = IndexedDocumentRepo.list_for_collection(db, name)
        for doc in indexed:
            delete_connector_file_vectors(collection_name, doc.connector_id, doc.external_id)
        IndexedDocumentRepo.delete_for_collection(db, name)
        CollectionConnectorRepo.delete_for_collection(db, name)
        KnowledgeSourceRepo.delete(db, name)
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()

    if delete_collection_vectors:
        try:
            import os
            from qdrant_client import QdrantClient
            qc = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
            )
            qc.delete_collection(collection_name)
        except Exception as exc:
            logger.warning("Could not delete Qdrant collection '%s': %s", collection_name, exc)


def _run_collection_ingest(name: str, source_path: str, source_type: str) -> dict:
    db = SharedSession()
    try:
        ks = KnowledgeSourceRepo.get(db, name)
        KnowledgeSourceRepo.set_status(db, name, "indexing")
        collection_name = ks.collection_name
        ks_name = ks.name
    finally:
        db.close()

    try:
        shared_db = SharedSession()
        try:
            config = load_collection_ingestion_config(shared_db, ks_name)
        finally:
            shared_db.close()

        if source_type == "pdf":
            config["pipeline"]["stages"]["ingestion"] = {
                "strategy": "pdf_ingestion",
                "config": {},
            }
        elif source_type == "web":
            config["pipeline"]["stages"]["ingestion"] = {
                "strategy": "web_ingestion",
                "config": {},
            }

        pipeline = IngestionPipeline(config)
        ctx = pipeline.run(
            source=source_path,
            indexing_overrides={"config": {"collection_name": collection_name}},
        )
    except Exception as exc:
        db = SharedSession()
        try:
            KnowledgeSourceRepo.set_status(db, ks_name, "error")
        finally:
            db.close()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    doc_count = len(ctx.documents)
    chunk_count = len(ctx.chunks)

    db = SharedSession()
    try:
        KnowledgeSourceRepo.increment_counts(db, ks_name, doc_count, chunk_count, status="ready")
    finally:
        db.close()

    try:
        local_db = SessionLocal()
        for doc in ctx.documents:
            record = DocumentRecord(
                filename=doc.filename or "unknown",
                pipeline_name=pipeline.name,
                collection_name=collection_name,
                chunk_count=len([c for c in ctx.chunks if c.document_id == doc.id]),
                content_preview=doc.content[:200],
                metadata_json={
                    **doc.metadata,
                    "collection_name": ks_name,
                    "ingest_source_path": source_path,
                },
            )
            local_db.add(record)
        local_db.commit()
        local_db.close()
    except Exception as exc:
        logger.warning("Could not save document metadata: %s", exc)

    return {
        "status": "success",
        "collection": ks_name,
        "document_count": doc_count,
        "chunk_count": chunk_count,
        "collection_name": collection_name,
        "timings": ctx.state.get("timings", {}),
    }


@router.post("/collections/{name}/ingest-from-connector")
async def ingest_collection_from_connector(name: str, req: CollectionIngestFromConnectorRequest):
    db = SharedSession()
    collection_name = ""
    try:
        ks = KnowledgeSourceRepo.get(db, name)
        collection_name = ks.collection_name
        connector_ids = CollectionConnectorRepo.ensure_legacy_links(db, name, ks.metadata_json)
        if not connector_ids:
            raise HTTPException(status_code=400, detail="Collection has no linked data sources")

        files = []
        for connector_id in connector_ids:
            DataConnectorRepo.get(db, connector_id)
            connector_files = ConnectorFileRepo.list_for_connector(db, connector_id)
            if req.file_ids:
                id_set = set(req.file_ids)
                connector_files = [f for f in connector_files if f.id in id_set]
            files.extend([(connector_id, f) for f in connector_files])
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()

    if not files:
        raise HTTPException(status_code=400, detail="No files available to ingest")

    results = []
    errors = []
    total_docs = 0
    total_chunks = 0

    for connector_id, f in files:
        path = Path(container_to_host_path(f.local_path))
        if not path.is_file():
            errors.append(f"{f.name}: file missing on disk")
            continue
        try:
            content_hash = file_content_hash(path)
            connector_metadata = {
                "connector_id": connector_id,
                "connector_file_id": f.id,
                "external_id": f.external_id,
                "filename": f.name,
                "qdrant_collection": collection_name,
            }
            existing = None
            db = SharedSession()
            try:
                existing = IndexedDocumentRepo.get_by_file_id(db, name, f.id)
                if existing:
                    delete_connector_file_vectors(
                        collection_name, existing.connector_id, existing.external_id
                    )
                    IndexedDocumentRepo.delete(db, existing.id)
            finally:
                db.close()

            source_type = source_type_for_path(path)
            result = _run_connector_file_ingest(name, str(path), source_type, connector_metadata)
            total_docs += result["document_count"]
            total_chunks += result["chunk_count"]

            db = SharedSession()
            try:
                IndexedDocumentRepo.upsert(
                    db,
                    knowledge_source_name=name,
                    connector_id=connector_id,
                    connector_file_id=f.id,
                    external_id=f.external_id,
                    content_hash=content_hash,
                    chunk_count=result["chunk_count"],
                    document_id=result.get("document_id"),
                )
                record = KnowledgeSourceRepo.get(db, name)
                record.document_count = IndexedDocumentRepo.count_for_collection(db, name)
                record.chunk_count = IndexedDocumentRepo.sum_chunks(db, name)
                record.status = "ready"
                db.commit()
            finally:
                db.close()

            results.append(result)
        except Exception as exc:
            errors.append(f"{f.name}: {exc}")

    return {
        "status": "success" if not errors else "partial",
        "files_processed": len(results),
        "document_count": total_docs,
        "chunk_count": total_chunks,
        "errors": errors,
    }
