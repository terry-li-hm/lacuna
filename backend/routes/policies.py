"""Policy routes for RegAtlas API."""

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from backend.state import (
    get_policy_service,
)
from backend.models.schemas import PolicyUpdateRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/policies")
async def list_policies(service=Depends(get_policy_service)):
    """List internal policies and procedures."""
    policies = service.list_policies()
    return {"policies": policies, "total": len(policies)}


@router.get("/policies/export")
async def export_policies(format: str = "csv", service=Depends(get_policy_service)):
    """Export policies."""
    policies = service.list_policies()

    if format.lower() == "json":
        return {"policies": policies, "total": len(policies)}
    if format.lower() != "csv":
        raise HTTPException(
            status_code=400, detail="Only CSV or JSON export is supported"
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "policy_id",
            "title",
            "summary",
            "status",
            "version",
            "owner",
            "created_at",
            "updated_at",
        ],
    )
    writer.writeheader()
    for policy in policies:
        writer.writerow(
            {
                "policy_id": policy.get("policy_id"),
                "title": policy.get("title"),
                "summary": policy.get("summary"),
                "status": policy.get("status"),
                "version": policy.get("version"),
                "owner": policy.get("owner"),
                "created_at": policy.get("created_at"),
                "updated_at": policy.get("updated_at"),
            }
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=policies.csv"},
    )


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str, service=Depends(get_policy_service)):
    """Get a policy by ID."""
    policy = service.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/policies/{policy_id}/update")
async def update_policy(
    policy_id: str, request: PolicyUpdateRequest, service=Depends(get_policy_service)
):
    """Update policy status/version/owner."""
    updated = service.update_policy(
        policy_id=policy_id,
        status=request.status,
        version=request.version,
        owner=request.owner,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Policy not found")

    from backend.state import _append_audit_log

    _append_audit_log(
        action="policy_updated",
        entity_type="policy",
        entity_id=policy_id,
        details={"status": request.status, "version": request.version},
    )

    return updated
