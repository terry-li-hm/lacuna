---
title: "refactor: Proper Structure for RegAtlas"
date: 2026-01-30
status: ready
effort: half-day
---

# RegAtlas Refactor: Proper Structure

## Goal

Transform RegAtlas from a scrappy prototype into a clean, portfolio-worthy codebase without over-engineering.

## Current State

- `backend/main.py`: 1668 lines, all routes + logic + storage mixed
- Storage: JSON files (`documents_db.json`, etc.)
- No tests
- No type hints on most functions

## Target State

```
backend/
├── main.py              # FastAPI app, CORS, lifespan only (~50 lines)
├── routes/
│   ├── __init__.py
│   ├── documents.py     # /upload, /documents, /documents/{id}
│   ├── requirements.py  # /requirements, /requirements/stats
│   ├── gap_analysis.py  # /gap-analysis
│   ├── policies.py      # /policies
│   └── system.py        # /healthz, /readyz, /stats
├── services/
│   ├── __init__.py
│   ├── document_service.py
│   ├── requirement_service.py
│   ├── gap_analysis_service.py
│   └── llm_service.py   # Wraps RequirementExtractor
├── storage/
│   ├── __init__.py
│   ├── database.py      # DuckDB connection + migrations
│   └── repositories.py  # DocumentRepo, RequirementRepo, PolicyRepo
├── models/
│   ├── __init__.py
│   └── schemas.py       # Pydantic models (moved from main.py)
└── tests/
    ├── __init__.py
    ├── test_gap_analysis.py
    └── test_documents.py
```

## Phase 1: Extract Pydantic Models (30 min)

**Task:** Move all Pydantic models to `backend/models/schemas.py`

1. Create `backend/models/__init__.py` and `backend/models/schemas.py`
2. Move these classes from `main.py`:
   - `QueryRequest`, `QueryResponse`
   - `CompareRequest`
   - `RequirementReviewRequest`
   - `SourceCreateRequest`
   - `PolicyUpdateRequest`
   - `WebhookCreateRequest`
   - `GapAnalysisRequest`, `GapAnalysisResponse`
   - `Provenance`, `GapRequirementMapping`
3. Update imports in `main.py`

**Verification:** `python -c "from backend.models.schemas import GapAnalysisRequest"`

## Phase 2: Extract Routes (1 hour)

**Task:** Split routes into logical modules

### 2.1 Create route files

Create `backend/routes/__init__.py`:
```python
from fastapi import APIRouter
from .documents import router as documents_router
from .requirements import router as requirements_router
from .gap_analysis import router as gap_analysis_router
from .policies import router as policies_router
from .system import router as system_router

__all__ = [
    "documents_router",
    "requirements_router",
    "gap_analysis_router",
    "policies_router",
    "system_router",
]
```

### 2.2 Move routes

| File | Endpoints |
|------|-----------|
| `routes/documents.py` | `/upload`, `/documents`, `/documents/{id}`, `/documents/export` |
| `routes/requirements.py` | `/requirements`, `/requirements/stats`, `/requirements/id/{id}`, `/requirements/export` |
| `routes/gap_analysis.py` | `/gap-analysis` |
| `routes/policies.py` | `/policies`, `/policies/{id}`, `/policies/export` |
| `routes/system.py` | `/`, `/healthz`, `/readyz`, `/stats`, `/entities`, `/audit-log` |

### 2.3 Update main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import (
    documents_router,
    requirements_router,
    gap_analysis_router,
    policies_router,
    system_router,
)

app = FastAPI(title="RegAtlas", version="0.2.0")

app.add_middleware(CORSMiddleware, ...)

app.include_router(system_router, tags=["system"])
app.include_router(documents_router, prefix="/documents", tags=["documents"])
app.include_router(requirements_router, prefix="/requirements", tags=["requirements"])
app.include_router(gap_analysis_router, tags=["gap-analysis"])
app.include_router(policies_router, prefix="/policies", tags=["policies"])
```

**Verification:** `curl http://localhost:8000/healthz`

## Phase 3: Add DuckDB Storage (1 hour)

**Task:** Replace JSON files with DuckDB

### 3.1 Create database module

