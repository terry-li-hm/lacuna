import asyncio
from unittest.mock import MagicMock

from backend.services.gap_graph import build_gap_graph


def test_gap_graph_compiles():
    graph = build_gap_graph()
    assert graph is not None


def test_gap_graph_collects_findings_and_draft_amendments():
    vector_store = MagicMock()
    vector_store.query.return_value = [{"id": "chunk-1", "text": "baseline"}]

    llm_service = MagicMock()

    def perform_gap_analysis(req, baseline_chunks, force_basic):
        assert baseline_chunks == [{"id": "chunk-1", "text": "baseline"}]
        assert force_basic is False
        if req["description"] == "Requirement A":
            return {
                "status": "Full",
                "reasoning": "Covered in baseline.",
                "provenance": [],
            }
        return {
            "status": "Gap",
            "reasoning": "Missing from baseline.",
            "provenance": [],
        }

    llm_service.perform_gap_analysis.side_effect = perform_gap_analysis
    llm_service.generate_draft_amendment.return_value = "Add a new control."

    result = asyncio.run(
        build_gap_graph().ainvoke(
            {
                "circular_doc_id": "circular-1",
                "baseline_id": "baseline-1",
                "requirements": [
                    {"description": "Requirement A"},
                    {"description": "Requirement B"},
                ],
                "current_req": None,
                "findings": [],
                "include_amendments": True,
                "no_llm": False,
                "vector_store": vector_store,
                "llm_service": llm_service,
            }
        )
    )

    findings = sorted(result["findings"], key=lambda finding: finding.description)
    assert [finding.status for finding in findings] == ["Full", "Gap"]
    assert findings[0].draft_amendment is None
    assert findings[1].draft_amendment == "Add a new control."
    assert vector_store.query.call_count == 2
    assert llm_service.perform_gap_analysis.call_count == 2
    llm_service.generate_draft_amendment.assert_called_once()
