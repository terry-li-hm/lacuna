---
title: "feat: Per-Client API Key Authentication"
type: feat
status: active
date: 2026-03-06
origin: docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md
---

# feat: Per-Client API Key Authentication

## Overview

Add `X-API-Key` header authentication to all Lacuna API routes, so the public Railway URL is no longer accessible without a key. One key per engagement — revoke by removing from config. No user accounts, no login UI.

(see brainstorm: docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md — "one key per engagement, revoke when the project ends, zero UI overhead")

## Proposed Solution

1. **FastAPI middleware** — checks `X-API-Key` header on all non-frontend routes. Returns 401 if missing or invalid. Bypasses check if no keys are configured (allows local dev without auth).
2. **Config field** — add `lacuna_api_keys: list[str]` to `Settings` via a comma-separated env var `LACUNA_API_KEYS=key1,key2,key3`.
3. **CLI passthrough** — CLI reads `LACUNA_API_KEY` env var, adds as `X-API-Key` header to all httpx calls.
4. **Frontend settings panel** — small gear icon → modal to enter API key. Stored in `localStorage`. Injected into all `fetch()` calls as `X-API-Key` header.
5. **CORS fix** — update `allow_origins` to include `https://lacuna.sh` (currently hardcoded to the old meridian URL).

## Technical Considerations

- **Middleware vs dependency:** Use FastAPI middleware (not a per-route `Depends`) so auth applies to all routes including future ones without per-route annotation. Add exclusion for `GET /` (frontend HTML) and `GET /health`.
- **Key format:** 32-char random hex strings (`secrets.token_hex(16)`). Generate with: `python3 -c "import secrets; print(secrets.token_hex(16))"`.
- **Timing-safe comparison:** Use `hmac.compare_digest()` to compare submitted key against valid keys — prevents timing attacks.
- **Bypass when unconfigured:** If `LACUNA_API_KEYS` is unset or empty, middleware skips the check. This allows `lacuna preflight` and local dev to work without a key. Add a warning log on startup if no keys are set.
- **CORS:** Current `allow_origins` list contains the old meridian URL. Fix to include `https://lacuna.sh` and `http://localhost:8000`. Consider `allow_origins=["*"]` for demo flexibility (auth is the real gate, not CORS).

## System-Wide Impact

- **Interaction graph:** All API requests pass through middleware → key check → route handler. Frontend `fetch()` calls need the header; without it they get 401 and the UI breaks silently. UI must handle 401 gracefully (redirect to settings modal).
- **`lacuna preflight`:** CLI must pick up `LACUNA_API_KEY` before preflight, or preflight will fail with 401. Add a note to the lacuna skill.
- **`lacuna warmup`:** Same — must have key in env.
- **State lifecycle:** No state changes. Middleware is pure read/reject.
- **API surface parity:** Every existing CLI command (`gap`, `query`, `docs`, `chat`, `warmup`, `preflight`, `export`, `upload`) needs the header added. All go through httpx — add header to the shared client construction, not per-command.

## Acceptance Criteria

- [ ] All `POST`, `GET` (non-frontend), `DELETE` routes return 401 without a valid `X-API-Key` header
- [ ] `GET /` (frontend) and `GET /health` return normally without auth
- [ ] Valid key in `X-API-Key` header allows access
- [ ] Invalid/missing key returns `{"detail": "Invalid or missing API key"}` with 401
- [ ] `LACUNA_API_KEYS=key1,key2` env var configures multiple valid keys
- [ ] When `LACUNA_API_KEYS` is unset, auth is bypassed with a startup warning log
- [ ] `LACUNA_API_KEY=<key> lacuna gap --circular hkma-cp --baseline demo-baseline` works
- [ ] All CLI commands pass the key header automatically when `LACUNA_API_KEY` is set
- [ ] Frontend settings panel (gear icon) allows entering and saving the API key to localStorage
- [ ] Frontend `fetch()` calls include `X-API-Key` from localStorage
- [ ] Frontend shows "Authentication required — check settings" on 401 response
- [ ] `allow_origins` updated to include `https://lacuna.sh`
- [ ] Key comparison uses `hmac.compare_digest()`

## Files to Touch

- `backend/main.py` — add auth middleware, fix CORS origins
- `backend/config.py` — add `lacuna_api_keys: list[str]` field
- `~/bin/lacuna` — read `LACUNA_API_KEY` env var, add to httpx client headers
- `frontend/index.html` — add settings panel/modal, inject key in fetch calls, handle 401

## Key Generation (for Railway deploy)

```bash
# Generate a new key for an engagement
python3 -c "import secrets; print(secrets.token_hex(16))"

# Set in Railway dashboard: LACUNA_API_KEYS=<generated-key>
# Share with client: LACUNA_API_KEY=<generated-key> lacuna preflight
```

## Dependencies & Risks

- **Breaking change:** Once deployed, all existing unauthenticated usage breaks. Deploy to Railway only when ready to share keys with active users. Until then, leave `LACUNA_API_KEYS` unset (bypass mode).
- **Key leakage:** If a key is shared with a client and forwarded elsewhere, revoke by removing from `LACUNA_API_KEYS` and redeploying. No session invalidation needed.
- **Frontend localStorage:** Not encrypted. Acceptable for a consulting tool — the key grants access to a demo environment, not production data.
- **`lacuna preflight` check:** Should add a check that `LACUNA_API_KEY` is set when `LACUNA_API_KEYS` is configured on the server. Currently preflight has no concept of auth.

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md](docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md) — decision: per-client API keys, no login UI, revocable per engagement
- FastAPI app: `backend/main.py` — existing middleware pattern (CORSMiddleware)
- Config: `backend/config.py` — pydantic-settings pattern for new env vars
- Python docs: `hmac.compare_digest` for timing-safe string comparison