`backend/storage/database.py`:
```python
import duckdb
from pathlib import Path

DB_PATH = Path("data/regatlas.duckdb")

def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH))

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id VARCHAR PRIMARY KEY,
            filename VARCHAR NOT NULL,
            jurisdiction VARCHAR NOT NULL,
            entity VARCHAR,
            business_unit VARCHAR,
            chunks_count INTEGER DEFAULT 0,
            requirements JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            policy_id VARCHAR PRIMARY KEY,
            title VARCHAR NOT NULL,
            path VARCHAR,
            summary TEXT,
            status VARCHAR DEFAULT 'active',
            version VARCHAR DEFAULT '1.0',
            owner VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            action VARCHAR NOT NULL,
            entity_type VARCHAR,
            entity_id VARCHAR,
            details JSON,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()
```

### 3.2 Create repositories

`backend/storage/repositories.py`:
```python
from typing import List, Dict, Any, Optional
from .database import get_connection

class DocumentRepository:
    def save(self, doc: Dict[str, Any]) -> None:
        conn = get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO documents
            (doc_id, filename, jurisdiction, entity, business_unit, chunks_count, requirements)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [doc["doc_id"], doc["filename"], doc["jurisdiction"],
              doc.get("entity"), doc.get("business_unit"),
              doc.get("chunks_count", 0), doc.get("requirements")])
        conn.close()

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        result = conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", [doc_id]
        ).fetchone()
        conn.close()
        return dict(result) if result else None

    def list_all(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        results = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in results]

    def delete(self, doc_id: str) -> bool:
        conn = get_connection()
        conn.execute("DELETE FROM documents WHERE doc_id = ?", [doc_id])
        conn.close()
        return True
```

### 3.3 Migration script

Create `backend/storage/migrate.py` to migrate existing JSON data to DuckDB:
```python
import json
from pathlib import Path
from .database import init_db, get_connection

def migrate_json_to_duckdb():
    init_db()
    data_dir = Path("data")

    # Migrate documents
    docs_file = data_dir / "documents_db.json"
    if docs_file.exists():
        docs = json.loads(docs_file.read_text())
        conn = get_connection()
        for doc_id, doc in docs.items():
            conn.execute(...)
        conn.close()
        docs_file.rename(docs_file.with_suffix(".json.bak"))
```

**Verification:** `python -c "from backend.storage.database import init_db; init_db()"`

## Phase 4: Extract Services (30 min)

**Task:** Create service layer between routes and storage

`backend/services/document_service.py`:
```python
from typing import List, Dict, Any, Optional
from backend.storage.repositories import DocumentRepository
from backend.document_processor import DocumentProcessor
from backend.vector_store import VectorStore

class DocumentService:
    def __init__(self, doc_repo: DocumentRepository, vector_store: VectorStore):
        self.doc_repo = doc_repo
        self.vector_store = vector_store
        self.processor = DocumentProcessor()

    def upload(self, file_content: bytes, filename: str, jurisdiction: str, ...) -> Dict[str, Any]:
        # Process document
        # Store in vector store
        # Save metadata to DB
        pass

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self.doc_repo.get(doc_id)

    def list_all(self) -> List[Dict[str, Any]]:
        return self.doc_repo.list_all()
```

**Verification:** Unit tests pass

## Phase 5: Add Basic Tests (30 min)

**Task:** Add smoke tests for critical paths

`backend/tests/test_gap_analysis.py`:
```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    response = client.get("/healthz")
    assert response.status_code == 200

def test_gap_analysis_missing_docs():
    response = client.post("/gap-analysis", json={
        "circular_doc_id": "nonexistent",
        "baseline_id": "also-nonexistent"
    })
    assert response.status_code == 404

def test_list_documents():
    response = client.get("/documents")
    assert response.status_code == 200
    assert "documents" in response.json()
```

`backend/tests/test_documents.py`:
```python
def test_upload_requires_file():
    response = client.post("/upload")
    assert response.status_code == 422  # Validation error
```

**Verification:** `pytest backend/tests/ -v`

## Summary

| Phase | Time | Deliverable |
|-------|------|-------------|
| 1. Extract models | 30 min | `backend/models/schemas.py` |
| 2. Extract routes | 1 hour | `backend/routes/*.py`, clean `main.py` |
| 3. Add DuckDB | 1 hour | `backend/storage/`, migration script |
| 4. Extract services | 30 min | `backend/services/*.py` |
| 5. Add tests | 30 min | `backend/tests/*.py` |

**Total: ~3.5 hours**

## Out of Scope

- Frontend changes
- CLI changes (still calls same API)
- New features
- Comprehensive test coverage
- CI/CD setup

## Success Criteria

1. `main.py` is under 100 lines
2. All existing endpoints work (manual smoke test)
3. Data persisted in DuckDB instead of JSON
4. `pytest` passes with basic tests
5. No functionality regression
