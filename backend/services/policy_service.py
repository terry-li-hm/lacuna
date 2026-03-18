import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.storage.repositories import PolicyRepository
from backend.state import _ensure_policy_seeded, _sort_by_iso

logger = logging.getLogger(__name__)


class PolicyService:
    def __init__(self, policy_repo: PolicyRepository):
        self.policy_repo = policy_repo

    def list_policies(self) -> List[Dict[str, Any]]:
        """List all policies."""
        _ensure_policy_seeded()
        return self.policy_repo.list_all()

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get a policy by ID."""
        _ensure_policy_seeded()
        return self.policy_repo.get(policy_id)

    def create_from_upload(
        self,
        content: str,
        title: str,
        filename: str,
        owner: str | None = None,
    ) -> dict:
        """Create a new policy from uploaded file content."""
        policy_id = f"policy_{uuid.uuid4().hex[:8]}"
        policy = {
            "policy_id": policy_id,
            "title": title,
            "path": filename,
            "summary": content[:500],
            "content": content,
            "status": "active",
            "version": "1.0",
            "owner": owner or "Unknown",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        self.policy_repo.save(policy)
        return policy

    def update_policy(
        self,
        policy_id: str,
        status: Optional[str] = None,
        version: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update policy metadata."""
        _ensure_policy_seeded()
        policy = self.policy_repo.get(policy_id)
        if not policy:
            return None

        if status is not None:
            policy["status"] = status
        if version is not None:
            policy["version"] = version
        if owner is not None:
            policy["owner"] = owner

        policy["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.policy_repo.save(policy)

        return policy
