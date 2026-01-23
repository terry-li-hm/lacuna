"""FastAPI application for regulatory analytics tool."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Iterable
from datetime import datetime, timezone, date
import os
import urllib.request
import xml.etree.ElementTree as ET
import csv
import io
import hashlib
import re
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import uuid

from .config import settings
from .document_processor import DocumentProcessor
from .requirement_extractor import RequirementExtractor
from .vector_store import VectorStore

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="RegAtlas",
    description="Cross-jurisdiction regulatory analytics platform for financial institutions",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
doc_processor = DocumentProcessor()
llm_api_key = settings.openai_api_key or settings.openrouter_api_key
req_extractor = RequirementExtractor(
    api_key=None if settings.no_llm else llm_api_key,
    model=settings.llm_model,
    base_url=settings.openai_base_url
)
vector_store = VectorStore(settings.chroma_persist_dir)

DOCUMENTS_DB_PATH = settings.data_dir / "documents_db.json"
CHANGE_DB_PATH = settings.data_dir / "change_log.json"
AUDIT_LOG_PATH = settings.data_dir / "audit_log.json"
SOURCES_DB_PATH = settings.data_dir / "sources_db.json"
EVIDENCE_DB_PATH = settings.data_dir / "evidence_db.json"
POLICIES_DB_PATH = settings.data_dir / "policies_db.json"
WEBHOOKS_DB_PATH = settings.data_dir / "webhooks_db.json"
STARTED_AT = datetime.now(timezone.utc)
ALLOWED_CHANGE_STATUS = {"new", "triaged", "assessing", "implemented"}
ALLOWED_CHANGE_SEVERITY = {"low", "medium", "high"}
ALLOWED_REQ_STATUS = {"new", "reviewed", "action_required"}


def load_documents_db(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load persisted document metadata from disk."""
    if not path.exists():
        return {}
    file_path = None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load documents DB from {path}: {e}")
        return {}


def save_documents_db(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """Persist document metadata to disk atomically."""
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_json_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load a JSON object (dict) from disk."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load JSON dict from {path}: {e}")
        return {}


def save_json_dict(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """Persist JSON dict atomically."""
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON list from disk."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load JSON list from {path}: {e}")
        return []


def save_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    """Persist JSON list atomically."""
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _paginate(items: List[Dict[str, Any]], limit: int | None, offset: int | None) -> List[Dict[str, Any]]:
    if limit is None or limit <= 0:
        return items[offset or 0:]
    return items[offset or 0: (offset or 0) + limit]


def _sort_by_iso(items: Iterable[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    def _key(item: Dict[str, Any]) -> datetime:
        value = item.get(field)
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(list(items), key=_key, reverse=True)


def _validate_date_str(value: str | None, field: str) -> None:
    if not value:
        return
    try:
        datetime.fromisoformat(value)
    except ValueError:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {field} date format") from exc


def _normalize_severity(value: str | None) -> str | None:
    if value is None:
        return None
    return value.lower()


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    return value.lower()


def _normalize_mandatory(value: str | None) -> str | None:
    if value is None:
        return None
    return value.lower()


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_choice(value: str | None, allowed: set[str], field: str) -> str | None:
    if value is None:
        return None
    normalized = value.lower()
    if normalized not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise HTTPException(status_code=400, detail=f"Invalid {field}. Allowed: {allowed_list}")
    return normalized


def _validate_url(value: str) -> None:
    if not (value.startswith("http://") or value.startswith("https://") or value.startswith("file://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme for source")


def _all_jurisdictions() -> List[str]:
    stored = {doc.get("jurisdiction") for doc in documents_db.values() if doc.get("jurisdiction")}
    indexed = set(vector_store.list_jurisdictions())
    return sorted(stored | indexed)


def _count_by_field(items: Iterable[Dict[str, Any]], field: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        value = (item.get(field) or "Unknown")
        if isinstance(value, str):
            key = value.strip() or "Unknown"
        else:
            key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0].lower()))


# Store for processed documents (in production, use a proper database)
documents_db: Dict[str, Dict[str, Any]] = load_documents_db(DOCUMENTS_DB_PATH)
change_db: Dict[str, Dict[str, Any]] = load_json_dict(CHANGE_DB_PATH)
audit_log: List[Dict[str, Any]] = load_json_list(AUDIT_LOG_PATH)
sources_db: Dict[str, Dict[str, Any]] = load_json_dict(SOURCES_DB_PATH)
evidence_db: List[Dict[str, Any]] = load_json_list(EVIDENCE_DB_PATH)
policies_db: Dict[str, Dict[str, Any]] = load_json_dict(POLICIES_DB_PATH)
webhooks_db: Dict[str, Dict[str, Any]] = load_json_dict(WEBHOOKS_DB_PATH)


# Pydantic models
class QueryRequest(BaseModel):
    query: str
    jurisdiction: str | None = None
    doc_id: str | None = None
    no_llm: bool | None = None
    n_results: int = settings.default_query_results


class CompareRequest(BaseModel):
    jurisdiction1: str
    jurisdiction2: str
    no_llm: bool | None = None


class QueryResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    summary: str | None = None


class RequirementReviewRequest(BaseModel):
    status: str | None = None
    reviewer: str | None = None
    notes: str | None = None
    tags: List[str] | None = None
    controls: List[str] | None = None
    policy_refs: List[str] | None = None


class ChangeCreateRequest(BaseModel):
    title: str
    jurisdiction: str
    entity: str | None = None
    business_unit: str | None = None
    summary: str | None = None
    source: str | None = None
    effective_date: str | None = None
    severity: str | None = None
    owner: str | None = None
    due_date: str | None = None
    status: str | None = None
    impacted_areas: List[str] | None = None
    related_requirement_ids: List[str] | None = None
    policy_refs: List[str] | None = None


class ChangeUpdateRequest(BaseModel):
    status: str | None = None
    severity: str | None = None
    owner: str | None = None
    due_date: str | None = None
    impact_assessment: str | None = None
    impacted_areas: List[str] | None = None
    related_requirement_ids: List[str] | None = None
    entity: str | None = None
    business_unit: str | None = None
    policy_refs: List[str] | None = None


class SourceCreateRequest(BaseModel):
    name: str
    url: str
    jurisdiction: str | None = None
    entity: str | None = None
    business_unit: str | None = None
    default_severity: str | None = None


class ChangeApprovalRequest(BaseModel):
    approver: str
    status: str = "pending"
    notes: str | None = None


class ChangeApprovalUpdateRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


class ChangeSuggestRequest(BaseModel):
    no_llm: bool | None = None
    n_results: int = 5


class ChangeImpactBriefRequest(BaseModel):
    no_llm: bool | None = None
    n_results: int = 5
    max_claims_per_section: int = 8
    max_citations: int = 20


class PolicyUpdateRequest(BaseModel):
    status: str | None = None
    version: str | None = None
    owner: str | None = None


class WebhookCreateRequest(BaseModel):
    url: str
    events: List[str] | None = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "RegAtlas",
        "version": "0.1.0",
        "documents_count": vector_store.get_document_count(),
        "jurisdictions": _all_jurisdictions()
    }


@app.get("/healthz")
async def healthz():
    """Lightweight health check."""
    return {"status": "ok", "started_at": STARTED_AT.isoformat()}


