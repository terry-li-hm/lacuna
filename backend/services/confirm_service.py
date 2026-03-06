"""Confirmed requirement list service."""

from datetime import datetime, timezone
from typing import Any

from backend.models.schemas import (
    AtomicRequirement,
    ConfirmedListResponse,
    ConfirmResponse,
)


class ConfirmService:
    def __init__(self, doc_repo: Any, confirm_repo: Any):
        # No state imports; dependencies are injected by the factory.
        self.doc_repo = doc_repo
        self.confirm_repo = confirm_repo

    def save(
        self,
        doc_id: str,
        requirements: list[AtomicRequirement],
        confirmed_by: str | None = None,
    ) -> ConfirmResponse:
        if not self.doc_repo.get(doc_id):
            raise ValueError(f"Document {doc_id} not found")

        payload = [req.model_dump() for req in requirements]
        self.confirm_repo.save(doc_id, payload, confirmed_by)
        saved = self.confirm_repo.get(doc_id)

        confirmed_at = datetime.now(timezone.utc).isoformat()
        if saved and saved.get("confirmed_at") is not None:
            confirmed_at = str(saved["confirmed_at"])

        return ConfirmResponse(
            doc_id=doc_id,
            confirmed_at=confirmed_at,
            total=len(requirements),
        )

    def get(self, doc_id: str) -> ConfirmedListResponse:
        row = self.confirm_repo.get(doc_id)
        if not row:
            raise ValueError(f"Confirmed requirement list for {doc_id} not found")

        requirements = [AtomicRequirement(**item) for item in row.get("requirements", [])]
        confirmed_at = str(row.get("confirmed_at"))

        return ConfirmedListResponse(
            doc_id=row.get("doc_id", doc_id),
            confirmed_at=confirmed_at,
            confirmed_by=row.get("confirmed_by"),
            total=len(requirements),
            requirements=requirements,
        )
