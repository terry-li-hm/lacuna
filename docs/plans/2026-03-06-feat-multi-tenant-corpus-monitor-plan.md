---
title: "feat: Multi-Tenant Doc Isolation + Corpus Auto-Monitor"
type: feat
status: active
date: 2026-03-06
---

# feat: Multi-Tenant Doc Isolation + Corpus Auto-Monitor

## Overview

Wave 5 — runs after auth (wave 2) is live. Two parallel tasks:

### Task A: Per-Key Document Isolation

Once multiple clients have API keys, they must not see each other's uploaded documents. The current DuckDB/ChromaDB storage is flat — all docs share the same namespace.

**Design:**
- Each API key maps to a `tenant_id` (stored in config alongside the key)
- `GET /documents` filters by `tenant_id` of the authenticated key
- `POST /upload` tags uploaded docs with the caller's `tenant_id`
- Pre-loaded regulatory corpus (HKMA, MAS, EU, etc.) has `tenant_id=shared` — visible to all
- ChromaDB: use `where={"tenant_id": {"$in": ["shared", caller_tenant_id]}}` on all vector queries
- No data migration needed: existing docs get `tenant_id=shared` via a startup migration

Config format: `LACUNA_API_KEYS=key1:tenantA,key2:tenantB,key3:shared`

### Task B: Corpus Auto-Monitor

Background task that checks known regulatory sources for new publications and creates "new document available" alerts in the change register.

**Design:**
- New `backend/services/corpus_monitor_service.py`
- Checks HKMA, MAS, FCA, EU AI Office URLs for new publications (simple HTTP HEAD + last-modified, or scrape known "Publications" pages)
- Runs on a schedule via FastAPI lifespan + asyncio background task (every 24h)
- On new publication detected: creates a change record in the existing changes/scan system
- New endpoint `GET /system/corpus-monitor/status` shows last check time + pending alerts
- CLI: `lacuna monitor` — manually trigger a check, show pending alerts

## Acceptance Criteria

### Multi-Tenant Isolation
- [ ] Client A's uploaded docs not visible to Client B
- [ ] Shared regulatory corpus visible to all authenticated keys
- [ ] `GET /documents` scoped to caller's tenant
- [ ] `POST /upload` tags docs with caller's tenant_id
- [ ] Vector queries filtered by tenant
- [ ] Config: `LACUNA_API_KEYS=key:tenant` format
- [ ] Existing docs migrated to `tenant_id=shared` on startup

### Corpus Monitor
- [ ] Background task checks sources every 24h
- [ ] New publication creates change record
- [ ] `GET /system/corpus-monitor/status` returns last check + alerts
- [ ] `lacuna monitor` CLI command triggers manual check

## Files to Touch

**Task A:**
- `backend/config.py` — parse key:tenant format
- `backend/main.py` — pass tenant_id from middleware to request context
- `backend/services/document_service.py` — filter by tenant
- `backend/services/vector_store.py` — filter ChromaDB queries by tenant
- `frontend/index.html` — no changes (transparent to UI)

**Task B:**
- `backend/services/corpus_monitor_service.py` — new file
- `backend/main.py` — register lifespan background task
- `~/bin/lacuna` — add `monitor` command

## Gate

Dispatch only after auth (wave 2) is deployed and tested.
