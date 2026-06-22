# Wiki Schema — Multi‑RAG Project

## Domain
**Multi‑RAG** — A split‑architecture RAG platform with ingestion (8081) and query (8082) services, shared Qdrant vector store and PostgreSQL backend, pluggable strategy pipelines, and React frontends.

## Conventions
- File names: lowercase, hyphens, no spaces
- Every page starts with YAML frontmatter
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- Bump `updated` date on every change
- Every new page added to `index.md` under the correct section
- Every action appended to `log.md`
- **Bidirectional sync with Mnemosyne memory system** — page creates/updates also stored as memory tagged `multirag:<slug>`

## Frontmatter
```yaml
---
title: Page Title
created: 2026-06-19
updated: 2026-06-19
type: entity | concept | comparison | query | summary
tags: [from taxonomy]
sources: [relevant project files]
---
```

## Tag Taxonomy
- **Architecture** — architecture, pipeline, strategy, pattern
- **Services** — ingestion, query, api, frontend
- **Data** — qdrant, postgres, vector, bm25, collection
- **Deployment** — docker, yaml, config, seeding, env
- **Knowledge** — agent, prompt, knowledge-base, chunk, embedding

## Wiki Pages
├── **entities/** — named things: services, repos, key files
├── **concepts/** — patterns & ideas: pipeline stages, strategy registry, RRF, HyDE
├── **comparisons/** — side-by-side: naive vs hybrid vs vector RAG
└── **queries/** — filed Q&A worth keeping

## Page Thresholds
- Create page for any major service, config file, or strategy
- Link from source of truth → docs that reference it
- Split pages > 200 lines

## Update Policy
Newer sources supersede older ones. Note contradictions in frontmatter.
