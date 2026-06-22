---
title: rag-ingestion-frontend
created: 2026-06-19
updated: 2026-06-19
type: entity
tags: [frontend, ingestion]
sources: [HYBRID_ARCHITECTURE.md]
---

# rag-ingestion-frontend

React app for managing knowledge sources and ingestion pipelines.

- **Path:** `rag-ingestion-frontend/`
- **Port:** 3001
- **Framework:** React + Vite + TypeScript
- **Backend:** [[rag-ingestion-manager]] (:8081)

## Routes
| Route | Purpose |
|-------|---------|
| `/sources` | Knowledge sources — create and ingest |
| `/data-sources` | Pathway connectors (Google Drive, S3) |
| `/manager`, `/creator`, `/rag/:id` | Ingestion pipelines |