@app.get("/readyz")
async def readyz():
    """Readiness check to confirm data stores are available."""
    try:
        vector_store.get_document_count()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Vector store unavailable") from exc
    return {"status": "ready"}


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    jurisdiction: str = Query(..., description="Regulatory jurisdiction (e.g., 'Hong Kong', 'Singapore')"),
    entity: str | None = Query(None, description="Entity or subsidiary name"),
    business_unit: str | None = Query(None, description="Business unit or line"),
    no_llm: bool = Query(False, description="Disable LLM extraction"),
    allow_duplicate: bool = Query(True, description="Allow duplicate uploads for same content")
):
    """
    Upload and process a regulatory document.
    
    Args:
        file: PDF or text file containing regulatory text
        jurisdiction: Jurisdiction this document belongs to
        
    Returns:
        Processing results including extracted requirements
    """
    logger.info(f"Received upload: {file.filename} for jurisdiction: {jurisdiction}")
    
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")
        if Path(file.filename).suffix.lower() not in {".pdf", ".txt"}:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # Generate document ID
        doc_id = str(uuid.uuid4())
        
        # Save uploaded file temporarily
        temp_dir = settings.data_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        safe_name = Path(file.filename).name
        file_path = temp_dir / f"{doc_id}_{safe_name}"
        
        with open(file_path, "wb") as f:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            max_size = settings.max_upload_mb * 1024 * 1024
            if len(content) > max_size:
                raise HTTPException(status_code=413, detail="Uploaded file is too large")
            f.write(content)

        content_hash = _content_hash(content)
        if not allow_duplicate:
            for doc in documents_db.values():
                if doc.get("content_hash") == content_hash:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Duplicate document detected (doc_id={doc.get('doc_id')})"
                    )
        
        # Process document
        processed = doc_processor.process_file(file_path)
        
        # Extract requirements
        full_text = processed["full_text"]
        if not full_text.strip():
            raise HTTPException(status_code=400, detail="No text extracted from document")
        requirements_payload = req_extractor.extract_requirements(
            full_text,
            jurisdiction,
            force_basic=no_llm
        )

        # Chunk and add to vector store
        chunks = doc_processor.chunk_text(full_text, chunk_size=1000, overlap=200)
        if not chunks:
            raise HTTPException(status_code=400, detail="Document text too short to index")
        
        metadata = {
            **processed["metadata"],
            "jurisdiction": jurisdiction,
            "entity": _normalize_text(entity),
            "business_unit": _normalize_text(business_unit),
            "doc_id": doc_id,
            "content_hash": content_hash,
            "size_bytes": len(content)
        }
        
        chunks_added = vector_store.add_document(doc_id, chunks, metadata)
        if chunks_added == 0:
            raise HTTPException(status_code=400, detail="No chunks indexed for document")
        
        # Normalize requirements and attach evidence
        requirements = _normalize_requirements(
            requirements_payload.get("requirements", []),
            doc_id=doc_id,
            jurisdiction=jurisdiction,
            filename=safe_name,
            entity=_normalize_text(entity),
            business_unit=_normalize_text(business_unit)
        )
        _attach_evidence(requirements, doc_id)

        # Store document info
        documents_db[doc_id] = {
            "doc_id": doc_id,
            "filename": safe_name,
            "jurisdiction": jurisdiction,
            "entity": _normalize_text(entity),
            "business_unit": _normalize_text(business_unit),
            "requirements": requirements,
            "raw_extraction": requirements_payload.get("raw_extraction"),
            "chunks_count": chunks_added,
            "metadata": metadata,
            "content_hash": content_hash,
            "size_bytes": len(content),
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        save_documents_db(DOCUMENTS_DB_PATH, documents_db)
        
        logger.info(f"Successfully processed document {doc_id}")
        
        return {
            "doc_id": doc_id,
            "filename": safe_name,
            "jurisdiction": jurisdiction,
            "chunks_added": chunks_added,
            "requirements": requirements
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path and file_path.exists():
            file_path.unlink()


@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Query regulatory documents using RAG.
    
    Args:
        request: Query request with search terms and optional filters
        
    Returns:
        Relevant document chunks and optional LLM-generated summary
    """
    logger.info(f"Query: '{request.query}' (jurisdiction: {request.jurisdiction})")
    
    try:
        if request.n_results < 1 or request.n_results > settings.max_query_results:
            raise HTTPException(
                status_code=400,
                detail=f"n_results must be between 1 and {settings.max_query_results}"
            )

        # Search vector store
        filters = {}
        if request.doc_id:
            filters["doc_id"] = request.doc_id

        results = vector_store.query(
            query_text=request.query,
            n_results=request.n_results,
            jurisdiction=request.jurisdiction,
            filters=filters or None
        )
        
        # Optionally generate summary with LLM
        summary = None
        if req_extractor.client and results and not request.no_llm:
            context = "\n\n".join([r["document"] for r in results[:3]])
            
            try:
                from openai import OpenAI
                client = OpenAI(
                    api_key=llm_api_key,
                    base_url=settings.openai_base_url
                )
                
                response = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": "You are a regulatory compliance expert. Provide concise, accurate answers based on the provided regulatory text."},
                        {"role": "user", "content": f"Based on the following regulatory text, answer this question: {request.query}\n\nContext:\n{context}"}
                    ],
                    temperature=0.1,
                    max_tokens=500
                )
                
                summary = response.choices[0].message.content or "No summary generated"
                
            except Exception as e:
                logger.warning(f"Could not generate summary: {e}")
        
        return QueryResponse(
            query=request.query,
            results=results,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare")
async def compare_jurisdictions(request: CompareRequest):
    """
    Compare regulatory requirements between two jurisdictions.
    
    Args:
        request: Comparison request specifying two jurisdictions
        
    Returns:
        Comparison summary highlighting similarities and differences
    """
    logger.info(f"Comparing: {request.jurisdiction1} vs {request.jurisdiction2}")
    
    try:
        # Find documents for each jurisdiction
        docs1 = [doc for doc in documents_db.values() 
                if doc["jurisdiction"] == request.jurisdiction1]
        docs2 = [doc for doc in documents_db.values() 
                if doc["jurisdiction"] == request.jurisdiction2]
        
        if not docs1:
            raise HTTPException(
                status_code=404,
                detail=f"No documents found for jurisdiction: {request.jurisdiction1}"
            )
        
        if not docs2:
            raise HTTPException(
                status_code=404,
                detail=f"No documents found for jurisdiction: {request.jurisdiction2}"
            )
        
        # Aggregate requirements
        req1 = {
            "jurisdiction": request.jurisdiction1,
            "requirements": []
        }
        req2 = {
            "jurisdiction": request.jurisdiction2,
            "requirements": []
        }
        
        for doc in docs1:
            req1["requirements"].extend(_extract_requirements_from_doc(doc))
        
        for doc in docs2:
            req2["requirements"].extend(_extract_requirements_from_doc(doc))
        
        # Generate comparison
        comparison = req_extractor.compare_requirements(
            req1,
            req2,
            force_basic=bool(request.no_llm)
        )
        
        return {
            "jurisdiction1": request.jurisdiction1,
            "jurisdiction2": request.jurisdiction2,
            "comparison": comparison,
            "documents_compared": {
                request.jurisdiction1: len(docs1),
                request.jurisdiction2: len(docs2)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing jurisdictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None
):
    """List all processed documents."""
    docs = _sort_by_iso(list(documents_db.values()), "uploaded_at")
    filtered = []
    for doc in docs:
        if jurisdiction and doc.get("jurisdiction") != jurisdiction:
            continue
        if entity and doc.get("entity") != entity:
            continue
        if business_unit and doc.get("business_unit") != business_unit:
            continue
        if q:
            haystack = " ".join(
                [
                    doc.get("filename") or "",
                    doc.get("jurisdiction") or "",
                    doc.get("entity") or "",
                    doc.get("business_unit") or ""
                ]
            ).lower()
            if q.lower() not in haystack:
                continue
        filtered.append(doc)

    total = len(filtered)
    paged = _paginate(filtered, limit, offset)
    return {
        "documents": paged,
        "total": total,
        "limit": limit,
        "offset": offset or 0,
        "jurisdictions": _all_jurisdictions()
    }


@app.get("/documents/export")
async def export_documents(format: str = "csv"):
    """Export document metadata."""
    docs = _sort_by_iso(list(documents_db.values()), "uploaded_at")
    if format.lower() == "json":
        return {"documents": docs, "total": len(docs)}
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV or JSON export is supported")

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "doc_id",
            "filename",
            "jurisdiction",
            "entity",
            "business_unit",
            "chunks_count",
            "requirements_count",
            "size_bytes",
            "content_hash",
            "uploaded_at"
        ]
    )
    writer.writeheader()
    for doc in docs:
        writer.writerow({
            "doc_id": doc.get("doc_id"),
            "filename": doc.get("filename"),
            "jurisdiction": doc.get("jurisdiction"),
            "entity": doc.get("entity"),
            "business_unit": doc.get("business_unit"),
            "chunks_count": doc.get("chunks_count"),
            "requirements_count": len(doc.get("requirements") or []),
            "size_bytes": doc.get("size_bytes"),
            "content_hash": doc.get("content_hash"),
            "uploaded_at": doc.get("uploaded_at")
        })

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents.csv"}
    )


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get a single document with requirements."""
    doc = documents_db.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.get("/documents/{doc_id}/requirements")
async def list_document_requirements(
    doc_id: str,
    limit: int | None = None,
    offset: int | None = None
):
    """List requirements for a specific document."""
    doc = documents_db.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    requirements = doc.get("requirements") or []
    return {
        "requirements": _paginate(requirements, limit, offset),
        "total": len(requirements),
        "limit": limit,
        "offset": offset or 0
    }


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its vector chunks."""
    doc = documents_db.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    vector_store.delete_document(doc_id)
    documents_db.pop(doc_id, None)
    save_documents_db(DOCUMENTS_DB_PATH, documents_db)

    return {"deleted": True, "doc_id": doc_id}


@app.get("/requirements")
async def list_requirements(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    requirement_type: str | None = None,
    mandatory: str | None = None,
    status: str | None = None,
    doc_id: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None
):
    """List requirements with optional filters."""
    requirements = _sort_by_iso(_gather_requirements(), "created_at")
    filtered = _filter_requirements(
        requirements,
        jurisdiction=jurisdiction,
        entity=entity,
        business_unit=business_unit,
        requirement_type=requirement_type,
        mandatory=mandatory,
        status=status,
        doc_id=doc_id,
        q=q
    )
    return {
        "requirements": _paginate(filtered, limit, offset),
        "total": len(filtered),
        "limit": limit,
        "offset": offset or 0,
        "types": sorted({r.get("requirement_type", "") for r in requirements if r.get("requirement_type")})
    }


@app.get("/requirements/stats")
async def requirement_stats():
    """Aggregate requirement counts."""
    requirements = _gather_requirements()
    return {
        "total": len(requirements),
        "by_jurisdiction": _count_by_field(requirements, "jurisdiction"),
        "by_type": _count_by_field(requirements, "requirement_type"),
        "by_status": _count_by_field(requirements, "status"),
        "by_mandatory": _count_by_field(requirements, "mandatory")
    }


@app.get("/requirements/id/{requirement_id}")
async def get_requirement(requirement_id: str):
    """Get a single requirement by ID."""
    for req in _gather_requirements():
        if req.get("requirement_id") == requirement_id:
            return req
    raise HTTPException(status_code=404, detail="Requirement not found")


@app.get("/requirements/id/{requirement_id}/evidence")
async def get_requirement_evidence(requirement_id: str):
    """Get evidence metadata for a requirement."""
    for req in _gather_requirements():
        if req.get("requirement_id") == requirement_id:
            return {"requirement_id": requirement_id, "evidence": req.get("evidence") or {}}
    raise HTTPException(status_code=404, detail="Requirement not found")


@app.post("/requirements/id/{requirement_id}/review")
async def review_requirement(requirement_id: str, request: RequirementReviewRequest):
    """Update requirement review metadata."""
    updated = None
    for doc in documents_db.values():
        for req in doc.get("requirements", []):
            if req.get("requirement_id") == requirement_id:
                if request.status is not None:
                    req["status"] = _validate_choice(request.status, ALLOWED_REQ_STATUS, "status")
                if request.reviewer is not None:
                    req["reviewer"] = request.reviewer
                if request.notes is not None:
                    req["review_notes"] = request.notes
                if request.tags is not None:
                    req["tags"] = request.tags
                if request.controls is not None:
                    req["controls"] = request.controls
                if request.policy_refs is not None:
                    req["policy_refs"] = request.policy_refs
                req["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                updated = req
                break
        if updated:
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Requirement not found")

    save_documents_db(DOCUMENTS_DB_PATH, documents_db)
    _append_audit_log(
        action="requirement_reviewed",
        entity_type="requirement",
        entity_id=requirement_id,
        details={"status": request.status, "reviewer": request.reviewer}
    )
    return updated


@app.get("/requirements/export")
async def export_requirements(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    requirement_type: str | None = None,
    mandatory: str | None = None,
    status: str | None = None,
    doc_id: str | None = None,
    q: str | None = None,
    format: str = "csv"
):
    """Export requirements in CSV format."""
    requirements = _filter_requirements(
        _gather_requirements(),
        jurisdiction=jurisdiction,
        entity=entity,
        business_unit=business_unit,
        requirement_type=requirement_type,
        mandatory=mandatory,
        status=status,
        doc_id=doc_id,
        q=q
    )

    if format.lower() == "json":
        return {"requirements": requirements, "total": len(requirements)}
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV or JSON export is supported")

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "requirement_id",
            "jurisdiction",
            "requirement_type",
            "description",
            "details",
            "mandatory",
            "confidence",
            "status",
            "reviewer",
            "review_notes",
            "controls",
            "policy_refs",
            "entity",
            "business_unit",
            "doc_id",
            "filename",
            "source_snippet",
            "evidence_chunk_id",
            "evidence_text"
        ]
    )
    writer.writeheader()
    for req in requirements:
        writer.writerow({
            "requirement_id": req.get("requirement_id"),
            "jurisdiction": req.get("jurisdiction"),
            "requirement_type": req.get("requirement_type"),
            "description": req.get("description"),
            "details": req.get("details"),
            "mandatory": req.get("mandatory"),
            "confidence": req.get("confidence"),
            "status": req.get("status"),
            "reviewer": req.get("reviewer"),
            "review_notes": req.get("review_notes"),
            "controls": ",".join(req.get("controls") or []),
            "policy_refs": ",".join(req.get("policy_refs") or []),
            "entity": req.get("entity"),
            "business_unit": req.get("business_unit"),
            "doc_id": req.get("doc_id"),
            "filename": req.get("filename"),
            "source_snippet": req.get("source_snippet"),
            "evidence_chunk_id": req.get("evidence", {}).get("chunk_id"),
            "evidence_text": req.get("evidence", {}).get("text")
        })

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=requirements.csv"}
    )


@app.post("/changes")
async def create_change(request: ChangeCreateRequest):
    """Create a regulatory change item."""
    _validate_date_str(request.effective_date, "effective_date")
    _validate_date_str(request.due_date, "due_date")
    status = _validate_choice(request.status, ALLOWED_CHANGE_STATUS, "status") or "new"
    severity = _validate_choice(request.severity, ALLOWED_CHANGE_SEVERITY, "severity") or "medium"
    change_id = str(uuid.uuid4())
    change = {
        "change_id": change_id,
        "title": request.title,
        "jurisdiction": request.jurisdiction,
        "entity": _normalize_text(request.entity),
        "business_unit": _normalize_text(request.business_unit),
        "summary": request.summary,
        "source": request.source,
        "effective_date": request.effective_date,
        "severity": severity,
        "owner": request.owner,
        "due_date": request.due_date,
        "status": status,
        "impacted_areas": request.impacted_areas or [],
        "impact_assessment": None,
        "related_requirement_ids": request.related_requirement_ids or [],
        "policy_refs": request.policy_refs or [],
        "approvals": [],
        "source_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "risk_score": 0
    }
    change["risk_score"] = _compute_risk_score(change)
    change_db[change_id] = change
    save_json_dict(CHANGE_DB_PATH, change_db)
    _append_audit_log(
        action="change_created",
        entity_type="change",
        entity_id=change_id,
        details={"title": request.title, "jurisdiction": request.jurisdiction}
    )
    _dispatch_webhooks("change.created", change)
    return change


@app.get("/changes")
async def list_changes(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    owner: str | None = None,
    q: str | None = None,
    include_overdue: bool = False,
    limit: int | None = None,
    offset: int | None = None
):
    """List regulatory change items with optional filters."""
    changes = _sort_by_iso(list(change_db.values()), "created_at")
    status_norm = _normalize_status(status)
    severity_norm = _normalize_severity(severity)
    filtered = []
    for change in changes:
        if jurisdiction and change.get("jurisdiction") != jurisdiction:
            continue
        if entity and change.get("entity") != entity:
            continue
        if business_unit and change.get("business_unit") != business_unit:
            continue
        if status_norm and (change.get("status") or "").lower() != status_norm:
            continue
        if severity_norm and (change.get("severity") or "").lower() != severity_norm:
            continue
        if owner and change.get("owner") != owner:
            continue
        if q:
            haystack = " ".join(
                [
                    change.get("title") or "",
                    change.get("summary") or "",
                    change.get("source") or ""
                ]
            ).lower()
            if q.lower() not in haystack:
                continue
        filtered.append(change)

    if include_overdue:
        now = datetime.now(timezone.utc).date()
        for change in filtered:
            due_date = change.get("due_date")
            status_val = change.get("status")
            overdue = False
            days_overdue = None
            if due_date and status_val != "implemented":
                try:
                    due = datetime.fromisoformat(due_date).date()
                    if due < now:
                        overdue = True
                        days_overdue = (now - due).days
                except ValueError:
                    pass
            change["overdue"] = overdue
            change["days_overdue"] = days_overdue

    return {
        "changes": _paginate(filtered, limit, offset),
        "total": len(filtered),
        "limit": limit,
        "offset": offset or 0
    }




@app.post("/changes/{change_id}")
async def update_change(change_id: str, request: ChangeUpdateRequest):
    """Update a regulatory change item."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if request.status is not None:
        change["status"] = _validate_choice(request.status, ALLOWED_CHANGE_STATUS, "status")
    if request.severity is not None:
        change["severity"] = _validate_choice(request.severity, ALLOWED_CHANGE_SEVERITY, "severity")
    if request.owner is not None:
        change["owner"] = request.owner
    if request.due_date is not None:
        _validate_date_str(request.due_date, "due_date")
        change["due_date"] = request.due_date
    if request.impact_assessment is not None:
        change["impact_assessment"] = request.impact_assessment
    if request.impacted_areas is not None:
        change["impacted_areas"] = request.impacted_areas
    if request.related_requirement_ids is not None:
        change["related_requirement_ids"] = request.related_requirement_ids
    if request.policy_refs is not None:
        change["policy_refs"] = request.policy_refs
    if request.entity is not None:
        change["entity"] = _normalize_text(request.entity)
    if request.business_unit is not None:
        change["business_unit"] = _normalize_text(request.business_unit)

    change["updated_at"] = datetime.now(timezone.utc).isoformat()
    change["risk_score"] = _compute_risk_score(change)
    save_json_dict(CHANGE_DB_PATH, change_db)
    _append_audit_log(
        action="change_updated",
        entity_type="change",
        entity_id=change_id,
        details={"status": request.status, "owner": request.owner}
    )
    _dispatch_webhooks("change.updated", change)
    return change


@app.delete("/changes/{change_id}")
async def delete_change(change_id: str):
    """Delete a regulatory change item."""
    if change_id not in change_db:
        raise HTTPException(status_code=404, detail="Change not found")
    deleted = change_db.pop(change_id, None)
    save_json_dict(CHANGE_DB_PATH, change_db)
    _append_audit_log(
        action="change_deleted",
        entity_type="change",
        entity_id=change_id,
        details={"title": deleted.get("title") if deleted else None}
    )
    _dispatch_webhooks("change.deleted", deleted or {"change_id": change_id})
    return {"deleted": True, "change_id": change_id}


@app.get("/changes/export")
async def export_changes(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    owner: str | None = None,
    q: str | None = None,
    format: str = "csv"
):
    """Export regulatory changes in CSV format."""
    changes = await list_changes(
        jurisdiction=jurisdiction,
        entity=entity,
        business_unit=business_unit,
        status=status,
        severity=severity,
        owner=owner,
        q=q
    )
    items = changes.get("changes", [])

    if format.lower() == "json":
        return {"changes": items, "total": len(items)}
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV or JSON export is supported")

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "change_id",
            "title",
            "jurisdiction",
            "summary",
            "source",
            "effective_date",
            "severity",
            "status",
            "owner",
            "due_date",
            "entity",
            "business_unit",
            "impacted_areas",
            "impact_assessment",
            "related_requirement_ids",
            "policy_refs",
            "risk_score",
            "created_at",
            "updated_at"
        ]
    )
    writer.writeheader()
    for change in items:
        writer.writerow({
            "change_id": change.get("change_id"),
            "title": change.get("title"),
            "jurisdiction": change.get("jurisdiction"),
            "summary": change.get("summary"),
            "source": change.get("source"),
            "effective_date": change.get("effective_date"),
            "severity": change.get("severity"),
            "status": change.get("status"),
            "owner": change.get("owner"),
            "due_date": change.get("due_date"),
            "entity": change.get("entity"),
            "business_unit": change.get("business_unit"),
            "impacted_areas": ",".join(change.get("impacted_areas") or []),
            "impact_assessment": change.get("impact_assessment"),
            "related_requirement_ids": ",".join(change.get("related_requirement_ids") or []),
            "policy_refs": ",".join(change.get("policy_refs") or []),
            "risk_score": change.get("risk_score"),
            "created_at": change.get("created_at"),
            "updated_at": change.get("updated_at")
        })

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reg_changes.csv"}
    )




