# Multi-RAG Project Setup Guide

Complete setup guide for deploying the **multi-rag** dual-stack system (ingestion + retrieval/generation) — FastAPI backends, Vite React frontends, Pathway Docker container, reverse proxy, and ngrok tunnel — from scratch in any environment.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Overview](#2-project-overview)
3. [Repository Setup](#3-repository-setup)
4. [Ingestion Backend Setup](#4-ingestion-backend-setup)
5. [Ingestion Frontend Setup](#5-ingestion-frontend-setup)
6. [Retrieval Backend Setup](#6-retrieval-backend-setup)
7. [Retrieval Frontend Setup](#7-retrieval-frontend-setup)
8. [Pathway Docker Container](#8-pathway-docker-container)
9. [External Services (PostgreSQL, Qdrant, LiteLLM)](#9-external-services)
10. [WSL ↔ Windows Docker Connectivity](#10-wsl--windows-docker-connectivity)
11. [Reverse Proxy Setup](#11-reverse-proxy-setup)
12. [ngrok Tunnel](#12-ngrok-tunnel)
13. [Running Everything](#13-running-everything)
14. [Verification](#14-verification)
15. [Architecture & Data Flow](#15-architecture--data-flow)
16. [Bug Fixes & Patches Applied](#16-bug-fixes--patches-applied)
17. [Troubleshooting](#17-troubleshooting)
18. [Quick-Start Reference](#18-quick-start-reference)

---

## 1. Prerequisites

### System Requirements

| Item | Version / Notes |
|------|----------------|
| **OS** | Linux / WSL2 (Ubuntu 22.04+ recommended) |
| **Python** | 3.10+ (tested on 3.13) |
| **Node.js** | 18+ (for frontends) |
| **Docker** | Docker Desktop for Windows (if Pathway runs on Windows) |
| **ngrok** | Free account with auth token + **ngrok binary** |
| **Package managers** | `uv` (Python), `npm` (Node) |

### Tools to Install First

```bash
# Python package manager (uv — faster than pip)
pip install uv        # or use the system package manager

# Docker CLI (inside WSL/Linux)
# If Docker Desktop on Windows, Docker CLI is already available in WSL

# ngrok binary
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc > /dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok -y
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

---

## 2. Project Overview

```
multi-rag/
├── rag-ingestion-frontend/     # Vite + React (port 3001, base: /ingestion/)
├── rag-ingestion-manager/      # FastAPI backend (port 8081)
├── rag-query-frontend/         # Query UI Vite + React (port 3000, base: /ret_gen/)
├── rag-query-manager/          # Query FastAPI backend (port 8083)
├── rag_shared/                 # Shared library (SQLAlchemy models, db connection)
├── reverse_proxy.py            # Python reverse proxy (port 3002) — path-based routing
├── docker-compose.yml          # Defines Pathway + LiteLLM + Qdrant containers
└── SETUP.md                    # This file
```

### Port Map

| Service | Port | Base Path | Description |
|---------|------|-----------|-------------|
| Reverse Proxy | **3002** | — | Entry point for all traffic; routes by path |
| Ingestion Frontend (Vite) | 3001 | `/ingestion/` | UI for data sources, collections, evaluation |
| Ingestion Backend (FastAPI) | 8081 | `/api/v1/` | Ingest APIs, collection sync, monitoring |
| Retrieval Frontend (Vite) | 3000 | `/ret_gen/` | UI for agents, prompts, querying |
| Retrieval Backend (FastAPI) | 8083 | `/api/v1/` | Query APIs, knowledge bases, agents |
| Pathway (Docker) | — | — | Google Drive sync, file extraction |
| Qdrant (Docker) | 6333 | — | Vector storage |
| LiteLLM (Docker) | 4000 | — | LLM proxy for embeddings |
| PostgreSQL (Docker) | 5432 | — | Main database |
| ngrok Agent | 4040 | — | Web UI for tunnel status |

### URL Scheme

```
https://YOUR-DOMAIN.ngrok-free.dev/ingestion/     → Ingestion UI
https://YOUR-DOMAIN.ngrok-free.dev/ingestion/api/* → Ingestion backend
https://YOUR-DOMAIN.ngrok-free.dev/ret_gen/        → Retrieval/Query UI
https://YOUR-DOMAIN.ngrok-free.dev/ret_gen/api/*   → Query backend
```

---

## 3. Repository Setup

```bash
# Create projects directory
mkdir -p /opt/data/my-hermes-projects
cd /opt/data/my-hermes-projects

# Clone the repository
git clone https://github.com/my-work-vj/opencld-config-rag.git multi-rag
cd multi-rag

# If using a specific branch
git checkout feature/evaluation-initialdone-Jun23
```

---

## 4. Ingestion Backend Setup

### 4.1 Python Virtual Environment

```bash
cd rag-ingestion-manager

# Create venv
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### 4.2 Install Critical Dependency: `kreuzberg`

> **⚠️ CRITICAL:** This library is often missed in `requirements.txt` but is **required** for file ingestion (PDFs, Office docs, images via OCR). Without it, every ingestion silently produces 0 documents, causing `'NoneType' object has no attribute 'get'` errors.

```bash
source .venv/bin/activate
uv pip install kreuzberg
```

### 4.3 Environment Variables (.env)

The backend reads from `rag-ingestion-manager/.env`:

```env
# Backend port
API_PORT=8081

# External services (running in Docker on Windows)
LITELLM_BASE_URL=http://host.docker.internal:4000/v1
LITELLM_API_KEY=***
EMBEDDING_MODEL=nvidia-embed

# Qdrant
QDRANT_HOST=host.docker.internal
QDRANT_PORT=6333

# PostgreSQL
POSTGRES_HOST=host.docker.internal
POSTGRES_PORT=5432
POSTGRES_USER=llmproxy
POSTGRES_PASSWORD=your-strong-password
POSTGRES_DB=rag_platform

# Pathway Docker
PATHWAY_DOCKER_IMAGE=pathwaycom/pathway:latest
PATHWAY_CONTAINER_NAME=opncld-rag-pathway
PATHWAY_DOCKER_TIMEOUT_SEC=900
CONNECTORS_DATA_DIR=./data/connectors
```

### 4.4 Start the Backend

```bash
cd /opt/data/my-hermes-projects/multi-rag/rag-ingestion-manager
source .venv/bin/activate
DOCKER_HOST=tcp://host.docker.internal:2375 \
PYTHONPATH="/opt/data/my-hermes-projects/multi-rag/rag-ingestion-manager:$PYTHONPATH" \
python api/main.py
```

On startup it:
1. Initializes database tables
2. Checks Pathway Docker container status
3. Starts the **MonitorWorker** (polls every 30s for connector changes)
4. Registers ingestion strategies (kreuzberg, text, pdf, web)
5. Starts on **port 8081** with auto-reload enabled

---

## 5. Ingestion Frontend Setup

### 5.1 Install Dependencies

```bash
cd /opt/data/my-hermes-projects/multi-rag/rag-ingestion-frontend
npm install
```

### 5.2 Configure Base Path

In `vite.config.ts`, set:
```ts
base: '/ingestion/',
server: { port: 3001, allowedHosts: true }
```

In `src/lib/env.ts`:
```ts
export const API_BASE = import.meta.env.VITE_API_BASE ?? '/ingestion/api'
```

In `src/App.tsx`:
```tsx
<BrowserRouter basename="/ingestion">
```

### 5.3 Start the Frontend

```bash
npx vite --port 3001 --host 0.0.0.0
```

---

## 6. Retrieval Backend Setup

### 6.1 Dependencies

The retrieval backend shares the same venv as ingestion. Dependencies are already installed if you followed §4.1–4.2.

### 6.2 Environment Variables

Copy the ingestion .env:
```bash
cp rag-ingestion-manager/.env rag-query-manager/.env
```

Or set the standard env vars (same external service hosts):
```env
API_PORT=8083
LITELLM_BASE_URL=http://host.docker.internal:4000/v1
QDRANT_HOST=host.docker.internal
QDRANT_PORT=6333
POSTGRES_HOST=host.docker.internal
POSTGRES_PORT=5432
POSTGRES_USER=llmproxy
POSTGRES_PASSWORD=your-strong-password
POSTGRES_DB=rag_platform
```

### 6.3 Start the Backend

```bash
cd /opt/data/my-hermes-projects/multi-rag/rag-query-manager
source /opt/data/my-hermes-projects/multi-rag/rag-ingestion-manager/.venv/bin/activate
PYTHONPATH="/opt/data/my-hermes-projects/multi-rag/rag-query-manager:$PYTHONPATH" \
python api/main.py
```

On startup it:
1. Connects to shared PostgreSQL pipeline database
2. Registers query strategies (vector_rag, hybrid_bm25, multi_collection, etc.)
3. Starts on **port 8083** with auto-reload

---

## 7. Retrieval Frontend Setup

### 7.1 Install Dependencies

```bash
cd /opt/data/my-hermes-projects/multi-rag/rag-query-frontend
npm install
```

### 7.2 Configure Base Path

In `vite.config.ts`:
```ts
base: '/ret_gen/',
server: { port: 3000, allowedHosts: true }
```

In `src/lib/env.ts`:
```ts
export const API_BASE = import.meta.env.VITE_API_BASE ?? '/ret_gen/api'
```

In `src/App.tsx`:
```tsx
<BrowserRouter basename="/ret_gen">
```

### 7.3 Start the Frontend

```bash
npx vite --port 3000 --host 0.0.0.0
```

---

## 8. Pathway Docker Container

### 8.1 docker-compose.yml

The project includes a `docker-compose.yml` that defines the Pathway container:

```yaml
services:
  pathway:
    image: pathwaycom/pathway:latest
    container_name: opncld-rag-pathway
    entrypoint: ["sleep", "infinity"]   # Stays alive; scripts run via docker exec
    volumes:
      - ./rag-ingestion-manager/data/connectors:/data/connectors
      - ./rag-ingestion-manager/connectors/pathway/scripts:/app/scripts
```

**Key point:** The container uses `sleep infinity` as entrypoint — it doesn't run anything autonomously. The backend `docker exec`s into it to run sync scripts.

### 8.2 Start the Container

On Windows (Docker Desktop):
```bash
cd multi-rag
docker compose up -d pathway
```

### 8.3 Verify

```bash
docker ps --filter name=opncld-rag-pathway
# Should show: Up about X minutes
```

---

## 9. External Services

### 9.1 Service Containers

These services run in Docker on Windows, not in WSL:

| Container | Image | Exposed Port |
|-----------|-------|-------------|
| `litellm` | litellm | 4000 (LLM API) |
| `litellm_db` | postgres:15 | 5432 (PostgreSQL) |
| `qdrant` | qdrant/qdrant | 6333 (Vector DB) |
| `opncld-rag-pathway` | pathwaycom/pathway | — (sync scripts) |

### 9.2 Connection from WSL

All services are accessed via `host.docker.internal`:
```
LITELLM  → http://host.docker.internal:4000/v1
QDRANT   → host.docker.internal:6333
POSTGRES → host.docker.internal:5432 (user: llmproxy, db: rag_platform)
DOCKER   → tcp://host.docker.internal:2375
```

---

## 10. WSL ↔ Windows Docker Connectivity

### 10.1 The Challenge

WSL2 runs in a separate VM with its own network. It cannot use the Docker Unix socket (`/var/run/docker.sock`).

### 10.2 Solution: Docker Desktop TCP

1. Open **Docker Desktop** → Settings → General
2. Check: **"Expose daemon on tcp://localhost:2375 without TLS"**
3. Apply & Restart

Then from WSL:
```bash
export DOCKER_HOST=tcp://host.docker.internal:2375
```

### 10.3 Verify

```bash
DOCKER_HOST=tcp://host.docker.internal:2375 docker ps
# Should list Windows Docker containers
```

### 10.4 Path Mapping

WSL paths (`/opt/data/...`) and Windows filesystem are bridged by Docker Desktop. The backend manages this via:
- `connectors/pathway/container.py` — `copy_files_from_container()` copies synced files back to WSL
- Cross-filesystem path mapping is handled automatically by Docker Desktop

---

## 11. Reverse Proxy Setup

A Python reverse proxy on port 3002 routes traffic based on URL path, allowing both frontends to share a single ngrok tunnel.

### 11.1 The Proxy (`reverse_proxy.py`)

```python
# Routing rules:
# /ingestion/api/*  → http://localhost:8081/api/v1/*
# /ret_gen/api/*    → http://localhost:8083/api/v1/*
# /ingestion/*      → http://localhost:3001/ingestion/*
# /ret_gen/*        → http://localhost:3000/ret_gen/*
```

### 11.2 Start the Proxy

```bash
python3 /opt/data/my-hermes-projects/multi-rag/reverse_proxy.py
```

### 11.3 Verify

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:3002/ingestion/     # → 200
curl -s -o /dev/null -w '%{http_code}' http://localhost:3002/ret_gen/       # → 200
curl -s http://localhost:3002/ingestion/api/health                          # → healthy
curl -s http://localhost:3002/ret_gen/api/health                            # → healthy
```

---

## 12. ngrok Tunnel

### 12.1 The CRL Problem

ngrok may fail on some networks with:
```
failed to send authentication request: failed to fetch CRL. EOF
```

**Fix:** Add `crl_noverify: true` to ngrok config.

### 12.2 ngrok Config (`~/.config/ngrok/ngrok.yml`)

```yaml
version: "2"
authtoken: YOUR_NGROK_AUTH_TOKEN
crl_noverify: true
tunnels:
  ingestion:
    proto: http
    addr: 3002            # Points to reverse proxy, not directly to 3001
    domain: YOUR-DOMAIN.ngrok-free.dev
```

### 12.3 Start ngrok

```bash
ngrok start --all --log=stdout
```

Or with the custom domain:
```bash
/opt/data/ngrok start --all --log=stdout
```

### 12.4 Verify Tunnel

```bash
curl -s http://localhost:4040/api/tunnels | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
```

---

## 13. Running Everything

### 13.1 Startup Order

1. **External services** (Docker on Windows): Pathway, LiteLLM, Qdrant, PostgreSQL
2. **Ingestion backend** (port 8081)
3. **Retrieval backend** (port 8083)
4. **Ingestion frontend** (port 3001, base `/ingestion/`)
5. **Retrieval frontend** (port 3000, base `/ret_gen/`)
6. **Reverse proxy** (port 3002)
7. **ngrok tunnel** (points to port 3002)

### 13.2 All-in-One Start Commands

```bash
# ---- 1. Ingestion Backend ----
cd /opt/data/my-hermes-projects/multi-rag/rag-ingestion-manager
source .venv/bin/activate
DOCKER_HOST=tcp://host.docker.internal:2375 \
PYTHONPATH="/opt/data/my-hermes-projects/multi-rag/rag-ingestion-manager:$PYTHONPATH" \
python api/main.py

# ---- 2. Retrieval Backend ----
cd /opt/data/my-hermes-projects/multi-rag/rag-query-manager
source /opt/data/my-hermes-projects/multi-rag/rag-ingestion-manager/.venv/bin/activate
PYTHONPATH="/opt/data/my-hermes-projects/multi-rag/rag-query-manager:$PYTHONPATH" \
python api/main.py

# ---- 3. Ingestion Frontend ----
cd /opt/data/my-hermes-projects/multi-rag/rag-ingestion-frontend
npx vite --port 3001 --host 0.0.0.0

# ---- 4. Retrieval Frontend ----
cd /opt/data/my-hermes-projects/multi-rag/rag-query-frontend
npx vite --port 3000 --host 0.0.0.0

# ---- 5. Reverse Proxy ----
python3 /opt/data/my-hermes-projects/multi-rag/reverse_proxy.py

# ---- 6. ngrok ----
/opt/data/ngrok start --all --log=stdout
```

### 13.3 Background Process Pattern (Hermes Agent)

```python
# Each in its own terminal(background=True) call with notify_on_complete=True
```

---

## 14. Verification

```bash
# === Local endpoints ===
echo "Ingestion Backend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/api/v1/health)"
echo "Retrieval Backend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8083/api/v1/health)"
echo "Ingestion Frontend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3001/ingestion/)"
echo "Retrieval Frontend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/ret_gen/)"
echo "Reverse Proxy: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3002/ingestion/)"

# === Through ngrok ===
TUNNEL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])")
curl -s "$TUNNEL/ingestion/" -o /dev/null -w "Ingestion via ngrok: HTTP %{http_code}\n"
curl -s "$TUNNEL/ret_gen/" -o /dev/null -w "Retrieval via ngrok: HTTP %{http_code}\n"
curl -s "$TUNNEL/ingestion/api/health" -o /dev/null -w "Ingestion API: HTTP %{http_code}\n"
curl -s "$TUNNEL/ret_gen/api/health" -o /dev/null -w "Query API: HTTP %{http_code}\n"
```

---

## 15. Architecture & Data Flow

### 15.1 Request Flow

```
Browser ──→ ngrok (443)
                │
                ▼
          Proxy (:3002)
           /  \        \
          /    \        \
    /ingestion/  /ret_gen/   /ingestion/api/   /ret_gen/api/
         |           |            |                  |
         ▼           ▼            ▼                  ▼
    Vite(:3001)  Vite(:3000)  FastAPI(:8081)   FastAPI(:8083)
    Ingestion    Query        Ingestion        Query
    UI           UI           Backend          Backend
```

### 15.2 Ingestion Pipeline

```
Google Drive → Pathway (Docker) → gdrive_sync.py
    │
    ▼
ConnectorFile (PostgreSQL) → files copied to WSL
    │
    ▼
For each new/changed file:
    ┌─ kreuzberg_ingestion ──► Document
    ├─ recursive_chunking   ──► Chunks
    ├─ litellm_embedding    ──► EmbeddingVectors
    └─ qdrant_indexing      ──► Qdrant vector store
```

### 15.3 Query Pipeline

```
User Query → LiteLLM rewrite → Vector Search (Qdrant)
    │
    ▼
LiteLLM Reranking → Context Assembly → LiteLLM Response Generation
```

### 15.4 Monitoring

`MonitorWorker` (in ingestion backend) polls every **30 seconds**:
1. `sync_all_monitored_connectors()` — re-syncs Google Drive via Pathway Docker
2. `sync_all_monitored_collections()` — reconciles files → indexed documents

---

## 16. Bug Fixes & Patches Applied

### 16.1 Missing `kreuzberg` Library

**Symptom:** `'NoneType' object has no attribute 'get'` on collection sync
**Root Cause:** Ingestion produces 0 documents without kreuzberg → `_run_connector_file_ingest()` returns `None`
**Fix:** `uv pip install kreuzberg`

### 16.2 `db.close()` Inside `for` Loop

**Symptom:** `Instance <ConnectorFile at ...> is not bound to a Session` — only 1 file processed
**Root Cause:** `finally: db.close()` inside the file loop closes the session after the first file
**Fix:** Moved `db.close()` outside the loop (in `services/collection_sync_service.py`)

### 16.3 BrowserRouter Missing `basename`

**Symptom:** Blank page (blue gradient background, no content)
**Root Cause:** React Router's `BrowserRouter` not configured with `basename="/ingestion"` or `basename="/ret_gen"` when apps are served from subpaths
**Fix:** Added `basename` prop to both frontends' `App.tsx`

### 16.4 Reverse Proxy Connection Handling

**Symptom:** Reverse proxy hangs on certain requests
**Root Cause:** Initial asyncio-based proxy had connection handling bugs
**Fix:** Switched to threaded `http.server` with `urllib.request`

### 16.5 ngrok CRL Check Failure

**Symptom:** `failed to send authentication request: failed to fetch CRL. EOF`
**Root Cause:** ngrok fetches CRL over HTTP but server expects HTTPS
**Fix:** `crl_noverify: true` in `ngrok.yml`

---

## 17. Troubleshooting

### 17.1 Port Already in Use

```bash
# Check what's on a port
python3 -c "import socket; s=socket.socket(); print('in use' if not s.connect_ex(('127.0.0.1', PORT)) else 'free'); s.close()"

# Kill process on port
fuser -k PORT/tcp 2>/dev/null || true
# or if fuser not available:
kill -9 $(ps aux | grep -E "python.*api/main" | grep -v grep | awk '{print $2}') 2>/dev/null
```

### 17.2 Backend Shows `degraded` Status

All external services unreachable:
- Check `DOCKER_HOST` is set
- Check `host.docker.internal` is resolvable
- Check Docker Desktop is running with TCP exposed on 2375
- Check env vars point to `host.docker.internal` not `localhost`

### 17.3 Frontend Shows Blank Page

- **Check Browser Router basename:** App.tsx must have `<BrowserRouter basename="/ingestion">` or `"/ret_gen"`
- **Check Vite base config:** vite.config.ts must have `base: '/ingestion/'` or `'/ret_gen/'`
- **Check API base:** env.ts must use `/ingestion/api` or `/ret_gen/api`
- **Check assets load:** Open browser DevTools → Network tab → ensure JS/CSS files return 200

### 17.4 "Address already in use" on Backend Start

Old uvicorn process still holding the port:
```bash
kill -9 $(ps aux | grep "python.*api/main" | grep -v grep | awk '{print $2}') 2>/dev/null
sleep 3
# Then restart
```

### 17.5 Google Drive Sync Fails

- Check credentials file exists at `data/connectors/{connector-id}/credentials.json`
- Check Pathway container is running: `docker ps --filter name=opncld-rag-pathway`
- Check `DOCKER_HOST` is correct
- Run manually: `docker exec opncld-rag-pathway python /scripts/gdrive_sync.py --help`

### 17.6 ngrok DNS Resolution Issues

Some networks block `.dev` TLD or `.ngrok-free.dev` domains. The tunnel may work from external networks (mobile data). Test from a different network.

### 17.7 Retrieval Backend Can't Read Collection Data

Both ingestion and query backends share the same PostgreSQL (`rag_platform`) and Qdrant. If the retrieval backend doesn't see collections, check:
- It connects to the correct database host (`host.docker.internal`)
- It uses the correct credentials
- The ingestion backend has actually created and populated the collection

---

## 18. Quick-Start Reference

### Fresh Setup Checklist

- [ ] `git clone` the repo
- [ ] `uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt`
- [ ] **`uv pip install kreuzberg`** ← critical!
- [ ] `npm install` in both `rag-ingestion-frontend/` and `rag-query-frontend/`
- [ ] Docker Desktop: expose daemon on tcp://localhost:2375
- [ ] Docker Desktop: `docker compose up -d pathway` for Pathway container
- [ ] Configure ngrok: `~/.config/ngrok/ngrok.yml` with `crl_noverify: true`
- [ ] Copy `.env` from `rag-ingestion-manager/` to `rag-query-manager/`
- [ ] Verify frontend `base`, `basename`, and `API_BASE` settings
- [ ] Start all services in order

### All Services in One Shell

```bash
export DOCKER_HOST=tcp://host.docker.internal:2375
export VENV=/opt/data/my-hermes-projects/multi-rag/rag-ingestion-manager/.venv/bin/activate
export BASE=/opt/data/my-hermes-projects/multi-rag

# Backends
cd $BASE/rag-ingestion-manager && source $VENV && PYTHONPATH="$(pwd):$PYTHONPATH" python api/main.py &
cd $BASE/rag-query-manager && source $VENV && PYTHONPATH="$(pwd):$PYTHONPATH" python api/main.py &

# Frontends
cd $BASE/rag-ingestion-frontend && npx vite --port 3001 --host 0.0.0.0 &
cd $BASE/rag-query-frontend && npx vite --port 3000 --host 0.0.0.0 &

# Reverse proxy
python3 $BASE/reverse_proxy.py &

# ngrok
ngrok start --all --log=stdout &
```

### Collection Status Codes

| Status | Meaning |
|--------|---------|
| `ready` | All files ingested and indexed |
| `syncing` | Currently syncing connector & ingesting files |
| `indexing` | Files are being processed by the ingestion pipeline |
| `error` | Sync or ingestion failed (check `errors` array) |
| `partial` | Some files succeeded, some failed |
| `skipped` | No linked data sources |

---

*Last updated: 2026-06-29*
