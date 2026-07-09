"""Vector collection API — embedding, chunking, indexing configuration."""

from __future__ import annotations

import logging
import os
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
from rag_shared.index_config import apply_index_config_to_stages, normalize_index_config
from rag_shared.constants import INGESTION_STAGES, QUERY_STAGES

from connectors.google_drive import source_type_for_path
from connectors.pathway.container import container_to_host_path
from monitoring.index_ops import delete_document_from_all_indexes, ensure_collection_indexes
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
        metadata=meta,
        chat_model=meta.get("chat_model") or "",
        reranker_model=meta.get("reranker_model") or "",
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


def _build_ingestion_stages(
    req: CreateCollectionRequest,
    collection_name: str,
    index_config: dict | None = None,
) -> dict:
    stages = clone_stage_map(DEFAULT_INGESTION_STAGES)
    for stage_name, cfg in _stage_dict_from_request(req.stages or {}).items():
        if stage_name in INGESTION_STAGES:
            stages[stage_name] = cfg
    stages["embedding"]["config"]["model"] = req.embedding_model

    indexing = stages.get("indexing", {})
    if "strategy" in indexing:
        indexing["config"]["collection_name"] = collection_name
        indexing["config"]["vector_size"] = req.vector_size
        indexing["config"]["model"] = req.embedding_model
    else:
        for idx_name, idx_cfg in indexing.items():
            if isinstance(idx_cfg, dict):
                idx_cfg.setdefault("config", {})
                idx_cfg["config"]["collection_name"] = collection_name
                idx_cfg["config"]["vector_size"] = req.vector_size
                idx_cfg["config"]["model"] = req.embedding_model

    if index_config:
        stages = apply_index_config_to_stages(
            stages,
            index_config,
            collection_name=collection_name,
        )
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
        index_config = (req.metadata or {}).get("index_config") if req.metadata else None
        ingestion_stages = _build_ingestion_stages(req, collection_name, index_config)
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
        if req.metadata:
            meta.update(req.metadata)
        if index_config:
            meta["index_config"] = index_config

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
            index_status = ensure_collection_indexes(
                collection_name,
                vector_size=req.vector_size,
                index_config=meta.get("index_config"),
            )
            logger.info("Index provisioning for '%s': %s", collection_name, index_status)
        except Exception as exc:
            logger.warning("Could not provision indexes for '%s': %s", collection_name, exc)

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
    should_resync = False
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
            # Handle both single-index and multi-index indexing stage config
            indexing = current.get("indexing", {})
            if "strategy" in indexing:
                indexing["config"]["collection_name"] = record.collection_name
                indexing["config"]["vector_size"] = record.vector_size
                indexing["config"]["model"] = record.embedding_model
            else:
                for idx_name, idx_cfg in indexing.items():
                    if isinstance(idx_cfg, dict):
                        idx_cfg.setdefault("config", {})
                        idx_cfg["config"]["collection_name"] = record.collection_name
                        idx_cfg["config"]["vector_size"] = record.vector_size
                        idx_cfg["config"]["model"] = record.embedding_model
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

        if req.metadata is not None:
            old_index_config = normalize_index_config(meta.get("index_config"))
            old_ingestion_mode = meta.get("ingestion_mode", "document_plain")
            meta.update(req.metadata)
            if "ingestion_mode" in req.metadata:
                new_ingestion_mode = req.metadata.get("ingestion_mode", "document_plain")
                if new_ingestion_mode != old_ingestion_mode:
                    indexed = IndexedDocumentRepo.list_for_collection(db, name)
                    for doc in indexed:
                        doc.content_hash = ""
                        doc.chunk_count = 0
                    db.commit()
                    should_resync = True
            if "index_config" in req.metadata:
                new_index_config = normalize_index_config(req.metadata["index_config"])
                current_stages = meta.get("ingestion_stages") or clone_stage_map(DEFAULT_INGESTION_STAGES)
                meta["ingestion_stages"] = apply_index_config_to_stages(
                    current_stages,
                    req.metadata["index_config"],
                    collection_name=record.collection_name,
                )
                meta["index_config"] = new_index_config
                try:
                    index_status = ensure_collection_indexes(
                        record.collection_name,
                        vector_size=record.vector_size or 2048,
                        index_config=new_index_config,
                    )
                    logger.info(
                        "Index provisioning for '%s' after config update: %s",
                        record.collection_name,
                        index_status,
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not provision indexes for '%s': %s",
                        record.collection_name,
                        exc,
                    )
                if old_index_config != new_index_config:
                    indexed = IndexedDocumentRepo.list_for_collection(db, name)
                    for doc in indexed:
                        doc.content_hash = ""
                        doc.chunk_count = 0
                    db.commit()
                    should_resync = True

        record.metadata_json = meta
        db.commit()
        db.refresh(record)
        info = _collection_info(record, db)
    except KnowledgeSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        db.close()

    if should_resync:
        _trigger_background_sync(name)
    return info


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
        index_config = (record.metadata_json or {}).get("index_config")
        connector_ids = CollectionConnectorRepo.list_connector_ids(db, name)
        indexed = IndexedDocumentRepo.list_for_collection(db, name)
        for doc in indexed:
            delete_document_from_all_indexes(
                collection_name,
                name,
                doc.connector_id,
                doc.external_id,
                index_config,
            )
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
    from services.ingestion_router import resolve_pipeline_overrides

    db = SharedSession()
    try:
        ks = KnowledgeSourceRepo.get(db, name)
        KnowledgeSourceRepo.set_status(db, name, "indexing")
        collection_name = ks.collection_name
        ks_name = ks.name
        meta = ks.metadata_json or {}
        ingestion_mode = meta.get("ingestion_mode", "document_plain")
    finally:
        db.close()

    try:
        shared_db = SharedSession()
        try:
            config = load_collection_ingestion_config(shared_db, ks_name)
        finally:
            shared_db.close()

        ingestion_overrides, chunking_overrides = resolve_pipeline_overrides(
            source_path,
            ingestion_mode=ingestion_mode,
            source_type=source_type,
        )

        if not ingestion_overrides:
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
            ingestion_overrides=ingestion_overrides,
            chunking_overrides=chunking_overrides,
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
                ks = KnowledgeSourceRepo.get(db, name)
                index_config = (ks.metadata_json or {}).get("index_config")
                existing = IndexedDocumentRepo.get_by_file_id(db, name, f.id)
                if existing:
                    delete_document_from_all_indexes(
                        collection_name,
                        name,
                        existing.connector_id,
                        existing.external_id,
                        index_config,
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


# ── Index Visualization ────────────────────────────────────────

def _resolve_qdrant_collection(name: str) -> str:
    """Resolve the display name to the internal Qdrant collection_name."""
    db = SharedSession()
    try:
        try:
            record = KnowledgeSourceRepo.get(db, name)
            return record.collection_name
        except KnowledgeSourceNotFoundError:
            return name
    finally:
        db.close()

@router.get("/collections/{name}/visualize/graph")
async def visualize_graph(name: str):
    """Return nodes and edges from Neo4j for the given collection."""
    qname = _resolve_qdrant_collection(name)
    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as e:
        logger.warning(f"Neo4j connection failed: {e}")
        raise HTTPException(status_code=503, detail=f"Neo4j unavailable: {e}")
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (n {collection_name: $name}) OPTIONAL MATCH (n)-[r]->(m {collection_name: $name}) RETURN n, r, m",
                name=qname,
            )
            node_ids: set[int] = set()
            edge_ids: set[int] = set()
            nodes_map: dict[int, dict] = {}
            edges: list[dict] = []
            for record in result:
                n = record.get("n")
                r = record.get("r")
                m = record.get("m")
                if n:
                    nid = n.get("id", id(n))
                    if nid not in node_ids:
                        node_ids.add(nid)
                        nodes_map[nid] = {"id": nid, "labels": list(n.labels) if hasattr(n, "labels") else [], "properties": dict(n)}
                if m:
                    mid = m.get("id", id(m))
                    if mid not in node_ids:
                        node_ids.add(mid)
                        nodes_map[mid] = {"id": mid, "labels": list(m.labels) if hasattr(m, "labels") else [], "properties": dict(m)}
                if r and n and m:
                    eid = id(r)
                    if eid not in edge_ids:
                        edge_ids.add(eid)
                        edges.append({"id": eid, "source": n.get("id", id(n)), "target": m.get("id", id(m)), "type": r.type if hasattr(r, "type") else str(type(r)), "properties": dict(r)})
            if not nodes_map:
                count_result = session.run("MATCH (n {collection_name: $name}) RETURN count(n) as c", name=qname).single()
                return {"nodes": [], "edges": [], "message": f"No graph data for collection '{qname}'", "node_count": count_result["c"] if count_result else 0, "edge_count": 0}
            return {"nodes": list(nodes_map.values()), "edges": edges, "node_count": len(nodes_map), "edge_count": len(edges), "collection_name": qname}
    except Exception as e:
        logger.error(f"Neo4j query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        driver.close()


@router.get("/collections/{name}/visualize/vectors")
async def visualize_vectors(name: str):
    """Return Qdrant collection stats and sample points for dense vectors."""
    qname = _resolve_qdrant_collection(name)
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=int(os.getenv("QDRANT_PORT", "6333")))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")
    try:
        try:
            info = qc.get_collection(qname)
        except Exception:
            matched = [c.name for c in qc.get_collections().collections if qname.lower() in c.name.lower()]
            if matched:
                qname = matched[0]
                info = qc.get_collection(qname)
            else:
                return {"available": False, "collections": [c.name for c in qc.get_collections().collections], "message": f"Collection '{name}' not found"}
        scroll = qc.scroll(collection_name=qname, limit=10, with_vectors=True, with_payload=True)
        points = scroll[0] if scroll else []
        samples = []
        for p in points:
            vec = p.vector
            vi = _preview_vectors(vec)
            samples.append({"id": str(p.id), "vector_dims": vi, "payload": {k: str(v)[:200] for k, v in (p.payload or {}).items()}})
        cfg = info.config if hasattr(info, "config") else {}
        params = {}
        if hasattr(cfg, "params"):
            params = {"vectors": str(cfg.params.vectors) if hasattr(cfg.params, "vectors") else "N/A", "sparse_vectors": str(cfg.params.sparse_vectors) if hasattr(cfg.params, "sparse_vectors") else None}
        return {
            "available": True, "name": qname,
            "points_count": getattr(info, "points_count", 0), "vectors_count": getattr(info, "vectors_count", 0),
            "status": getattr(info, "status", "unknown"), "config": params,
            "sample_points": samples, "sample_count": len(samples),
        }
    except Exception as e:
        logger.error(f"Qdrant query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{name}/visualize/sparse")
