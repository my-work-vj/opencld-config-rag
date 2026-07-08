"""Index configuration helpers — map UI flags to ingestion stages."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from rag_shared.defaults import DEFAULT_INGESTION_STAGES, clone_stage_map

INDEX_CONFIG_MAP: dict[str, str] = {
    "vector": "qdrant_dense",
    "sparse": "qdrant_sparse",
    "graph": "neo4j_graph",
    "metadata": "metadata",
    "memory": "memory_indexing",
}

DEFAULT_INDEX_CONFIG: dict[str, bool] = {
    "vector": True,
    "sparse": False,
    "graph": False,
    "metadata": True,
    "memory": False,
}


def normalize_index_config(raw: dict[str, Any] | None) -> dict[str, bool]:
    if not raw:
        return dict(DEFAULT_INDEX_CONFIG)
    return {
        "vector": bool(raw.get("vector", DEFAULT_INDEX_CONFIG["vector"])),
        "sparse": bool(raw.get("sparse", DEFAULT_INDEX_CONFIG["sparse"])),
        "graph": bool(raw.get("graph", DEFAULT_INDEX_CONFIG["graph"])),
        "metadata": bool(raw.get("metadata", DEFAULT_INDEX_CONFIG["metadata"])),
        "memory": bool(raw.get("memory", DEFAULT_INDEX_CONFIG["memory"])),
    }


def apply_index_config_to_stages(
    stages: dict[str, Any],
    index_config: dict[str, Any] | None,
    *,
    collection_name: str,
) -> dict[str, Any]:
    """Filter indexing stages and sparse_embedding based on index_config flags."""
    result = deepcopy(stages)
    flags = normalize_index_config(index_config)

    indexing = result.get("indexing")
    if not isinstance(indexing, dict):
        indexing = deepcopy(DEFAULT_INGESTION_STAGES.get("indexing", {}))
        result["indexing"] = indexing

    default_indexing = DEFAULT_INGESTION_STAGES.get("indexing", {})
    if index_config:
        allowed: set[str] = set()
        for flag, idx_key in INDEX_CONFIG_MAP.items():
            if flags.get(flag):
                allowed.add(idx_key)
        for idx_key in allowed:
            if idx_key not in indexing and idx_key in default_indexing:
                indexing[idx_key] = deepcopy(default_indexing[idx_key])
        result["indexing"] = {k: v for k, v in indexing.items() if k in allowed}
        for idx_name, idx_cfg in result.get("indexing", {}).items():
            if isinstance(idx_cfg, dict):
                idx_cfg.setdefault("config", {})
                idx_cfg["config"]["collection_name"] = collection_name

    if flags.get("sparse"):
        result.setdefault(
            "sparse_embedding",
            deepcopy(DEFAULT_INGESTION_STAGES["sparse_embedding"]),
        )
    else:
        result.pop("sparse_embedding", None)

    return result


def enabled_index_types(index_config: dict[str, Any] | None) -> list[str]:
    flags = normalize_index_config(index_config)
    return [name for name, enabled in flags.items() if enabled]
