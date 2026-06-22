---
title: hybrid-rag
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [retrieval, bm25, rrf, hybrid]
sources: [strategies/retrieval/__init__.py]
---

# Hybrid RAG (BM25 + Dense + RRF Fusion)

The highest-quality retrieval strategy — combines dense vectors with a **BM25 sparse index** and fuses results via **Reciprocal Rank Fusion (RRF)**.

## Config
```yaml
retrieval:
  strategy: hybrid_bm25_vector
  config:
    top_k: 5
    dense_weight: 0.5
    sparse_weight: 0.5
    rrf_k: 60
    sparse_top_k: 15
```

## How It Works
1. **BM25 Index** — built at query time from all chunks in the collection (tokenized by regex `\w+`, standard BM25 scoring with k1=1.5, b=0.75)
2. **Dense Search** — query → embedding → vector search in Qdrant
3. **Sparse Search** — query → BM25 scoring against the built index
4. **RRF Fusion** — combines both rankings:
   ```
   RRF_score(d) = dense_weight/(k + rank_dense(d)) + sparse_weight/(k + rank_sparse(d))
   ```
5. **Reranking** — optional LiteLLM cross-encoder reranker on the fused results

## Characteristics
- **Speed:** Slowest (requires building BM25 index + two searches + fusion)
- **Quality:** Best — catches semantic matches via vectors AND keyword matches via BM25
- **Use case:** Production RAG, domain-specific search where recall matters

## Key Components
- `BM25Index` — in-process BM25 scorer (no external dependency)
- `reciprocal_rank_fusion()` — RRF fusion function with configurable k and per-method weights
- Results deduplicated by content prefix to avoid showing the same chunk from both pipelines
