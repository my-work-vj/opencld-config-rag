# Multi-RAG: Universal RAG-as-a-Service Deployment Guide

> **A production-ready ingestion & query pipeline** with automatic data source syncing (Pathway-powered), multi-index storage (dense/sparse vectors, graph, metadata, memory), and per-collection visualization.

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                   RAG INGESTION MANAGER (:8081)                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  FastAPI  │  IngestionPipeline  │  Strategies (plugin arch)  │  │
│  │           │  ┌──────────────┐   │  ┌──────────┐┌──────────┐ │  │
│  │  Routes   │  │kreuzberg_ing │   │  │qdrant_idx││bm25_sparse│ │  │
│  │           │  │multigranular │   │  │metadata  ││neo4j_graph │ │  │
│  │  Viz      │  │litellm_embed │   │  │memory_idx││...        │ │  │
│  └───────────┘  └──────────────┘   │  └──────────┘└──────────┘ │  │
└──────────────────────┬──────────────────────────────────────────-┘
                       │
     ┌─────────────────┼──────────────────┬──────────────────┐
     ▼                 ▼                  ▼                  ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Qdrant   │  │ PostgreSQL   │  │ Neo4j         │  │ Redis        │
│ :6333    │  │ :5432        │  │ :7687         │  │ :6379        │
│ (vectors)│  │ (metadata)   │  │ (graph)       │  │ (memory)     │
└──────────┘  └──────────────┘  └──────────────┘  └──────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                    INGESTION FRONTEND (:3001)                       │
│  React + Vite + Tailwind + React Query + React Router              │
│  Pages: Welcome, DataSources, Collections, Evaluation, KBs         │
│  Visualization modals: Graph ─ Dense Vectors ─ Sparse ─ Metadata   │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                   RAG QUERY MANAGER (:8082)                         │
│  FastAPI  │  Retrieval strategies  │  Reranking  │  Response gen   │
│  Query Frontend (:3002) — test RAG retrieval interactively          │
└────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  PATHWAY (Docker)                                   │ LiteLLM   │
│  Google Drive connector auto-sync                    │ :4000     │
└──────────────────────────────────────────────────────┴────────────┘
```

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Structure](#2-project-structure)
3. [Service Dependencies (Docker)](#3-service-dependencies-docker)
4. [Backend — RAG Ingestion Manager](#4-backend--rag-ingestion-manager)
5. [Frontend — Ingestion UI](#5-frontend--ingestion-ui)
6. [Query Side — Manager + Frontend](#6-query-side--manager--frontend)
7. [Pathway Auto-Sync](#7-pathway-auto-sync)
8. [API Endpoints Reference](#8-api-endpoints-reference)
9. [Visualization System](#9-visualization-system)
10. [Index Configuration System](#10-index-configuration-system)
11. [Usage Walkthrough](#11-usage-walkthrough)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

| Dependency      | Version  | Notes                                      |
|-----------------|----------|--------------------------------------------|
| Python          | ≥3.11    | Tested on 3.13                             |
| Node.js         | ≥20      | Tested on 20 LTS                           |
| Docker          | ≥24      | Required for Qdrant, Neo4j, Redis, Pathway |
| Docker Compose  | ≥2.20    | For Pathway container management           |
| uv              | ≥0.4     | (Optional) Faster pip alternative          |

## 2. Project Structure

```
multi-rag/
├── docker-compose.yml            # Pathway Docker service
├── reverse_proxy.py              # Optional multi-port reverse proxy
│
├── rag-ingestion-manager/        # 🎯 PRIMARY BACKEND
│   ├── api/main.py               # FastAPI entry with lifespan (DB, Pathway, monitoring init)
│   ├── api/routes/
│   │   ├── collections.py        # Collection CRUD + ingestion + visualization endpoints
│   │   ├── data_connectors.py    # Google Drive / connector management
│   │   ├── evaluation.py         # RAG evaluation endpoints
│   │   ├── knowledge_bases.py    # Knowledge base management
│   │   └── knowledge_sources.py  # Legacy knowledge sources
│   ├── core/
│   │   ├── pipeline.py           # IngestionPipeline orchestrator
│   │   ├── registry.py           # StrategyRegistry (plugin pattern)
│   │   ├── base_strategies.py    # Abstract base classes (Document, Chunk, etc.)
│   │   ├── db.py                 # SQLAlchemy engine + session
│   │   └── models.py             # DB models (DocumentRecord, etc.)
│   ├── strategies/
│   │   ├── ingestion/            # kreuzberg_ingestion, text_ingestion, pdf_ingestion, web_ingestion
│   │   ├── chunking/             # multigranularity, hierarchical, recursive_chunking
│   │   ├── embedding/            # litellm_embedding, bm25_sparse, hashing_sparse
│   │   └── indexing/             # qdrant_indexing, qdrant_sparse_indexing, metadata_indexing,
│   │                             # neo4j_graph, memory_indexing
│   ├── connectors/               # Data source connectors + Pathway Docker integration
│   ├── services/
│   │   ├── collection_sync_service.py
│   │   ├── connector_sync_service.py
│   │   └── evaluation_service.py
│   ├── monitoring/               # Background monitoring worker
│   ├── evaluation/               # RAG evaluation metrics
│   ├── config/                   # YAML pipeline presets
│   └── .env                      # 🔐 Environment variables
│
├── rag-ingestion-frontend/       # 🎯 PRIMARY FRONTEND
│   ├── src/
│   │   ├── pages/                # WelcomePage, CollectionsPage, CollectionDetailPage,
│   │   │                         # DataSourcesPage, EvaluationDashboardPage, KnowledgeBasesPage
│   │   ├── components/
│   │   │   ├── layout/AppShell.tsx
│   │   │   ├── visualization/    # FloatingModal, GraphVisualization, IndexVisualizations
│   │   │   └── ui/               # Button, Card, Badge, Feedback, Field
│   │   ├── lib/                  # api.ts (client), env.ts, poll.ts, stage-defaults.ts
│   │   └── types/api.ts          # TypeScript interfaces for all API responses
│   ├── package.json
│   └── vite.config.ts
│
├── rag-query-manager/            # QUERY BACKEND (:8082)
│   ├── api/routes/               # knowledge.py, prompts.py
│   ├── core/                     # pipeline.py, registry.py, agent_runner.py
│   └── strategies/
│       ├── retrieval/            # multi_collection.py
│       ├── reranking/            # pass_through, litellm_reranking
│       └── response/             # contextual_response
│
├── rag-query-frontend/           # QUERY FRONTEND (:3002)
│
└── rag_shared/                   # 📦 SHARED LIBRARY
    ├── schemas.py                # All Pydantic models (CreateCollectionRequest, etc.)
    ├── defaults.py               # DEFAULT_INGESTION_STAGES, DEFAULT_QUERY_STAGES
    ├── constants.py              # INGESTION_STAGES, QUERY_STAGES tuples
    ├── collection_loader.py      # Runtime config builder + index filtering
    ├── knowledge_repo.py         # KnowledgeSourceRepo (PostgreSQL ORM)
    ├── connector_repo.py         # DataConnectorRepo
    ├── collection_connector_repo.py
    ├── connector_file_repo.py
    ├── indexed_document_repo.py
    ├── db.py                     # Shared SQLAlchemy session
    ├── models.py                 # Shared ORM models
    ├── slug.py                   # Collection name slugifier
    └── seed.py                   # Database seeding
