#!/usr/bin/env python3
"""Re-seed Lacuna corpus after fresh volume mount or data loss.

Usage:
    python3 tools/seed_corpus.py [--base-url https://lacuna.sh]

After completion, run:
    python3 tools/update_aliases.py
"""
import json, subprocess, time, sys, argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "data/documents/corpus"
DEMO = REPO / "demo-docs"

DOCS = [
    ("hkma-cp",     CORPUS / "hkma/hkma-genai-consumer-protection-2024.pdf",  "HKMA GenAI Consumer Protection 2024",      "HK",          False),
    ("hkma-gai",    CORPUS / "hkma/hkma-genai-financial-services-2024.pdf",   "HKMA GenAI Financial Services 2024",       "HK",          False),
    ("hkma-sandbox",CORPUS / "hkma/hkma-genai-sandbox-arrangement-2024.pdf",  "HKMA GenAI Sandbox Arrangement 2024",      "HK",          False),
    ("hkma-spm",    CORPUS / "hkma/hkma-spm-ca-g-1-revised-2024.pdf",         "HKMA SPM CA-G-1 Revised 2024",             "HK",          False),
    ("eu-ai-act",   CORPUS / "eu/eu-ai-act-2024-1689.pdf",                    "EU AI Act (Regulation 2024/1689)",          "EU",          True),
    ("fca",         CORPUS / "uk/fca-ai-update-2024.pdf",                     "FCA AI Update 2024",                       "UK",          True),
    ("mas-consult", CORPUS / "mas/mas-ai-risk-management-consultation-2025.pdf","MAS AI Risk Management Consultation 2025","SG",          False),
    ("mas-mrmf",    CORPUS / "mas/mas-ai-model-risk-management-2024.pdf",     "MAS AI Model Risk Management 2024",        "SG",          False),
    ("nist-rmf",    CORPUS / "global/nist-ai-rmf-1.0.pdf",                    "NIST AI Risk Management Framework 1.0",    "GLOBAL",      True),
    ("nist-iso42001",CORPUS / "global/nist-ai-rmf-iso42001-crosswalk.pdf",    "NIST AI RMF to ISO 42001 Crosswalk",       "GLOBAL",      True),
    ("sg-genai",    CORPUS / "sg/sg-genai-governance-framework-2024.pdf",     "Singapore GenAI Governance Framework 2024","SG",          True),
    ("demo-baseline",DEMO / "codex-argentum-v1.txt",                          "Codex Argentum v1.1",                      "ILLUSTRATIVE",False),
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://lacuna.sh")
    args = parser.parse_args()
    BASE = args.base_url.rstrip("/")

    results = {}
    for alias, path, name, jur, no_llm in DOCS:
        if not Path(path).exists():
            print(f"  SKIP {alias} — file not found: {path}")
            continue
        cmd = ["curl", "-s", "--max-time", "600", "-X", "POST",
               f"{BASE}/upload?jurisdiction={jur}{'&no_llm=true' if no_llm else ''}",
               "-F", f"file=@{path}"]
        print(f"  Uploading {alias}...", flush=True)
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = int(time.time() - t0)
        try:
            d = json.loads(r.stdout)
            if d.get("duplicate"):
                doc_id = d.get("doc_id", "DUPLICATE")
                print(f"    -> {doc_id}  (duplicate, {elapsed}s)", flush=True)
            else:
                doc_id = d.get("doc_id", "ERROR")
                print(f"    -> {doc_id}  ({elapsed}s)", flush=True)
            results[alias] = doc_id
        except Exception as e:
            print(f"    ERROR: {r.stdout[:200]}", flush=True)
            results[alias] = "ERROR"

    out = Path("/tmp/lacuna-new-ids.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {out}")
    print("\nNext step: python3 tools/update_aliases.py")
    return results

if __name__ == "__main__":
    main()