@app.post("/changes/{change_id}/approvals")
async def add_change_approval(change_id: str, request: ChangeApprovalRequest):
    """Add an approval step for a change item."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    approval = {
        "approval_id": str(uuid.uuid4()),
        "approver": request.approver,
        "status": request.status,
        "notes": request.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None
    }
    change.setdefault("approvals", []).append(approval)
    change["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_json_dict(CHANGE_DB_PATH, change_db)
    _append_audit_log(
        action="change_approval_added",
        entity_type="change",
        entity_id=change_id,
        details={"approval_id": approval["approval_id"], "approver": request.approver}
    )
    _dispatch_webhooks("change.approval_added", approval)
    return approval


@app.get("/changes/{change_id}/approvals")
async def list_change_approvals(change_id: str):
    """List approvals for a change item."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    approvals = change.get("approvals") or []
    return {"approvals": approvals, "total": len(approvals)}


@app.post("/changes/{change_id}/approvals/{approval_id}")
async def update_change_approval(
    change_id: str,
    approval_id: str,
    request: ChangeApprovalUpdateRequest
):
    """Update approval status for a change item."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    approvals = change.get("approvals", [])
    updated = None
    for approval in approvals:
        if approval.get("approval_id") == approval_id:
            if request.status is not None:
                approval["status"] = request.status
            if request.notes is not None:
                approval["notes"] = request.notes
            approval["updated_at"] = datetime.now(timezone.utc).isoformat()
            updated = approval
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Approval not found")

    change["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_json_dict(CHANGE_DB_PATH, change_db)
    _append_audit_log(
        action="change_approval_updated",
        entity_type="change",
        entity_id=change_id,
        details={"approval_id": approval_id, "status": request.status}
    )
    _dispatch_webhooks("change.approval_updated", updated)
    return updated


@app.post("/changes/{change_id}/ai-suggest")
async def suggest_change_impact(change_id: str, request: ChangeSuggestRequest):
    """Suggest impacted requirements and impact summary."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    query_text = " ".join(
        [
            change.get("title") or "",
            change.get("summary") or "",
            change.get("jurisdiction") or "",
        ]
    ).strip()

    results = []
    if query_text:
        results = vector_store.query(query_text=query_text, n_results=request.n_results)

    matched_requirements = []
    suggested_controls = set()
    suggested_policy_refs = set()
    suggested_impacted_areas = set(change.get("impacted_areas") or [])
    for item in results:
        metadata = item.get("metadata") or {}
        doc_id = metadata.get("doc_id")
        reqs = _extract_requirements_from_doc(documents_db.get(doc_id, {}))
        for req in reqs:
            matched_requirements.append(req)
            for control in req.get("controls") or []:
                suggested_controls.add(control)
            for policy in req.get("policy_refs") or []:
                suggested_policy_refs.add(policy)

    impact_summary = _basic_impact_summary(change, matched_requirements)
    use_llm = req_extractor.client is not None and not (request.no_llm or False)
    if use_llm and matched_requirements:
        context = "\n".join(
            f"- {req.get('requirement_type')}: {req.get('description')}" for req in matched_requirements[:5]
        )
        prompt = (
            f"Summarize impact for this regulatory change:\n"
            f"Title: {change.get('title')}\n"
            f"Summary: {change.get('summary')}\n"
            f"Jurisdiction: {change.get('jurisdiction')}\n\n"
            f"Related requirements:\n{context}\n\n"
            "Provide a concise impact assessment (2-4 sentences)."
        )
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "You are a regulatory compliance expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            impact_summary = response.choices[0].message.content or impact_summary
        except Exception as e:
            logger.warning(f"AI impact summary failed: {e}")

    return {
        "change_id": change_id,
        "impact_summary": impact_summary,
        "suggested_controls": sorted(suggested_controls),
        "suggested_policy_refs": sorted(suggested_policy_refs),
        "matched_requirements": matched_requirements[: request.n_results],
    }


