# Lacuna — Project Reference

## Deployment

- **Railway project:** `c2b227f0-f4de-43b8-b6b7-f5ebdd6b90ea`
- **Railway service:** `9c410474-b16e-4aa6-a8a7-d2e00d7ab79d`
- **URL:** https://meridian-production-1bdb.up.railway.app
- **Volume:** mounted at `/app/data` (persists DuckDB + ChromaDB + JSON stores)
- **Deploy:** `railway up --detach` (not GitHub auto-deploy)

## Package Names

- PyPI / npm / crates.io: `lacunae` (platform stubs)
- Demo CLI: `lacuna` (~/bin/lacuna) — `lacuna gap/query/docs/warmup/preflight`

## Gotchas

- **OpenRouter model IDs don't use date suffixes.** `anthropic/claude-sonnet-4` not `anthropic/claude-sonnet-4-20250514`. Cost us all-Gap results in gap analysis until fixed.
- **Railway volumes mount as root.** Dockerfile CMD does `chown -R appuser:appuser /app/data` at runtime before dropping to appuser via `runuser`.
- **Large PDF uploads block the event loop.** Sync OpenAI calls freeze uvicorn. Upload big docs with `no_llm=true` and accept missing requirements, or fix with `asyncio.to_thread()` (not yet done).
- **Railway has a 5-min HTTP timeout.** Large doc LLM extraction can exceed this — server finishes but client times out.

## Corpus

12 docs, 5 jurisdictions (HK, SG, EU, UK, Global), ~1600 chunks, 341+ requirements. EU AI Act, FCA, NIST crosswalk, and Singapore GenAI Framework uploaded with `no_llm` (chunks but no extracted requirements).

## Key Doc IDs (current deployment)

- `7f247634-cdcb-455a-bd02-7083feb1ed6e` — HKMA Consumer Protection 2024 (8 reqs) — alias: `hkma-cp`
- `a4d64616-f9c1-4ec7-a8b8-e5c2e04d8b5d` — HKMA GenAI Financial Services 2024 (132 reqs) — alias: `hkma-gai`
- `eccf4ae5-dd33-49f6-b9f8-97bfd3b0181e` — HKMA Sandbox Arrangement (9 reqs) — alias: `hkma-sandbox`
- `dc5333c9-95cd-49ac-b2ed-12a88b7145f5` — HKMA SPM CA-G-1 (1 req) — alias: `hkma-spm`
- `ebcc1f4b-77d2-4f97-8251-512eaf388685` — EU AI Act (no_llm) — alias: `eu-ai-act`
- `4fdb030f-90d4-46ea-a104-121347c762d9` — FCA AI Update (no_llm) — alias: `fca`
- `c071bf07-dac5-4370-8538-c92c753db760` — MAS AI Risk Management Consultation 2025 — alias: `mas-consult`
- `36c7686e-c6f7-4807-adb8-03d0afe5d3e1` — MAS AI Model Risk Management 2024 — alias: `mas-mrmf`
- `ef3d9bff-a442-443f-97ca-9fc7d0108618` — **Codex Argentum v1.0 (illustrative AI governance baseline, Capco-authored, no HSBC branding)** — alias: `demo-baseline`
- `b55c5916-28ae-449b-bd61-54dea2bbbcc1` — NIST AI RMF 1.0 (no_llm, 131 chunks) — alias: `nist-rmf`
- `47c8640c-05a3-484a-b730-1e1cc22179bd` — NIST AI RMF → ISO 42001 Crosswalk (no_llm, 32 chunks) — alias: `nist-iso42001`
- `9138e0ea-c3fb-4b85-95d8-893a81726449` — Singapore GenAI Governance Framework 2024 (no_llm, 73 chunks) — alias: `sg-genai`

## Demo Gap Analysis (pre-calibrated, cached)

**Primary demo — HKMA Consumer Protection vs Codex Argentum v1.0:**
- circular_doc_id: `7f247634-cdcb-455a-bd02-7083feb1ed6e`
- baseline_id: `ef3d9bff-a442-443f-97ca-9fc7d0108618`
- is_policy_baseline: false
- Result: 1 Full, 5 Partial, 2 Gap — paragraph-level reasoning + provenance citations

**Second baseline (credibility test — doc you didn't write):**
- baseline_id: `b55c5916-28ae-449b-bd61-54dea2bbbcc1` (NIST AI RMF)
- Run same HKMA circular against it to show tool works on external text

**Note:** Cache is in-memory on Railway. Pre-run before demo day if service has restarted.

## Demo

See `DEMO_SCRIPT.md`. Gap analysis demo button uses Consumer Protection vs Financial Services guidance (Claude Sonnet 4 via OpenRouter).
