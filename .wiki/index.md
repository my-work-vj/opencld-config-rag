# Wiki Index — Multi‑RAG Project

> Content catalog. Every wiki page listed under its type with a one-line summary.
> Last updated: 2026-06-19 | Total pages: 16

## Entities
- [[rag-ingestion-manager]] — Ingestion service (port 8081): sources → chunk → embed → index
- [[rag-query-manager]] — Query service (port 8082): retrieve → rerank → respond
- [[rag_shared]] — Shared Python package: models, repo, loader, seed, routes
- [[rag-ingestion-frontend]] — React app for source/ingest management (port 3001)
- [[rag-query-frontend]] — React app for knowledge bases, agents, querying (port 3000)

## Concepts
- [[pipeline-config-yaml]] — YAML pipeline blueprints driving all RAG stages
- [[strategy-registry-pattern]] — Pluggable strategy classes registered via decorators
- [[split-architecture]] — Independent ingestion + query services sharing Qdrant + PostgreSQL
- [[naive-rag]] — Dense vector search only, fastest
- [[vector-rag]] — Dense search with HyDE query expansion + reranking
- [[hybrid-rag]] — BM25 + dense vector with RRF fusion + reranking (best quality)
- [[data-model]] — PostgreSQL tables and core entity relationships
- [[connectors-google-drive]] — Google Drive connector via Pathway Docker

## Comparisons

## Queries
