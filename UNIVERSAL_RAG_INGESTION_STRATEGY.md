# Universal RAG Ingestion Knowledge — Strategy Implementation

> **Branch:** `feature/my-new-ingest-july9`  
> **Scope:** `rag-ingestion-frontend/`, `rag-ingestion-manager/`, `rag_shared/`  
> **Product name:** Universal RAG Ingestion Knowledge (Ingestion Manager)

This document describes the end-to-end strategy for our RAG-as-a-Service ingestion layer: how data flows from connectors through index profiles into knowledge bases, and how multimodal parsing aligns with industry-managed knowledge base platforms (AWS Bedrock KB, DigitalOcean GenAI KB, Azure AI Search, etc.).

---

## Table of Contents

1. [Vision & Mental Model](#1-vision--mental-model)
2. [Industry Alignment](#2-industry-alignment)
3. [Architecture](#3-architecture)
4. [Phase A — KB Index Catalog](#4-phase-a--kb-index-catalog)
5. [Phase B — Universal Multimodal Ingestion](#5-phase-b--universal-multimodal-ingestion)
6. [Phase C — UX & Terminology](#6-phase-c--ux--terminology)
7. [Index Types & Storage](#7-index-types--storage)
8. [Pipeline Stages & Strategies](#8-pipeline-stages--strategies)
9. [API Reference (Ingestion)](#9-api-reference-ingestion)
10. [Frontend Routes & Components](#10-frontend-routes--components)
11. [Configuration & Environment](#11-configuration--environment)
12. [Operations & Verification](#12-operations--verification)
13. [Deferred Scope](#13-deferred-scope)
14. [File Map](#14-file-map)

---

## 1. Vision & Mental Model

Universal RAG separates **what you ingest** from **how you index it** and **how you query it**:

```
Data Sources  →  Index Profiles  →  Knowledge Bases  →  RAG Builder (query service, later)
```

| Layer | Purpose | User action |
|-------|---------|-------------|
| **Data Sources** | Connectors (Google Drive, uploads) sync raw files via Pathway | Connect once, files auto-sync |
| **Index Profiles** | One recipe per indexing need: index types + perception mode + pipeline stages | Create multiple profiles from the same source |
| **Knowledge Bases** | Cluster of profiles for unified retrieval; exposes an **index catalog** | Group profiles evaluated and ready for query |
| **RAG Builder** | Picks indexes per retrieval strategy at query time | *(out of scope for this phase)* |

**Key design principle:** The same data source can feed **multiple index profiles** with different recipes (e.g. plain-text + vector-only vs. vision + vector + graph). Knowledge bases aggregate profiles so downstream agents do not bind to individual Qdrant collections.

---

## 2. Industry Alignment

Managed RAG platforms follow a common pattern:

| Stage | Industry pattern | Our implementation |
|-------|------------------|-------------------|
| Connectors | S3, SharePoint, web crawl, Drive | Pathway Google Drive + file upload connectors |
| Parsing | OCR, layout, page-as-image for PDFs | `document_plain` (Kreuzberg) or `document_vision` (page raster + text) |
| Chunking | Fixed, semantic, hierarchical | `recursive_chunking`, `image_chunking`, `multigranularity` |
| Embedding | Dense + sparse + multimodal | LiteLLM → `nvidia-embed` (2048-dim, text/image/text_image) |
| Storage | Vector + keyword + graph + metadata | Qdrant dense/sparse, Neo4j, PostgreSQL, Redis |
| KB grouping | Logical KB over multiple data sources | Knowledge Base + **index catalog** API |
| Retrieval | Strategy selects indexes at query time | Handoff via `GET /knowledge-bases/{name}/index-catalog` |

**Multimodal PDF pattern:** Enterprise KBs often rasterize PDF pages and embed page image + extracted text together. Our `pdf_vision_ingestion` strategy implements this “page-as-image” pattern with PyMuPDF, producing `text_image` modality chunks when page text exists.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Universal RAG Ingestion Knowledge                     │
│                         (rag-ingestion-frontend :3001)                   │
│  Welcome → Data Sources → Index Profiles → Evaluation → Knowledge Bases   │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ REST
┌───────────────────────────────────▼─────────────────────────────────────┐
│                    rag-ingestion-manager (:8081)                         │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────────┐ │
│  │ API Routes  │  │ collection_sync  │  │ ingestion_router (modality)  │ │
│  │ collections │  │ _service         │  │ document_plain / vision    │ │
│  │ knowledge_  │  └────────┬─────────┘  └─────────────┬──────────────┘ │
│  │ bases       │           │                          │                │
│  └─────────────┘           ▼                          ▼                │
│                    IngestionPipeline (strategy registry)                 │
│  ingestion → chunking → embedding → sparse_embedding → indexing          │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
        ┌───────────────┬───────────┼───────────┬───────────────┐
        ▼               ▼           ▼           ▼               ▼
    Qdrant          PostgreSQL    Neo4j        Redis         LiteLLM
   (dense/sparse)   (metadata)   (graph)     (memory)      (nvidia-embed)
        ▲
        │
   Pathway Docker (Google Drive sync)
```

**Shared library:** `rag_shared/` holds schemas, repos, index config helpers, and the KB catalog builder used by both ingestion and (future) query services.

---

## 4. Phase A — KB Index Catalog

### Goal

Provide a **live, query-ready catalog** of all index profiles in a knowledge base so RAG Builder can select retrieval indexes without reading stale snapshots.

### Backend

#### `rag_shared/kb_catalog.py`

- **`build_profile_catalog(db, source_name)`** — Builds a catalog entry from a live `KnowledgeSource`:
  - `index_config`, `enabled_indexes`, `ingestion_mode`
  - `data_connector_ids`, `modalities`, `document_count`, `chunk_count`
  - `store_namespace` (= Qdrant collection name)
  - `embedding_model`, `vector_size`, `status`

- **`build_kb_index_catalog(db, kb_name)`** — Aggregates across all profiles in a KB:
  - `profiles[]` — per-profile catalog entries
  - `aggregated_indexes` — union of enabled index types
  - `data_connector_ids`, `modalities`

#### `rag_shared/knowledge_repo.py`

- **`resolve_sources(db, kb_name)`** — Returns live profile catalogs on every KB read (mitigates stale stored JSON).
- **`_kb_source_snapshot()`** — Delegates to `build_profile_catalog`.
- **`merge_collections()`** — Uses live snapshots when linking profiles.

#### API

```
GET /knowledge-bases/{name}/index-catalog
```

Response model: `KnowledgeBaseIndexCatalog` (`rag_shared/schemas.py`).

#### Evaluation gate

Profiles must pass ≥90% of evaluation thresholds before being added to a knowledge base (`knowledge_bases.py` → `_validate_evaluation_for_kb`).

### Frontend

| File | Change |
|------|--------|
| `src/lib/api.ts` | `knowledgeBaseIndexCatalog(name)` client |
| `src/types/api.ts` | `KnowledgeBaseSource`, `KnowledgeBaseIndexCatalog` types |
| `src/components/KbCatalogBadges.tsx` | Aggregated index badges + profile catalog rows |
| `src/pages/KnowledgeBasesPage.tsx` | Aggregated indexes on list cards |
| `src/pages/KnowledgeBaseDetailPage.tsx` | Index catalog panel + per-profile badges |

---

## 5. Phase B — Universal Multimodal Ingestion

### Goal

Route files to the correct ingestion/chunking strategies based on **perception mode** and file modality, with multimodal embeddings through LiteLLM.

### Perception Modes

| Mode | Behavior | Modalities |
|------|----------|------------|
| `document_plain` | Kreuzberg text extraction (default) | `text` |
| `document_vision` | Images + PDF pages via vision pipeline | `text`, `image`, `text_image` |
| `websites` | Placeholder for future web crawl | `text`, `web` |

Stored in index profile metadata: `metadata.ingestion_mode`.

### Modality Router

**`services/ingestion_router.py`** — `resolve_pipeline_overrides(path, ingestion_mode, source_type)`:

| File type | `document_vision` overrides |
|-----------|----------------------------|
| Standalone images (png, jpg, …) | `image_ingestion` + `image_chunking` |
| PDF | `pdf_vision_ingestion` + `image_chunking` |
| Other | No override (default Kreuzberg pipeline) |

**`services/modality.py`** — `detect_source_modality()`, `is_pdf_path()`, `is_image_path()`, `bytes_to_data_url()`.

### PDF Vision Ingestion

**`strategies/ingestion/pdf_vision_ingestion.py`** (`PdfVisionIngestion`):

1. Opens PDF with PyMuPDF (`fitz`)
2. Renders each page to PNG (configurable `page_zoom`, `max_pages`)
3. Extracts per-page text
4. Emits one `Document` per page with metadata:
   - `modality: "text_image"` if page has text, else `"image"`
   - `image_path`, `page_number`, `source_pdf`

Dependency: `pymupdf>=1.24.0` in `requirements.txt`.

### Multimodal Embeddings

**`strategies/embedding/__init__.py`** (`LiteLLMEmbedding`):

| Modality | Embedding path |
|----------|----------------|
| `text` (default) | Batch text embeddings via LiteLLM |
| `image` | Single image as data URL |
| `text_image` | `_embed_text_image_chunk()` — combined text + image input for `nvidia-embed` |

Model dimensions resolved via `services/litellm_model_info.py` (`/model/info` with fallback).

### Sync Integration

**`services/collection_sync_service.py`** passes `source_type` and reads `ingestion_mode` from profile metadata, applying router overrides per file.

**`api/routes/collections.py`** — `_run_collection_ingest()` aligned with router (no hardcoded `pdf_ingestion`).

Resync triggers when `ingestion_mode` changes on PATCH.

---

## 6. Phase C — UX & Terminology

### Product Branding

**`src/lib/terminology.ts`** centralizes labels:

| Constant | Value |
|----------|-------|
| `PRODUCT_TITLE` | Universal RAG Ingestion Knowledge |
| `INDEX_PROFILE_PLURAL` | Index profiles |
| `INDEX_PROFILES_PATH` | `/index-profiles` |
| `ingestionModeLabel()` | Human-readable perception mode |

API paths remain `/collections` for backward compatibility; UI routes redirect `/collections` → `/index-profiles`.

### Welcome Page

Three-step Universal RAG pipeline:

1. **Data Sources** — Connectors sync content
2. **Index Profiles** — Choose index types + perception mode
3. **Knowledge Bases** — Group profiles; index catalog for RAG Builder

### Index Profile Create Form

**Prominent (always visible):**

- Index type toggles (`IndexConfigEditor`)
- Perception mode picker (`IngestionModePicker`)

**Collapsible “Advanced pipeline settings”:**

- Embedding model selector
- Chunking strategy overrides (`RagStagesEditor` with `advancedOnly`)

### Knowledge Base UI

- List cards show aggregated index badges
- Detail page shows full index catalog from live API
- Per-profile: `IndexConfigBadges`, ingestion mode, doc counts

### App Shell

Sidebar title: **Universal RAG Ingestion Knowledge** / Ingestion Manager.

---

## 7. Index Types & Storage

Configured per index profile via `index_config` flags:

| Flag | Index stage | Backend |
|------|-------------|---------|
| `vector` | `qdrant_dense` | Qdrant dense vectors |
| `sparse` | `qdrant_sparse` + `sparse_embedding` | Qdrant sparse / BM25 |
| `graph` | `neo4j_graph` | Neo4j entity graph |
| `metadata` | `metadata` | PostgreSQL document/chunk records |
| `memory` | `memory_indexing` | Redis per-document catalog |

**`rag_shared/index_config.py`** — `normalize_index_config()`, `apply_index_config_to_stages()`, `enabled_index_types()`.

Saving index config changes triggers re-indexing for linked connector files.

---

## 8. Pipeline Stages & Strategies

### Ingestion stages (per profile)

```
ingestion → chunking → embedding → [sparse_embedding] → indexing
```

### Registered strategies (ingestion scope)

| Stage | Strategies |
|-------|------------|
| Ingestion | `kreuzberg_ingestion`, `image_ingestion`, `pdf_vision_ingestion` |
| Chunking | `recursive_chunking`, `image_chunking`, `multigranularity` |
| Embedding | `litellm_embedding` (text + image + text_image) |
| Indexing | `qdrant_dense`, `qdrant_sparse`, `neo4j_graph`, `metadata`, `memory_indexing` |

Strategy options exposed to UI via `rag_shared/strategy_options.py`.

---

## 9. API Reference (Ingestion)

### Index Profiles (collections)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/collections` | List index profiles |
| POST | `/collections` | Create profile (index_config, ingestion_mode, stages) |
| GET | `/collections/{name}` | Profile detail |
| PATCH | `/collections/{name}` | Update config; resync on ingestion_mode change |
| DELETE | `/collections/{name}` | Delete profile |
| POST | `/collections/{name}/sync` | Trigger connector sync + ingest |

### Knowledge Bases

| Method | Path | Description |
|--------|------|-------------|
| GET | `/knowledge-bases` | List KBs with live source snapshots |
| POST | `/knowledge-bases` | Create KB (requires evaluated profiles) |
| GET | `/knowledge-bases/{name}` | KB detail |
| GET | `/knowledge-bases/{name}/index-catalog` | **Aggregated index catalog for RAG Builder** |
| POST | `/knowledge-bases/{kb}/collections/{profile}` | Add profile |
| DELETE | `/knowledge-bases/{kb}/collections/{profile}` | Remove profile |

### Data Sources

| Method | Path | Description |
|--------|------|-------------|
| GET | `/data-sources` | List connectors |
| POST | `/data-sources` | Create connector |
| POST | `/data-sources/{id}/sync` | Pathway sync |

---

## 10. Frontend Routes & Components

### Routes (`App.tsx`)

| Path | Page |
|------|------|
| `/` | WelcomePage |
| `/data-sources` | DataSourcesPage |
| `/index-profiles` | CollectionsPage (Index profiles) |
| `/index-profiles/:name` | CollectionDetailPage |
| `/evaluation` | EvaluationDashboardPage |
| `/evaluation/:name` | CollectionEvaluationPage |
| `/knowledge-bases` | KnowledgeBasesPage |
| `/knowledge-bases/:name` | KnowledgeBaseDetailPage |

Redirects: `/collections` → `/index-profiles`.

### Key components

| Component | Role |
|-----------|------|
| `IndexConfigEditor` | Index type toggles + badges |
| `IngestionModePicker` | Perception mode radio group |
| `RagStagesEditor` | Embedding model + chunking overrides |
| `KbCatalogBadges` | KB catalog visualization |
| `IndexVisualizations` | Graph, vector, sparse, metadata, memory modals |

---

## 11. Configuration & Environment

### Ingestion Manager (`rag-ingestion-manager/.env`)

```env
LITELLM_BASE_URL=http://localhost:4000/v1
LITELLM_API_KEY=sk-vj
EMBEDDING_MODEL=nvidia-embed
DEFAULT_VECTOR_SIZE=2048
DATABASE_URL=postgresql://...
QDRANT_URL=http://localhost:6333
```

### PYTHONPATH

When running scripts from `rag-ingestion-manager/`, set repo root on `PYTHONPATH` so `rag_shared` resolves:

```powershell
$env:PYTHONPATH="C:\path\to\my-multi-rag"
```

### Docker services

| Service | Port | Purpose |
|---------|------|---------|
| LiteLLM | 4000 | Embedding/chat proxy |
| PostgreSQL | 5432 | Metadata + app DB |
| Qdrant | 6333 | Vector store |
| Pathway | Docker | Google Drive sync |
| Neo4j | 7687 | Graph index (optional) |
| Redis | 6379 | Memory index (optional) |

See `MULTI_RAG_DEPLOYMENT_GUIDE.md` for full deployment steps.

---

## 12. Operations & Verification

### Start services

```powershell
# Backend (avoid --reload on Windows — port ghosting)
cd rag-ingestion-manager
$env:PYTHONPATH="..\"
.\.venv\Scripts\uvicorn.exe api.main:app --host 127.0.0.1 --port 8081

# Frontend
cd rag-ingestion-frontend
npm run dev
# → http://localhost:3001/ingestion/
```

### Verify Phase A

1. Create two index profiles with different index configs
2. Create a knowledge base linking both
3. `GET /knowledge-bases/{name}/index-catalog` — confirm `aggregated_indexes` and per-profile `enabled_indexes`
4. UI: Knowledge Base detail → Index catalog panel

### Verify Phase B

1. Create index profile with `document_vision` + vector enabled
2. Link a data source with a PDF
3. Sync profile → confirm page-level chunks in Qdrant
4. Check chunk metadata: `modality: text_image`, `page_number`

### Verify Phase C

1. Welcome page shows 3-step pipeline
2. Create form: perception mode visible; advanced settings collapsed by default
3. App shell shows “Universal RAG Ingestion Knowledge”

### Build

```powershell
cd rag-ingestion-frontend
npm run build   # tsc + vite — must pass clean
```

---

## 13. Deferred Scope

Explicitly **not** implemented in this branch:

| Item | Notes |
|------|-------|
| `rag-query-frontend` / `rag-query-manager` | RAG Builder index selection from KB catalog |
| Audio / video ingestion | Modality router extensible later |
| `websites` ingestion mode | UI placeholder only |
| Auto-refresh KB stored snapshots on profile PATCH | Mitigated by live `resolve_sources` on read |

---

## 14. File Map

### New files

```
rag_shared/kb_catalog.py
rag-ingestion-manager/strategies/ingestion/pdf_vision_ingestion.py
rag-ingestion-frontend/src/lib/terminology.ts
rag-ingestion-frontend/src/components/KbCatalogBadges.tsx
UNIVERSAL_RAG_INGESTION_STRATEGY.md
```

### Modified (core)

```
rag_shared/knowledge_repo.py
rag_shared/schemas.py
rag_shared/strategy_options.py
rag-ingestion-manager/api/routes/knowledge_bases.py
rag-ingestion-manager/api/routes/collections.py
rag-ingestion-manager/services/collection_sync_service.py
rag-ingestion-manager/services/ingestion_router.py
rag-ingestion-manager/services/modality.py
rag-ingestion-manager/strategies/embedding/__init__.py
rag-ingestion-manager/strategies/ingestion/__init__.py
rag-ingestion-manager/requirements.txt
rag-ingestion-frontend/src/pages/WelcomePage.tsx
rag-ingestion-frontend/src/pages/CollectionsPage.tsx
rag-ingestion-frontend/src/pages/KnowledgeBasesPage.tsx
rag-ingestion-frontend/src/pages/KnowledgeBaseDetailPage.tsx
rag-ingestion-frontend/src/components/RagStagesEditor.tsx
rag-ingestion-frontend/src/components/layout/AppShell.tsx
rag-ingestion-frontend/src/lib/api.ts
rag-ingestion-frontend/src/types/api.ts
```

---

## Summary

This implementation delivers a **production-shaped RAG-as-a-Service ingestion layer**:

- **Connectors** sync data automatically (Pathway)
- **Index profiles** encode multi-index recipes and perception mode per use case
- **Multimodal parsing** handles images and PDF pages with industry-standard page-as-image + text embeddings
- **Knowledge bases** expose a live **index catalog** for downstream RAG Builder retrieval strategy selection
- **UX** reflects the Universal RAG mental model with clear terminology and progressive disclosure of advanced pipeline settings

The query service can consume `GET /knowledge-bases/{name}/index-catalog` to implement strategy-driven hybrid retrieval without coupling agents to individual vector collections.