```

---

## 3. Service Dependencies (Docker)

All backing services run via Docker. Start them before the backend:

### 3.1 Qdrant (Vector Database)

```bash
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  qdrant/qdrant:latest
```

### 3.2 PostgreSQL (Metadata + App State)

```bash
docker run -d --name litellm_db \
  -p 5432:5432 \
  -e POSTGRES_USER=llmproxy \
  -e POSTGRES_PASSWORD=your-strong-password \
  -e POSTGRES_DB=rag_platform \
  postgres:16
```

### 3.3 Neo4j (Graph Index)

```bash
docker run -d --name neo4j \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_PLUGINS='["apoc"]' \
  neo4j:latest

# ⚠️ Change default password on first run:
docker exec -it neo4j cypher-shell -u neo4j -p neo4j \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'password';"
```

Verify: Open `http://localhost:7474` in a browser.

### 3.4 Redis (Memory Index)

```bash
docker run -d --name redis-rag \
  -p 6379:6379 \
  redis:alpine
```

Verify: `docker exec redis-rag redis-cli PING` → `PONG`

### 3.5 LiteLLM (AI Proxy)

LiteLLM is the model proxy for embedding and LLM calls.

```bash
docker run -d --name litellm \
  -p 4000:4000 \
  -e DATABASE_URL=postgresql://llmproxy:your-strong-password@host.docker.internal:5432/rag_platform \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml --port 4000 --detailed_response
```

