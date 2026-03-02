---
title: "feat: lacuna — demo gap analysis CLI"
type: feat
status: active
date: 2026-03-02
---

# lacuna — Regulatory Gap Analysis Demo CLI

Single-file Python CLI (`uv run --script`) that wraps the Meridian Railway API for live demos. Polished Rich terminal output, short name aliases for doc IDs, four focused commands.

## Context

- **Backend:** `https://meridian-production-1bdb.up.railway.app` (FastAPI, no auth)
- **Existing CLI:** `~/code/reg-atlas/cli/` — Typer + httpx, correct API patterns but stale URL and plain output. Borrow client patterns; don't extend.
- **Demo pair (pre-cached):** `hkma-cp` vs `demo-baseline` → 1 Full / 5 Partial / 2 Gap

## File Location

```
~/bin/lacuna          ← uv run --script, executable, on PATH
```

Single file. No package structure needed for a demo tool.

## Script Header

```python
#!/usr/bin/env -S uv run --script --python 3.13
# /// script
# requires-python = ">=3.13"
# dependencies = ["httpx", "rich", "typer"]
# ///
```

## Commands

### `lacuna docs`
Lists all documents from `GET /documents`.

Output: Rich table — Name | Jurisdiction | Chunks | Requirements | ID (short)

```
┌─────────────────────────────────────┬──────────────┬────────┬──────┬──────────┐
│ Document                            │ Jurisdiction │ Chunks │ Reqs │ ID       │
├─────────────────────────────────────┼──────────────┼────────┼──────┼──────────┤
│ HKMA Consumer Protection 2024       │ Hong Kong    │ 42     │ 8    │ 7f247634 │
│ Meridian Demo Baseline (Capco)      │ —            │ 23     │ 17   │ ef3d9bff │
│ NIST AI RMF 1.0                     │ —            │ 131    │ —    │ b55c5916 │
└─────────────────────────────────────┴──────────────┴────────┴──────┴──────────┘
```

### `lacuna gap --circular <name_or_id> --baseline <name_or_id>`

POSTs to `/gap-analysis`. Resolves short names to UUIDs via alias map.

Output:
1. Summary panel: `Full: 1  Partial: 5  Gap: 2`
2. Findings table — one row per requirement, colour-coded status
3. On `--verbose`: expands reasoning + provenance text per finding

Status colours: `Full` → green, `Partial` → yellow, `Gap` → red

```
┌─────────────────────────────────────────────────────────────────┐
│  Gap Analysis: hkma-cp  ▶  demo-baseline                        │
│  Full: 1   Partial: 5   Gap: 2                                  │
└─────────────────────────────────────────────────────────────────┘

  ● Full      Transparency/disclosure — baseline covers this clearly
  ◑ Partial   Customer opt-out — baseline has escalation pathway but
              lacks HKMA's specific opt-out at customer's discretion
  ◑ Partial   PDPO compliance — addressed but not explicit
  ○ Gap       BDAI Guiding Principles — not referenced in baseline
  ○ Gap       Proactive consumer protection — no equivalent control
```

### `lacuna query "<question>" [--jurisdiction hk|sg|eu|uk]`

POSTs to `/query`. Jurisdiction map: `hk` → `Hong Kong`, `sg` → `Singapore`, `eu` → `European Union`, `uk` → `United Kingdom`.

Output:
1. LLM summary in a panel
2. Sources: filename + chunk excerpt (truncated to 120 chars)

### `lacuna warmup`

Runs the demo gap analysis pair to pre-warm the in-memory cache on Railway. Prints confirmation with timing.

```bash
lacuna warmup
# → Warming up gap analysis cache...
# → hkma-cp × demo-baseline  ✓  (28.4s)
# → Cache is hot. Demo ready.
```

## Doc Aliases

Hardcoded map in the script — no config file needed for a demo tool:

```python
ALIASES = {
    "hkma-cp":       "7f247634-cdcb-455a-bd02-7083feb1ed6e",
    "hkma-gai":      "a4d64616-...",
    "hkma-sandbox":  "eccf4ae5-...",
    "hkma-spm":      "dc5333c9-...",
    "eu-ai-act":     "ebcc1f4b-...",
    "fca":           "4fdb030f-...",
    "mas-consult":   "c071bf07-...",
    "mas-mrmf":      "36c7686e-...",
    "demo-baseline": "ef3d9bff-a442-443f-97ca-9fc7d0108618",
    "nist-rmf":      "b55c5916-28ae-449b-bd61-54dea2bbbcc1",
}
```

`resolve(name)` → checks ALIASES, falls back to treating input as raw UUID.

## API Client

Thin `httpx` wrapper, no class needed at this scale:

```python
BASE_URL = os.getenv("LACUNA_API_URL", "https://meridian-production-1bdb.up.railway.app")

def api_get(path, **params): ...
def api_post(path, payload): ...
```

Timeout: 120s (gap analysis can take 30s+ on cold cache).

## Acceptance Criteria

- [ ] `lacuna docs` prints a Rich table of all documents with short IDs
- [ ] `lacuna gap --circular hkma-cp --baseline demo-baseline` returns the 1/5/2 split with colour-coded findings
- [ ] `lacuna gap --circular hkma-cp --baseline demo-baseline --verbose` shows full reasoning + provenance per finding
- [ ] `lacuna query "What are HKMA's GenAI consumer protection requirements?" --jurisdiction hk` returns summary + sources
- [ ] `lacuna warmup` hits the demo pair and confirms cache is hot
- [ ] Short name aliases resolve correctly; raw UUIDs also accepted
- [ ] Script runs via `uv run --script` with no pre-installed deps
- [ ] `chmod +x ~/bin/lacuna` — invocable as `lacuna` from PATH

## Non-Goals

- No upload, no document management — that's the Meridian web UI
- No config file — aliases are hardcoded, URL via env var only
- No tests — demo tool, not production code

## Implementation Notes

- Reference `~/code/reg-atlas/cli/api/client.py` for exact payload shapes (especially `gap_analysis()` lines 100–116)
- `is_policy_baseline: false` always — uploaded docs are in doc_repo, not policy_repo
- Gap analysis timeout: use `httpx.Timeout(120.0)` — Railway can be slow on cold start
- Rich `Console`, `Table`, `Panel`, `Markdown` from `rich` library
- Typer for CLI — `app = typer.Typer(no_args_is_help=True)`

## Full Doc IDs (for alias map)

From `~/code/reg-atlas/CLAUDE.md`:
- `a4d64616` — need full UUID (partial only in CLAUDE.md — fetch from `/documents` at first run or hardcode short prefix)
- All others: full UUIDs available in CLAUDE.md

## Sources

- API shapes: `~/code/reg-atlas/backend/models/schemas.py`
- Existing client: `~/code/reg-atlas/cli/api/client.py`
- Doc IDs: `~/code/reg-atlas/CLAUDE.md`
- uv script pattern: `MEMORY.md` — `#!/usr/bin/env -S uv run --script`, must include `--python 3.13`