async def visualize_sparse(name: str):
    """Return Qdrant sparse vector data for the collection."""
    qname = _resolve_qdrant_collection(name)
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=int(os.getenv("QDRANT_PORT", "6333")))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")
    try:
        try:
            info = qc.get_collection(qname)
        except Exception:
            matched = [c.name for c in qc.get_collections().collections if qname.lower() in c.name.lower()]
            if matched:
                qname = matched[0]
                info = qc.get_collection(qname)
            else:
                return {"available": False, "message": f"Collection '{name}' not found"}
        has_sparse = False
        if hasattr(info, "config") and hasattr(info.config, "params") and hasattr(info.config.params, "sparse_vectors"):
            has_sparse = info.config.params.sparse_vectors is not None
        samples = []
        if has_sparse:
            scroll = qc.scroll(collection_name=qname, limit=5, with_vectors=True, with_payload=True)
            for p in scroll[0] if scroll else []:
                vec = p.vector
                if isinstance(vec, dict) and "sparse" in vec:
                    sv = vec["sparse"]
                    if hasattr(sv, "indices") and hasattr(sv, "values"):
                        samples.append({"id": str(p.id), "sparse_indices": len(sv.indices), "sparse_values": len(sv.values), "non_zero": min(len(sv.indices), 20)})
        return {"available": has_sparse, "name": qname, "points_count": getattr(info, "points_count", 0), "sparse_config": str(has_sparse), "sample_sparse_entries": samples, "sample_count": len(samples)}
    except Exception as e:
        logger.error(f"Sparse query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{name}/visualize/metadata")