### 3.6 One-Command Init

```bash
docker rm -f qdrant litellm_db neo4j redis-rag litellm 2>/dev/null

docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
docker run -d --name litellm_db -p 5432:5432 \
  -e POSTGRES_USER=llmproxy -e POSTGRES_PASSWORD=password -e POSTGRES_DB=rag_platform \
  postgres:16
docker run -d --name neo4j -p 7687:7687 -p 7474:7474 -e NEO4J_PLUGINS='["apoc"]' neo4j:latest
docker run -d --name redis-rag -p 6379:6379 redis:alpine

# Then after 30s, change neo4j password:
docker exec neo4j cypher-shell -u neo4j -p neo4j \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'password';"
```

---

## 4. Backend — RAG Ingestion Manager

### 4.1 Environment Setup

```bash
# Clone and cd
cd rag-ingestion-manager

# Create virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install redis  # for Memory index
uv pip install neo4j  # for Graph index (Python driver)
```

### 4.2 Configuration

Copy and edit `.env`:

```bash
cp .env.example .env
```

Minimum required `.env`:

```ini
API_PORT=8081

# LiteLLM
LITELLM_BASE_URL=http://host.docker.internal:4000/v1
LITELLM_API_KEY=sk-vj
EMBEDDING_MODEL=nvidia-embed

# Qdrant
QDRANT_HOST=host.docker.internal
QDRANT_PORT=6333

# PostgreSQL
POSTGRES_HOST=host.docker.internal
POSTGRES_PORT=5432
POSTGRES_USER=llmproxy
POSTGRES_PASSWORD=password
POSTGRES_DB=rag_platform

# Neo4j (graph index)
NEO4J_URI=bolt://host.docker.internal:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# Redis (memory index)
REDIS_HOST=host.docker.internal
REDIS_PORT=6379
REDIS_DB=0

# Pathway Docker
PATHWAY_DOCKER_IMAGE=pathwaycom/pathway:latest
PATHWAY_CONTAINER_NAME=opncld-rag-pathway
PATHWAY_DOCKER_TIMEOUT_SEC=900
CONNECTORS_DATA_DIR=./data/connectors
```

> **`host.docker.internal`** is used throughout so the Python backend (running on the host) and Docker containers can talk to each other. If running everything in Docker natively, use service names instead.

### 4.3 Database Initialization

```bash
# Seed the database with default pipelines, connectors, and prompt templates
PYTHONPATH="/path/to/multi-rag:$PYTHONPATH" ./.venv/bin/python scripts/seed_db.py
```

The backend also auto-initializes tables on startup via `init_db()`.

### 4.4 Start the Backend

```bash
PYTHONPATH="/path/to/multi-rag:$PYTHONPATH" ./.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8081
```

Expected startup log:

```
RAG Ingestion Manager starting (hybrid config: DB runtime)
PostgreSQL DB: rag_platform
LiteLLM: http://host.docker.internal:4000/v1
Qdrant: host.docker.internal:6333
Database tables initialized
Pathway Docker: Pathway container 'opncld-rag-pathway' is running
Stage 'ingestion': kreuzberg_ingestion, text_ingestion, pdf_ingestion, web_ingestion
Stage 'chunking': multigranularity, hierarchical
Stage 'embedding': litellm_embedding, bm25_sparse, hashing_sparse
Stage 'sparse_embedding': bm25_sparse, hashing_sparse
Stage 'indexing': qdrant_indexing, qdrant_sparse_indexing, metadata_indexing, memory_indexing, neo4j_graph
Application startup complete.
```

