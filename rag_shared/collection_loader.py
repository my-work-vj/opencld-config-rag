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
            # Multi-index format for indexing: dict of {index_name: {strategy, config}}
            # Detect by checking if "strategy" key exists at the top level
            if stage_name == "indexing" and "strategy" not in cfg:
                # Multi-index format — pass through as-is
                stages[stage_name] = dict(cfg)
            else:
                stages[stage_name] = {
                    "strategy": cfg.get("strategy", ""),
                    "config": dict(cfg.get("config") or {}),
                }
    if "indexing" in stages:
        config = stages["indexing"]
        if "strategy" in config:
            # Single-index format
            c = config["config"]
            c["collection_name"] = collection_name
            if embedding_model:
                c.setdefault("model", embedding_model)
            if vector_size:
                c.setdefault("vector_size", vector_size)
        else:
            # Multi-index format — inject collection_name into each sub-index
            for idx_name, idx_cfg in config.items():
                if isinstance(idx_cfg, dict):
                    idx_cfg.setdefault("config", {})
                    idx_cfg["config"]["collection_name"] = collection_name
                    if embedding_model:
                        idx_cfg["config"].setdefault("model", embedding_model)
                    if vector_size:
                        idx_cfg["config"].setdefault("vector_size", vector_size)
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
        stages = _stages_from_metadata(
            raw,
            collection_name=record.collection_name,
            embedding_model=record.embedding_model or DEFAULT_EMBEDDING_MODEL,
            vector_size=record.vector_size or 2048,
            chat_model=meta.get("chat_model") or DEFAULT_CHAT_MODEL,
            reranker_model=meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
            allowed=INGESTION_STAGES,
        )
    else:
        defaults = clone_stage_map(DEFAULT_INGESTION_STAGES)
        stages = _stages_from_metadata(
            defaults,
            collection_name=record.collection_name,
            embedding_model=record.embedding_model or DEFAULT_EMBEDDING_MODEL,
            vector_size=record.vector_size or 2048,
            chat_model=meta.get("chat_model") or DEFAULT_CHAT_MODEL,
            reranker_model=meta.get("reranker_model") or DEFAULT_RERANKER_MODEL,
            allowed=INGESTION_STAGES,
        )
    # Filter indexing stages to only those enabled in index_config
    _filter_indexing_by_config(stages, meta.get("index_config", {}), record.collection_name)
    return stages


# Mapping from index_config flag → indexing stage key name
_INDEX_CONFIG_MAP: dict[str, str] = {
    "vector": "qdrant_dense",
    "sparse": "qdrant_sparse",
    "graph": "neo4j_graph",
    "metadata": "metadata",
    "memory": "memory_indexing",
}


def _filter_indexing_by_config(
    stages: dict[str, Any],
    index_config: dict[str, Any],
    collection_name: str,
) -> None:
    """Remove indexing strategies that are not enabled in index_config."""
    indexing = stages.get("indexing")
    if not isinstance(indexing, dict):
        return
    if not index_config:
        # No config means all indexes should run (backward compat)
        return
    allowed: set[str] = set()
    for flag, idx_key in _INDEX_CONFIG_MAP.items():
        if index_config.get(flag, False):
            allowed.add(idx_key)
    # Add memory_indexing if it's not already in the defaults but is enabled
    if index_config.get("memory") and "memory_indexing" not in indexing:
        indexing["memory_indexing"] = {
            "strategy": "memory_indexing",
            "config": {"collection_name": collection_name},
        }
    # Filter: keep only enabled index stages
    stages["indexing"] = {k: v for k, v in indexing.items() if k in allowed}



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
