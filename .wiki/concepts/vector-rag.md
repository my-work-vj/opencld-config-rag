---
title: vector-rag
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [retrieval, hyde, query-rewrite]
sources: [strategies/retrieval/__init__.py]
---

# Vector RAG

Dense search with **HyDE** (Hypothetical Document Embeddings) and **query expansion**.

## Config
```yaml
retrieval:
  strategy: vector_rag
  config:
    top_k: 5
    query_rewrite: true
    use_hyde: true
    multi_query: true
    hyde_chat_model: llama-3.3-70b-versatile
```

## How It Works
1. **Query Rewriting** — LLM rewrites the user query to be more search-friendly
2. **HyDE** — LLM generates a hypothetical answer document, then embeds *that* (not the raw query) for retrieval — bridges the query-document vocabulary gap
3. **Multi-Query** — generates multiple query variants and searches each
4. **Fusion** — merges results from all query variants, deduplicates by content hash

## Characteristics
- **Speed:** Medium (calls LLM for query rewriting/HyDE generation)
- **Quality:** Better than [[naive-rag]] — handles vocabulary mismatch
- **Use case:** Standard RAG where quality matters over raw speed
