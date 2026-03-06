# Lacuna — Project Reference

## Deployment

- **Railway project:** `56536e61-c258-4ea6-a074-531ecb57e36a`
- **Railway service:** `838bfe97-b9e3-4eb0-b1d5-2a3db86006b9`
- **URL:** https://lacuna.sh (custom domain) — Railway: https://lacuna-production-8dbb.up.railway.app
- **Volume:** `lacuna-volume` mounted at `/app/data` (persists DuckDB + ChromaDB + JSON stores) — created Mar 6 2026; was missing before, data was ephemeral
- **Deploy:** `railway up --detach` (not GitHub auto-deploy)

> Old project (meridian): `c2b227f0` — deleted Mar 3 2026.

## Package Names

- PyPI / npm / crates.io: `lacunae` (platform stubs)
- Demo CLI: `lacuna` (~/bin/lacuna) — `lacuna gap/query/docs/warmup/preflight`

## Gotchas

- **OpenRouter model IDs don't use date suffixes.** `anthropic/claude-sonnet-4` not `anthropic/claude-sonnet-4-20250514`. Cost us all-Gap results in gap analysis until fixed.
- **Railway volumes mount as root.** Dockerfile CMD does `chown -R appuser:appuser /app/data` at runtime before dropping to appuser via `runuser`.
- **Large PDF uploads block the event loop.** Sync OpenAI calls freeze uvicorn. Upload big docs with `no_llm=true` and accept missing requirements, or fix with `asyncio.to_thread()` (not yet done).
- **Railway has a 5-min HTTP timeout.** Large doc LLM extraction can exceed this — server finishes but client times out.

## Corpus

9 docs currently live (Mar 6 2026 re-seed), 4 jurisdictions (HK, SG, EU, UK). NIST RMF, NIST ISO 42001, SG GenAI not yet re-uploaded (PDFs not in repo). EU AI Act and FCA uploaded with `no_llm`.

## Key Doc IDs (current deployment)

- `95282d33-aa48-4528-8539-ca8f93a8812a` — HKMA Consumer Protection 2024 (7 reqs) — alias: `hkma-cp`
- `6fa684d3-aa1e-4f68-9607-db13b18e379b` — HKMA GenAI Financial Services 2024 (130 reqs) — alias: `hkma-gai`
- `63610388-9678-4a4d-a5e4-64ad541c2573` — HKMA Sandbox Arrangement (9 reqs) — alias: `hkma-sandbox`
- `55b1ab09-4ba1-41fc-8617-b889b20523b3` — HKMA SPM CA-G-1 (1 req) — alias: `hkma-spm`
- `4d2946c9-6c0c-4805-a86b-5fa05920d3d1` — EU AI Act (no_llm) — alias: `eu-ai-act`
- `4ee46ae2-7129-40b9-9ec1-97e058d0ae95` — FCA AI Update (no_llm) — alias: `fca`
- `136c8986-c5dc-4f17-9da9-053643e89cce` — MAS AI Risk Management Consultation 2025 — alias: `mas-consult`
- `c5bd5b9a-91c8-44d4-aa60-850d977e7f82` — MAS AI Model Risk Management 2024 — alias: `mas-mrmf`
- `74af858d-887b-4031-a1ba-7a293fda5a35` — **Codex Argentum v1.1 (illustrative AI governance baseline, Capco-authored, no HSBC branding)** — alias: `demo-baseline`
- *(nist-rmf, nist-iso42001, sg-genai not re-uploaded — source PDFs not in repo. Upload manually if needed for demo.)*

## Demo Gap Analysis (pre-calibrated, cached)

**Primary demo — HKMA Consumer Protection vs Codex Argentum v1.1:**
- circular_doc_id: `95282d33-aa48-4528-8539-ca8f93a8812a`
- baseline_id: `74af858d-887b-4031-a1ba-7a293fda5a35`
- is_policy_baseline: false
- Result: 0 Full, 5 Partial, 2 Gap — paragraph-level reasoning + provenance citations
- ⚠ Codex Argentum updated to v1.1 (§3.9, §8.1e added Mar 3) — re-warm before next demo, results will differ

**Second baseline (credibility test — doc you didn't write):**
- Use `mas-mrmf` (MAS AI Model Risk Management 2024) — in system, not Capco-authored
- Run same HKMA circular against it to show tool works on external text
- Note: NIST RMF not currently in system (PDFs not in repo)

**Note:** Cache is in-memory on Railway. Pre-run before demo day if service has restarted.

## Demo

See `DEMO_SCRIPT.md`. Gap analysis demo button uses Consumer Protection vs Financial Services guidance (Claude Sonnet 4 via OpenRouter).

## Corpus Rebuild (after volume loss / fresh deploy)

All source PDFs are in `data/documents/corpus/` in the repo. Run the seed script:
```bash
python3 /tmp/lacuna-seed.py   # creates /tmp/lacuna-seed.py first — see below
```

Seed script location: `tools/seed_corpus.py` (checked in). After seed completes, update UUID mappings:
```bash
python3 tools/update_aliases.py   # reads /tmp/lacuna-new-ids.json, updates bin/lacuna + CLAUDE.md
```

**Corpus PDFs available locally:**
- `data/documents/corpus/hkma/` — 4 HKMA docs (hkma-cp, hkma-gai, hkma-sandbox, hkma-spm)
- `data/documents/corpus/eu/` — EU AI Act (no_llm)
- `data/documents/corpus/uk/` — FCA AI Update (no_llm)
- `data/documents/corpus/mas/` — 2 MAS docs
- `demo-docs/codex-argentum-v1.txt` — Codex Argentum v1.1
- **Missing locally:** NIST RMF, NIST ISO 42001, SG GenAI Framework (were uploaded no_llm; not in git)

## Re-upload Workflow (Codex Argentum)

When updating and re-uploading `codex-argentum-v1.txt`:
```bash
BASE="https://lacuna.sh"
```
1. Delete current doc: `curl -X DELETE "$BASE/documents/<doc_id>"`
2. Upload with 600s timeout (LLM extraction takes 2-3 min, Railway 5-min HTTP timeout is tight): `curl --max-time 600 -X POST "$BASE/upload?jurisdiction=ILLUSTRATIVE" -F "file=@demo-docs/codex-argentum-v1.txt;type=text/plain" -o /tmp/lacuna-upload.json`
3. Run in background — `/tmp/lacuna-upload.json` is written on completion
4. Get new doc ID: `python3 -c "import json; d=json.load(open('/tmp/lacuna-upload.json')); print(d['doc_id'])"`
5. Update both doc ID entries in CLAUDE.md (corpus list + demo gap analysis config)
6. Flag demo cache as stale — re-warm before next demo
