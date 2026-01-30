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
import uuid

from backend.config import settings
from backend.models.schemas import (
    QueryRequest,
    QueryResponse,
    CompareRequest,
    RequirementReviewRequest,
    SourceCreateRequest,
    PolicyUpdateRequest,
    WebhookCreateRequest,
    GapAnalysisRequest,
    GapAnalysisResponse,
    Provenance,
    GapRequirementMapping,
)
from backend.routes import (
    documents_router,
    requirements_router,
    gap_analysis_router,
    policies_router,
    system_router,
)
from backend import state

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="RegAtlas",
    description="Cross-jurisdiction regulatory analytics platform for financial institutions",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize state and components
state.init_state()
state.init_components()

# Include routers
app.include_router(system_router, tags=["system"])
app.include_router(documents_router, tags=["documents"])
app.include_router(requirements_router, tags=["requirements"])
app.include_router(gap_analysis_router, tags=["gap-analysis"])
app.include_router(policies_router, tags=["policies"])


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
                detail=f"n_results must be between 1 and {settings.max_query_results}",
            )

        # Search vector store
        filters = {}
        if request.doc_id:
            filters["doc_id"] = request.doc_id

        results = state.vector_store.query(
            query_text=request.query,
            n_results=request.n_results,
            jurisdiction=request.jurisdiction,
            filters=filters or None,
        )

        # Optionally generate summary with LLM
        summary = None
        if state.req_extractor.client and results and not request.no_llm:
            context = "\n\n".join([r["document"] for r in results[:3]])

            try:
                from openai import OpenAI

                client = OpenAI(
                    api_key=state.llm_api_key, base_url=settings.openai_base_url
                )

                response = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a regulatory compliance expert. Provide concise, accurate answers based on the provided regulatory text.",
                        },
                        {
                            "role": "user",
                            "content": f"Based on the following regulatory text, answer this question: {request.query}\n\nContext:\n{context}",
                        },
                    ],
                    temperature=0.1,
                    max_tokens=500,
                )

                summary = response.choices[0].message.content or "No summary generated"

            except Exception as e:
                logger.warning(f"Could not generate summary: {e}")

        return QueryResponse(query=request.query, results=results, summary=summary)

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
        docs1 = [
            doc
            for doc in state.documents_db.values()
            if doc["jurisdiction"] == request.jurisdiction1
        ]
        docs2 = [
            doc
            for doc in state.documents_db.values()
            if doc["jurisdiction"] == request.jurisdiction2
        ]

        if not docs1:
            raise HTTPException(
                status_code=404,
                detail=f"No documents found for jurisdiction: {request.jurisdiction1}",
            )

        if not docs2:
            raise HTTPException(
                status_code=404,
                detail=f"No documents found for jurisdiction: {request.jurisdiction2}",
            )

        # Aggregate requirements
        req1 = {"jurisdiction": request.jurisdiction1, "requirements": []}
        req2 = {"jurisdiction": request.jurisdiction2, "requirements": []}

        for doc in docs1:
            req1["requirements"].extend(state._extract_requirements_from_doc(doc))

        for doc in docs2:
            req2["requirements"].extend(state._extract_requirements_from_doc(doc))

        # Generate comparison
        comparison = state.req_extractor.compare_requirements(
            req1, req2, force_basic=bool(request.no_llm)
        )

        return {
            "jurisdiction1": request.jurisdiction1,
            "jurisdiction2": request.jurisdiction2,
            "comparison": comparison,
            "documents_compared": {
                request.jurisdiction1: len(docs1),
                request.jurisdiction2: len(docs2),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing jurisdictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sources")
async def add_source(request: SourceCreateRequest):
    """Register a regulatory source feed."""
    state._validate_url(request.url)
    source_id = str(uuid.uuid4())
    state.sources_db[source_id] = {
        "source_id": source_id,
        "name": request.name,
        "url": request.url,
        "jurisdiction": request.jurisdiction,
        "entity": state._normalize_text(request.entity),
        "business_unit": state._normalize_text(request.business_unit),
        "default_severity": request.default_severity or "medium",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    state.save_json_dict(state.SOURCES_DB_PATH, state.sources_db)
    state._append_audit_log(
        action="source_added",
        entity_type="source",
        entity_id=source_id,
        details={"name": request.name},
    )
    return state.sources_db[source_id]


@app.get("/sources")
async def list_sources(
    q: str | None = None, limit: int | None = None, offset: int | None = None
):
    """List all regulatory sources."""
    sources = state._sort_by_iso(list(state.sources_db.values()), "created_at")
    if q:
        filtered = []
        for source in sources:
            haystack = " ".join(
                [
                    source.get("name") or "",
                    source.get("url") or "",
                    source.get("jurisdiction") or "",
                    source.get("entity") or "",
                    source.get("business_unit") or "",
                ]
            ).lower()
            if q.lower() in haystack:
                filtered.append(source)
        sources = filtered
    return {
        "sources": state._paginate(sources, limit, offset),
        "total": len(sources),
        "limit": limit,
        "offset": offset or 0,
    }


@app.get("/sources/{source_id}")
async def get_source(source_id: str):
    """Get a regulatory source."""
    source = state.sources_db.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@app.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Delete a regulatory source."""
    if source_id not in state.sources_db:
        raise HTTPException(status_code=404, detail="Source not found")
    state.sources_db.pop(source_id, None)
    state.save_json_dict(state.SOURCES_DB_PATH, state.sources_db)
    state._append_audit_log(
        action="source_deleted", entity_type="source", entity_id=source_id
    )
    return {"deleted": True, "source_id": source_id}


@app.post("/webhooks")
async def add_webhook(request: WebhookCreateRequest):
    """Register an outbound webhook."""
    if not (request.url.startswith("http://") or request.url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid webhook URL scheme")
    webhook_id = str(uuid.uuid4())
    state.webhooks_db[webhook_id] = {
        "webhook_id": webhook_id,
        "url": request.url,
        "events": request.events or ["document.uploaded", "gap_analysis.completed"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    state.save_json_dict(state.WEBHOOKS_DB_PATH, state.webhooks_db)
    return state.webhooks_db[webhook_id]


@app.get("/webhooks")
async def list_webhooks(
    q: str | None = None, limit: int | None = None, offset: int | None = None
):
    """List webhooks."""
    webhooks = state._sort_by_iso(list(state.webhooks_db.values()), "created_at")
    if q:
        filtered = []
        for hook in webhooks:
            haystack = " ".join(
                [hook.get("url") or "", ",".join(hook.get("events") or [])]
            ).lower()
            if q.lower() in haystack:
                filtered.append(hook)
        webhooks = filtered
    return {
        "webhooks": state._paginate(webhooks, limit, offset),
        "total": len(webhooks),
        "limit": limit,
        "offset": offset or 0,
    }


@app.get("/webhooks/{webhook_id}")
async def get_webhook(webhook_id: str):
    """Get a webhook by ID."""
    webhook = state.webhooks_db.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@app.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    if webhook_id not in state.webhooks_db:
        raise HTTPException(status_code=404, detail="Webhook not found")
    state.webhooks_db.pop(webhook_id, None)
    state.save_json_dict(state.WEBHOOKS_DB_PATH, state.webhooks_db)
    return {"deleted": True, "webhook_id": webhook_id}


@app.post("/evidence/upload")
async def upload_evidence(
    entity_type: str = Query(..., description="requirement"),
    entity_id: str = Query(..., description="Target entity ID"),
    file: UploadFile = File(...),
):
    """Upload evidence file and link it to a requirement."""
    if entity_type != "requirement":
        raise HTTPException(
            status_code=400, detail="Only requirement entity_type is supported"
        )

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
        "size_bytes": len(content),
    }
    state.evidence_db.append(entry)
    state.save_json_list(state.EVIDENCE_DB_PATH, state.evidence_db)
    state._append_audit_log(
        action="evidence_uploaded",
        entity_type=entity_type,
        entity_id=entity_id,
        details={"evidence_id": evidence_id, "filename": safe_name},
    )
    return entry


@app.get("/evidence")
async def list_evidence(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
):
    """List evidence records."""
    filtered = []
    for entry in state._sort_by_iso(state.evidence_db, "uploaded_at"):
        if entity_type and entry.get("entity_type") != entity_type:
            continue
        if entity_id and entry.get("entity_id") != entity_id:
            continue
        path = Path(entry.get("path") or "")
        enriched = {
            **entry,
            "file_exists": path.exists(),
            "file_size": path.stat().st_size if path.exists() else None,
        }
        filtered.append(enriched)
    return {
        "evidence": state._paginate(filtered, limit, offset),
        "total": len(filtered),
        "limit": limit,
        "offset": offset or 0,
    }


@app.get("/evidence/{evidence_id}/download")
async def download_evidence(evidence_id: str):
    """Download an evidence file by ID."""
    entry = next(
        (item for item in state.evidence_db if item.get("evidence_id") == evidence_id),
        None,
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Evidence not found")
    path = Path(entry.get("path") or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")
    return FileResponse(path, filename=entry.get("filename") or path.name)


@app.delete("/evidence/{evidence_id}")
async def delete_evidence(evidence_id: str):
    """Delete an evidence record and file."""
    entry = next(
        (item for item in state.evidence_db if item.get("evidence_id") == evidence_id),
        None,
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Evidence not found")
    path = Path(entry.get("path") or "")
    if path.exists():
        path.unlink()
    state.evidence_db.remove(entry)
    state.save_json_list(state.EVIDENCE_DB_PATH, state.evidence_db)
    state._append_audit_log(
        action="evidence_deleted",
        entity_type=entry.get("entity_type") or "evidence",
        entity_id=entry.get("entity_id") or evidence_id,
        details={"evidence_id": evidence_id},
    )
    return {"deleted": True, "evidence_id": evidence_id}


@app.get("/integrations/export")
async def export_integrations():
    """Export core data for integration."""
    return {
        "requirements": state._gather_requirements(),
        "documents": list(state.documents_db.values()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
