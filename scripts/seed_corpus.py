#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""Seed Meridian with real regulatory documents and configure horizon scanning.

Usage:
    python scripts/seed_corpus.py                          # default: http://localhost:8000
    python scripts/seed_corpus.py --target https://meridian-production-1bdb.up.railway.app
"""

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents" / "corpus"

# Document manifest: (relative_path, jurisdiction, display_name)
DOCUMENTS = [
    ("hkma/hkma-genai-consumer-protection-2024.pdf", "Hong Kong", "HKMA GenAI Consumer Protection Circular (Aug 2024)"),
    ("hkma/hkma-spm-ca-g-1-revised-2024.pdf", "Hong Kong", "HKMA Revised SPM CA-G-1 Capital Adequacy (Nov 2024)"),
    ("hkma/hkma-genai-sandbox-arrangement-2024.pdf", "Hong Kong", "HKMA GenAI Sandbox Arrangement (Sep 2024)"),
    ("hkma/hkma-genai-financial-services-2024.pdf", "Hong Kong", "HKMA GenAI in Financial Services (Nov 2024)"),
    ("mas/mas-ai-model-risk-management-2024.pdf", "Singapore", "MAS AI Model Risk Management (2024)"),
    ("mas/mas-ai-risk-management-consultation-2025.pdf", "Singapore", "MAS AI Risk Management Guidelines Consultation (2025)"),
    ("eu/eu-ai-act-2024-1689.pdf", "European Union", "EU AI Act - Regulation 2024/1689"),
    ("uk/fca-ai-update-2024.pdf", "United Kingdom", "FCA AI Update (2024)"),
]

# RSS feed sources for horizon scanning
SOURCES = [
    {
        "name": "HKMA Circulars & Guidelines",
        "url": "https://www.hkma.gov.hk/eng/key-functions/banking/banking-regulatory-and-supervisory-regime/regulatory-framework/circulars/rss.xml",
        "jurisdiction": "Hong Kong",
        "default_severity": "high",
    },
    {
        "name": "MAS Media Releases",
        "url": "https://www.mas.gov.sg/rss/media-releases.xml",
        "jurisdiction": "Singapore",
        "default_severity": "medium",
    },
    {
        "name": "EUR-Lex AI Act Updates",
        "url": "https://eur-lex.europa.eu/EN/display-feed.html?myRssId=QV47JE&lang=en",
        "jurisdiction": "European Union",
        "default_severity": "medium",
    },
]

# Sample change items for demo
SAMPLE_CHANGES = [
    {
        "title": "HKMA GenAI Consumer Protection Circular - Implementation Review",
        "jurisdiction": "Hong Kong",
        "severity": "high",
        "status": "new",
        "owner": "Compliance Team",
        "due_date": (date.today() - timedelta(days=5)).isoformat(),
        "summary": "Review current GenAI deployments against the 10 guiding principles in the Aug 2024 circular. Assess opt-out mechanisms and transparency disclosures.",
        "source": "HKMA Circular B1/15C",
        "impacted_areas": ["Retail Banking", "Digital Services", "Risk Management"],
    },
    {
        "title": "MAS AI Risk Management Consultation Response",
        "jurisdiction": "Singapore",
        "severity": "medium",
        "status": "new",
        "owner": "Regional Compliance",
        "due_date": (date.today() + timedelta(days=14)).isoformat(),
        "summary": "Prepare response to MAS consultation P017-2025 on AI Risk Management Guidelines. Consultation closed Jan 31 2026 — assess final guidelines impact.",
        "source": "MAS Consultation P017-2025",
        "impacted_areas": ["AI/ML Operations", "Model Risk", "Technology Risk"],
    },
    {
        "title": "EU AI Act High-Risk Classification Assessment",
        "jurisdiction": "European Union",
        "severity": "high",
        "status": "new",
        "owner": "EU Regulatory Affairs",
        "due_date": (date.today() - timedelta(days=12)).isoformat(),
        "summary": "Assess which AI systems used by EU subsidiaries fall under Article 6 high-risk classification. Map to Annex III categories.",
        "source": "EU AI Act 2024/1689",
        "impacted_areas": ["EU Subsidiaries", "AI Governance", "Legal"],
    },
]


def upload_document(client: httpx.Client, base_url: str, path: Path, jurisdiction: str, name: str) -> dict | None:
    """Upload a single document to Meridian."""
    if not path.exists():
        print(f"  SKIP  {name} — file not found: {path}")
        return None

    try:
        with open(path, "rb") as f:
            response = client.post(
                f"{base_url}/upload",
                files={"file": (path.name, f, "application/pdf")},
                params={"jurisdiction": jurisdiction},
                timeout=600,
            )
        if response.status_code == 409:
            print(f"  EXISTS {name}")
            return {"duplicate": True}
        response.raise_for_status()
        result = response.json()
        doc_id = result.get("doc_id", "?")
        chunks = result.get("chunks_count", 0)
        reqs = len(result.get("requirements", []))
        print(f"  OK    {name} → {doc_id[:8]} ({chunks} chunks, {reqs} requirements)")
        return result
    except Exception as e:
        print(f"  ERROR {name}: {e}")
        return None


def register_source(client: httpx.Client, base_url: str, source: dict) -> dict | None:
    """Register an RSS feed source."""
    try:
        response = client.post(
            f"{base_url}/sources",
            json=source,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        print(f"  OK    {source['name']} ({source['jurisdiction']})")
        return result
    except Exception as e:
        print(f"  ERROR {source['name']}: {e}")
        return None


def create_change(client: httpx.Client, base_url: str, change: dict) -> dict | None:
    """Create a sample change item."""
    try:
        response = client.post(
            f"{base_url}/changes",
            json=change,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        print(f"  OK    {change['title'][:60]}")
        return result
    except Exception as e:
        print(f"  ERROR {change['title'][:40]}: {e}")
        return None


def trigger_scan(client: httpx.Client, base_url: str) -> dict | None:
    """Trigger a horizon scan of all registered sources."""
    try:
        response = client.post(f"{base_url}/scan", timeout=60)
        response.raise_for_status()
        result = response.json()
        print(f"  OK    Scanned {result.get('scanned', 0)} sources, created {result.get('total_created', 0)} items")
        return result
    except Exception as e:
        print(f"  ERROR Scan failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Seed Meridian with regulatory corpus")
    parser.add_argument("--target", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--skip-docs", action="store_true", help="Skip document uploads")
    parser.add_argument("--skip-sources", action="store_true", help="Skip source registration")
    parser.add_argument("--skip-scan", action="store_true", help="Skip horizon scan")
    parser.add_argument("--skip-changes", action="store_true", help="Skip sample changes")
    args = parser.parse_args()

    base_url = args.target.rstrip("/")
    print(f"\nMeridian Seed Script")
    print(f"Target: {base_url}")

    client = httpx.Client()

    # Health check
    try:
        resp = client.get(f"{base_url}/healthz", timeout=10)
        resp.raise_for_status()
        print(f"Status: {resp.json().get('status', 'unknown')}\n")
    except Exception as e:
        print(f"ERROR: Cannot reach {base_url} — {e}")
        sys.exit(1)

    # 1. Upload documents
    if not args.skip_docs:
        print("=" * 60)
        print("1. Uploading regulatory documents")
        print("=" * 60)
        doc_results = {}
        for rel_path, jurisdiction, name in DOCUMENTS:
            full_path = CORPUS_DIR / rel_path
            result = upload_document(client, base_url, full_path, jurisdiction, name)
            if result and not result.get("duplicate"):
                doc_results[name] = result
                time.sleep(0.5)  # Be gentle with the API
        print(f"\nUploaded {len(doc_results)} documents\n")

    # 2. Register RSS sources
    if not args.skip_sources:
        print("=" * 60)
        print("2. Registering RSS feed sources")
        print("=" * 60)
        for source in SOURCES:
            register_source(client, base_url, source)
        print()

    # 3. Trigger horizon scan
    if not args.skip_scan:
        print("=" * 60)
        print("3. Running horizon scan")
        print("=" * 60)
        trigger_scan(client, base_url)
        print()

    # 4. Create sample change items
    if not args.skip_changes:
        print("=" * 60)
        print("4. Creating sample change items")
        print("=" * 60)
        for change in SAMPLE_CHANGES:
            create_change(client, base_url, change)
        print()

    # 5. Summary
    print("=" * 60)
    print("Seed complete!")
    print("=" * 60)
    try:
        stats = client.get(f"{base_url}/stats", timeout=10).json()
        print(f"  Documents:    {stats.get('total_documents', '?')}")
        print(f"  Chunks:       {stats.get('total_chunks', '?')}")
        print(f"  Requirements: {stats.get('total_requirements', '?')}")
        print(f"  Jurisdictions: {', '.join(stats.get('jurisdictions', []))}")
    except Exception:
        pass

    try:
        changes = client.get(f"{base_url}/changes", timeout=10).json()
        alerts = client.get(f"{base_url}/alerts", timeout=10).json()
        print(f"  Changes:      {changes.get('total', '?')}")
        print(f"  Overdue:      {alerts.get('total', '?')}")
    except Exception:
        pass

    print(f"\nDashboard: {base_url.replace('/api', '')}")
    client.close()


if __name__ == "__main__":
    main()
