"""Change tracking service for regulatory horizon scanning."""

import hashlib
import logging
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ChangeService:
    def __init__(self, changes_db: Dict[str, Dict[str, Any]], audit_repo: Any):
        self.changes_db = changes_db
        self.audit_repo = audit_repo

    def create_change(
        self,
        title: str,
        jurisdiction: str,
        severity: str = "medium",
        status: str = "new",
        owner: str | None = None,
        due_date: str | None = None,
        summary: str | None = None,
        source: str | None = None,
        effective_date: str | None = None,
        entity: str | None = None,
        business_unit: str | None = None,
        impacted_areas: List[str] | None = None,
        related_requirement_ids: List[str] | None = None,
        risk_score: float | None = None,
        source_url: str | None = None,
    ) -> Dict[str, Any]:
        from backend.state import save_json_dict, CHANGES_DB_PATH

        change_id = str(uuid.uuid4())
        change = {
            "change_id": change_id,
            "title": title,
            "jurisdiction": jurisdiction,
            "entity": entity,
            "business_unit": business_unit,
            "severity": (severity or "medium").lower(),
            "status": (status or "new").lower(),
            "owner": owner,
            "due_date": due_date,
            "summary": summary,
            "source": source,
            "source_url": source_url,
            "effective_date": effective_date,
            "impacted_areas": impacted_areas or [],
            "related_requirement_ids": related_requirement_ids or [],
            "risk_score": risk_score,
            "overdue": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        self._compute_overdue(change)
        self.changes_db[change_id] = change
        save_json_dict(CHANGES_DB_PATH, self.changes_db)
        self.audit_repo.append(
            action="change_created",
            entity_type="change",
            entity_id=change_id,
            details={"title": title},
        )
        return change

    def list_changes(
        self,
        jurisdiction: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        overdue: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Dict[str, Any]:
        from backend.state import _sort_by_iso, _paginate

        changes = list(self.changes_db.values())
        # Recompute overdue flags
        for c in changes:
            self._compute_overdue(c)

        changes = _sort_by_iso(changes, "created_at")

        if jurisdiction:
            changes = [c for c in changes if c.get("jurisdiction") == jurisdiction]
        if severity:
            changes = [c for c in changes if c.get("severity") == severity.lower()]
        if status:
            changes = [c for c in changes if c.get("status") == status.lower()]
        if owner:
            changes = [c for c in changes if c.get("owner") == owner]
        if overdue and overdue.lower() == "true":
            changes = [c for c in changes if c.get("overdue")]
        if q:
            q_lower = q.lower()
            changes = [
                c
                for c in changes
                if q_lower
                in f"{c.get('title', '')} {c.get('summary', '')} {c.get('source', '')}".lower()
            ]

        total = len(changes)
        paged = _paginate(changes, limit, offset)
        return {
            "changes": paged,
            "total": total,
            "limit": limit,
            "offset": offset or 0,
        }

    def get_change(self, change_id: str) -> Dict[str, Any]:
        change = self.changes_db.get(change_id)
        if not change:
            raise HTTPException(status_code=404, detail="Change not found")
        self._compute_overdue(change)
        return change

    def update_change(self, change_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        from backend.state import save_json_dict, CHANGES_DB_PATH

        change = self.changes_db.get(change_id)
        if not change:
            raise HTTPException(status_code=404, detail="Change not found")

        for key in [
            "status",
            "severity",
            "owner",
            "due_date",
            "impact_assessment",
            "impacted_areas",
            "related_requirement_ids",
            "policy_refs",
        ]:
            if key in updates and updates[key] is not None:
                change[key] = updates[key]

        change["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._compute_overdue(change)
        self.changes_db[change_id] = change
        save_json_dict(CHANGES_DB_PATH, self.changes_db)
        self.audit_repo.append(
            action="change_updated",
            entity_type="change",
            entity_id=change_id,
            details={"fields": list(updates.keys())},
        )
        return change

    def delete_change(self, change_id: str) -> Dict[str, Any]:
        from backend.state import save_json_dict, CHANGES_DB_PATH

        if change_id not in self.changes_db:
            raise HTTPException(status_code=404, detail="Change not found")
        self.changes_db.pop(change_id, None)
        save_json_dict(CHANGES_DB_PATH, self.changes_db)
        self.audit_repo.append(
            action="change_deleted", entity_type="change", entity_id=change_id
        )
        return {"deleted": True, "change_id": change_id}

    def get_overdue_alerts(self) -> Dict[str, Any]:
        """Return changes that are overdue (past due_date and not closed)."""
        today = date.today()
        overdue = []
        for change in self.changes_db.values():
            if change.get("status") in ("closed", "resolved"):
                continue
            due = change.get("due_date")
            if not due:
                continue
            try:
                due_date = date.fromisoformat(due)
            except (ValueError, TypeError):
                continue
            if due_date < today:
                days_overdue = (today - due_date).days
                overdue.append(
                    {
                        **change,
                        "days_overdue": days_overdue,
                        "escalation_required": days_overdue > 7,
                    }
                )
        overdue.sort(key=lambda x: x.get("days_overdue", 0), reverse=True)
        return {"overdue": overdue, "total": len(overdue)}

    def content_hash(self, title: str, url: str) -> str:
        """Generate dedup hash from title + URL."""
        return hashlib.sha256(f"{title}|{url}".encode()).hexdigest()[:16]

    def _compute_overdue(self, change: Dict[str, Any]) -> None:
        """Set the overdue flag based on due_date."""
        due = change.get("due_date")
        if not due or change.get("status") in ("closed", "resolved"):
            change["overdue"] = False
            return
        try:
            due_date = date.fromisoformat(due)
            change["overdue"] = due_date < date.today()
        except (ValueError, TypeError):
            change["overdue"] = False
