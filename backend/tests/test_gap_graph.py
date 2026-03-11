import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.gap_graph import build_gap_graph
from backend.services.gap_analysis_service import GapAnalysisService


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


def _invoke(state):
    return asyncio.run(build_gap_graph().ainvoke(state))


def _base_state(**overrides):
    vs = MagicMock()
    vs.query.return_value = [{"id": "c1", "text": "chunk"}]
    ls = MagicMock()
    ls.perform_gap_analysis.return_value = {"status": "Gap", "reasoning": "missing", "provenance": []}
    ls.generate_draft_amendment.return_value = "draft text"
    state = {
        "circular_doc_id": "circ-1",
        "baseline_id": "base-1",
        "requirements": [{"description": "Req A"}],
        "current_req": None,
        "findings": [],
        "include_amendments": False,
        "no_llm": False,
        "vector_store": vs,
        "llm_service": ls,
    }
    state.update(overrides)
    return state, vs, ls


def test_empty_requirements_returns_no_findings():
    state, _, _ = _base_state(requirements=[])
    result = _invoke(state)
    assert result["findings"] == []


def test_no_llm_flag_passed_to_service():
    state, _, ls = _base_state(no_llm=True)
    _invoke(state)
    _, _, force_basic = ls.perform_gap_analysis.call_args[0]
    assert force_basic is True


def test_amendments_not_generated_when_flag_false():
    state, _, ls = _base_state(include_amendments=False)
    # Gap status would trigger amendment if flag were True
    ls.perform_gap_analysis.return_value = {"status": "Gap", "reasoning": "r", "provenance": []}
    _invoke(state)
    ls.generate_draft_amendment.assert_not_called()


def test_amendments_not_generated_for_full_status():
    state, _, ls = _base_state(include_amendments=True)
    ls.perform_gap_analysis.return_value = {"status": "Full", "reasoning": "r", "provenance": []}
    _invoke(state)
    ls.generate_draft_amendment.assert_not_called()


# --- GapAnalysisService integration ---

def _make_service(requirements=None):
    doc_repo = MagicMock()
    doc_repo.get.return_value = {"id": "circ-1", "requirements": requirements or [{"description": "R1"}]}
    policy_repo = MagicMock()
    vs = MagicMock()
    vs.query.return_value = [{"id": "c1", "text": "chunk"}]
    ls = MagicMock()
    ls.perform_gap_analysis.return_value = {"status": "Partial", "reasoning": "r", "provenance": []}
    ls.gap_analysis_model = "test-model"
    svc = GapAnalysisService(doc_repo, policy_repo, vs, ls)
    return svc, ls


def test_service_summary_counts_match_findings():
    svc, ls = _make_service(requirements=[
        {"description": "R1"},
        {"description": "R2"},
        {"description": "R3"},
    ])
    def gap_analysis(req, chunks, force_basic):
        return {"status": {"R1": "Full", "R2": "Partial", "R3": "Gap"}.get(req["description"], "Gap"),
                "reasoning": "r", "provenance": []}
    ls.perform_gap_analysis.side_effect = gap_analysis

    result = asyncio.run(svc.perform_gap_analysis("circ-1", "base-1"))
    assert result.summary == {"Full": 1, "Partial": 1, "Gap": 1}
    assert len(result.findings) == 3


def test_service_raises_on_missing_circular():
    svc, _ = _make_service()
    svc.doc_repo.get.return_value = None
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(svc.perform_gap_analysis("missing", "base-1"))
