"""Cross-jurisdiction synthesis routes for Meridian API."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.models.schemas import SynthesisRequest, SynthesisResponse
from backend.state import get_document_repo, get_policy_repo, get_synthesis_service

logger = logging.getLogger(__name__)
router = APIRouter()

_DISPLAY_MAP = {
    "hkma-cp": "HKMA GenAI Consumer Protection 2024",
    "hkma-gai": "HKMA GenAI Financial Services 2024",
    "hkma-sandbox": "HKMA GenAI Sandbox Arrangement 2024",
    "hkma-spm": "HKMA SPM CA-G-1 Revised 2024",
    "eu-ai-act": "EU AI Act (Regulation 2024/1689)",
    "fca": "FCA AI Update 2024",
    "mas-consult": "MAS AI Risk Management Consultation 2025",
    "mas-mrmf": "MAS AI Model Risk Management 2024",
    "nist-rmf": "NIST AI Risk Management Framework 1.0",
    "nist-iso42001": "NIST AI RMF to ISO 42001 Crosswalk",
    "sg-genai": "Singapore GenAI Governance Framework 2024",
    "demo-baseline": "Codex Argentum v1.1",
}


def _normalize(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _document_tokens(doc: dict) -> set[str]:
    metadata = doc.get("metadata") or {}
    filename = doc.get("filename") or ""
    stem = Path(filename).stem if filename else ""
    tokens = {
        _normalize(doc.get("doc_id")),
        _normalize(filename),
        _normalize(stem),
        _normalize(metadata.get("title")),
        _normalize(metadata.get("name")),
        _normalize(metadata.get("alias")),
    }
    aliases = metadata.get("aliases")
    if isinstance(aliases, list):
        tokens.update(_normalize(alias) for alias in aliases)
    return {token for token in tokens if token}


def _resolve_document_identifier(identifier: str) -> str:
    doc_repo = get_document_repo()
    doc = doc_repo.get(identifier)
    if doc:
        return identifier

    normalized = _normalize(identifier)
    expected_title = _normalize(_DISPLAY_MAP.get(identifier))
    for candidate in doc_repo.list_all():
        tokens = _document_tokens(candidate)
        if normalized in tokens or (expected_title and expected_title in tokens):
            return candidate["doc_id"]

    raise ValueError(f"Document {identifier} not found")


def _resolve_policy_identifier(identifier: str) -> str:
    policy_repo = get_policy_repo()
    policy = policy_repo.get(identifier)
    if policy:
        return identifier

    normalized = _normalize(identifier)
    for candidate in policy_repo.list_all():
        tokens = {
            _normalize(candidate.get("policy_id")),
            _normalize(candidate.get("title")),
            _normalize(candidate.get("path")),
        }
        if normalized in {token for token in tokens if token}:
            return candidate["policy_id"]

    raise ValueError(f"Policy baseline {identifier} not found")


@router.post("/synthesis", response_model=SynthesisResponse)
async def synthesize(
    request: SynthesisRequest,
    service=Depends(get_synthesis_service),
):
    """Run gap analysis across multiple circulars and synthesize the results."""
    try:
        circular_ids = [
            _resolve_document_identifier(circular_id)
            for circular_id in request.circular_ids
        ]
        baseline_id = (
            _resolve_policy_identifier(request.baseline_id)
            if request.is_policy_baseline
            else _resolve_document_identifier(request.baseline_id)
        )

        logger.info(
            "Cross-jurisdiction synthesis: circulars=%s baseline=%s",
            circular_ids,
            baseline_id,
        )
        return await service.synthesize(
            circular_ids=circular_ids,
            baseline_id=baseline_id,
            is_policy_baseline=request.is_policy_baseline,
            include_amendments=request.include_amendments,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404 if "not found" in str(exc).lower() else 400,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Error performing cross-jurisdiction synthesis: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
