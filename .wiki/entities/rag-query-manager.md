---
title: rag-query-manager
created: 2026-06-19
updated: 2026-06-19
type: entity
tags: [services, query, api]
sources: [HYBRID_ARCHITECTURE.md, SPLIT_ARCHITECTURE.md]
---

# rag-query-manager

Query microservice — handles retrieval, reranking, and response generation.

## Overview
- **Port:** 8082
- **Language:** Python (FastAPI)
- **Path:** `rag-query-manager/`
- **DB:** Reads `rag_platform` PostgreSQL (read-only for pipeline config)

## Pipeline Stages
1. **knowledge_store** — selects Qdrant collection by pipeline config
2. **Retrieval** — dense / HyDE / multi‑query / BM25 / RRF fusion
3. **Reranking** — pass‑through or LiteLLM cross‑encoder reranking
4. **Response** — contextual LLM response with source citations

## Key Files
| File | Purpose |
|------|---------|
| `api/main.py` | FastAPI app entry |
| `config/default_query.yaml` | Default pipeline blueprint |
| `core/pipeline.py` | Pipeline runner |
| `strategies/` | Pluggable strategy classes |

## API Endpoints
- `GET /api/v1/health`
- `GET /api/v1/pipelines`
- `POST /api/v1/query` — run a query against a pipeline
- `POST /api/v1/compare` — compare multiple pipelines side by side
- `GET /api/v1/logs` — query history
- `GET /knowledge-sources` — read-only, for KB UI

## Dependencies
- [[rag_shared]] for models & CRUD
- [[rag-ingestion-manager]] for vector data (indirect)
- [[rag-query-frontend]] for UI