@app.post("/changes/{change_id}/impact-brief")
async def generate_change_impact_brief(change_id: str, request: ChangeImpactBriefRequest):
    """Generate an audit-grade impact brief with claim-level citations."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    query_text = " ".join(
        [
            change.get("title") or "",
            change.get("summary") or "",
            change.get("jurisdiction") or "",
        ]
    ).strip()

    results = []
    if query_text:
        results = vector_store.query(query_text=query_text, n_results=request.n_results)

    matched_requirements = _collect_matched_requirements(results)
    requirements_context = _requirements_context(
        matched_requirements,
        max_items=max(request.max_claims_per_section, 0)
    )

    use_llm = req_extractor.client is not None and not (request.no_llm or False)
    summary_claims = []
    llm_error = None
    if use_llm and requirements_context:
        prompt = _impact_brief_prompt(change, requirements_context, request.max_claims_per_section)
        try:
            response = req_extractor.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "You are a regulatory compliance expert. Respond with JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=800
            )
            raw = response.choices[0].message.content or ""
            payload = _extract_json_payload(raw) or {}
            summary_claims = payload.get("summary", []) if isinstance(payload, dict) else []
            if request.max_claims_per_section > 0:
                summary_claims = summary_claims[: request.max_claims_per_section]
        except Exception as exc:
            llm_error = str(exc)
            logger.warning(f"Impact brief LLM failed: {exc}")

    if not summary_claims:
        summary_claims = _deterministic_claims(
            change,
            matched_requirements,
            max_claims=request.max_claims_per_section,
        )

    validated = _validate_claims(summary_claims, max_citations=request.max_citations)
    validation = _claim_validation_summary(validated)

    return {
        "change_id": change_id,
        "change": {
            "title": change.get("title"),
            "jurisdiction": change.get("jurisdiction"),
            "summary": change.get("summary"),
            "effective_date": change.get("effective_date"),
            "severity": change.get("severity"),
        },
        "brief": {
            "summary": validated,
        },
        "requirements": requirements_context,
        "validation": validation,
        "metadata": {
            "llm_used": bool(use_llm and summary_claims and llm_error is None),
            "llm_error": llm_error,
            "n_results": request.n_results,
            "max_claims_per_section": request.max_claims_per_section,
            "max_citations": request.max_citations,
        },
    }


@app.get("/alerts")
async def get_alerts(
    jurisdiction: str | None = None,
    owner: str | None = None,
    severity: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None
):
    """Return overdue change items."""
    overdue = _get_overdue_changes()
    filtered = []
    severity_norm = _normalize_severity(severity) if severity else None
    for change in overdue:
        if jurisdiction and change.get("jurisdiction") != jurisdiction:
            continue
        if owner and change.get("owner") != owner:
            continue
        if entity and change.get("entity") != entity:
            continue
        if business_unit and change.get("business_unit") != business_unit:
            continue
        if severity_norm and (change.get("severity") or "").lower() != severity_norm:
            continue
        filtered.append(change)
    return {"overdue": filtered, "total": len(filtered)}


@app.get("/entities")
async def list_entities():
    """List entities and business units found in data."""
    entities = set()
    business_units = set()
    for doc in documents_db.values():
        if doc.get("entity"):
            entities.add(doc["entity"])
        if doc.get("business_unit"):
            business_units.add(doc["business_unit"])
    for change in change_db.values():
        if change.get("entity"):
            entities.add(change["entity"])
        if change.get("business_unit"):
            business_units.add(change["business_unit"])
    return {
        "entities": sorted(entities),
        "business_units": sorted(business_units)
    }


@app.get("/policies")
async def list_policies():
    """List internal policies and procedures."""
    _ensure_policy_seeded()
    return {"policies": list(policies_db.values()), "total": len(policies_db)}


@app.get("/policies/export")
async def export_policies(format: str = "csv"):
    """Export policies."""
    _ensure_policy_seeded()
    policies = _sort_by_iso(list(policies_db.values()), "created_at")
    if format.lower() == "json":
        return {"policies": policies, "total": len(policies)}
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV or JSON export is supported")

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["policy_id", "title", "summary", "status", "version", "owner", "created_at", "updated_at"]
    )
    writer.writeheader()
    for policy in policies:
        writer.writerow({
            "policy_id": policy.get("policy_id"),
            "title": policy.get("title"),
            "summary": policy.get("summary"),
            "status": policy.get("status"),
            "version": policy.get("version"),
            "owner": policy.get("owner"),
            "created_at": policy.get("created_at"),
            "updated_at": policy.get("updated_at")
        })

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=policies.csv"}
    )


@app.get("/policies/{policy_id}")
async def get_policy(policy_id: str):
    """Get a policy by ID."""
    _ensure_policy_seeded()
    policy = policies_db.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.post("/policies/{policy_id}/update")
async def update_policy(policy_id: str, request: PolicyUpdateRequest):
    """Update policy status/version/owner."""
    _ensure_policy_seeded()
    policy = policies_db.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if request.status is not None:
        policy["status"] = request.status
    if request.version is not None:
        policy["version"] = request.version
    if request.owner is not None:
        policy["owner"] = request.owner
    policy["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_json_dict(POLICIES_DB_PATH, policies_db)
    _append_audit_log(
        action="policy_updated",
        entity_type="policy",
        entity_id=policy_id,
        details={"status": request.status, "version": request.version}
    )
    return policy


@app.post("/sources")
async def add_source(request: SourceCreateRequest):
    """Register a regulatory source feed."""
    _validate_url(request.url)
    source_id = str(uuid.uuid4())
    sources_db[source_id] = {
        "source_id": source_id,
        "name": request.name,
        "url": request.url,
        "jurisdiction": request.jurisdiction,
        "entity": _normalize_text(request.entity),
        "business_unit": _normalize_text(request.business_unit),
        "default_severity": request.default_severity or "medium",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_json_dict(SOURCES_DB_PATH, sources_db)
    _append_audit_log(
        action="source_added",
        entity_type="source",
        entity_id=source_id,
        details={"name": request.name}
    )
    return sources_db[source_id]


@app.get("/sources")
async def list_sources(
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None
):
    """List all regulatory sources."""
    sources = _sort_by_iso(list(sources_db.values()), "created_at")
    if q:
        filtered = []
        for source in sources:
            haystack = " ".join(
                [
                    source.get("name") or "",
                    source.get("url") or "",
                    source.get("jurisdiction") or "",
                    source.get("entity") or "",
                    source.get("business_unit") or ""
                ]
            ).lower()
            if q.lower() in haystack:
                filtered.append(source)
        sources = filtered
    return {
        "sources": _paginate(sources, limit, offset),
        "total": len(sources),
        "limit": limit,
        "offset": offset or 0
    }


@app.get("/sources/{source_id}")
async def get_source(source_id: str):
    """Get a regulatory source."""
    source = sources_db.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@app.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Delete a regulatory source."""
    if source_id not in sources_db:
        raise HTTPException(status_code=404, detail="Source not found")
    sources_db.pop(source_id, None)
    save_json_dict(SOURCES_DB_PATH, sources_db)
    _append_audit_log(
        action="source_deleted",
        entity_type="source",
        entity_id=source_id
    )
    return {"deleted": True, "source_id": source_id}


