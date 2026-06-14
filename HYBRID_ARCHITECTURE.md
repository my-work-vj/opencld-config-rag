# Hybrid Configuration Architecture

Three layers work together:

| Layer | Role | Location |
|-------|------|----------|
| **Python strategies** | What each strategy *does* | `rag-ingestion-manager/strategies/`, `rag-query-manager/strategies/` |
| **YAML (dev/CI)** | Human-readable presets, Git review, seeding | `pipelines/*.yaml` |
| **PostgreSQL (runtime)** | Source of truth at query/ingest time | `rag_pipelines` table |

Both services read the **same database** (`POSTGRES_DB=rag_platform`). They never read YAML at runtime.

## Setup (with existing Docker containers)

Uses your running containers:

| Container | Service | Host endpoint |
|-----------|---------|---------------|
| `litellm` | LiteLLM proxy | `http://localhost:4000/v1` |
| `litellm_db` | PostgreSQL 16 | `localhost:5432` |
| `qdrant` | Qdrant | `localhost:6333` |

```bash
# 1. Create rag_platform DB in existing Postgres (once)
docker exec litellm_db psql -U llmproxy -d litellm -c "CREATE DATABASE rag_platform;"

# 2. Env files are at repo root + both service folders (POSTGRES_DB=rag_platform)
#    LITELLM_API_KEY=sk-vj  (must match a valid key in your LiteLLM proxy)

# 3. Seed pipelines from YAML → database
python scripts/seed_db.py

# 4. Start services
cd rag-ingestion-manager && python -m api.main   # :8081
cd rag-query-manager && python -m api.main       # :8082
```

Health check (all three should be true):

```bash
curl http://localhost:8081/api/v1/health
curl http://localhost:8082/api/v1/health
```

## Unified Pipeline YAML (`pipelines/`)

Each file defines **all stages** for both services:

```yaml
pipeline:
  id: default_rag              # primary key in DB
  name: Default RAG
  description: ...
  embedding_model: nvidia-embed
  chat_model: llama-3.3-70b-versatile
  reranker_model: rerank-english-v3.0
  llm_params:
    temperature: 0.3
  stages:
    ingestion:    { strategy, config }   # Project 1
    chunking:     { strategy, config }
    embedding:    { strategy, config }
    indexing:     { strategy, config }
    knowledge_store: { strategy, config }  # Project 2
    retrieval:    { strategy, config }
    reranking:    { strategy, config }
    response:     { strategy, config }
```

**Preset files:** `default_rag.yaml`, `naive_rag.yaml`, `vector_rag.yaml`, `hybrid_rag.yaml`

## Daily Workflows

### Developer adds a preset pipeline
1. Add `pipelines/my_pipeline.yaml`
2. Commit to Git (PR review)
3. Run `python scripts/seed_db.py` (or `POST /api/v1/pipelines/seed`)
4. Both services pick it up on next request

### User creates RAG via API (future UI)
```bash
curl -X POST http://localhost:8081/api/v1/pipelines \
  -H "Content-Type: application/json" \
  -d @new_pipeline.json
```

### User updates config at runtime
```bash
curl -X PATCH http://localhost:8082/api/v1/pipelines/default_rag \
  -H "Content-Type: application/json" \
  -d '{"llm_params": {"temperature": 0.9}}'
```

No redeploy. Next ingest/query uses the new config.

## API Endpoints (both services)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/pipelines` | List all pipelines from DB |
| GET | `/api/v1/pipelines/{id}` | Get one pipeline |
| POST | `/api/v1/pipelines` | Create pipeline (UI-driven) |
| PATCH | `/api/v1/pipelines/{id}` | Update pipeline |
| DELETE | `/api/v1/pipelines/{id}` | Delete pipeline |
| POST | `/api/v1/pipelines/seed` | Re-seed from `pipelines/*.yaml` |
| GET | `/api/v1/pipelines/{id}/resolved/ingestion` | Debug: ingestion stages only |
| GET | `/api/v1/pipelines/{id}/resolved/query` | Debug: query stages only |

## Runtime Execution

```
ingest/query request with pipeline_id
        │
        ▼
  PipelineRepo.get(id)     ← PostgreSQL
        │
        ▼
  loader.record_to_runtime_config()
    • filter stages (ingestion vs query)
    • sync knowledge_store.collection_name ← indexing.collection_name
    • inject embedding_model / chat_model / reranker_model aliases
        │
        ▼
  IngestionPipeline / QueryPipeline
```

## Shared Package

`rag_shared/` at repo root:
- `models.py` — `rag_pipelines`, `rag_pipeline_audit`
- `repo.py` — CRUD + audit log
- `loader.py` — DB → runtime config
- `seed.py` — YAML → DB
- `routes.py` — shared pipeline CRUD router

## End-to-End Example

```bash
# Seed
python scripts/seed_db.py

# Ingest (uses DB config for default_rag)
curl -X POST http://localhost:8081/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"source":"./rag-ingestion-manager/test_doc.txt","pipeline":"default_rag"}'

# Query
curl -X POST http://localhost:8082/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is this about?","pipeline":"default_rag"}'
```
