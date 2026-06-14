# Multi‑RAG Manager – Implementation Overview & Run Guide

## Overview
The **Multi‑RAG Manager** provides a pluggable retrieval‑augmented generation (RAG) pipeline using the Strategy pattern. Three retrieval strategies are available:

1. **Naive RAG** – dense vector search only.
2. **Vector RAG** – dense search with optional HyDE (hypothetical document) and query‑expansion.
3. **Hybrid RAG** – combines dense vectors and a BM25 sparse index with Reciprocal Rank Fusion (RRF).

Each stage (ingestion → chunking → embedding → indexing → retrieval → reranking → response) is implemented as a separate strategy class under `strategies/` and registered via `@StrategyRegistry.register`.

## Features
- **Strategy‑based pipeline** – swap any stage at runtime.
- **Multiple ingestion sources** – plain‑text, PDF, web pages.
- **Chunking** – recursive or fixed‑size with overlap.
- **Embedding** – unified LiteLLM proxy (default `llama‑3.3‑70b‑versatile`).
- **Indexing** – Qdrant vector store (singleton client).
- **Retrieval** – dense, HyDE, multi‑query, BM25 sparse, RRF fusion.
- **Reranking** – LiteLLM rerank endpoint.
- **Response generation** – contextual LLM response with source citations.
- **Docker‑ready** – services run on standard ports (LiteLLM 4000, PostgreSQL 5432, Qdrant 6333).

## Prerequisites
- **Docker** (>= 27) and **Docker Compose**.
- **Python 3.12** with a virtual environment (`.venv`).
- Environment variables (see `.env.example`):
  ```
  LLM_MODEL=llama-3.3-70b-versatile
  EMBEDDING_MODEL=nvidia-embed
  QDRANT_HOST=localhost
  QDRANT_PORT=6333
  POSTGRES_HOST=localhost
  POSTGRES_PORT=5432
  LITELLM_PROXY_URL=http://localhost:4000
  ```

## Setup & Installation
```bash
# Clone repo and cd into project
git clone <repo-url> && cd opncld-rag

# Create virtual environment and install deps
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy env file and adjust values if needed
cp .env.example .env
```

## Run Services (Docker)
```bash
# Start LiteLLM proxy, PostgreSQL, and Qdrant
docker compose up -d
```
- Verify containers are up: `docker ps` should show ports 4000, 5432, 6333.

## Initialise Database & Index
```bash
# Apply any migrations (if using Alembic – adapt as needed)
alembic upgrade head

# Optional: pre‑load test documents
python scripts/ingest_demo.py  # loads test_doc.txt, PDFs, etc.
```

## Launch the API Server
```bash
uvicorn api.main:app --reload
```
- The FastAPI docs are available at `http://localhost:8000/docs`.

## Pipeline Configuration (YAML)

The `multi-rag-manager/config/` folder contains **pipeline blueprints** — YAML files that define which strategy to use at each of the 7 pipeline stages and what parameters to pass. This makes the RAG pipeline fully configurable without touching any code.

### Files

| File | Retrieval Strategy | Description |
|---|---|---|
| `default_pipeline.yaml` | `naive_rag` | Simple dense retrieval, no rewriting, no reranking — fastest |
| `naive_rag_pipeline.yaml` | `naive_rag` | Same as default (explicit alias) |
| `vector_rag_pipeline.yaml` | `vector_rag` | HyDE query expansion + LiteLLM cross-encoder reranking |
| `hybrid_rag_pipeline.yaml` | `hybrid_bm25_vector` | BM25 + dense vector with RRF fusion + reranking — best quality |

### Structure

Every YAML follows the same shape:

```yaml
pipeline:
  name: <pipeline_name>
  description: <human-readable description>
  stages:
    ingestion:       # text_ingestion / pdf_ingestion / web_ingestion
    chunking:        # recursive_chunking / fixed_size_chunking
    embedding:       # litellm_embedding
    indexing:        # qdrant_indexing
    retrieval:       # naive_rag / vector_rag / hybrid_bm25_vector
    reranking:       # pass_through / litellm_reranking
    response:        # contextual_response
```

