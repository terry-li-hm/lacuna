"""Pydantic models for Meridian API."""

from typing import Any, Dict, List

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """Request model for querying regulatory documents."""

    query: str
    jurisdiction: str | None = None
    doc_id: str | None = None
    no_llm: bool | None = None
    n_results: int = 5


class QueryResponse(BaseModel):
    """Response model for document queries."""

    query: str
    results: List[Dict[str, Any]]
    summary: str | None = None


class CompareRequest(BaseModel):
    """Request model for comparing jurisdictions."""

    jurisdiction1: str
    jurisdiction2: str
    no_llm: bool | None = None


class RequirementReviewRequest(BaseModel):
    """Request model for reviewing requirements."""

    status: str | None = None
    reviewer: str | None = None
    notes: str | None = None
    tags: List[str] | None = None
    controls: List[str] | None = None
    policy_refs: List[str] | None = None


class SourceCreateRequest(BaseModel):
    """Request model for creating regulatory sources."""

    name: str
    url: str
    jurisdiction: str | None = None
    entity: str | None = None
    business_unit: str | None = None
    default_severity: str | None = None


class PolicyUpdateRequest(BaseModel):
    """Request model for updating policies."""

    status: str | None = None
    version: str | None = None
    owner: str | None = None


class WebhookCreateRequest(BaseModel):
    """Request model for creating webhooks."""

    url: str
    events: List[str] | None = None


class Provenance(BaseModel):
    """Provenance information for gap analysis."""

    id: str
    source_type: str
    doc_id: str
    chunk_id: str
    requirement_id: str | None = None
    text_segment: str
    location: Dict[str, Any] | None = None
    verification_status: str = "verified"


class GapRequirementMapping(BaseModel):
    """Mapping between circular requirement and baseline."""

    circular_req_id: str
    description: str
    status: str  # "Full", "Partial", "Gap"
    reasoning: str
    baseline_match_id: str | None = None
    baseline_match_text: str | None = None
    provenance: List[Provenance] = []


class GapAnalysisRequest(BaseModel):
    """Request model for gap analysis."""

    circular_doc_id: str
    baseline_id: str
    is_policy_baseline: bool = False
    no_llm: bool = False


class GapAnalysisResponse(BaseModel):
    """Response model for gap analysis."""

    report_id: str
    circular_id: str
    baseline_id: str
    generated_at: str
    summary: Dict[str, int]
    findings: List[GapRequirementMapping]


class BatchGapAnalysisRequest(BaseModel):
    """Request model for batch gap analysis."""

    circular_doc_ids: List[str]
    baseline_id: str
    is_policy_baseline: bool = False
    no_llm: bool = False


class BatchGapAnalysisResult(BaseModel):
    """Result model for a single circular in a batch gap analysis."""

    circular_doc_id: str
    result: GapAnalysisResponse | None = None
    error: str | None = None


class BatchGapAnalysisResponse(BaseModel):
    """Response model for batch gap analysis."""

    baseline_id: str
    results: List[BatchGapAnalysisResult]


__all__ = [
    "QueryRequest",
    "QueryResponse",
    "CompareRequest",
    "RequirementReviewRequest",
    "SourceCreateRequest",
    "PolicyUpdateRequest",
    "WebhookCreateRequest",
    "Provenance",
    "GapRequirementMapping",
    "GapAnalysisRequest",
    "GapAnalysisResponse",
    "BatchGapAnalysisRequest",
    "BatchGapAnalysisResult",
    "BatchGapAnalysisResponse",
]