@app.post("/scan")
async def scan_sources(source_id: str | None = None):
    """Scan regulatory sources and create change items."""
    sources = [sources_db[source_id]] if source_id and source_id in sources_db else list(sources_db.values())
    if not sources:
        raise HTTPException(status_code=404, detail="No sources configured")

    created = []
    for source in sources:
        entries = _parse_feed_entries(source["url"])
        for entry in entries:
            dedupe_key = entry.get("id") or entry.get("link") or entry.get("title")
            if not dedupe_key:
                continue
            if _change_exists_for_source(source["source_id"], dedupe_key):
                continue
            change_id = str(uuid.uuid4())
            change = {
                "change_id": change_id,
                "title": entry.get("title") or "Regulatory update",
                "jurisdiction": source.get("jurisdiction"),
                "entity": source.get("entity"),
                "business_unit": source.get("business_unit"),
                "summary": entry.get("summary"),
                "source": entry.get("link"),
                "effective_date": entry.get("published"),
                "severity": source.get("default_severity", "medium"),
                "owner": None,
                "due_date": None,
                "status": "new",
                "impacted_areas": [],
                "impact_assessment": None,
                "related_requirement_ids": [],
                "approvals": [],
                "source_id": source["source_id"],
                "source_entry_id": dedupe_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
                "risk_score": 0
            }
            change["risk_score"] = _compute_risk_score(change)
            change_db[change_id] = change
            created.append(change)
    save_json_dict(CHANGE_DB_PATH, change_db)
    _append_audit_log(
        action="sources_scanned",
        entity_type="source",
        entity_id=source_id or "all",
        details={"created_changes": len(created)}
    )
    for change in created:
        _dispatch_webhooks("change.created", change)
    return {"created": created, "total_created": len(created)}


