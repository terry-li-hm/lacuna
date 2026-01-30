import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.storage.repositories import DocumentRepository, AuditLogRepository
from backend.state import (
    _gather_requirements,
    _filter_requirements,
    _validate_choice,
    ALLOWED_REQ_STATUS,
)

logger = logging.getLogger(__name__)


class RequirementService:
    def __init__(self, doc_repo: DocumentRepository, audit_repo: AuditLogRepository):
        self.doc_repo = doc_repo
        self.audit_repo = audit_repo

    def list_requirements(
        self,
        jurisdiction: Optional[str] = None,
        entity: Optional[str] = None,
        business_unit: Optional[str] = None,
        requirement_type: Optional[str] = None,
        mandatory: Optional[str] = None,
        status: Optional[str] = None,
        doc_id: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List requirements with optional filters."""
        # For now, we still use _gather_requirements which uses documents_db
        # But we should eventually transition to using the repository
        # Since _gather_requirements is already there and handles the document mapping, let's use it for now
        # and we will refactor it to use doc_repo in a future phase if needed.
        # Actually, let's try to use doc_repo here to be "proper".

        all_docs = self.doc_repo.list_all()
        requirements = []
        for doc in all_docs:
            reqs = doc.get("requirements", [])
            if isinstance(reqs, list):
                requirements.extend(reqs)

        # Sort by created_at descending (from _sort_by_iso logic)
        def _get_date(item):
            val = item.get("created_at")
            try:
                return datetime.fromisoformat(val)
            except:
                return datetime.min.replace(tzinfo=timezone.utc)

        requirements.sort(key=_get_date, reverse=True)

        return _filter_requirements(
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

    def get_requirement(self, requirement_id: str) -> Optional[Dict[str, Any]]:
        """Get a single requirement by ID."""
        all_docs = self.doc_repo.list_all()
        for doc in all_docs:
            for req in doc.get("requirements", []):
                if req.get("requirement_id") == requirement_id:
                    return req
        return None

    def review_requirement(
        self,
        requirement_id: str,
        status: Optional[str] = None,
        reviewer: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        controls: Optional[List[str]] = None,
        policy_refs: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update requirement review metadata."""
        all_docs = self.doc_repo.list_all()
        target_doc = None
        updated_req = None

        for doc in all_docs:
            for req in doc.get("requirements", []):
                if req.get("requirement_id") == requirement_id:
                    if status is not None:
                        req["status"] = _validate_choice(
                            status, ALLOWED_REQ_STATUS, "status"
                        )
                    if reviewer is not None:
                        req["reviewer"] = reviewer
                    if notes is not None:
                        req["review_notes"] = notes
                    if tags is not None:
                        req["tags"] = tags
                    if controls is not None:
                        req["controls"] = controls
                    if policy_refs is not None:
                        req["policy_refs"] = policy_refs
                    req["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                    updated_req = req
                    target_doc = doc
                    break
            if updated_req:
                break

        if updated_req is None or target_doc is None:
            return None

        # Save the updated document back to the repo
        self.doc_repo.save(target_doc)

        # Log to audit repo
        self.audit_repo.append(
            action="requirement_reviewed",
            entity_type="requirement",
            entity_id=requirement_id,
            details={"status": status, "reviewer": reviewer},
        )

        return updated_req

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate requirement counts."""
        all_docs = self.doc_repo.list_all()
        requirements = []
        for doc in all_docs:
            reqs = doc.get("requirements", [])
            if isinstance(reqs, list):
                requirements.extend(reqs)

        from backend.state import _count_by_field

        return {
            "total": len(requirements),
            "by_jurisdiction": _count_by_field(requirements, "jurisdiction"),
            "by_type": _count_by_field(requirements, "requirement_type"),
            "by_status": _count_by_field(requirements, "status"),
            "by_mandatory": _count_by_field(requirements, "mandatory"),
        }

    def get_requirement_types(self) -> List[str]:
        """Get unique requirement types."""
        all_docs = self.doc_repo.list_all()
        types = set()
        for doc in all_docs:
            for req in doc.get("requirements", []):
                if req.get("requirement_type"):
                    types.add(req.get("requirement_type"))
        return sorted(list(types))