Verify: `curl http://localhost:8081/api/v1/health`

```json
{
  "status": "healthy",
  "llm_available": true,
  "qdrant_available": true,
  "postgres_available": true,
  "pathway_docker_ready": true
}
```

---

## 5. Frontend — Ingestion UI

### 5.1 Setup

```bash
cd rag-ingestion-frontend
npm install
```

### 5.2 Environment

```bash
cp .env.example .env
```

Minimal `.env`:

```env
VITE_API_BASE=http://localhost:8081/api/v1
```

### 5.3 Start

```bash
npm run dev
# → http://localhost:3001 (default)
```

The dev server proxies `/api/v1` (configured in `vite.config.ts`).

### 5.4 Pages

| Route                    | Description                                      |
|--------------------------|--------------------------------------------------|
| `/` or `/ingestion`      | Welcome page with service status                 |
| `/ingestion/collections` | Collections list with index tags                 |
| `/ingestion/collections/:name` | Collection detail with viz buttons + docs   |
| `/ingestion/data-sources` | Connector management (Google Drive etc.)        |
| `/ingestion/evaluation`  | Evaluation dashboard                             |
| `/ingestion/knowledge-bases` | Knowledge base cluster management           |

---

## 6. Query Side — Manager + Frontend

### 6.1 Query Backend

```bash
cd rag-query-manager
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt

cp .env.example .env  # Edit as needed

# Start
PYTHONPATH="/path/to/multi-rag:$PYTHONPATH" ./.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8082
```

### 6.2 Query Frontend

```bash
cd rag-query-frontend
npm install
npm run dev
# → http://localhost:3002
```

---

## 7. Pathway Auto-Sync

Pathway runs as a Docker container and continuously syncs Google Drive folders.

### 7.1 Start the Pathway Container

```bash
# The docker-compose.yml starts it:
docker compose up -d pathway

# Or the backend auto-starts it via bootstrap_pathway()
```

### 7.2 How It Works

1. **Connector created** via UI → Google Drive folder ID stored in DB
2. **Pathway script** (`connectors/pathway/scripts/gdrive_sync.py`) watches the folder
3. **Files are synced** to local disk at `rag-ingestion-manager/data/connectors/<uuid>/`
4. **Ingestion trigger**: When a collection sync is requested, the backend reads files from disk and runs them through the ingestion pipeline

### 7.3 Google Drive Connector Setup

1. Go to Google Cloud Console → Enable Google Drive API
2. Create a **Service Account** → Download `credentials.json`
3. Share your Drive folder with the service account email
4. In the UI: Data Sources → Add Connector → Google Drive → Upload credentials

---

## 8. API Endpoints Reference

### 8.1 Health

```
GET /api/v1/health
```

### 8.2 Collections

| Method | Endpoint                                         | Description                          |
|--------|--------------------------------------------------|--------------------------------------|
| GET    | `/api/v1/collections`                            | List all collections                 |
| POST   | `/api/v1/collections`                            | Create collection                    |
| GET    | `/api/v1/collections/{name}`                     | Get collection detail                |
| PATCH  | `/api/v1/collections/{name}`                     | Update collection                    |
| POST   | `/api/v1/collections/{name}/sync`                | Trigger sync from connectors         |
| POST   | `/api/v1/collections/{name}/ingest`              | Direct file upload ingestion         |
| GET    | `/api/v1/collections/{name}/documents`           | List indexed documents               |
| DELETE | `/api/v1/collections/{name}`                     | Delete collection                    |

### 8.3 Create a Collection (with index selection)

```json
POST /api/v1/collections
{
  "name": "my-docs",
  "description": "My document collection",
  "embedding_model": "nvidia-embed",
  "vector_size": 2048,
  "data_connector_ids": ["<connector-uuid>"],
  "metadata": {
    "index_config": {
      "vector": true,
      "sparse": true,
      "graph": false,
      "metadata": true,
      "memory": false
    }
  }
}
```

