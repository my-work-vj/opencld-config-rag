"""Inline default RAG stage configuration — replaces YAML pipeline presets."""

from __future__ import annotations

from typing import Any

INLINE_PIPELINE_ID = "inline"

DEFAULT_EMBEDDING_MODEL = "nvidia-embed"
DEFAULT_CHAT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_RERANKER_MODEL = "rerank-english-v3.0"
DEFAULT_VECTOR_SIZE = 2048

DEFAULT_LLM_PARAMS: dict[str, Any] = {
    "temperature": 0.3,
    "max_tokens": 2048,
}

DEFAULT_INGESTION_STAGES: dict[str, dict[str, Any]] = {
    "ingestion": {"strategy": "pdf_ingestion", "config": {}},
    "chunking": {
        "strategy": "recursive_chunking",
        "config": {"chunk_size": 512, "chunk_overlap": 50},
    },
    "embedding": {
        "strategy": "litellm_embedding",
        "config": {"model": DEFAULT_EMBEDDING_MODEL},
    },
    "indexing": {
        "strategy": "qdrant_indexing",
        "config": {
            "collection_name": "rag_documents",
            "vector_size": DEFAULT_VECTOR_SIZE,
            "distance": "Cosine",
            "recreate": False,
            "model": DEFAULT_EMBEDDING_MODEL,
        },
    },
}

DEFAULT_QUERY_STAGES: dict[str, dict[str, Any]] = {
    "knowledge_store": {
        "strategy": "qdrant_store",
        "config": {"collection_name": "rag_documents", "validate": True},
    },
    "retrieval": {
        "strategy": "vector_rag",
        "config": {
            "top_k": 5,
            "top_k_rerank": 10,
            "query_rewrite": True,
            "use_hyde": True,
        },
    },
    "reranking": {
        "strategy": "litellm_reranking",
        "config": {"model": DEFAULT_RERANKER_MODEL, "top_k": 5},
    },
    "response": {
        "strategy": "contextual_response",
        "config": {
            "model": DEFAULT_CHAT_MODEL,
            "temperature": 0.3,
            "max_tokens": 2048,
            "system_prompt": (
                "You are a helpful RAG assistant. Answer based ONLY on the provided context.\n"
                "If the context doesn't contain enough information, say so clearly.\n"
                "Cite sources using [source: filename] notation."
            ),
        },
    },
}


def clone_stage_map(stages: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "strategy": cfg.get("strategy", ""),
            "config": dict(cfg.get("config") or {}),
        }
        for name, cfg in stages.items()
    }
