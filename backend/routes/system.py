"""System routes for RegAtlas API."""

import csv
import io
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.state import (
    STARTED_AT,
    _all_jurisdictions,
    _append_audit_log,
    _count_by_field,
    _gather_requirements,
    _paginate,
    _sort_by_iso,
    audit_log,
    documents_db,
    evidence_db,
    req_extractor,
    sources_db,
    vector_store,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "RegAtlas",
        "version": "0.1.0",
        "documents_count": vector_store.get_document_count(),
        "jurisdictions": _all_jurisdictions(),
    }


@router.get("/healthz")
async def healthz():
    """Lightweight health check."""
    return {"status": "ok", "started_at": STARTED_AT.isoformat()}


@router.get("/readyz")
async def readyz():
    """Readiness check to confirm data stores are available."""
    try:
        vector_store.get_document_count()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Vector store unavailable") from exc
    return {"status": "ready"}


@router.get("/stats")
async def get_stats():
    """Get system statistics."""
    requirements_count = sum(
        len(doc.get("requirements", [])) for doc in documents_db.values()
    )
    return {
        "total_chunks": vector_store.get_document_count(),
        "total_documents": len(documents_db),
        "jurisdictions": _all_jurisdictions(),
        "llm_available": req_extractor.client is not None,
        "total_requirements": requirements_count,
        "total_audit_events": len(audit_log),
        "total_sources": len(sources_db),
        "total_evidence": len(evidence_db),
        "started_at": STARTED_AT.isoformat(),
        "uptime_seconds": int(
            (datetime.now(timezone.utc) - STARTED_AT).total_seconds()
        ),
    }


@router.get("/entities")
async def list_entities():
    """List entities and business units found in data."""
    entities = set()
    business_units = set()
    for doc in documents_db.values():
        if doc.get("entity"):
            entities.add(doc["entity"])
        if doc.get("business_unit"):
            business_units.add(doc["business_unit"])
    return {"entities": sorted(entities), "business_units": sorted(business_units)}


@router.get("/audit-log")
async def get_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
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
        "offset": offset or 0,
    }


@router.get("/audit-log/export")
async def export_audit_log(format: str = "csv"):
    """Export audit log entries."""
    entries = _sort_by_iso(audit_log, "timestamp")
    if format.lower() == "json":
        return {"entries": entries, "total": len(entries)}
    if format.lower() != "csv":
        raise HTTPException(
            status_code=400, detail="Only CSV or JSON export is supported"
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["timestamp", "action", "entity_type", "entity_id", "details"],
    )
    writer.writeheader()
    for entry in entries:
        writer.writerow(
            {
                "timestamp": entry.get("timestamp"),
                "action": entry.get("action"),
                "entity_type": entry.get("entity_type"),
                "entity_id": entry.get("entity_id"),
                "details": json.dumps(entry.get("details") or {}, ensure_ascii=True),
            }
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
