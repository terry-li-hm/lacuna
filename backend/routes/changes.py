"""Change tracking and horizon scanning routes for RegAtlas API."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.state import get_change_service

logger = logging.getLogger(__name__)
router = APIRouter()


class ChangeCreateRequest(BaseModel):
    title: str
    jurisdiction: str
    entity: str | None = None
    business_unit: str | None = None
    severity: str = "medium"
    status: str = "new"
    owner: str | None = None
    due_date: str | None = None
    summary: str | None = None
    source: str | None = None
    effective_date: str | None = None
    impacted_areas: List[str] | None = None
    related_requirement_ids: List[str] | None = None


class ChangeUpdateRequest(BaseModel):
    status: str | None = None
    severity: str | None = None
    owner: str | None = None
    due_date: str | None = None
    impact_assessment: str | None = None
    impacted_areas: List[str] | None = None
    related_requirement_ids: List[str] | None = None
    policy_refs: List[str] | None = None


@router.post("/changes")
async def create_change(
    request: ChangeCreateRequest, service=Depends(get_change_service)
):
    """Create a new regulatory change item."""
    return service.create_change(**request.model_dump())


@router.get("/changes")
async def list_changes(
    jurisdiction: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    overdue: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    service=Depends(get_change_service),
):
    """List regulatory change items with optional filters."""
    return service.list_changes(
        jurisdiction=jurisdiction,
        severity=severity,
        status=status,
        owner=owner,
        overdue=overdue,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/changes/{change_id}")
async def get_change(change_id: str, service=Depends(get_change_service)):
    """Get a single change item."""
    return service.get_change(change_id)


@router.post("/changes/{change_id}")
async def update_change(
    change_id: str,
    request: ChangeUpdateRequest,
    service=Depends(get_change_service),
):
    """Update a change item."""
    return service.update_change(change_id, request.model_dump(exclude_none=True))


@router.delete("/changes/{change_id}")
async def delete_change(change_id: str, service=Depends(get_change_service)):
    """Delete a change item."""
    return service.delete_change(change_id)


@router.get("/alerts")
async def get_alerts(service=Depends(get_change_service)):
    """Get overdue change items requiring attention."""
    return service.get_overdue_alerts()


@router.post("/changes/{change_id}/ai-suggest")
async def ai_suggest(change_id: str, service=Depends(get_change_service)):
    """Get AI suggestions for a change item (stub — returns placeholder)."""
    change = service.get_change(change_id)
    return {
        "change_id": change_id,
        "suggestions": {
            "impact_assessment": f"This {change.get('severity', 'medium')}-severity change in {change.get('jurisdiction', 'Unknown')} may affect existing compliance controls.",
            "recommended_actions": [
                "Review existing policies for overlap",
                "Assess implementation timeline against effective date",
                "Identify affected business units",
            ],
        },
    }


@router.post("/changes/{change_id}/approvals")
async def add_approval(change_id: str, service=Depends(get_change_service)):
    """Record an approval for a change item (stub)."""
    change = service.get_change(change_id)
    return {"change_id": change_id, "approval_status": "recorded"}
