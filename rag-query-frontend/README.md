# OpenCLD RAG — Query Frontend

React dashboard for **rag-query-manager** (port **8082**).

## Pages

| Route | Page |
|-------|------|
| `/` | Welcome — query service status |
| `/knowledge-bases` | Knowledge bases — group sources |
| `/knowledge-bases/:name` | KB detail — add/remove sources |
| `/prompts` | Prompt templates — versioning |
| `/prompts/:id` | Prompt detail |
| `/agents` | RAG agents |
| `/agents/:name` | Agent builder and test query |
| `/manager` | Pipeline list |
| `/rag/:id` | Pipeline config — query test |
| `/evaluator` | Compare pipelines + query logs |

## Prerequisites

- Node.js 20+
- `rag-query-manager` running on port **8082**

## Setup

```bash
cd rag-query-frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:3000

Dev server proxies `/api` → `http://localhost:8082/api/v1`

## Build

```bash
npm run build
npm run preview
```

## Related

- **Ingestion UI**: `rag-ingestion-frontend` (port 3001 → :8081)