Each stage declares a `strategy` name and a `config` dict. The config keys are passed as `**kwargs` to that strategy's methods at runtime.

### How they are loaded

On server startup (`main.py`), the framework scans `config/*.yaml`, parses each file into a `PipelineConfig` object, and registers them in an in-memory registry. When you call `POST /api/v1/query` with `"pipeline": "hybrid"`, the API loads the corresponding YAML blueprint, assembles a `RAGPipeline` from it, and runs each stage sequentially.

The `default_pipeline.yaml` acts as the fallback when no explicit pipeline name is provided (e.g. during `/ingest` when `pipeline` is omitted from the request body).

## API Usage
All API endpoints are prefixed with **`/api/v1`**. The base URL for the running server is `http://localhost:8000`.

### Health Check
**Endpoint:** `GET /api/v1/health`  
Returns status of LLM, Qdrant, PostgreSQL and a count of pipelines.

```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

### List Pipelines
**Endpoint:** `GET /api/v1/pipelines`  
Lists all pipeline configuration files.

```bash
curl -X GET "http://localhost:8000/api/v1/pipelines"
```

### Get a Specific Pipeline
**Endpoint:** `GET /api/v1/pipelines/{name}`  
Details for a pipeline.

```bash
curl -X GET "http://localhost:8000/api/v1/pipelines/naive"
```

### List Strategies
**Endpoint:** `GET /api/v1/strategies`  
Shows strategies grouped by stage.

```bash
curl -X GET "http://localhost:8000/api/v1/strategies"
```

### Ingest Documents
**Endpoint:** `POST /api/v1/ingest`  

**PDF ingestion example:**

```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
        "strategy": "pdf_ingestion",
        "source": "C:/Users/2782234/Downloads/res",
        "source_type": "pdf"
      }'
```

**Text ingestion example:**

```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
        "strategy": "text_ingestion",
        "source": "C:/Users/2782234/Downloads/res",
        "source_type": "text"
      }'
```

Successful response:

```json
{
  "document_count": 3,
  "chunk_count": 27,
  "embedding_count": 27,
  "pipeline": "default",
  "status": "success"
}
```

### Run a Query
**Endpoint:** `POST /api/v1/query`  

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
        "pipeline": "hybrid",
        "query": "What are the benefits of hybrid retrieval?",
        "top_k": 5,
        "dense_weight": 0.6,
        "sparse_weight": 0.4,
        "rrf_k": 60,
        "sparse_top_k": 15
      }'
```

Response includes `answer`, `chunks`, `metadata`, etc.

### Compare Pipelines
**Endpoint:** `POST /api/v1/compare`

```bash
curl -X POST "http://localhost:8000/api/v1/compare" \
  -H "Content-Type: application/json" \
  -d '{
        "pipelines": ["naive", "vector", "hybrid"],
        "query": "Explain RRF fusion",
        "top_k": 5
      }'
```

### Retrieve Query Logs
**Endpoint:** `GET /api/v1/logs` (optional `pipeline` query param)

```bash
curl -X GET "http://localhost:8000/api/v1/logs?limit=10&pipeline=hybrid"
```

## Quick End‑to‑End Example

```bash
# 1️⃣ Ingest PDFs
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{"strategy":"pdf_ingestion","source":"C:/Users/2782234/Downloads/res","source_type":"pdf"}'

# 2️⃣ Query the hybrid pipeline
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"pipeline":"hybrid","query":"Summarize the key points","top_k":3}'
```

## Troubleshooting
- **Qdrant connection errors** – ensure the container is running and `QDRANT_HOST`/`PORT` match.
- **LiteLLM 4000 unreachable** – verify the proxy container logs; the model name must exist in LiteLLM’s config.
- **Missing environment vars** – `source .env` again or set them in your shell.
- **Docker port conflicts** – stop any other services using 4000/5432/6333 or change the ports in `docker-compose.yml` and update `.env`.

--- 

*This guide reflects the current implementation state as of 2026‑06‑08.*