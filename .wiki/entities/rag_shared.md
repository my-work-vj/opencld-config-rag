---
title: rag_shared
created: 2026-06-19
updated: 2026-06-19
type: entity
tags: [architecture, shared]
sources: [HYBRID_ARCHITECTURE.md]
---

# rag_shared

Shared Python package at the repo root, used by both [[rag-ingestion-manager]] and [[rag-query-manager]].

## Location
`rag_shared/` at repo root

## Contents
| Module | Purpose |
|--------|---------|
| `models.py` | `rag_pipelines`, `rag_pipeline_audit` ORM models |
| `repo.py` | CRUD operations + audit log |
| `loader.py` | DB → runtime config translation |
| `seed.py` | YAML → DB seeding |
| `routes.py` | Shared pipeline CRUD router (mounted by both services) |
| `schemas.py` | Pydantic request/response schemas |
| `yaml_export.py` | DB → YAML export |
| `path_setup.py` | Python path bootstrap |
| `constants.py` | Shared constants |
| `db.py` | SQLAlchemy engine & session |
| `prompt_repo.py` | Prompt template CRUD |
| `knowledge_repo.py` | Knowledge base CRUD |
| `indexed_document_repo.py` | Indexed document tracking |
| `collection_connector_repo.py` | Collection-connector mappings |
| `connector_repo.py` | Connector definitions |
| `connector_file_repo.py` | Connector file registry |
| `defaults.py` | Default values & fallbacks |
| `slug.py` | Slug generation utilities |
| `agent_yaml.py` | Agent pipeline YAML parsing |
