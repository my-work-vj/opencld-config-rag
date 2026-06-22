---
title: rag-query-frontend
created: 2026-06-19
updated: 2026-06-19
type: entity
tags: [frontend, query]
sources: [HYBRID_ARCHITECTURE.md]
---

# rag-query-frontend

React app for querying knowledge bases, managing prompts, and configuring agents.

- **Path:** `rag-query-frontend/`
- **Port:** 3000
- **Framework:** React + Vite + TypeScript
- **Backend:** [[rag-query-manager]] (:8082)

## Routes
| Route | Purpose |
|-------|---------|
| `/knowledge-bases` | Group sources for retrieval |
| `/prompts` | Prompt manager (versioned templates) |
| `/agents` | RAG agent pipelines |
| `/manager`, `/rag/:id`, `/evaluator` | Query pipelines and evaluation |
