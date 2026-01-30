import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["REG_ATLAS_NO_LLM"] = "1"
os.environ["REG_ATLAS_IN_MEMORY"] = "1"

from backend.main import app

client = TestClient(app)
BASE = Path(__file__).resolve().parents[1]
DOC1 = BASE / "data/documents/sample_hkma_capital.txt"

def test_gap_analysis_e2e():
    print("Testing Gap Analysis E2E...")
    
    # 1. Upload baseline
    with DOC1.open("rb") as f:
        resp = client.post(
            "/upload",
            params={"jurisdiction": "Hong Kong", "no_llm": "true"},
            files={"file": (DOC1.name, f, "text/plain")},
        )
    assert resp.status_code == 200, f"Upload baseline failed: {resp.text}"
    baseline_id = resp.json().get("doc_id")
    print(f"Baseline uploaded: {baseline_id}")

    # 2. Upload circular
    with DOC1.open("rb") as f:
        resp = client.post(
            "/upload",
            params={"jurisdiction": "Hong Kong", "no_llm": "true"},
            files={"file": (DOC1.name, f, "text/plain")},
        )
    assert resp.status_code == 200, f"Upload circular failed: {resp.text}"
    circular_id = resp.json().get("doc_id")
    print(f"Circular uploaded: {circular_id}")

    # 3. Perform Gap Analysis
    print("Running gap analysis request...")
    resp = client.post(
        "/gap-analysis",
        json={
            "circular_doc_id": circular_id,
            "baseline_id": baseline_id,
            "no_llm": True
        }
    )
    assert resp.status_code == 200, f"Gap analysis request failed: {resp.text}"
    data = resp.json()
    
    assert "report_id" in data
    assert "findings" in data
    assert len(data["findings"]) > 0
    assert "summary" in data
    
    print(f"Gap Analysis Report ID: {data['report_id']}")
    print(f"Summary: {data['summary']}")
    print(f"Findings count: {len(data['findings'])}")
    
    for f in data["findings"]:
        assert "status" in f
        assert "description" in f
        assert "reasoning" in f
        assert "provenance" in f

if __name__ == "__main__":
    try:
        test_gap_analysis_e2e()
        print("\n✅ Test passed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
