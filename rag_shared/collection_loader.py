"""Build ingestion and query runtime config from a collection (knowledge source) record."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from rag_shared.constants import INGESTION_STAGES, QUERY_STAGES
from rag_shared.defaults import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_INGESTION_STAGES,
    DEFAULT_QUERY_STAGES,
    DEFAULT_RERANKER_MODEL,
    clone_stage_map,
)
from rag_shared.knowledge_repo import KnowledgeSourceNotFoundError, KnowledgeSourceRepo
from rag_shared.loader import _apply_model_aliases, _sync_collection_name


def _stages_from_metadata(
    raw: dict[str, Any],
    *,
    collection_name: str,
    embedding_model: str,
    vector_size: int,
    chat_model: str,
    reranker_model: str,
    allowed: tuple[str, ...],
) -> dict[str, Any]:
    stages: dict[str, Any] = {}
    for stage_name in allowed:
        if stage_name in raw:
            cfg = raw[stage_name]
            stages[stage_name] = {
                "strategy": cfg.get("strategy", ""),
                "config": dict(cfg.get("config") or {}),
            }
    if "indexing" in stages:
        stages["indexing"]["config"]["collection_name"] = collection_name
        if embedding_model:
            stages["indexing"]["config"].setdefault("model", embedding_model)
        if vector_size:
            stages["indexing"]["config"].setdefault("vector_size", vector_size)
    if "embedding" in stages and embedding_model:
        stages["embedding"]["config"].setdefault("model", embedding_model)
    if "knowledge_store" in stages:
        stages["knowledge_store"]["config"]["collection_name"] = collection_name
    if "response" in stages and chat_model:
        stages["response"]["config"].setdefault("model", chat_model)
    if "reranking" in stages and reranker_model:
        stages["reranking"]["config"].setdefault("model", reranker_model)
    return _sync_collection_name(stages)


def _ingestion_stages_for_record(record) -> dict[str, Any]:
    meta = record.metadata_json or {}
    raw = meta.get("ingestion_stages")
    if raw:
        return _stages_from_metadata(
            raw,
            collection_name=record.collection_name,
            embedding_model=record.embedding_model or DEFAULT_EMBEDDING_MODEL,
            vector_size=record.vector_size or 2048,
            chat_model=meta.get("chat_model") or DEFAULT_CHAT_MODEL,
            reranker_model=meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
            allowed=INGESTION_STAGES,
        )
    defaults = clone_stage_map(DEFAULT_INGESTION_STAGES)
    return _stages_from_metadata(
        defaults,
        collection_name=record.collection_name,
        embedding_model=record.embedding_model or DEFAULT_EMBEDDING_MODEL,
        vector_size=record.vector_size or 2048,
        chat_model=meta.get("chat_model") or DEFAULT_CHAT_MODEL,
        reranker_model=meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
        allowed=INGESTION_STAGES,
    )


def _query_stages_for_record(record) -> dict[str, Any]:
    meta = record.metadata_json or {}
    raw = meta.get("query_stages")
    if raw:
        return _stages_from_metadata(
            raw,
            collection_name=record.collection_name,
            embedding_model=record.embedding_model or DEFAULT_EMBEDDING_MODEL,
            vector_size=record.vector_size or 2048,
            chat_model=meta.get("chat_model") or DEFAULT_CHAT_MODEL,
            reranker_model=meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
            allowed=QUERY_STAGES,
        )
    defaults = clone_stage_map(DEFAULT_QUERY_STAGES)
    return _stages_from_metadata(
        defaults,
        collection_name=record.collection_name,
        embedding_model=record.embedding_model or DEFAULT_EMBEDDING_MODEL,
        vector_size=record.vector_size or 2048,
        chat_model=meta.get("chat_model") or DEFAULT_CHAT_MODEL,
        reranker_model=meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
        allowed=QUERY_STAGES,
    )


def _runtime_shell(record, stages: dict[str, Any]) -> dict[str, Any]:
    meta = record.metadata_json or {}
    return {
        "pipeline": {
            "id": f"collection:{record.name}",
            "name": record.name,
            "description": record.description or "",
            "stages": stages,
            "embedding_model": record.embedding_model or DEFAULT_EMBEDDING_MODEL,
            "chat_model": meta.get("chat_model") or DEFAULT_CHAT_MODEL,
            "reranker_model": meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
            "llm_params": meta.get("llm_params") or {},
            "status": "active",
        }
    }


def load_collection_ingestion_config(db: Session, collection_name: str) -> dict[str, Any]:
    """Load ingestion config for a collection from its stored stage settings."""
    try:
        record = KnowledgeSourceRepo.get(db, collection_name)
    except KnowledgeSourceNotFoundError as exc:
        raise exc

    stages = _ingestion_stages_for_record(record)
    config = _runtime_shell(record, stages)
    config["pipeline"]["stages"] = _sync_collection_name(config["pipeline"]["stages"])
    return config


def load_collection_query_config(db: Session, collection_name: str) -> dict[str, Any]:
    """Load query config for a collection from its stored stage settings."""
    try:
        record = KnowledgeSourceRepo.get(db, collection_name)
    except KnowledgeSourceNotFoundError as exc:
        raise exc

    stages = _query_stages_for_record(record)
    meta = record.metadata_json or {}
    shell = {
        "id": f"collection:{record.name}",
        "name": record.name,
        "description": record.description or "",
        "stages": stages,
        "embedding_model": record.embedding_model or DEFAULT_EMBEDDING_MODEL,
        "chat_model": meta.get("chat_model") or DEFAULT_CHAT_MODEL,
        "reranker_model": meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
        "llm_params": meta.get("llm_params") or {},
        "status": "active",
    }
    stages = _apply_model_aliases(
        type("Record", (), shell)(),
        stages,
    )
    stages = _sync_collection_name(stages)
    return _runtime_shell(record, stages)
