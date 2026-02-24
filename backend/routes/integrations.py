"""Integration routes for RegAtlas API."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends

from backend.state import get_integration_service, get_scan_service, documents_db, _gather_requirements
from backend.models.schemas import SourceCreateRequest, WebhookCreateRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sources")
async def add_source(
    request: SourceCreateRequest, service=Depends(get_integration_service)
):
    """Register a regulatory source feed."""
    return service.add_source(
        name=request.name,
        url=request.url,
        jurisdiction=request.jurisdiction,
        entity=request.entity,
        business_unit=request.business_unit,
        default_severity=request.default_severity,
    )


@router.get("/sources")
async def list_sources(
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    service=Depends(get_integration_service),
):
    """List all regulatory sources."""
    return service.list_sources(q=q, limit=limit, offset=offset)


@router.get("/sources/{source_id}")
async def get_source(source_id: str, service=Depends(get_integration_service)):
    """Get a regulatory source."""
    return service.get_source(source_id)


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, service=Depends(get_integration_service)):
    """Delete a regulatory source."""
    return service.delete_source(source_id)


@router.post("/webhooks")
async def add_webhook(
    request: WebhookCreateRequest, service=Depends(get_integration_service)
):
    """Register an outbound webhook."""
    return service.add_webhook(url=request.url, events=request.events)


@router.get("/webhooks")
async def list_webhooks(
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    service=Depends(get_integration_service),
):
    """List webhooks."""
    return service.list_webhooks(q=q, limit=limit, offset=offset)


@router.get("/webhooks/{webhook_id}")
async def get_webhook(webhook_id: str, service=Depends(get_integration_service)):
    """Get a webhook by ID."""
    return service.get_webhook(webhook_id)


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, service=Depends(get_integration_service)):
    """Delete a webhook."""
    return service.delete_webhook(webhook_id)


@router.post("/scan")
async def scan_sources(service=Depends(get_scan_service)):
    """Scan all registered RSS/Atom sources for new regulatory changes."""
    return service.scan_all_sources()


@router.get("/integrations/export")
async def export_integrations():
    """Export core data for integration."""
    return {
        "requirements": _gather_requirements(),
        "documents": list(documents_db.values()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