@app.post("/webhooks")
async def add_webhook(request: WebhookCreateRequest):
    """Register an outbound webhook."""
    if not (request.url.startswith("http://") or request.url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid webhook URL scheme")
    webhook_id = str(uuid.uuid4())
    webhooks_db[webhook_id] = {
        "webhook_id": webhook_id,
        "url": request.url,
        "events": request.events or ["change.created", "change.updated"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_json_dict(WEBHOOKS_DB_PATH, webhooks_db)
    return webhooks_db[webhook_id]


@app.get("/webhooks")
async def list_webhooks(
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None
):
    """List webhooks."""
    webhooks = _sort_by_iso(list(webhooks_db.values()), "created_at")
    if q:
        filtered = []
        for hook in webhooks:
            haystack = " ".join(
                [
                    hook.get("url") or "",
                    ",".join(hook.get("events") or [])
                ]
            ).lower()
            if q.lower() in haystack:
                filtered.append(hook)
        webhooks = filtered
    return {
        "webhooks": _paginate(webhooks, limit, offset),
        "total": len(webhooks),
        "limit": limit,
        "offset": offset or 0
    }


@app.get("/webhooks/{webhook_id}")
async def get_webhook(webhook_id: str):
    """Get a webhook by ID."""
    webhook = webhooks_db.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@app.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    if webhook_id not in webhooks_db:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhooks_db.pop(webhook_id, None)
    save_json_dict(WEBHOOKS_DB_PATH, webhooks_db)
    return {"deleted": True, "webhook_id": webhook_id}


@app.post("/evidence/upload")
async def upload_evidence(
    entity_type: str = Query(..., description="requirement or change"),
    entity_id: str = Query(..., description="Target entity ID"),
    file: UploadFile = File(...)
):
    """Upload evidence file and link it to a requirement or change."""
    if entity_type not in {"requirement", "change"}:
        raise HTTPException(status_code=400, detail="Invalid entity_type")

    evidence_id = str(uuid.uuid4())
    base_dir = settings.data_dir / "evidence" / entity_type / entity_id
    base_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    file_path = base_dir / f"{evidence_id}_{safe_name}"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Evidence file is empty")
    max_size = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="Evidence file is too large")
    with open(file_path, "wb") as f:
        f.write(content)

    entry = {
        "evidence_id": evidence_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "filename": safe_name,
        "path": str(file_path),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": len(content)
    }
    evidence_db.append(entry)
    save_json_list(EVIDENCE_DB_PATH, evidence_db)
    _append_audit_log(
        action="evidence_uploaded",
        entity_type=entity_type,
        entity_id=entity_id,
        details={"evidence_id": evidence_id, "filename": safe_name}
    )
    return entry


@app.get("/evidence")
async def list_evidence(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None
):
    """List evidence records."""
    filtered = []
    for entry in _sort_by_iso(evidence_db, "uploaded_at"):
        if entity_type and entry.get("entity_type") != entity_type:
            continue
        if entity_id and entry.get("entity_id") != entity_id:
            continue
        path = Path(entry.get("path") or "")
        enriched = {
            **entry,
            "file_exists": path.exists(),
            "file_size": path.stat().st_size if path.exists() else None
        }
        filtered.append(enriched)
    return {
        "evidence": _paginate(filtered, limit, offset),
        "total": len(filtered),
        "limit": limit,
        "offset": offset or 0
    }


@app.get("/evidence/{evidence_id}/download")
async def download_evidence(evidence_id: str):
    """Download an evidence file by ID."""
    entry = next((item for item in evidence_db if item.get("evidence_id") == evidence_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Evidence not found")
    path = Path(entry.get("path") or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")
    return FileResponse(path, filename=entry.get("filename") or path.name)


@app.delete("/evidence/{evidence_id}")
async def delete_evidence(evidence_id: str):
    """Delete an evidence record and file."""
    entry = next((item for item in evidence_db if item.get("evidence_id") == evidence_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Evidence not found")
    path = Path(entry.get("path") or "")
    if path.exists():
        path.unlink()
    evidence_db.remove(entry)
    save_json_list(EVIDENCE_DB_PATH, evidence_db)
    _append_audit_log(
        action="evidence_deleted",
        entity_type=entry.get("entity_type") or "evidence",
        entity_id=entry.get("entity_id") or evidence_id,
        details={"evidence_id": evidence_id}
    )
    return {"deleted": True, "evidence_id": evidence_id}


@app.get("/integrations/export")
async def export_integrations():
    """Export core data for integration."""
    return {
        "changes": list(change_db.values()),
        "requirements": _gather_requirements(),
        "documents": list(documents_db.values()),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@app.get("/audit-log")
async def get_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int | None = None,
    offset: int | None = None
):
    """Return audit log entries."""
    filtered = []
    for entry in _sort_by_iso(audit_log, "timestamp"):
        if entity_type and entry.get("entity_type") != entity_type:
            continue
        if entity_id and entry.get("entity_id") != entity_id:
            continue
        if action and entry.get("action") != action:
            continue
        filtered.append(entry)
    return {
        "entries": _paginate(filtered, limit, offset),
        "total": len(filtered),
        "limit": limit,
        "offset": offset or 0
    }


@app.get("/audit-log/export")
async def export_audit_log(format: str = "csv"):
    """Export audit log entries."""
    entries = _sort_by_iso(audit_log, "timestamp")
    if format.lower() == "json":
        return {"entries": entries, "total": len(entries)}
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV or JSON export is supported")

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["timestamp", "action", "entity_type", "entity_id", "details"]
    )
    writer.writeheader()
    for entry in entries:
        writer.writerow({
            "timestamp": entry.get("timestamp"),
            "action": entry.get("action"),
            "entity_type": entry.get("entity_type"),
            "entity_id": entry.get("entity_id"),
            "details": json.dumps(entry.get("details") or {}, ensure_ascii=True)
        })

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"}
    )


@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    requirements_count = sum(len(doc.get("requirements", [])) for doc in documents_db.values())
    severity_counts = {"low": 0, "medium": 0, "high": 0}
    status_counts: Dict[str, int] = {}
    for change in change_db.values():
        sev = (change.get("severity") or "medium").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1
        status = change.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_chunks": vector_store.get_document_count(),
        "total_documents": len(documents_db),
        "jurisdictions": _all_jurisdictions(),
        "llm_available": req_extractor.client is not None,
        "total_requirements": requirements_count,
        "total_changes": len(change_db),
        "total_audit_events": len(audit_log),
        "total_sources": len(sources_db),
        "total_evidence": len(evidence_db),
        "overdue_changes": len(_get_overdue_changes()),
        "change_severity_counts": severity_counts,
        "change_status_counts": status_counts,
        "started_at": STARTED_AT.isoformat(),
        "uptime_seconds": int((datetime.now(timezone.utc) - STARTED_AT).total_seconds())
    }


@app.get("/changes/stats")
async def change_stats():
    """Aggregate change counts."""
    changes = list(change_db.values())
    return {
        "total": len(changes),
        "by_jurisdiction": _count_by_field(changes, "jurisdiction"),
        "by_status": _count_by_field(changes, "status"),
        "by_severity": _count_by_field(changes, "severity"),
        "by_owner": _count_by_field(changes, "owner"),
        "overdue": len(_get_overdue_changes())
    }


@app.get("/changes/{change_id}")
async def get_change(change_id: str):
    """Get a single change item."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    return change


def _normalize_requirements(
    requirements: List[Dict[str, Any]],
    doc_id: str,
    jurisdiction: str,
    filename: str,
    entity: str | None = None,
    business_unit: str | None = None
) -> List[Dict[str, Any]]:
    normalized = []
    for req in requirements:
        normalized.append({
            "requirement_id": str(uuid.uuid4()),
            "jurisdiction": jurisdiction,
            "doc_id": doc_id,
            "filename": filename,
            "requirement_type": req.get("requirement_type") or "Unknown",
            "description": req.get("description"),
            "details": req.get("details"),
            "mandatory": req.get("mandatory") or "Unknown",
            "confidence": req.get("confidence", "Medium"),
            "source_snippet": req.get("source_snippet"),
            "entity": entity,
            "business_unit": business_unit,
            "status": "new",
            "reviewer": None,
            "review_notes": None,
            "tags": [],
            "controls": [],
            "policy_refs": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {}
        })
    return normalized


def _attach_evidence(requirements: List[Dict[str, Any]], doc_id: str) -> None:
    for req in requirements:
        query_text = " ".join(
            [
                req.get("requirement_type") or "",
                req.get("description") or "",
                req.get("details") or ""
            ]
        ).strip()
        if not query_text:
            continue
        results = vector_store.query(
            query_text=query_text,
            n_results=1,
            filters={"doc_id": doc_id}
        )
        if results:
            match = results[0]
            req["evidence"] = {
                "chunk_id": match.get("id"),
                "text": match.get("document"),
                "metadata": match.get("metadata")
            }


def _gather_requirements() -> List[Dict[str, Any]]:
    requirements = []
    updated = False
    for doc_id, doc in documents_db.items():
        reqs = doc.get("requirements", [])
        if isinstance(reqs, dict) and reqs.get("requirements"):
            raw_extraction = reqs.get("raw_extraction")
            reqs = _normalize_requirements(
                reqs.get("requirements", []),
                doc_id=doc.get("doc_id") or doc_id,
                jurisdiction=doc.get("jurisdiction") or "Unknown",
                filename=doc.get("filename") or "Unknown",
                entity=doc.get("entity"),
                business_unit=doc.get("business_unit")
            )
            _attach_evidence(reqs, doc.get("doc_id") or doc_id)
            doc["requirements"] = reqs
            doc["raw_extraction"] = doc.get("raw_extraction") or raw_extraction
            updated = True
        elif isinstance(reqs, list) and reqs and "requirement_id" not in reqs[0]:
            reqs = _normalize_requirements(
                reqs,
                doc_id=doc.get("doc_id") or doc_id,
                jurisdiction=doc.get("jurisdiction") or "Unknown",
                filename=doc.get("filename") or "Unknown",
                entity=doc.get("entity"),
                business_unit=doc.get("business_unit")
            )
            _attach_evidence(reqs, doc.get("doc_id") or doc_id)
            doc["requirements"] = reqs
            updated = True

        if isinstance(doc.get("requirements"), list):
            requirements.extend(doc.get("requirements", []))

    if updated:
        save_documents_db(DOCUMENTS_DB_PATH, documents_db)
    return requirements


def _filter_requirements(
    requirements: List[Dict[str, Any]],
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    requirement_type: str | None = None,
    mandatory: str | None = None,
    status: str | None = None,
    doc_id: str | None = None,
    q: str | None = None
) -> List[Dict[str, Any]]:
    filtered = []
    mandatory_norm = _normalize_mandatory(mandatory)
    status_norm = _normalize_status(status)
    for req in requirements:
        if jurisdiction and req.get("jurisdiction") != jurisdiction:
            continue
        if entity and req.get("entity") != entity:
            continue
        if business_unit and req.get("business_unit") != business_unit:
            continue
        if requirement_type and req.get("requirement_type") != requirement_type:
            continue
        if mandatory_norm and (req.get("mandatory") or "").lower() != mandatory_norm:
            continue
        if status_norm and (req.get("status") or "").lower() != status_norm:
            continue
        if doc_id and req.get("doc_id") != doc_id:
            continue
        if q:
            haystack = " ".join(
                [
                    req.get("requirement_type") or "",
                    req.get("description") or "",
                    req.get("details") or "",
                    req.get("source_snippet") or ""
                ]
            ).lower()
            if q.lower() not in haystack:
                continue
        filtered.append(req)
    return filtered


def _extract_requirements_from_doc(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    reqs = doc.get("requirements", [])
    if isinstance(reqs, list):
        return reqs
    if isinstance(reqs, dict):
        return reqs.get("requirements", [])
    return []


def _change_exists_for_source(source_id: str, entry_id: str) -> bool:
    for change in change_db.values():
        if change.get("source_id") == source_id and change.get("source_entry_id") == entry_id:
            return True
    return False


def _parse_feed_entries(url: str) -> List[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            content = response.read()
    except Exception as e:
        logger.warning(f"Failed to fetch feed {url}: {e}")
        return []

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        logger.warning(f"Failed to parse feed {url}: {e}")
        return []

    entries: List[Dict[str, Any]] = []

    # RSS 2.0
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = (item.findtext("description") or "").strip()
        entries.append(
            {
                "title": title,
                "link": link,
                "id": guid or link or title,
                "published": pub_date,
                "summary": description,
            }
        )

    # Atom
    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = link_el.attrib.get("href", "").strip() if link_el is not None else ""
        entry_id = (entry.findtext("{http://www.w3.org/2005/Atom}id") or "").strip()
        updated = (entry.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
        summary = (entry.findtext("{http://www.w3.org/2005/Atom}summary") or "").strip()
        entries.append(
            {
                "title": title,
                "link": link,
                "id": entry_id or link or title,
                "published": updated,
                "summary": summary,
            }
        )

    return entries


def _basic_impact_summary(change: Dict[str, Any], matched: List[Dict[str, Any]]) -> str:
    title = change.get("title") or "Regulatory update"
    jurisdiction = change.get("jurisdiction") or "Unknown jurisdiction"
    types = sorted({req.get("requirement_type") for req in matched if req.get("requirement_type")})[:3]
    if types:
        return f"{title} may impact {', '.join(types)} requirements in {jurisdiction}. Review affected controls and update policies as needed."
    return f"{title} requires assessment in {jurisdiction}. Review impacted controls, policies, and reporting obligations."


def _collect_matched_requirements(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched: List[Dict[str, Any]] = []
    seen = set()
    for item in results:
        metadata = item.get("metadata") or {}
        doc_id = metadata.get("doc_id")
        reqs = _extract_requirements_from_doc(documents_db.get(doc_id, {}))
        for req in reqs:
            req_id = req.get("requirement_id")
            if not req_id or req_id in seen:
                continue
            seen.add(req_id)
            matched.append(req)
    return matched


def _requirements_context(
    requirements: List[Dict[str, Any]],
    max_items: int
) -> List[Dict[str, Any]]:
    context = []
    limit = max_items if max_items > 0 else len(requirements)
    for req in requirements[:limit]:
        evidence = req.get("evidence") or {}
        metadata = evidence.get("metadata") or {}
        evidence_text = (evidence.get("text") or req.get("source_snippet") or "").strip()
        context.append(
            {
                "requirement_id": req.get("requirement_id"),
                "requirement_type": req.get("requirement_type"),
                "description": req.get("description"),
                "doc_id": req.get("doc_id") or metadata.get("doc_id"),
                "chunk_id": evidence.get("chunk_id"),
                "evidence_text": evidence_text,
            }
        )
    return context


def _impact_brief_prompt(
    change: Dict[str, Any],
    requirements: List[Dict[str, Any]],
    max_claims: int
) -> str:
    requirements_text = "\n".join(
        f"- {req.get('requirement_id')}: {req.get('description')} | evidence: {req.get('evidence_text')}"
        for req in requirements
    )
    return (
        "Generate an audit-grade impact brief for a regulatory change. "
        "Return JSON only in this exact shape:\n"
        "{\n"
        '  "summary": [\n'
        "    {\n"
        '      "claim": "string",\n'
        '      "citations": [\n'
        "        {\n"
        '          "requirement_id": "string",\n'
        '          "doc_id": "string",\n'
        '          "chunk_id": "string",\n'
        '          "evidence_text": "string"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Change title: {change.get('title')}\n"
        f"Summary: {change.get('summary')}\n"
        f"Jurisdiction: {change.get('jurisdiction')}\n"
        f"Max claims: {max_claims}\n\n"
        "Requirements with evidence:\n"
        f"{requirements_text}\n\n"
        "Rules:\n"
        "- Each claim must include at least one citation.\n"
        "- Use only the provided requirements and evidence.\n"
        "- Keep to the max claim count.\n"
    )


def _extract_json_payload(text: str) -> Dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _deterministic_claims(
    change: Dict[str, Any],
    requirements: List[Dict[str, Any]],
    max_claims: int
) -> List[Dict[str, Any]]:
    claims = []
    limit = max_claims if max_claims > 0 else len(requirements)
    if not requirements:
        return [
            {
                "claim": _basic_impact_summary(change, []),
                "citations": [],
                "evidence_gap": True,
            }
        ]
    for req in requirements[:limit]:
        evidence = req.get("evidence") or {}
        evidence_text = (evidence.get("text") or req.get("source_snippet") or "").strip()
        citation = {
            "requirement_id": req.get("requirement_id"),
            "doc_id": req.get("doc_id"),
            "chunk_id": evidence.get("chunk_id"),
            "evidence_text": evidence_text,
        }
        claims.append(
            {
                "claim": req.get("description") or _basic_impact_summary(change, [req]),
                "citations": [citation] if evidence_text else [],
            }
        )
    return claims


def _validate_claims(claims: List[Dict[str, Any]], max_citations: int) -> List[Dict[str, Any]]:
    validated = []
    remaining = max_citations if max_citations > 0 else None
    for claim in claims:
        citations = claim.get("citations") or []
        citations = [
            citation
            for citation in citations
            if (citation.get("evidence_text") or "").strip()
        ]
        if remaining is not None:
            if remaining <= 0:
                citations = []
            elif len(citations) > remaining:
                citations = citations[:remaining]
            remaining = max(remaining - len(citations), 0)
        entry = {
            "claim": claim.get("claim"),
            "citations": citations,
        }
        if not citations:
            base_claim = entry.get("claim") or "No evidence found"
            if "no evidence found" not in base_claim.lower():
                entry["claim"] = f"{base_claim} (no evidence found)"
            entry["evidence_gap"] = True
        validated.append(entry)
    return validated


def _claim_validation_summary(claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(claims)
    with_citations = sum(1 for claim in claims if claim.get("citations"))
    missing = [idx for idx, claim in enumerate(claims) if not claim.get("citations")]
    ratio = (with_citations / total) if total else 0.0
    return {
        "total_claims": total,
        "claims_with_citations": with_citations,
        "claims_missing_citations": missing,
        "evidence_coverage_ratio": ratio,
    }


def _get_overdue_changes() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).date()
    overdue = []
    for change in change_db.values():
        due_date = change.get("due_date")
        status = change.get("status")
        if not due_date or status == "implemented":
            continue
        try:
            due = datetime.fromisoformat(due_date).date()
        except ValueError:
            continue
        if due < now:
            overdue.append({
                "change_id": change.get("change_id"),
                "title": change.get("title"),
                "jurisdiction": change.get("jurisdiction"),
                "owner": change.get("owner"),
                "severity": change.get("severity"),
                "entity": change.get("entity"),
                "business_unit": change.get("business_unit"),
                "due_date": due_date,
                "days_overdue": (now - due).days,
                "risk_score": change.get("risk_score"),
                "escalation_required": _needs_escalation(change, due)
            })
    return overdue


def _ensure_policy_seeded() -> None:
    if policies_db:
        return
    policy_dir = settings.data_dir / "policies"
    if not policy_dir.exists():
        return
    for path in policy_dir.glob("*.md"):
        policy_id = path.stem
        content = path.read_text(encoding="utf-8")
        title = content.splitlines()[0].replace("#", "").strip() if content else policy_id
        policies_db[policy_id] = {
            "policy_id": policy_id,
            "title": title,
            "path": str(path),
            "summary": _summarize_policy(content),
            "status": "active",
            "version": "1.0",
            "owner": "Compliance",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None
        }
    save_json_dict(POLICIES_DB_PATH, policies_db)


def _summarize_policy(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return " ".join(lines[1:4])[:240] if len(lines) > 1 else ""


def _compute_risk_score(change: Dict[str, Any]) -> int:
    severity = (change.get("severity") or "medium").lower()
    base = {"low": 1, "medium": 2, "high": 3}.get(severity, 2)
    score = base
    due_date = change.get("due_date")
    if due_date:
        try:
            due = datetime.fromisoformat(due_date).date()
            now = datetime.now(timezone.utc).date()
            if due < now:
                score += 2
            else:
                days_to_due = (due - now).days
                if days_to_due <= 7:
                    score += 1
        except ValueError:
            pass
    return score


def _needs_escalation(change: Dict[str, Any], due: datetime.date) -> bool:
    if (change.get("severity") or "").lower() == "high":
        return True
    now = datetime.now(timezone.utc).date()
    return due < now


def _dispatch_webhooks(event: str, payload: Dict[str, Any]) -> None:
    for webhook in webhooks_db.values():
        if event not in webhook.get("events", []):
            continue
        url = webhook.get("url")
        if not url:
            continue
        body = json.dumps({"event": event, "payload": payload}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=5):
                pass
        except Exception as e:
            logger.warning(f"Webhook dispatch failed to {url}: {e}")


def _append_audit_log(
    action: str,
    entity_type: str,
    entity_id: str,
    details: Dict[str, Any] | None = None
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details or {}
    }
    audit_log.append(entry)
    save_json_list(AUDIT_LOG_PATH, audit_log)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
