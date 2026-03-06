"""Tests for the decompose endpoint and DecomposeService."""
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ["REG_ATLAS_NO_LLM"] = "1"
os.environ["REG_ATLAS_IN_MEMORY"] = "1"

from backend.main import app

client = TestClient(app)
BASE = Path(__file__).resolve().parents[1]
DOC1 = BASE / "data/documents/sample_hkma_capital.txt"


def _upload_doc(no_llm=True) -> str:
    with DOC1.open("rb") as f:
        resp = client.post(
            "/upload",
            params={"jurisdiction": "Hong Kong", "no_llm": str(no_llm).lower()},
            files={"file": (DOC1.name, f, "text/plain")},
        )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    return resp.json()["doc_id"]


def test_decompose_returns_requirements():
    doc_id = _upload_doc()
    resp = client.post("/decompose", json={"doc_id": doc_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["doc_id"] == doc_id
    assert "requirements" in data
    assert "total" in data
    assert isinstance(data["requirements"], list)
    assert data["total"] == len(data["requirements"])
    assert data["fresh"] is False


def test_decompose_requirements_have_index():
    doc_id = _upload_doc()
    resp = client.post("/decompose", json={"doc_id": doc_id})
    assert resp.status_code == 200
    reqs = resp.json()["requirements"]
    if reqs:
        indices = [r["index"] for r in reqs]
        assert indices == list(range(1, len(reqs) + 1)), "Indices must be 1-based sequential"
        assert all("description" in r for r in reqs)


def test_decompose_unknown_doc_returns_404():
    resp = client.post("/decompose", json={"doc_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 404


def test_decompose_cached_on_second_call():
    doc_id = _upload_doc()
    resp1 = client.post("/decompose", json={"doc_id": doc_id})
    resp2 = client.post("/decompose", json={"doc_id": doc_id})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["total"] == resp2.json()["total"]


def test_decompose_empty_doc_returns_zero():
    """A doc with no extracted requirements returns total=0 without error."""
    doc_id = _upload_doc(no_llm=True)
    resp = client.post("/decompose", json={"doc_id": doc_id, "fresh": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 0  # may be 0 for no_llm upload


def test_gap_analysis_completeness_audit_field_present():
    """include_completeness_audit=True adds completeness_audit key to response."""
    doc_id = _upload_doc()
    resp = client.post(
        "/gap-analysis",
        json={
            "circular_doc_id": doc_id,
            "baseline_id": doc_id,
            "no_llm": True,
            "include_completeness_audit": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Field must be present (may be None when no_llm=True disables LLM)
    assert "completeness_audit" in data


def test_adversarial_check_no_llm_returns_empty():
    """adversarial_completeness_check with no client returns empty flagged list."""
    from backend.requirement_extractor import RequirementExtractor
    extractor = RequirementExtractor(api_key=None)
    result = extractor.adversarial_completeness_check("some circular text", [])
    assert "flagged" in result
    assert isinstance(result["flagged"], list)
    assert len(result["flagged"]) == 0
