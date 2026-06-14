# Split Architecture: Ingestion + Query

The original `multi-rag-manager` is split into two **independent** services that share **Qdrant** (vectors) and **PostgreSQL** (`rag_platform`, `rag_pipelines`). See [HYBRID_ARCHITECTURE.md](HYBRID_ARCHITECTURE.md).

## Projects

| Project | Port | Responsibility |
|---------|------|----------------|
| `rag-ingestion-manager` | 8081 | ingestion → chunking → embedding → indexing |
| `rag-query-manager` | 8082 | knowledge_store → retrieval → reranking → response |

## Contract Between Services

- **Ingestion** writes vectors to a Qdrant collection (default: `rag_documents`).
- **Query** reads from the same collection via the `knowledge_store` pipeline stage.
- No direct HTTP coupling — deploy, scale, and version independently.

## YAML Pipeline Shape

### Ingestion (`rag-ingestion-manager/config/`)

```yaml
pipeline:
  name: default_ingestion
  stages:
    ingestion:   { strategy, config }
    chunking:    { strategy, config }
    embedding:   { strategy, config }
    indexing:    { strategy, config }
```

### Query (`rag-query-manager/config/`)

```yaml
pipeline:
  name: default_query
  stages:
    knowledge_store: { strategy, config }  # NEW stage
    retrieval:       { strategy, config }
    reranking:       { strategy, config }
    response:        { strategy, config }
```

## Run Both Services

```bash
# Terminal 1 — Ingestion
cd rag-ingestion-manager
pip install -r requirements.txt
cp .env.example .env
python -m api.main

# Terminal 2 — Query
cd rag-query-manager
pip install -r requirements.txt
cp .env.example .env
python -m api.main
```

## End-to-End Flow

```bash
# 1. Ingest documents (port 8081)
curl -X POST http://localhost:8081/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"source":"./test_doc.txt","pipeline":"default_rag"}'

# 2. Query (port 8082)
curl -X POST http://localhost:8082/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is this about?","pipeline":"default_rag"}'

# 3. Compare retrieval strategies
curl -X POST http://localhost:8082/api/v1/compare \
  -H "Content-Type: application/json" \
  -d '{"query":"...","pipelines":["naive_rag","vector_rag","hybrid_rag"]}'
```

## Adding Strategies

Same pattern in both projects:

1. Create `strategies/<stage>/your_strategy.py`
2. Subclass the stage base class
3. Decorate with `@StrategyRegistry.register("<stage>", "<name>")`
4. Import the module in `api/main.py`
5. Reference in a YAML config — no core code changes

## Legacy

`multi-rag-manager/` remains as the original monolith for reference. New work should use the split projects.