async def visualize_metadata(name: str):
    """Return metadata records from PostgreSQL for the collection."""
    qname = _resolve_qdrant_collection(name)
    try:
        from sqlalchemy import create_engine, text
        pg_user = os.getenv("POSTGRES_USER", "rag_user")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "rag_pass")
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_db = os.getenv("POSTGRES_DB", "rag_platform")
        engine = create_engine(f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PostgreSQL unavailable: {e}")
    try:
        with engine.connect() as conn:
            docs = [dict(r._mapping) for r in conn.execute(text("SELECT id, filename, chunk_count, created_at FROM documents WHERE collection_name = :name ORDER BY created_at DESC LIMIT 20"), {"name": qname})]
            doc_count = conn.execute(text("SELECT COUNT(*) FROM documents WHERE collection_name = :name"), {"name": qname}).scalar() or 0
            chunk_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM chunks c "
                    "JOIN documents d ON c.document_id = d.id "
                    "WHERE d.collection_name = :name"
                ),
                {"name": qname},
            ).scalar() or 0
            chunks = [
                dict(r._mapping)
                for r in conn.execute(
                    text(
                        "SELECT c.chunk_index, c.chunk_level, LENGTH(c.content) AS content_length "
                        "FROM chunks c "
                        "JOIN documents d ON c.document_id = d.id "
                        "WHERE d.collection_name = :name "
                        "ORDER BY c.chunk_index LIMIT 10"
                    ),
                    {"name": qname},
                )
            ]
            return {
                "available": True,
                "collection_name": qname,
                "document_count": doc_count,
                "chunk_count": chunk_count,
                "documents": [{k: str(v)[:150] for k, v in d.items()} for d in docs],
                "sample_chunks": [{k: str(v)[:120] for k, v in c.items()} for c in chunks],
            }
    except Exception as e:
        logger.error(f"PostgreSQL query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{name}/visualize/memory")
