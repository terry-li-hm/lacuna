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
    draft_amendment: str | None = None
    provenance: List[Provenance] = []


class GapAnalysisRequest(BaseModel):
    """Request model for gap analysis."""

    circular_doc_id: str
    baseline_id: str
    is_policy_baseline: bool = False
    include_amendments: bool = False
    use_confirmed: bool = False
    include_completeness_audit: bool = False
    no_llm: bool = False


class CompletenessFlag(BaseModel):
    """Potential requirement omission identified by adversarial pass."""

    description: str
    reasoning: str | None = None
    source_hint: str | None = None


class CompletenessAudit(BaseModel):
    """Completeness audit payload attached to gap analysis response."""

    flagged: List[CompletenessFlag]
    not_flagged_rationale: str | None = None
    model: str


class GapAnalysisResponse(BaseModel):
    """Response model for gap analysis."""

    report_id: str
    circular_id: str
    baseline_id: str
    generated_at: str
    summary: Dict[str, int]
    findings: List[GapRequirementMapping]
    completeness_audit: CompletenessAudit | None = None


class JurisdictionResult(BaseModel):
    """Gap analysis result for a single jurisdiction or circular."""

    circular_id: str
    jurisdiction: str
    summary: Dict[str, int]
    findings: List[GapRequirementMapping]


class SynthesisRequest(BaseModel):
    """Request model for cross-jurisdiction synthesis."""

    circular_ids: List[str]
    baseline_id: str
    is_policy_baseline: bool = False
    include_amendments: bool = False


class SynthesisResponse(BaseModel):
    """Response model for cross-jurisdiction synthesis."""

    synthesis_id: str
    baseline_id: str
    generated_at: str
    jurisdictions: List[JurisdictionResult]
    cross_jurisdiction_summary: str


class AtomicRequirement(BaseModel):
    """Atomic requirement item for decomposition review."""

    index: int
    requirement_id: str
    requirement_type: str | None = None
    description: str
    source_snippet: str | None = None
    chunk_index: int | None = None
    mandatory: str | None = None
    confidence: str | None = None


class DecomposeRequest(BaseModel):
    """Request model for requirement decomposition."""

    doc_id: str
    fresh: bool = False


class DecomposeResponse(BaseModel):
    """Response model for requirement decomposition."""

    doc_id: str
    generated_at: str
    total: int
    fresh: bool
    requirements: List[AtomicRequirement]


class ConfirmRequest(BaseModel):
    """Request model for confirmed requirement list save."""

    requirements: List[AtomicRequirement]
    confirmed_by: str | None = None


class ConfirmResponse(BaseModel):
    """Response model for confirmed requirement list save."""

    doc_id: str
    confirmed_at: str
    total: int


class ConfirmedListResponse(BaseModel):
    """Response model for confirmed requirement list retrieval."""

    doc_id: str
    confirmed_at: str
    confirmed_by: str | None
    total: int
    requirements: List[AtomicRequirement]


class BatchGapAnalysisRequest(BaseModel):
    """Request model for batch gap analysis."""

    circular_doc_ids: List[str]
    baseline_id: str
    is_policy_baseline: bool = False
    include_amendments: bool = False
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
    "CompletenessFlag",
    "CompletenessAudit",
    "GapAnalysisRequest",
    "GapAnalysisResponse",
    "JurisdictionResult",
    "SynthesisRequest",
    "SynthesisResponse",
    "AtomicRequirement",
    "DecomposeRequest",
    "DecomposeResponse",
    "ConfirmRequest",
    "ConfirmResponse",
    "ConfirmedListResponse",
    "BatchGapAnalysisRequest",
    "BatchGapAnalysisResult",
    "BatchGapAnalysisResponse",
]