### 8.4 Visualization Endpoints

| Method | Endpoint                                            | Description                   |
|--------|-----------------------------------------------------|-------------------------------|
| GET    | `/api/v1/collections/{name}/visualize/graph`        | Neo4j graph data              |
| GET    | `/api/v1/collections/{name}/visualize/vectors`      | Dense vector stats + samples  |
| GET    | `/api/v1/collections/{name}/visualize/sparse`       | Sparse vector stats + samples |
| GET    | `/api/v1/collections/{name}/visualize/metadata`     | PostgreSQL metadata records   |
| GET    | `/api/v1/collections/{name}/visualize/memory`       | Redis memory store entries    |

### 8.5 Connectors

| Method | Endpoint                                                | Description                     |
|--------|---------------------------------------------------------|---------------------------------|
| GET    | `/api/v1/connector-types`                               | List available connector types  |
| POST   | `/api/v1/data-connectors`                               | Create connector                |
| GET    | `/api/v1/data-connectors`                               | List connectors                 |
| GET    | `/api/v1/data-connectors/{id}`                          | Get connector detail            |
| POST   | `/api/v1/data-connectors/{id}/sync`                     | Trigger sync                    |
| POST   | `/api/v1/data-connectors/{id}/test`                     | Test connector connectivity     |
| POST   | `/api/v1/data-connectors/{id}/upload`                   | Upload files to connector       |

---

## 9. Visualization System

The visualization system shows live data from each index type in floating-window modals.

### 9.1 How It Works

1. **Collection detail page** loads `index_config` from collection metadata
2. **Buttons are conditionally rendered** — only for enabled index types
3. **On click**, the frontend calls the corresponding visualization endpoint
4. **A floating modal** opens with live data rendered as stat cards + tables

### 9.2 Button Mapping

| Index Config Flag  | Button Label    | Viz Endpoint    | Backend Data Source |
|--------------------|-----------------|-----------------|---------------------|
| `vector: true`     | "Dense Vectors" | `/visualize/vectors` | Qdrant             |
| `sparse: true`     | "Sparse Vectors"| `/visualize/sparse`  | Qdrant (sparse)    |
| `graph: true`      | "Graph"         | `/visualize/graph`   | Neo4j              |
| `metadata: true`   | "Metadata"      | `/visualize/metadata`| PostgreSQL         |
| `memory: true`     | "Memory"        | `/visualize/memory`  | Redis              |

### 9.3 Color Legend

| Index        | Color   | Button Icon  |
|--------------|---------|--------------|
| Graph        | Cyan    | `GitBranch`  |
| Dense Vectors| Blue   | `Layers`     |
| Sparse Vectors| Violet| `Hash`       |
| Metadata     | Emerald | `Database`   |
| Memory       | Amber   | `Brain`      |

---

## 10. Index Configuration System

Collections have an `index_config` stored in `metadata_json` that controls:

1. **Which indexers run** during ingestion (filtered in `collection_loader.py`)
2. **Which viz buttons appear** in the frontend

### 10.1 Index Mapping

The mapping from `index_config` flags to indexing strategies lives in `rag_shared/collection_loader.py`:

```python
_INDEX_CONFIG_MAP = {
    "vector": "qdrant_dense",       # Qdrant dense vector indexer
    "sparse": "qdrant_sparse",      # Qdrant sparse/BM25 vector indexer
    "graph": "neo4j_graph",         # Neo4j graph entity/relation indexer
    "metadata": "metadata",         # PostgreSQL metadata indexer
    "memory": "memory_indexing",    # Redis memory store indexer
}
```

### 10.2 Filtering Logic

During ingestion pipeline config loading, `_filter_indexing_by_config()` removes disabled indexers:

