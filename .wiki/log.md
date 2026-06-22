# Wiki Log — Multi‑RAG Project

> Chronological record of all wiki actions. Append-only.
> Format: `## [YYYY-MM-DD] action | subject`

## [2026-06-19] create | Wiki initialized
- Domain: Multi‑RAG split‑architecture RAG platform
- Structure created with SCHEMA.md, index.md, log.md
- Initial pages seeded from HYBRID_ARCHITECTURE.md, PROJECT_GUIDE.md, SPLIT_ARCHITECTURE.md

## [2026-06-19] create | Entity pages seeded
- [[rag-ingestion-manager]] — Ingestion service details
- [[rag-query-manager]] — Query service details
- [[rag_shared]] — Shared package reference
- [[rag-ingestion-frontend]] — Ingestion UI app
- [[rag-query-frontend]] — Query UI app

## [2026-06-19] create | Concept pages seeded
- [[split-architecture]] — Independent ingestion + query services
- [[strategy-registry-pattern]] — Pluggable strategy decorator pattern
- [[pipeline-config-yaml]] — YAML pipeline blueprint structure

## [2026-06-19] deep-dive | Full codebase analysis
- [[data-model]] — PostgreSQL tables: rag_pipelines, knowledge_sources, agents, data_connectors, etc.
- [[connectors-google-drive]] — Google Drive connector via Pathway Docker
- [[naive-rag]] — Dense vector search only
- [[vector-rag]] — HyDE + query expansion
- [[hybrid-rag]] — BM25 + dense + RRF fusion
