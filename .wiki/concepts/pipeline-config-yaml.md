---
title: pipeline-config-yaml
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [architecture, yaml, config]
sources: [HYBRID_ARCHITECTURE.md, PROJECT_GUIDE.md]
---

# Pipeline Config YAML

YAML pipeline blueprints define every stage of the RAG pipeline. They live in `pipelines/` at the repo root and are seeded into PostgreSQL at deploy time.

## Structure

```yaml
pipeline:
  id: default_rag
  name: Default RAG
  description: Simple dense retrieval, no rewriting, no reranking
  embedding_model: nvidia-embed
  chat_model: llama-3.3-70b-versatile
  reranker_model: rerank-english-v3.0
  llm_params:
    temperature: 0.3
  stages:
    ingestion:   { strategy: text_ingestion,   config: {...} }
    chunking:    { strategy: recursive_chunking, config: { chunk_size: 1000, overlap: 200 } }
    embedding:   { strategy: litellm_embedding, config: {} }
    indexing:    { strategy: qdrant_indexing,   config: { collection_name: rag_documents } }
    knowledge_store: { strategy: qdrant_store, config: { collection_name: rag_documents } }
    retrieval:   { strategy: naive_rag,         config: { top_k: 5 } }
    reranking:   { strategy: pass_through,      config: {} }
    response:    { strategy: contextual_response, config: { temperature: 0.3 } }
```

## Preset Files

| File | Retrieval Strategy | Quality | Speed |
|------|-------------------|---------|-------|
| `naive_rag.yaml` | Dense only | Low | Fastest |
| `vector_rag.yaml` | HyDE + reranking | Medium | Medium |
| `hybrid_rag.yaml` | BM25 + dense + RRF + reranking | Best | Slowest |

## Workflow

```
Developer edits YAML → commits to Git → PR review →
   python scripts/seed_db.py (or POST /api/v1/pipelines/seed)
   → Both services pick it up on next request
```

## Runtime Resolution
1. `PipelineRepo.get(id)` reads from PostgreSQL
2. `loader.record_to_runtime_config()` filters stages (ingestion vs query), injects model aliases
3. `IngestionPipeline` / `QueryPipeline` assembles strategy objects from the resolved config

No redeploy needed — next ingest/query uses the new config immediately.
