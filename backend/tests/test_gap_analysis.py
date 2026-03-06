import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_finding(status, draft_amendment=None):
    return {
        "circular_req_id": "req-1",
        "description": "Test requirement",
        "status": status,
        "reasoning": "Test reasoning",
        "baseline_match_id": None,
        "baseline_match_text": None,
        "provenance": [],
        "draft_amendment": draft_amendment,
    }


def test_gap_analysis_missing_docs(client, mock_gap_analysis_service):
    """Test gap analysis with missing documents returns 404."""
    # Setup mock to raise ValueError like the service would
    mock_gap_analysis_service.perform_gap_analysis.side_effect = ValueError(
        "Document not found"
    )

    response = client.post(
        "/gap-analysis",
        json={
            "circular_doc_id": "nonexistent",
            "baseline_id": "also-nonexistent",
            "is_policy_baseline": False,
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_gap_analysis_success(client, mock_gap_analysis_service):
    """Test successful gap analysis smoke test."""
    mock_gap_analysis_service.perform_gap_analysis.return_value = {
        "report_id": "gap_123",
        "circular_id": "doc1",
        "baseline_id": "base1",
        "generated_at": "2026-01-30T00:00:00Z",
        "summary": {"Full": 1, "Partial": 0, "Gap": 0},
        "findings": [],
    }

    response = client.post(
        "/gap-analysis",
        json={
            "circular_doc_id": "doc1",
            "baseline_id": "base1",
            "is_policy_baseline": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["circular_id"] == "doc1"
    assert response.json()["report_id"] == "gap_123"


def test_gap_analysis_include_amendments_flag(client, mock_gap_analysis_service):
    """include_amendments=True is passed through to the service."""
    mock_gap_analysis_service.perform_gap_analysis.return_value = {
        "report_id": "gap_456",
        "circular_id": "doc1",
        "baseline_id": "base1",
        "generated_at": "2026-01-30T00:00:00Z",
        "summary": {"Full": 0, "Partial": 1, "Gap": 1},
        "findings": [
            _make_finding("Partial", draft_amendment="Add explicit board accountability clause."),
            _make_finding("Gap", draft_amendment="Insert new §4.2 covering BDAI principles."),
        ],
    }

    response = client.post(
        "/gap-analysis",
        json={
            "circular_doc_id": "doc1",
            "baseline_id": "base1",
            "is_policy_baseline": False,
            "include_amendments": True,
        },
    )

    assert response.status_code == 200
    mock_gap_analysis_service.perform_gap_analysis.assert_called_once()
    call_kwargs = mock_gap_analysis_service.perform_gap_analysis.call_args
    assert call_kwargs.kwargs.get("include_amendments") is True
    findings = response.json()["findings"]
    assert findings[0]["draft_amendment"] == "Add explicit board accountability clause."
    assert findings[1]["draft_amendment"] == "Insert new §4.2 covering BDAI principles."


def test_gap_analysis_amendments_default_false(client, mock_gap_analysis_service):
    """include_amendments defaults to False — draft_amendment fields are None."""
    mock_gap_analysis_service.perform_gap_analysis.return_value = {
        "report_id": "gap_789",
        "circular_id": "doc1",
        "baseline_id": "base1",
        "generated_at": "2026-01-30T00:00:00Z",
        "summary": {"Full": 0, "Partial": 1, "Gap": 1},
        "findings": [
            _make_finding("Partial"),
            _make_finding("Gap"),
        ],
    }

    response = client.post(
        "/gap-analysis",
        json={"circular_doc_id": "doc1", "baseline_id": "base1"},
    )

    assert response.status_code == 200
    for finding in response.json()["findings"]:
        assert finding["draft_amendment"] is None


def test_gap_analysis_summary_counts(client, mock_gap_analysis_service):
    """Summary counts match the findings list."""
    mock_gap_analysis_service.perform_gap_analysis.return_value = {
        "report_id": "gap_sum",
        "circular_id": "doc1",
        "baseline_id": "base1",
        "generated_at": "2026-01-30T00:00:00Z",
        "summary": {"Full": 1, "Partial": 2, "Gap": 1},
        "findings": [
            _make_finding("Full"),
            _make_finding("Partial"),
            _make_finding("Partial"),
            _make_finding("Gap"),
        ],
    }

    response = client.post(
        "/gap-analysis",
        json={"circular_doc_id": "doc1", "baseline_id": "base1"},
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["Full"] == 1
    assert summary["Partial"] == 2
    assert summary["Gap"] == 1