async def visualize_memory(name: str):
    """Return memory store data from Redis for the collection."""
    qname = _resolve_qdrant_collection(name)
    try:
        import redis as redis_mod
        rh = os.getenv("REDIS_HOST", "localhost")
        rp = int(os.getenv("REDIS_PORT", "6379"))
        rpwd = os.getenv("REDIS_PASSWORD", None)
        kwargs = {"host": rh, "port": rp, "decode_responses": True}
        if rpwd: kwargs["password"] = rpwd
        r = redis_mod.Redis(**kwargs)
        r.ping()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {e}")
    try:
        doc_keys = r.keys(f"rag:doc:{qname}:*")
        memory_keys = r.keys(f"rag:memory:{qname}:*")
        keys = list(dict.fromkeys([*doc_keys, *memory_keys]))
        entries = []
        for k in keys[:50]:
            ks = str(k)
            try:
                entries.append({"key": ks, "value": str(r.get(k))[:200], "type": r.type(ks), "ttl": r.ttl(k)})
            except Exception:
                pass
        return {"available": True, "collection_name": qname, "total_keys": len(keys), "entries": entries}
    except Exception as e:
        logger.error(f"Redis query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _short_vec(v, max_len: int = 10) -> dict:
    """Convert a dense vector to a short numeric preview."""
    if v is None:
        return {"length": 0, "preview": []}
    if hasattr(v, "indices") and hasattr(v, "values"):
        indices = list(v.indices) if hasattr(v.indices, "__iter__") else []
        return {"type": "sparse", "non_zero": len(indices), "indices_preview": indices[:max_len]}
    if hasattr(v, "tolist"):
        v = v.tolist()
    if isinstance(v, dict):
        return {k: _short_vec(val, max_len) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        preview = []
        for x in v[:max_len]:
            if isinstance(x, (int, float)):
                preview.append(round(float(x), 6))
            elif isinstance(x, (list, tuple)) and x:
                preview.append(round(float(x[0]), 6))
            else:
                preview.append(str(x)[:20])
        return {"length": len(v), "preview": preview}
    try:
        return {"length": 1, "preview": [round(float(v), 6)]}
    except (TypeError, ValueError):
        return {"length": 0, "preview": [], "raw": str(v)[:80]}


def _preview_vectors(vec, max_len: int = 10) -> dict:
    """Build a visualization-friendly preview for Qdrant point vectors."""
    if vec is None:
        return {}
    if isinstance(vec, dict):
        return {k: _short_vec(v, max_len) for k, v in vec.items()}
    return {"dense": _short_vec(vec, max_len)}
