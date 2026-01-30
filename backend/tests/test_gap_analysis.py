import pytest


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
