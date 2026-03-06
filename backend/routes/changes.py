"""Change tracking and horizon scanning routes for Meridian API."""

import csv
import io
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.state import get_change_service, get_gap_analysis_service

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
    circular_doc_id: str | None = None  # if set, auto-run gap analysis vs demo-baseline


class ChangeUpdateRequest(BaseModel):
    status: str | None = None
    severity: str | None = None
    owner: str | None = None
    due_date: str | None = None
    impact_assessment: str | None = None
    impacted_areas: List[str] | None = None
    related_requirement_ids: List[str] | None = None
    policy_refs: List[str] | None = None


async def _auto_gap_analysis(circular_doc_id: str) -> None:
    """Background task: run gap analysis vs demo-baseline for a new circular."""
    import os
    try:
        gap_svc = get_gap_analysis_service()
        baseline_id = os.getenv("LACUNA_DEMO_BASELINE_ID")
        if not baseline_id:
            logger.warning("Auto gap analysis skipped: LACUNA_DEMO_BASELINE_ID not set")
            return
        logger.info(f"Auto gap analysis: {circular_doc_id} vs {baseline_id}")
        await gap_svc.perform_gap_analysis(
            circular_doc_id=circular_doc_id,
            baseline_id=baseline_id,
            is_policy_baseline=False,
        )
        logger.info(f"Auto gap analysis complete for {circular_doc_id}")
    except Exception as e:
        logger.warning(f"Auto gap analysis failed for {circular_doc_id}: {e}")


@router.post("/changes")
async def create_change(
    request: ChangeCreateRequest,
    background_tasks: BackgroundTasks,
    service=Depends(get_change_service),
):
    """Create a new regulatory change item."""
    circular_doc_id = request.circular_doc_id
    data = request.model_dump()
    data.pop("circular_doc_id", None)
    result = service.create_change(**data)
    if circular_doc_id:
        background_tasks.add_task(_auto_gap_analysis, circular_doc_id)
    return result


@router.get("/changes")
async def list_changes(
    jurisdiction: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    overdue: str | None = None,
    include_overdue: str | None = None,
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
        overdue=overdue or include_overdue,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/changes/export")
async def export_changes(format: str = "csv", service=Depends(get_change_service)):
    """Export change items."""
    result = service.list_changes()
    changes = result.get("changes", [])

    if format.lower() == "json":
        return {"changes": changes, "total": len(changes)}
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV or JSON export is supported")

    buffer = io.StringIO()
    fieldnames = ["change_id", "title", "jurisdiction", "severity", "status", "owner", "due_date", "summary", "source", "created_at"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for change in changes:
        writer.writerow(change)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=changes.csv"},
    )


@router.get("/changes/stats")
async def changes_stats(service=Depends(get_change_service)):
    """Get change item statistics."""
    result = service.list_changes()
    changes = result.get("changes", [])

    by_status: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    by_jurisdiction: Dict[str, int] = {}
    overdue_count = 0

    for c in changes:
        s = c.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        sev = c.get("severity", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        j = c.get("jurisdiction", "Unknown")
        by_jurisdiction[j] = by_jurisdiction.get(j, 0) + 1
        if c.get("overdue"):
            overdue_count += 1

    return {
        "total": len(changes),
        "overdue": overdue_count,
        "by_status": by_status,
        "by_severity": by_severity,
        "by_jurisdiction": by_jurisdiction,
    }


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
async def get_alerts(
    jurisdiction: str | None = None,
    service=Depends(get_change_service),
):
    """Get overdue change items requiring attention."""
    result = service.get_overdue_alerts()
    if jurisdiction:
        result["overdue"] = [
            item for item in result["overdue"] if item.get("jurisdiction") == jurisdiction
        ]
        result["total"] = len(result["overdue"])
    return result


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


@router.post("/changes/{change_id}/impact-brief")
async def impact_brief(change_id: str, service=Depends(get_change_service)):
    """Generate an impact brief for a change item (stub)."""
    change = service.get_change(change_id)
    return {
        "change_id": change_id,
        "brief": {
            "summary": [
                f"Change: {change.get('title', 'Unknown')}",
                f"Jurisdiction: {change.get('jurisdiction', 'Unknown')}",
                f"Severity: {change.get('severity', 'medium')}",
            ],
            "impacted_areas": change.get("impacted_areas", []),
            "recommended_timeline": "30 days from effective date",
        },
    }


@router.post("/changes/{change_id}/approvals")
async def add_approval(change_id: str, service=Depends(get_change_service)):
    """Record an approval for a change item (stub)."""
    service.get_change(change_id)  # Validate exists
    return {"change_id": change_id, "approval_status": "recorded"}


@router.get("/changes/{change_id}/approvals")
async def list_approvals(change_id: str, service=Depends(get_change_service)):
    """List approvals for a change item (stub)."""
    service.get_change(change_id)  # Validate exists
    return {"change_id": change_id, "approvals": []}
