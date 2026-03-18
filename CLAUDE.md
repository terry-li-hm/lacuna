# Lacuna — Project Reference

## Deployment

- **Railway project:** `56536e61-c258-4ea6-a074-531ecb57e36a`
- **Railway service:** `838bfe97-b9e3-4eb0-b1d5-2a3db86006b9`
- **URL:** https://lacuna.sh (custom domain) — Railway: https://lacuna-production-8dbb.up.railway.app
- **Volume:** `lacuna-volume` mounted at `/app/data` (persists DuckDB + ChromaDB + JSON stores) — created Mar 6 2026; was missing before, data was ephemeral
- **Deploy:** `railway up --detach` (not GitHub auto-deploy)

**Why Railway (not Fly.io/Render/Vercel) — decided Mar 2026:**
- Already deployed with persistent volume mounted — migration friction not justified mid-demo cycle
- Vercel: no persistent POSIX disk → ChromaDB (SQLite) won't work without replacing vector store
- Render: persistent disk blocks zero-downtime deploys (volume unmounts on redeploy)
- Fly.io is the stronger choice on reliability (fewer 2025 incidents, better volume semantics)
- Railway's $100M Series B (Jan 2026) + bare-metal rebuild is a positive signal for stability
- **Revisit trigger:** Lacuna moves from demo → live client access → migrate to Fly.io

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

- `f49e7b31-bbc1-445d-b31f-ec5ac8397b28` — HKMA Consumer Protection 2024 (7 reqs) — alias: `hkma-cp`
- `8a2c389f-fcf4-4d5d-80a2-abde8980ea5b` — HKMA GenAI Financial Services 2024 (130 reqs) — alias: `hkma-gai`
- `9ff0b0cc-d39b-4a1c-877b-0d5a161d5a64` — HKMA Sandbox Arrangement (9 reqs) — alias: `hkma-sandbox`
- `2ab7d62f-c6ed-4d89-a02a-0c8966f0d03d` — HKMA SPM CA-G-1 (1 req) — alias: `hkma-spm`
- `98719ac7-bc70-490c-9eb7-89bd28247375` — EU AI Act (no_llm) — alias: `eu-ai-act`
- `76d51ae3-e193-4b90-8836-f92d5405cecc` — FCA AI Update (no_llm) — alias: `fca`
- `c6221a19-2438-48be-8363-693f7e779b3b` — MAS AI Risk Management Consultation 2025 — alias: `mas-consult`
- `1c855025-a01f-4a81-859e-0cecbe39eec8` — MAS AI Model Risk Management 2024 — alias: `mas-mrmf`
- `4f4115d5-034e-4112-a938-2fbad051a998` — **Codex Argentum v1.1 (illustrative AI governance baseline, Capco-authored, no HSBC branding)** — alias: `demo-baseline`
- *(nist-rmf, nist-iso42001, sg-genai not re-uploaded — source PDFs not in repo. Upload manually if needed for demo.)*

## Demo Gap Analysis (pre-calibrated, cached)

**Primary demo — HKMA Consumer Protection vs Codex Argentum v1.1:**
- circular_doc_id: `f49e7b31-bbc1-445d-b31f-ec5ac8397b28`
- baseline_id: `4f4115d5-034e-4112-a938-2fbad051a998`
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



## Product Strategy

See [[Lacuna - Product Strategy]] — CLI-first principle, completeness verification workflow, web UI sequencing.