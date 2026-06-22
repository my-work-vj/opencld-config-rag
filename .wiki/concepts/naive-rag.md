---
title: naive-rag
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [retrieval, naive]
sources: [strategies/retrieval/__init__.py]
---

# Naive RAG

Dense vector search only — the simplest retrieval strategy.

## Config
```yaml
retrieval:
  strategy: naive_rag
  config:
    top_k: 5
```

## How It Works
1. Query is embedded via the same LiteLLM model used during ingestion
2. Dense vector search against the Qdrant collection
3. Ranking by cosine similarity to the query embedding

## Characteristics
- **Speed:** Fastest retrieval
- **Quality:** Lowest — no query expansion, no reranking
- **Use case:** Quick RAG demos, when latency matters more than quality
