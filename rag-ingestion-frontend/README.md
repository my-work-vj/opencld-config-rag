# OpenCLD RAG — Ingestion Frontend

React dashboard for **rag-ingestion-manager** (port **8081**).

## Pages

| Route | Page |
|-------|------|
| `/` | Welcome — ingestion service status |
| `/data-sources` | Pathway connectors (Google Drive, etc.) |
| `/sources` | Knowledge sources — create, ingest, delete |
| `/sources/:name` | Source detail — documents and ingest |
| `/manager` | Pipeline list |
| `/creator` | RAG Creator — preset-based pipeline creation |
| `/rag/:id` | Pipeline config — ingest test |

## Prerequisites

- Node.js 20+
- `rag-ingestion-manager` running on port **8081**

## Setup

```bash
cd rag-ingestion-frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:3001

Dev server proxies `/api` → `http://localhost:8081/api/v1`

## Build

```bash
npm run build
npm run preview
```

## Related

- **Query UI**: `rag-query-frontend` (port 3000 → :8082)
