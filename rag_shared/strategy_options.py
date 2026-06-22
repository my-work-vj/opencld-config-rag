"""Known strategy options per stage for UI pickers."""

from __future__ import annotations

from typing import Any

STAGE_STRATEGY_OPTIONS: dict[str, list[str]] = {
    "ingestion": ["kreuzberg_ingestion", "text_ingestion", "pdf_ingestion", "web_ingestion"],
    "chunking": ["recursive_chunking", "fixed_size_chunking"],
    "embedding": ["litellm_embedding"],
    "indexing": ["qdrant_indexing"],
    "knowledge_store": ["qdrant_store"],
    "retrieval": ["vector_rag", "naive_rag", "hybrid_bm25_vector", "multi_collection"],
    "reranking": ["pass_through", "litellm_reranking"],
    "response": ["contextual_response"],
}


def merge_strategy_options(registry: dict[str, list[str]]) -> dict[str, list[str]]:
    """Merge live registry strategies with static catalog (union, stable order)."""
    merged: dict[str, list[str]] = {}
    for stage, options in STAGE_STRATEGY_OPTIONS.items():
        live = registry.get(stage, [])
        seen: set[str] = set()
        ordered: list[str] = []
        for name in [*live, *options]:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        merged[stage] = ordered
    for stage, live in registry.items():
        if stage not in merged:
            merged[stage] = live
    return merged
