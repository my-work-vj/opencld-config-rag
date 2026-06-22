---
title: strategy-registry-pattern
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [architecture, pattern, strategy]
sources: [PROJECT_GUIDE.md]
---

# Strategy Registry Pattern

The Multi‑RAG platform uses the **Strategy pattern** with a decorator-based registry to make every pipeline stage pluggable.

## How It Works

1. Each stage has a **base class** (e.g., `BaseChunking`)
2. Concrete implementations subclass the base and are registered via `@StrategyRegistry.register("<stage>", "<name>")`
3. YAML configs reference strategy by name — no core code changes needed

```python
@StrategyRegistry.register("chunking", "recursive_chunking")
class RecursiveChunking(BaseChunking):
    def chunk(self, document, config):
        ...
```

## Available Strategies

| Stage | Strategies |
|-------|-----------|
| Ingestion | `text_ingestion`, `pdf_ingestion`, `web_ingestion` |
| Chunking | `recursive_chunking`, `fixed_size_chunking` |
| Embedding | `litellm_embedding` |
| Indexing | `qdrant_indexing` |
| Retrieval | `naive_rag`, `vector_rag` (HyDE), `hybrid_bm25_vector` (BM25 + dense + RRF) |
| Reranking | `pass_through`, `litellm_reranking` |
| Response | `contextual_response` |

## Where to Add a New Strategy
1. Create `strategies/<stage>/your_strategy.py`
2. Subclass the stage base class
3. Decorate with `@StrategyRegistry.register("<stage>", "<name>")`
4. Import the module in `api/main.py`
5. Reference in a YAML config — done
