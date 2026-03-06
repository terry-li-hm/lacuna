"""Service for requirement decomposition workflows."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.models.schemas import AtomicRequirement, DecomposeResponse
from backend.storage.repositories import DocumentRepository
from backend.requirement_extractor import RequirementExtractor


def _extract_requirements_from_doc(doc: dict) -> list[dict]:
    """Extract the requirements list from a stored document dict.

    Mirrors backend.state._extract_requirements_from_doc but lives here to
    avoid a circular import: state.py imports DecomposeService via the
    get_decompose_service factory, so DecomposeService must not import state.
    """
    reqs = doc.get("requirements", [])
    if isinstance(reqs, list):
        return reqs
    if isinstance(reqs, dict):
        return reqs.get("requirements", [])
    return []


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

        atomic = []
        for i, req in enumerate(requirements):
            if not isinstance(req, dict):
                continue
            raw_chunk_index = req.get("chunk_index")
            try:
                chunk_index: int | None = int(raw_chunk_index) if raw_chunk_index is not None else None
            except (ValueError, TypeError):
                chunk_index = None
            atomic.append(
                AtomicRequirement(
                    index=i + 1,
                    requirement_id=req.get("requirement_id") or str(uuid4()),
                    requirement_type=req.get("requirement_type"),
                    description=req.get("description") or "",
                    source_snippet=req.get("source_snippet"),
                    chunk_index=chunk_index,
                    mandatory=req.get("mandatory"),
                    confidence=req.get("confidence"),
                )
            )

        return DecomposeResponse(
            doc_id=doc_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total=len(atomic),
            fresh=fresh,
            requirements=atomic,
        )
