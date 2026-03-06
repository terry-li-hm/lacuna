"""Tests for the decompose feature — route, service, and schema coverage."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi.testclient import TestClient

# Mock state initialization before importing app
with patch("backend.state.init_state"), patch("backend.state.init_components"):
    from backend.main import app
    from backend.state import get_decompose_service

from backend.models.schemas import (
    AtomicRequirement,
    CompletenessAudit,
    CompletenessFlag,
    DecomposeRequest,
    DecomposeResponse,
    GapAnalysisResponse,
)
from backend.services.decompose_service import DecomposeService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_decompose_service():
    service = MagicMock(spec=DecomposeService)
    service.decompose = AsyncMock()
    return service


@pytest.fixture(autouse=True)
def override_decompose_service(mock_decompose_service):
    app.dependency_overrides[get_decompose_service] = lambda: mock_decompose_service
    yield
    app.dependency_overrides.pop(get_decompose_service, None)


def _make_atomic(index=1, req_id="req-abc", description="Store data securely"):
    return AtomicRequirement(
        index=index,
        requirement_id=req_id,
        requirement_type="DataProtection",
        description=description,
        source_snippet="Data must be stored securely.",
        chunk_index=0,
        mandatory="yes",
        confidence="High",
    )


def _make_decompose_response(doc_id="doc-1", fresh=False, requirements=None):
    if requirements is None:
        requirements = [_make_atomic()]
    return DecomposeResponse(
        doc_id=doc_id,
        generated_at="2026-03-06T00:00:00+00:00",
        total=len(requirements),
        fresh=fresh,
        requirements=requirements,
    )


# ---------------------------------------------------------------------------
# Route tests — POST /decompose
# ---------------------------------------------------------------------------

def test_decompose_valid_doc_id(client, mock_decompose_service):
    """POST /decompose with a valid doc_id returns 200 and correct payload."""
    mock_decompose_service.decompose.return_value = _make_decompose_response(
        doc_id="doc-1"
    )

    response = client.post("/decompose", json={"doc_id": "doc-1"})

    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == "doc-1"
    assert data["total"] == 1
    assert len(data["requirements"]) == 1
    assert data["requirements"][0]["description"] == "Store data securely"
    assert data["fresh"] is False


def test_decompose_unknown_doc_id_returns_404(client, mock_decompose_service):
    """POST /decompose with an unknown doc_id → 404."""
    mock_decompose_service.decompose.side_effect = ValueError(
        "Document unknown-doc not found"
    )

    response = client.post("/decompose", json={"doc_id": "unknown-doc"})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_decompose_fresh_true_calls_service_with_fresh(client, mock_decompose_service):
    """POST /decompose with fresh=true passes fresh=True to the service."""
    mock_decompose_service.decompose.return_value = _make_decompose_response(
        doc_id="doc-1", fresh=True
    )

    response = client.post("/decompose", json={"doc_id": "doc-1", "fresh": True})

    assert response.status_code == 200
    assert response.json()["fresh"] is True
    mock_decompose_service.decompose.assert_called_once_with("doc-1", fresh=True)


def test_decompose_fresh_false_is_default(client, mock_decompose_service):
    """POST /decompose without fresh param defaults to fresh=False."""
    mock_decompose_service.decompose.return_value = _make_decompose_response(
        doc_id="doc-2"
    )

    response = client.post("/decompose", json={"doc_id": "doc-2"})

    assert response.status_code == 200
    mock_decompose_service.decompose.assert_called_once_with("doc-2", fresh=False)


def test_decompose_non_not_found_value_error_returns_400(client, mock_decompose_service):
    """ValueError without 'not found' in the message → 400, not 404."""
    mock_decompose_service.decompose.side_effect = ValueError("Invalid input")

    response = client.post("/decompose", json={"doc_id": "doc-x"})

    assert response.status_code == 400


def test_decompose_internal_error_returns_500(client, mock_decompose_service):
    """Unexpected exception → 500."""
    mock_decompose_service.decompose.side_effect = RuntimeError("Something exploded")

    response = client.post("/decompose", json={"doc_id": "doc-y"})

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Service unit tests — DecomposeService.decompose()
# ---------------------------------------------------------------------------

def _make_doc(requirements=None, raw_text="Full document text."):
    doc = {
        "doc_id": "svc-doc-1",
        "jurisdiction": "HK",
        "raw_text": raw_text,
        "requirements": requirements if requirements is not None else [],
    }
    return doc


@pytest.fixture
def mock_doc_repo():
    return MagicMock()


@pytest.fixture
def mock_req_extractor():
    extractor = MagicMock()
    extractor.client = MagicMock()  # Simulates LLM client present
    extractor.extract_requirements = MagicMock()
    return extractor


@pytest.fixture
def decompose_service(mock_doc_repo, mock_req_extractor):
    return DecomposeService(doc_repo=mock_doc_repo, req_extractor=mock_req_extractor)


def test_service_fast_path_reads_stored_requirements(
    decompose_service, mock_doc_repo
):
    """DecomposeService.decompose() fast path reads requirements from the stored doc."""
    stored_reqs = [
        {
            "requirement_id": "req-stored-1",
            "requirement_type": "DataGovernance",
            "description": "Maintain audit logs",
            "source_snippet": "Logs must be retained.",
            "chunk_index": 0,
            "mandatory": "yes",
            "confidence": "High",
        }
    ]
    mock_doc_repo.get.return_value = _make_doc(requirements=stored_reqs)

    result = asyncio.run(decompose_service.decompose("svc-doc-1", fresh=False))

    assert isinstance(result, DecomposeResponse)
    assert result.total == 1
    assert result.requirements[0].requirement_id == "req-stored-1"
    assert result.requirements[0].description == "Maintain audit logs"
    assert result.fresh is False
    # Must not have called the extractor on the fast path
    decompose_service.req_extractor.extract_requirements.assert_not_called()


def test_service_fast_path_empty_requirements_returns_total_zero(
    decompose_service, mock_doc_repo
):
    """Empty requirements list → total=0, not an error."""
    mock_doc_repo.get.return_value = _make_doc(requirements=[])

    result = asyncio.run(decompose_service.decompose("svc-doc-1", fresh=False))

    assert result.total == 0
    assert result.requirements == []
    assert result.doc_id == "svc-doc-1"


def test_service_raises_value_error_for_missing_doc(
    decompose_service, mock_doc_repo
):
    """Missing document raises ValueError with 'not found' in the message."""
    mock_doc_repo.get.return_value = None

    with pytest.raises(ValueError, match="not found"):
        asyncio.run(decompose_service.decompose("nonexistent"))


def test_service_fresh_path_calls_asyncio_to_thread(
    decompose_service, mock_doc_repo, mock_req_extractor
):
    """fresh=True path calls asyncio.to_thread (wrapping the sync extractor)."""
    stored_reqs = [
        {
            "requirement_id": "req-old",
            "description": "Old requirement",
            "source_snippet": "snippet",
            "chunk_index": 0,
            "mandatory": "yes",
            "confidence": "Medium",
        }
    ]
    mock_doc_repo.get.return_value = _make_doc(requirements=stored_reqs)

    fresh_reqs = [
        {
            "requirement_id": "req-fresh",
            "requirement_type": "Privacy",
            "description": "Fresh extracted requirement",
            "source_snippet": "Full document text.",
            "chunk_index": 0,
            "mandatory": "yes",
            "confidence": "High",
        }
    ]
    mock_req_extractor.extract_requirements.return_value = {"requirements": fresh_reqs}

    with patch("backend.services.decompose_service.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
        mock_to_thread.return_value = {"requirements": fresh_reqs}
        result = asyncio.run(decompose_service.decompose("svc-doc-1", fresh=True))

    mock_to_thread.assert_called_once()
    # First positional arg should be the extract_requirements method
    assert mock_to_thread.call_args[0][0] == mock_req_extractor.extract_requirements
    assert result.fresh is True
    assert result.total == 1
    assert result.requirements[0].description == "Fresh extracted requirement"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_gap_analysis_response_has_completeness_audit_field_when_set():
    """GapAnalysisResponse.completeness_audit is populated when include_completeness_audit=True."""
    audit = CompletenessAudit(
        flagged=[
            CompletenessFlag(
                description="Missed data retention requirement",
                reasoning="No finding covered retention periods.",
                source_hint="§4.2 retention",
            )
        ],
        not_flagged_rationale="All other items covered.",
        model="anthropic/claude-sonnet-4",
    )
    response = GapAnalysisResponse(
        report_id="gap_test01",
        circular_id="doc-circular",
        baseline_id="doc-baseline",
        generated_at="2026-03-06T00:00:00+00:00",
        summary={"Full": 0, "Partial": 1, "Gap": 0},
        findings=[],
        completeness_audit=audit,
    )

    assert response.completeness_audit is not None
    assert len(response.completeness_audit.flagged) == 1
    assert response.completeness_audit.flagged[0].description == "Missed data retention requirement"
    assert response.completeness_audit.model == "anthropic/claude-sonnet-4"


def test_gap_analysis_response_completeness_audit_none_by_default():
    """GapAnalysisResponse.completeness_audit defaults to None."""
    response = GapAnalysisResponse(
        report_id="gap_noaudit",
        circular_id="doc-a",
        baseline_id="doc-b",
        generated_at="2026-03-06T00:00:00+00:00",
        summary={"Full": 1},
        findings=[],
    )

    assert response.completeness_audit is None


# ---------------------------------------------------------------------------
# adversarial_completeness_check — no LLM client
# ---------------------------------------------------------------------------

def test_adversarial_completeness_check_no_client_returns_empty_flagged():
    """adversarial_completeness_check with no LLM client returns empty flagged list gracefully."""
    from backend.requirement_extractor import RequirementExtractor

    extractor = RequirementExtractor(api_key=None)
    assert extractor.client is None

    result = extractor.adversarial_completeness_check(
        circular_text="Some circular text",
        findings=[{"description": "req 1", "status": "Full", "reasoning": "covered"}],
    )

    assert "flagged" in result
    assert result["flagged"] == []
    # Should not raise; should return gracefully
    assert isinstance(result, dict)
