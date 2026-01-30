"""Requirements routes for RegAtlas API."""

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from backend.state import (
    get_requirement_service,
)
from backend.models.schemas import RequirementReviewRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/requirements")
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
    offset: int | None = None,
    service=Depends(get_requirement_service),
):
    """List requirements with optional filters."""
    from backend.state import _paginate

    requirements = service.list_requirements(
        jurisdiction=jurisdiction,
        entity=entity,
        business_unit=business_unit,
        requirement_type=requirement_type,
        mandatory=mandatory,
        status=status,
        doc_id=doc_id,
        q=q,
    )

    total = len(requirements)
    paged = _paginate(requirements, limit, offset)

    return {
        "requirements": paged,
        "total": total,
        "limit": limit,
        "offset": offset or 0,
        "types": service.get_requirement_types(),
    }


@router.get("/requirements/stats")
async def requirement_stats(service=Depends(get_requirement_service)):
    """Aggregate requirement counts."""
    return service.get_stats()


@router.get("/requirements/id/{requirement_id}")
async def get_requirement(
    requirement_id: str, service=Depends(get_requirement_service)
):
    """Get a single requirement by ID."""
    req = service.get_requirement(requirement_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return req


@router.get("/requirements/id/{requirement_id}/evidence")
async def get_requirement_evidence(
    requirement_id: str, service=Depends(get_requirement_service)
):
    """Get evidence metadata for a requirement."""
    req = service.get_requirement(requirement_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    return {
        "requirement_id": requirement_id,
        "evidence": req.get("evidence") or {},
    }


@router.post("/requirements/id/{requirement_id}/review")
async def review_requirement(
    requirement_id: str,
    request: RequirementReviewRequest,
    service=Depends(get_requirement_service),
):
    """Update requirement review metadata."""
    updated = service.review_requirement(
        requirement_id=requirement_id,
        status=request.status,
        reviewer=request.reviewer,
        notes=request.notes,
        tags=request.tags,
        controls=request.controls,
        policy_refs=request.policy_refs,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Requirement not found")

    return updated


@router.get("/requirements/export")
async def export_requirements(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    requirement_type: str | None = None,
    mandatory: str | None = None,
    status: str | None = None,
    doc_id: str | None = None,
    q: str | None = None,
    format: str = "csv",
    service=Depends(get_requirement_service),
):
    """Export requirements in CSV format."""
    requirements = service.list_requirements(
        jurisdiction=jurisdiction,
        entity=entity,
        business_unit=business_unit,
        requirement_type=requirement_type,
        mandatory=mandatory,
        status=status,
        doc_id=doc_id,
        q=q,
    )

    if format.lower() == "json":
        return {"requirements": requirements, "total": len(requirements)}
    if format.lower() != "csv":
        raise HTTPException(
            status_code=400, detail="Only CSV or JSON export is supported"
        )

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
            "evidence_text",
        ],
    )
    writer.writeheader()
    for req in requirements:
        writer.writerow(
            {
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
                "evidence_text": req.get("evidence", {}).get("text"),
            }
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=requirements.csv"},
    )
