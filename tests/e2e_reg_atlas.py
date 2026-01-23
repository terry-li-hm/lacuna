import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("REG_ATLAS_NO_LLM", "1")
os.environ.setdefault("REG_ATLAS_IN_MEMORY", "1")

from backend.main import app  # noqa: E402


client = TestClient(app)

BASE = Path(__file__).resolve().parents[1]
DOC1 = BASE / "data/documents/sample_hkma_capital.txt"
DOC2 = BASE / "data/documents/sample_mas_liquidity.txt"


def assert_ok(resp, label):
    assert resp.status_code == 200, f"{label} failed: {resp.status_code} {resp.text}"


def test_e2e():
    # Health
    resp = client.get("/")
    assert_ok(resp, "health")
    resp = client.get("/healthz")
    assert_ok(resp, "healthz")
    resp = client.get("/readyz")
    assert_ok(resp, "readyz")

    # Upload docs
    with DOC1.open("rb") as f:
        resp = client.post(
            "/upload",
            params={"jurisdiction": "Hong Kong", "no_llm": "true"},
            files={"file": (DOC1.name, f, "text/plain")},
        )
    assert_ok(resp, "upload hk")
    doc_id = resp.json().get("doc_id")

    with DOC2.open("rb") as f:
        resp = client.post(
            "/upload",
            params={"jurisdiction": "Singapore", "no_llm": "true"},
            files={"file": (DOC2.name, f, "text/plain")},
        )
    assert_ok(resp, "upload sg")

    # Query
    resp = client.post(
        "/query",
        json={
            "query": "What are capital requirements?",
            "jurisdiction": "Hong Kong",
            "n_results": 3,
            "no_llm": True,
        },
    )
    assert_ok(resp, "query")

    # Compare
    resp = client.post(
        "/compare",
        json={
            "jurisdiction1": "Hong Kong",
            "jurisdiction2": "Singapore",
            "no_llm": True,
        },
    )
    assert_ok(resp, "compare")

    # Requirements list
    resp = client.get("/requirements", params={"jurisdiction": "Hong Kong"})
    assert_ok(resp, "requirements")
    reqs = resp.json().get("requirements", [])
    req_id = reqs[0]["requirement_id"] if reqs else None
    resp = client.get("/requirements/stats")
    assert_ok(resp, "requirements stats")

    if doc_id:
        resp = client.get(f"/documents/{doc_id}/requirements")
        assert_ok(resp, "document requirements")

    # Requirement review
    if req_id:
        resp = client.post(
            f"/requirements/id/{req_id}/review",
            json={
                "status": "reviewed",
                "reviewer": "Compliance",
                "notes": "E2E test",
                "tags": ["test"],
                "controls": ["RC-1"],
                "policy_refs": ["POL-AML-001"],
            },
        )
        assert_ok(resp, "requirement review")
        resp = client.get(f"/requirements/id/{req_id}/evidence")
        assert_ok(resp, "requirement evidence")

    # Export requirements
    resp = client.get("/requirements/export", params={"format": "csv"})
    assert_ok(resp, "requirements export")

    # Change create
    resp = client.post(
        "/changes",
        json={
            "title": "HKMA circular on LCR reporting",
            "jurisdiction": "Hong Kong",
            "summary": "LCR disclosure updates",
            "source": "https://example.com/hkma",
            "effective_date": "2026-06-30",
            "severity": "high",
            "owner": "Compliance",
            "due_date": "2026-07-31",
            "impacted_areas": ["Risk", "Treasury"],
            "related_requirement_ids": [req_id] if req_id else [],
        },
    )
    assert_ok(resp, "change create")
    change_id = resp.json().get("change_id")

    if change_id:
        resp = client.get(f"/changes/{change_id}")
        assert_ok(resp, "change get")

    # Change approval
    if change_id:
        resp = client.post(
            f"/changes/{change_id}/approvals",
            json={"approver": "Head of Compliance", "status": "pending", "notes": "Queued"},
        )
        assert_ok(resp, "change approval")
        resp = client.get(f"/changes/{change_id}/approvals")
        assert_ok(resp, "change approvals list")

    # AI suggest
    if change_id:
        resp = client.post(
            f"/changes/{change_id}/ai-suggest",
            json={"no_llm": True, "n_results": 3},
        )
        assert_ok(resp, "change ai suggest")

    # Impact brief
    if change_id:
        resp = client.post(
            f"/changes/{change_id}/impact-brief",
            json={"no_llm": True, "n_results": 3, "max_claims_per_section": 5},
        )
        assert_ok(resp, "change impact brief")
        payload = resp.json()
        assert "brief" in payload
        assert isinstance(payload["brief"].get("summary", []), list)

    # Evidence upload
    if change_id:
        with DOC1.open("rb") as f:
            resp = client.post(
                "/evidence/upload",
                params={"entity_type": "change", "entity_id": change_id},
                files={"file": (DOC1.name, f, "text/plain")},
            )
        assert_ok(resp, "evidence upload")

    # Change update
    if change_id:
        resp = client.post(
            f"/changes/{change_id}",
            json={
                "status": "assessing",
                "owner": "Risk",
                "impact_assessment": "Impacts liquidity reporting controls",
                "impacted_areas": ["Risk"],
                "related_requirement_ids": [req_id] if req_id else [],
                "policy_refs": ["aml-kyc-policy"],
            },
        )
        assert_ok(resp, "change update")

    # Change list
    resp = client.get("/changes", params={"jurisdiction": "Hong Kong", "include_overdue": "true"})
    assert_ok(resp, "change list")

    # Export changes
    resp = client.get("/changes/export", params={"format": "csv"})
    assert_ok(resp, "change export")

    resp = client.get("/documents/export", params={"format": "json"})
    assert_ok(resp, "documents export")

    # Source + scan (offline feed)
    rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Reg Updates</title>
        <item>
          <title>Sample Regulatory Update</title>
          <link>https://example.com/update</link>
          <guid>sample-update-1</guid>
          <pubDate>2026-01-23</pubDate>
          <description>Sample update description</description>
        </item>
      </channel>
    </rss>"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        tmp.write(rss.encode("utf-8"))
        feed_url = f"file://{tmp.name}"

    resp = client.post(
        "/sources",
        json={"name": "Local Feed", "url": feed_url, "jurisdiction": "Hong Kong"},
    )
    assert_ok(resp, "source create")
    source_id = resp.json().get("source_id")
    if source_id:
        resp = client.get(f"/sources/{source_id}")
        assert_ok(resp, "source get")

    resp = client.post("/scan", params={"source_id": source_id})
    assert_ok(resp, "source scan")

    # Webhook
    resp = client.post(
        "/webhooks",
        json={"url": "https://example.com/webhook", "events": ["change.created"]},
    )
    assert_ok(resp, "webhook create")
    webhook_id = resp.json().get("webhook_id")
    if webhook_id:
        resp = client.get(f"/webhooks/{webhook_id}")
        assert_ok(resp, "webhook get")

    # Alerts
    resp = client.get("/alerts")
    assert_ok(resp, "alerts")
    resp = client.get("/alerts", params={"jurisdiction": "Hong Kong"})
    assert_ok(resp, "alerts filtered")

    # Policies
    resp = client.get("/policies")
    assert_ok(resp, "policies list")
    resp = client.get("/policies/export", params={"format": "json"})
    assert_ok(resp, "policies export")
    policies = resp.json().get("policies", [])
    if policies:
        policy_id = policies[0]["policy_id"]
        resp = client.post(
            f"/policies/{policy_id}/update",
            json={"status": "active", "version": "1.1", "owner": "Compliance"},
        )
        assert_ok(resp, "policy update")

    # Audit log
    resp = client.get("/audit-log")
    assert_ok(resp, "audit log")
    resp = client.get("/audit-log/export", params={"format": "json"})
    assert_ok(resp, "audit log export")

    # Stats
    resp = client.get("/stats")
    assert_ok(resp, "stats")
    resp = client.get("/changes/stats")
    assert_ok(resp, "changes stats")
