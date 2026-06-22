---
title: rag-ingestion-manager
created: 2026-06-19
updated: 2026-06-19
type: entity
tags: [services, ingestion, api]
sources: [HYBRID_ARCHITECTURE.md, SPLIT_ARCHITECTURE.md, PROJECT_GUIDE.md]
---

# rag-ingestion-manager

Ingestion microservice — handles the pipeline stages **before** vectors are stored.

## Overview
- **Port:** 8081
- **Language:** Python (FastAPI)
- **Path:** `rag-ingestion-manager/`
- **DB:** Reads/writes `rag_platform` PostgreSQL (shared with query service)

## Pipeline Stages
1. **Ingestion** — text, PDF, web sources (strategy-based)
2. **Chunking** — recursive or fixed-size with overlap
3. **Embedding** — via LiteLLM proxy (default `nvidia-embed`)
4. **Indexing** — writes vectors to Qdrant collection (default: `rag_documents`)

## Key Files
| File | Purpose |
|------|---------|
| `api/main.py` | FastAPI app entry |
| `config/default_ingestion.yaml` | Default pipeline blueprint |
| `core/pipeline.py` | Pipeline runner |
| `strategies/` | Pluggable strategy classes per stage |

## API Endpoints
- `GET /api/v1/health`
- `GET /api/v1/pipelines`
- `POST /api/v1/pipelines` — create
- `POST /api/v1/pipelines/seed` — reseed from YAML
- `POST /api/v1/ingest` — ingest documents

## Dependencies
- [[qdrant]] for vector storage
- [[rag_shared]] for models & CRUD
- [[rag-ingestion-frontend]] for UI
