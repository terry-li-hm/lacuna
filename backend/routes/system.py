"""System routes for Meridian API."""

import csv
import io
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from backend.state import (
    STARTED_AT,
    get_system_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def root(service=Depends(get_system_service)):
    """Application status endpoint."""
    return {
        "status": "healthy",
        "app": "Meridian",
        "version": "0.1.0",
        "documents_count": service.vector_store.get_document_count(),
        "jurisdictions": service.get_stats()["jurisdictions"],
    }


@router.get("/healthz")
async def healthz():
    """Lightweight health check."""
    return {"status": "ok", "started_at": STARTED_AT.isoformat()}


@router.get("/readyz")
async def readyz(service=Depends(get_system_service)):
    """Readiness check to confirm data stores are available."""
    try:
        service.vector_store.get_document_count()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Vector store unavailable") from exc
    return {"status": "ready"}


@router.get("/stats")
async def get_stats(service=Depends(get_system_service)):
    """Get system statistics."""
    from backend.state import get_change_service
    stats = service.get_stats()
    try:
        changes = get_change_service().list_changes()
        stats["total_changes"] = len(changes)
    except Exception:
        stats["total_changes"] = 0
    return stats


@router.get("/entities")
async def list_entities(service=Depends(get_system_service)):
    """List entities and business units found in data."""
    return service.get_entities()


@router.get("/audit-log")
async def get_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    service=Depends(get_system_service),
):
    """Return audit log entries."""
    from backend.state import _paginate

    entries = service.get_audit_log(
        entity_type=entity_type, entity_id=entity_id, action=action
    )

    total = len(entries)
    paged = _paginate(entries, limit, offset)

    return {
        "entries": paged,
        "total": total,
        "limit": limit,
        "offset": offset or 0,
    }


@router.get("/audit-log/export")
async def export_audit_log(format: str = "csv", service=Depends(get_system_service)):
    """Export audit log entries."""
    entries = service.get_audit_log()

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
