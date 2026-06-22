---
title: split-architecture
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [architecture, pattern]
sources: [SPLIT_ARCHITECTURE.md, HYBRID_ARCHITECTURE.md]
---

# Split Architecture

The Multi‑RAG platform splits the original monolith into two independent services.

## Motivation
- Independent deploy & scale — ingestion can be batch/scheduled, query is latency-sensitive
- Clear ownership boundaries
- No direct HTTP coupling between services (share data layer only)

## How It Works
```
┌──────────────────────┐     ┌──────────────────────┐
│  rag-ingestion-manager│     │  rag-query-manager    │
│  :8081               │     │  :8082                │
│                      │     │                       │
│  ingest → chunk →    │     │  retrieve → rerank →  │
│  embed → index       │     │  respond               │
└──────┬───────────────┘     └──────┬────────────────┘
       │                            │
       ▼                            ▼
  ┌─────────┐                ┌───────────┐
  │ Qdrant  │◄───────────────│ Qdrant    │
  │ (write) │                │ (read)    │
  └─────────┘                └───────────┘
       ▲                            ▲
       │                            │
  ┌────┴────────────────────────────┴────┐
  │        PostgreSQL (rag_platform)      │
  │   rag_pipelines, prompt_templates     │
  │   agents, knowledge_bases             │
  └───────────────────────────────────────┘
```

## YAML Pipelines
Each YAML file defines **all** stages for both services.

**Ingestion stages** ([[rag-ingestion-manager]]):
`ingestion → chunking → embedding → indexing`

**Query stages** ([[rag-query-manager]]):
`knowledge_store → retrieval → reranking → response`

## Key Contracts
- PostgreSQL is the **runtime truth** for pipeline configs (never read YAML at runtime)
- YAML → DB via `python scripts/seed_db.py` / `scripts/seed_prompts.py` / `scripts/seed_agent_pipelines.py`
- Qdrant collection name synced between indexing and knowledge_store stages
