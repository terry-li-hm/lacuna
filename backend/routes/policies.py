"""Policy routes for RegAtlas API."""

import csv
import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.state import (
    POLICIES_DB_PATH,
    _append_audit_log,
    _ensure_policy_seeded,
    _sort_by_iso,
    policies_db,
    save_json_dict,
    get_policy_repo,
)
from backend.models.schemas import PolicyUpdateRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/policies")
async def list_policies():
    """List internal policies and procedures."""
    _ensure_policy_seeded()
    return {"policies": list(policies_db.values()), "total": len(policies_db)}


@router.get("/policies/export")
async def export_policies(format: str = "csv"):
    """Export policies."""
    _ensure_policy_seeded()
    policies = _sort_by_iso(list(policies_db.values()), "created_at")
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
async def get_policy(policy_id: str):
    """Get a policy by ID."""
    _ensure_policy_seeded()
    policy = policies_db.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/policies/{policy_id}/update")
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

    # Also save to DuckDB
    try:
        repo = get_policy_repo()
        repo.save(policy)
    except Exception as e:
        logger.warning(f"Failed to save policy to DuckDB: {e}")

    _append_audit_log(
        action="policy_updated",
        entity_type="policy",
        entity_id=policy_id,
        details={"status": request.status, "version": request.version},
    )
    return policy
