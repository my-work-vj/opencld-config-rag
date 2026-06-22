---
title: data-model
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [architecture, data]
sources: [rag_shared/models.py, rag_shared/schemas.py]
---

# Data Model

The Multi‑RAG platform uses **PostgreSQL** as its runtime source of truth and **Qdrant** as the vector store.

## PostgreSQL Tables

| Table | Purpose |
|-------|---------|
| `rag_pipelines` | Unified pipeline configs (ingestion + query stages) — seeded from YAML |
| `knowledge_sources` | Named Qdrant collections with per-collection stage configs |
| `knowledge_bases` | Groups of knowledge sources queried together |
| `agents` | Named query agents (LLM + prompt + knowledge target + strategies) |
| `prompt_templates` / `prompt_versions` | Versioned system prompt templates |
| `data_connectors` | External data sources (Google Drive) — connection + credentials |
| `connector_files` | File catalog synced from connectors |
| `collection_connectors` | Many-to-many mapping: collections ↔ connectors |
| `indexed_documents` | Tracks which connector files have been indexed (for incremental sync) |
| `rag_pipeline_audit` | Audit trail for pipeline config changes |

## Core Flow

### Knowledge Source (Collection)
A `knowledge_source` IS a Qdrant collection. It stores:
- `name`, `collection_name` (Qdrant), `embedding_model`, `vector_size`, `status`
- `metadata_json` — JSON blob holding **ingestion_stages** ([[pipeline-config-yaml]]) and **query_stages**

### Agent
An `agent` is a query configuration that bundles:
- **Knowledge target** — one or more `knowledge_bases` (which group `knowledge_sources`)
- **Prompt** — inline system prompt or versioned `prompt_template`
- **LLM model** — via LiteLLM proxy
- **Strategies** — `retrieval_strategy`, `reranking_strategy`, `response_strategy`