```python
# In collection_loader.py
def _filter_indexing_by_config(stages, index_config, collection_name):
    indexing = stages.get("indexing")
    allowed = set()
    for flag, idx_key in _INDEX_CONFIG_MAP.items():
        if index_config.get(flag, False):
            allowed.add(idx_key)
    stages["indexing"] = {k: v for k, v in indexing.items() if k in allowed}
```

### 10.3 Default Ingestion Stages

When no custom stages are provided, the system uses `DEFAULT_INGESTION_STAGES` from `rag_shared/defaults.py`:

| Stage             | Strategy              | Details                          |
|-------------------|-----------------------|----------------------------------|
| `ingestion`       | `kreuzberg_ingestion` | Multi-format file extraction     |
| `chunking`        | `multigranularity`    | Size: 512 tokens, overlap: 50    |
| `embedding`       | `litellm_embedding`   | Uses `nvidia-embed` model        |
| `sparse_embedding`| `bm25_sparse`         | BM25 sparse vector generation    |
| `indexing`        | _(multi-index dict)_  | qdrant_dense, qdrant_sparse, neo4j_graph, metadata, memory_indexing |

---

## 11. Usage Walkthrough

### 11.1 First Launch

```bash
# 1. Start all Docker services
./start-all-services.sh  # or run each docker command manually

# 2. Start the ingestion backend
cd rag-ingestion-manager
source .venv/bin/activate
PYTHONPATH="/opt/data/my-hermes-projects/multi-rag:$PYTHONPATH" \
  uvicorn api.main:app --host 0.0.0.0 --port 8081

# 3. Start the ingestion frontend
cd rag-ingestion-frontend
npm run dev

# 4. Open http://localhost:3001
```

### 11.2 Create a Collection

1. Navigate to **Collections** → **New Collection**
2. Fill in:
   - Name: `my-collection`
   - Embedding model: `nvidia-embed`
   - Vector size: `2048`
   - Linked data source: _(select a connector)_
3. **Select indexes**: Vector, Sparse, Graph, Metadata, Memory
4. Click **Create** → Collection appears with summary

### 11.3 Sync & Ingest

1. Go to collection detail page
2. Click **Sync** → files are ingested through the pipeline
3. After syncing: document count and chunk count update

### 11.4 Visualize Indexes

1. On the collection detail page, locate **INDEX VISUALIZATIONS**
2. Click any enabled button → floating modal opens
3. **Dense Vectors**: Shows point count, vector dims, payload previews
4. **Metadata**: Shows document/chunk count, recent docs
5. **Graph**: Shows node/edge network (requires Neo4j)
6. **Sparse Vectors**: Shows sparse vector entries
7. **Memory**: Shows Redis key-value entries

### 11.5 Query

1. Open the Query Frontend at `http://localhost:3002`
2. Select a collection / knowledge base
3. Ask a question → RAG pipeline retrieves chunks and generates a response

---

## 12. Troubleshooting

### 12.1 Port Already in Use (EADDRINUSE)

```bash
# Find what's using port 8081
lsof -i :8081
# Kill it
kill -9 <PID>
```

### 12.2 Qdrant Connection Refused

```bash
# Check if container is running
docker ps | grep qdrant

# Check connectivity
curl http://localhost:6333/collections

# Try from inside Docker network
docker run --rm curlimages/curl:latest http://host.docker.internal:6333/collections
```

### 12.3 Neo4j Authorization

Neo4j requires password change on first launch:

```bash
docker exec neo4j cypher-shell -u neo4j -p neo4j \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'password';"
```

If you see `CredentialsExpired` in the viz endpoint, repeat the above.

### 12.4 Redis Module Not Found

```bash
cd rag-ingestion-manager
source .venv/bin/activate
uv pip install redis
# Restart backend
```

### 12.5 Pipeline Shows No Indexers

If `ingestion-config` returns empty indexing:

1. Check `index_config` in collection metadata
2. Verify flags match expected keys: `vector`, `sparse`, `graph`, `metadata`, `memory`
3. Check the collection has data synced first

### 12.6 Host.docker.internal Not Resolving

On Linux, Docker's `host.docker.internal` doesn't resolve by default. Add:

