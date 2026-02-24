# Meridian — Project Reference

## Deployment

- **Railway project:** `c2b227f0-f4de-43b8-b6b7-f5ebdd6b90ea`
- **Railway service:** `9c410474-b16e-4aa6-a8a7-d2e00d7ab79d`
- **URL:** https://meridian-production-1bdb.up.railway.app
- **Volume:** mounted at `/app/data` (persists DuckDB + ChromaDB + JSON stores)
- **Deploy:** `railway up --detach` (not GitHub auto-deploy)

## Package Names

- PyPI / npm / crates.io: `meridian-reg`

## Gotchas

- **OpenRouter model IDs don't use date suffixes.** `anthropic/claude-sonnet-4` not `anthropic/claude-sonnet-4-20250514`. Cost us all-Gap results in gap analysis until fixed.
- **Railway volumes mount as root.** Dockerfile CMD does `chown -R appuser:appuser /app/data` at runtime before dropping to appuser via `runuser`.
- **Large PDF uploads block the event loop.** Sync OpenAI calls freeze uvicorn. Upload big docs with `no_llm=true` and accept missing requirements, or fix with `asyncio.to_thread()` (not yet done).
- **Railway has a 5-min HTTP timeout.** Large doc LLM extraction can exceed this — server finishes but client times out.

## Corpus

8 docs, 4 jurisdictions (HK, SG, EU, UK), 1390 chunks, 341+ requirements. EU AI Act and FCA uploaded with `no_llm` (chunks but no extracted requirements).

## Key Doc IDs (current deployment)

- `7f247634` — HKMA Consumer Protection 2024 (8 reqs)
- `a4d64616` — HKMA GenAI Financial Services 2024 (132 reqs)
- `eccf4ae5` — HKMA Sandbox Arrangement (9 reqs)
- `dc5333c9` — HKMA SPM CA-G-1 (1 req)
- `ebcc1f4b` — EU AI Act (no_llm)
- FCA AI Update (no_llm)
- 2x MAS docs

## Demo

See `DEMO_SCRIPT.md`. Gap analysis demo button uses Consumer Protection vs Financial Services guidance (Claude Sonnet 4 via OpenRouter).
