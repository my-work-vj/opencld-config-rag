---
title: connectors-google-drive
created: 2026-06-19
updated: 2026-06-19
type: concept
tags: [connectors, google-drive, ingestion]
sources: [connectors/google_drive.py, connectors/pathway/]
---

# Google Drive Connector

Connects to Google Drive folders via **Pathway** Docker container (`pw.io.gdrive`).

## How It Works
1. **Service Account** credentials JSON uploaded through the UI
2. Connector normalizes Drive folder/file URL or ID
3. Pathway Docker container runs scripts that use `pw.io.gdrive` to sync files
4. Files are downloaded to `data/connectors/<connector-id>/`
5. `ConnectorFileRepo` catalogs synced files in PostgreSQL
6. Collections linked to the connector pick up new/changed files via **background sync**

## Available Connector Interactions
- `POST /data-sources` — create connector (Google Drive only currently)
- `POST /data-sources/{id}/test` — validate credentials and list items
- `POST /data-sources/{id}/sync` — pull latest file catalog
- `POST /collections/{name}/sync` — kick off ingestion for linked collections

## Monitoring
A background worker (`monitoring/worker.py`) runs on a configurable interval:
- Checks all monitored connectors for new/changed files
- Triggers incremental sync for linked collections
- Tracks indexed documents via `indexed_documents` table to avoid re-indexing
