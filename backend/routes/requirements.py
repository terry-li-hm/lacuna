"""Requirements routes for RegAtlas API."""

import csv
import io
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.state import (
    DOCUMENTS_DB_PATH,
    _append_audit_log,
    _count_by_field,
    _filter_requirements,
    _gather_requirements,
    _paginate,
    _sort_by_iso,
    _validate_choice,
    ALLOWED_REQ_STATUS,
    documents_db,
    save_documents_db,
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
        q=q,
    )
    return {
        "requirements": _paginate(filtered, limit, offset),
        "total": len(filtered),
        "limit": limit,
        "offset": offset or 0,
        "types": sorted(
            {
                r.get("requirement_type", "")
                for r in requirements
                if r.get("requirement_type")
            }
        ),
    }


@router.get("/requirements/stats")
async def requirement_stats():
    """Aggregate requirement counts."""
    requirements = _gather_requirements()
    return {
        "total": len(requirements),
        "by_jurisdiction": _count_by_field(requirements, "jurisdiction"),
        "by_type": _count_by_field(requirements, "requirement_type"),
        "by_status": _count_by_field(requirements, "status"),
        "by_mandatory": _count_by_field(requirements, "mandatory"),
    }


@router.get("/requirements/id/{requirement_id}")
async def get_requirement(requirement_id: str):
    """Get a single requirement by ID."""
    for req in _gather_requirements():
        if req.get("requirement_id") == requirement_id:
            return req
    raise HTTPException(status_code=404, detail="Requirement not found")


@router.get("/requirements/id/{requirement_id}/evidence")
async def get_requirement_evidence(requirement_id: str):
    """Get evidence metadata for a requirement."""
    for req in _gather_requirements():
        if req.get("requirement_id") == requirement_id:
            return {
                "requirement_id": requirement_id,
                "evidence": req.get("evidence") or {},
            }
    raise HTTPException(status_code=404, detail="Requirement not found")


@router.post("/requirements/id/{requirement_id}/review")
async def review_requirement(requirement_id: str, request: RequirementReviewRequest):
    """Update requirement review metadata."""
    from datetime import datetime, timezone

    updated = None
    for doc in documents_db.values():
        for req in doc.get("requirements", []):
            if req.get("requirement_id") == requirement_id:
                if request.status is not None:
                    req["status"] = _validate_choice(
                        request.status, ALLOWED_REQ_STATUS, "status"
                    )
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
        details={"status": request.status, "reviewer": request.reviewer},
    )
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
