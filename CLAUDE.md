# Lacuna — Project Reference

## Deployment

- **Railway project:** `56536e61-c258-4ea6-a074-531ecb57e36a`
- **Railway service:** `838bfe97-b9e3-4eb0-b1d5-2a3db86006b9`
- **URL:** https://lacuna-production-8dbb.up.railway.app
- **Volume:** mounted at `/app/data` (persists DuckDB + ChromaDB + JSON stores)
- **Deploy:** `railway up --detach` (not GitHub auto-deploy)

> Old project (meridian): `c2b227f0` — keep alive until lacuna.sh custom domain confirmed working.

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

- `86bcafef-0fbb-4e04-932b-75bd1d2c7b3f` — HKMA Consumer Protection 2024 (7 reqs) — alias: `hkma-cp`
- `b49334de-4f79-4dde-99ca-52c861b3351c` — HKMA GenAI Financial Services 2024 (130 reqs) — alias: `hkma-gai`
- `6abfcf50-d0ac-44c9-9608-b187cd683009` — HKMA Sandbox Arrangement (9 reqs) — alias: `hkma-sandbox`
- `ec614bf1-4962-4c77-b40b-e35461e8d54b` — HKMA SPM CA-G-1 (1 req) — alias: `hkma-spm`
- `4a8de9c2-027a-4799-af3a-afff5b72528f` — EU AI Act (no_llm) — alias: `eu-ai-act`
- `0b9af5df-3c6a-4b33-8ea5-741161122e17` — FCA AI Update (no_llm) — alias: `fca`
- `42af8c8b-ff0a-4431-a89f-320e0cfd7c04` — MAS AI Risk Management Consultation 2025 — alias: `mas-consult`
- `7aa4d4a2-d707-4508-82af-78958a36dc68` — MAS AI Model Risk Management 2024 — alias: `mas-mrmf`
- `3a1e50ec-5340-4c06-b92a-3600986bb9c7` — **Codex Argentum v1.0 (illustrative AI governance baseline, Capco-authored, no HSBC branding)** — alias: `demo-baseline`
- `bca67e5b-babe-4870-b0a1-e99e87e327a4` — NIST AI RMF 1.0 (no_llm, 131 chunks) — alias: `nist-rmf`
- `d9716356-d8f3-43b6-9e20-ce4ce0c32098` — NIST AI RMF → ISO 42001 Crosswalk (no_llm, 32 chunks) — alias: `nist-iso42001`
- `5b1a0507-c478-43d9-b911-c8a8fdb3d0e4` — Singapore GenAI Governance Framework 2024 (no_llm, 73 chunks) — alias: `sg-genai`

## Demo Gap Analysis (pre-calibrated, cached)

**Primary demo — HKMA Consumer Protection vs Codex Argentum v1.0:**
- circular_doc_id: `86bcafef-0fbb-4e04-932b-75bd1d2c7b3f`
- baseline_id: `3a1e50ec-5340-4c06-b92a-3600986bb9c7`
- is_policy_baseline: false
- Result: 0 Full, 3 Partial, 4 Gap — paragraph-level reasoning + provenance citations

**Second baseline (credibility test — doc you didn't write):**
- baseline_id: `bca67e5b-babe-4870-b0a1-e99e87e327a4` (NIST AI RMF)
- Run same HKMA circular against it to show tool works on external text

**Note:** Cache is in-memory on Railway. Pre-run before demo day if service has restarted.

## Demo

See `DEMO_SCRIPT.md`. Gap analysis demo button uses Consumer Protection vs Financial Services guidance (Claude Sonnet 4 via OpenRouter).