```bash
# In /etc/hosts or use extra_hosts in docker-compose
echo "172.17.0.1 host.docker.internal" | sudo tee -a /etc/hosts
```

Or set all `.env` hosts to `localhost` and run everything on host.

### 12.7 LiteLLM Not Available

```bash
# Test LiteLLM health
curl http://localhost:4000/health

# Check available models
curl http://localhost:4000/v1/models

# LiteLLM config.yaml (minimal)
echo 'model_list:
  - model_name: nvidia-embed
    litellm_params:
      model: openai/nvidia-embed
      api_key: sk-vj
' > config.yaml
```

---

## Appendix A: Quick-Start Script

```bash
#!/usr/bin/env bash
# start-all.sh — Start all services for Multi-RAG
set -e

PROJECT_ROOT="/opt/data/my-hermes-projects/multi-rag"

echo "=== Starting Docker Services ==="
docker rm -f qdrant litellm_db neo4j redis-rag 2>/dev/null

docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
docker run -d --name litellm_db -p 5432:5432 \
  -e POSTGRES_USER=llmproxy -e POSTGRES_PASSWORD=password -e POSTGRES_DB=rag_platform \
  postgres:16
docker run -d --name neo4j -p 7687:7687 -p 7474:7474 -e NEO4J_PLUGINS='["apoc"]' neo4j:latest
docker run -d --name redis-rag -p 6379:6379 redis:alpine

echo "=== Waiting for services (45s) ==="
sleep 45

echo "=== Setting Neo4j Password ==="
docker exec neo4j cypher-shell -u neo4j -p neo4j \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'password';" 2>/dev/null || true

echo "=== Starting Ingestion Backend ==="
cd "$PROJECT_ROOT/rag-ingestion-manager"
source .venv/bin/activate
PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" nohup uvicorn api.main:app \
  --host 0.0.0.0 --port 8081 > backend.log 2>&1 &
echo "Backend PID: $!"

echo "=== Starting Ingestion Frontend ==="
cd "$PROJECT_ROOT/rag-ingestion-frontend"
npm run dev > frontend.log 2>&1 &
echo "Frontend PID: $!"

echo "=== Done ==="
echo "Backend:  http://localhost:8081"
echo "Frontend: http://localhost:3001"
echo "API Docs: http://localhost:8081/docs"
```

---

## Appendix B: Environment Quick Reference

| Variable              | Default                    | Purpose                    |
|-----------------------|----------------------------|----------------------------|
| `API_PORT`            | `8081`                     | Backend server port        |
| `LITELLM_BASE_URL`    | `http://localhost:4000/v1` | LLM proxy endpoint         |
| `LITELLM_API_KEY`     | `sk-vj`                    | LiteLLM auth               |
| `EMBEDDING_MODEL`     | `nvidia-embed`             | Embedding model name       |
| `QDRANT_HOST`         | `localhost`                | Qdrant server host         |
| `QDRANT_PORT`         | `6333`                     | Qdrant gRPC/HTTP port      |
| `POSTGRES_HOST`       | `localhost`                | PostgreSQL host            |
| `POSTGRES_PORT`       | `5432`                     | PostgreSQL port            |
| `POSTGRES_USER`       | `llmproxy`                | DB user                    |
| `POSTGRES_DB`         | `rag_platform`            | DB name                    |
| `NEO4J_URI`           | `bolt://localhost:7687`    | Neo4j Bolt URI             |
| `NEO4J_USER`          | `neo4j`                    | Neo4j user                 |
| `NEO4J_PASSWORD`      | `password`                 | Neo4j password             |
| `NEO4J_DATABASE`      | `neo4j`                    | Neo4j database             |
| `REDIS_HOST`          | `localhost`                | Redis host                 |
| `REDIS_PORT`          | `6379`                     | Redis port                 |
| `REDIS_DB`            | `0`                        | Redis logical DB           |
| `PATHWAY_DOCKER_IMAGE`| `pathwaycom/pathway:latest`| Pathway Docker image       |
| `CONNECTORS_DATA_DIR` | `./data/connectors`        | Local connector data path  |
