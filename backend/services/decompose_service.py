"""Service for requirement decomposition workflows."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.models.schemas import AtomicRequirement, DecomposeResponse
from backend.state import _extract_requirements_from_doc
from backend.storage.repositories import DocumentRepository
from backend.requirement_extractor import RequirementExtractor


class DecomposeService:
    """Build review-friendly atomic requirement lists from stored or fresh extraction."""

    def __init__(self, doc_repo: DocumentRepository, req_extractor: RequirementExtractor):
        self.doc_repo = doc_repo
        self.req_extractor = req_extractor

    async def decompose(self, doc_id: str, fresh: bool = False) -> DecomposeResponse:
        doc = self.doc_repo.get(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        if fresh:
            # Fresh path is intentionally read-only: do not overwrite stored requirements.
            text = (
                doc.get("raw_text")
                or doc.get("content")
                or doc.get("raw_extraction")
                or "\n".join(
                    req.get("source_snippet", "")
                    for req in _extract_requirements_from_doc(doc)
                    if isinstance(req, dict)
                )
            )
            extracted = await asyncio.to_thread(
                self.req_extractor.extract_requirements,
                text,
                doc.get("jurisdiction", "Unknown"),
            )
            requirements = extracted.get("requirements", [])
        else:
            requirements = _extract_requirements_from_doc(doc)

        atomic = [
            AtomicRequirement(
                index=i + 1,
                requirement_id=req.get("requirement_id") or str(uuid4()),
                requirement_type=req.get("requirement_type"),
                description=req.get("description") or "",
                source_snippet=req.get("source_snippet"),
                chunk_index=req.get("chunk_index"),
                mandatory=req.get("mandatory"),
                confidence=req.get("confidence"),
            )
            for i, req in enumerate(requirements)
            if isinstance(req, dict)
        ]

        return DecomposeResponse(
            doc_id=doc_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total=len(atomic),
            fresh=fresh,
            requirements=atomic,
        )
