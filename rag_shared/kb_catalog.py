"""Knowledge-base index catalog — profile snapshots for RAG Builder handoff."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from rag_shared.collection_connector_repo import CollectionConnectorRepo
from rag_shared.index_config import enabled_index_types, normalize_index_config
from rag_shared.knowledge_repo import KnowledgeSourceNotFoundError, KnowledgeSourceRepo


def build_profile_catalog(db: Session, source_name: str) -> dict[str, Any]:
    """Build a query-ready catalog entry from a live KnowledgeSource record."""
    ks = KnowledgeSourceRepo.get(db, source_name)
    meta = ks.metadata_json or {}
    index_config = normalize_index_config(meta.get("index_config"))
    connector_ids = CollectionConnectorRepo.list_connector_ids(db, source_name)
    if not connector_ids:
        connector_ids = list(meta.get("data_connector_ids") or [])
        legacy = meta.get("data_connector_id")
        if legacy and legacy not in connector_ids:
            connector_ids.insert(0, legacy)

    ingestion_mode = meta.get("ingestion_mode", "document_plain")
    enabled = enabled_index_types(index_config)

    return {
        "source_name": ks.name,
        "collection_name": ks.collection_name,
        "store_namespace": ks.collection_name,
        "vector_size": ks.vector_size or 2048,
        "embedding_model": ks.embedding_model or "",
        "index_config": index_config,
        "enabled_indexes": enabled,
        "ingestion_mode": ingestion_mode,
        "data_connector_ids": connector_ids,
        "status": ks.status or "ready",
        "document_count": ks.document_count or 0,
        "chunk_count": ks.chunk_count or 0,
        "monitor_enabled": bool(meta.get("monitor_enabled", True)),
        "modalities": _modalities_for_mode(ingestion_mode),
    }


def build_kb_index_catalog(db: Session, kb_name: str) -> dict[str, Any]:
    """Aggregate index catalog across all profiles in a knowledge base."""
    from rag_shared.knowledge_repo import KnowledgeBaseRepo

    kb = KnowledgeBaseRepo.get(db, kb_name)
    profiles: list[dict[str, Any]] = []
    aggregated_indexes: set[str] = set()
    connectors: set[str] = set()
    modalities: set[str] = set()

    for src in kb.sources or []:
        source_name = src.get("source_name")
        if not source_name:
            continue
        try:
            catalog = build_profile_catalog(db, source_name)
        except KnowledgeSourceNotFoundError:
            catalog = {
                "source_name": source_name,
                "collection_name": src.get("collection_name", source_name),
                "store_namespace": src.get("collection_name", source_name),
                "status": "missing",
                "enabled_indexes": [],
                "data_connector_ids": [],
                "modalities": [],
            }
        profiles.append(catalog)
        aggregated_indexes.update(catalog.get("enabled_indexes") or [])
        connectors.update(catalog.get("data_connector_ids") or [])
        modalities.update(catalog.get("modalities") or [])

    return {
        "knowledge_base": kb.name,
        "description": kb.description or "",
        "profile_count": len(profiles),
        "profiles": profiles,
        "aggregated_indexes": sorted(aggregated_indexes),
        "data_connector_ids": sorted(connectors),
        "modalities": sorted(modalities),
    }


def _modalities_for_mode(ingestion_mode: str) -> list[str]:
    if ingestion_mode == "document_vision":
        return ["text", "image", "text_image"]
    if ingestion_mode == "websites":
        return ["text", "web"]
    return ["text"]
