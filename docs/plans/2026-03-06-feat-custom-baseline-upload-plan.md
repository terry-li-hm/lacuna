---
title: "feat: Custom Baseline Upload (CLI + UI)"
type: feat
status: active
date: 2026-03-06
origin: docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md
---

# feat: Custom Baseline Upload (CLI + UI)

## Overview

Allow a client's own policy document to be uploaded as a gap analysis baseline — the core unlock for taking Lacuna from an illustrative demo to a live consulting tool. The `/upload` backend endpoint already exists; this feature adds a `lacuna upload` CLI command and a drag-and-drop UI card, plus makes the baseline dropdown dynamic.

(see brainstorm: docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md — "the tool becomes genuinely useful the moment it handles the client's own messy internal language")

## Proposed Solution

Three coordinated changes:

1. **`lacuna upload` CLI command** — wraps `POST /upload` with `jurisdiction=ILLUSTRATIVE`, handles PDF/TXT/DOCX, marks the doc as a baseline in the alias table (local only).
2. **UI drag-and-drop upload card** — new section in `frontend/index.html` above the Gap Analysis card. Shows progress, then updates the baseline dropdown dynamically.
3. **Dynamic baseline dropdown** — baseline selector in the gap analysis form fetches from `GET /documents` on page load instead of using hardcoded values. Filters to docs with requirements count > 0 (or jurisdiction = ILLUSTRATIVE).

## Technical Considerations

- **Backend:** No new endpoint needed. `POST /upload` already accepts `UploadFile` + `jurisdiction` query param. Use `jurisdiction=ILLUSTRATIVE` for client baselines to distinguish them from regulatory circulars.
- **DOCX support:** `python-docx` extracts plain text before passing to the existing processor. Add to `pyproject.toml` dependencies.
- **Large doc timeout:** Railway has a 5-min HTTP timeout. The existing 600s curl pattern in CLAUDE.md documents the workaround — CLI should use a 600s timeout for upload. UI should show a "Processing (this may take 2-3 minutes)..." spinner.
- **Dynamic dropdown:** `GET /documents` returns all docs. Filter on the frontend: show docs with `jurisdiction == "ILLUSTRATIVE"` (or any non-regulatory jurisdiction) in the baseline dropdown. Regulatory docs appear in the circular dropdown.
- **Persistence:** Railway volume at `/app/data` persists across restarts. Uploaded baselines survive service restarts like all other docs.

## System-Wide Impact

- **Interaction graph:** `lacuna upload` → `POST /upload` → `document_service.upload_document()` → requirement extraction (LLM) → ChromaDB chunks + DuckDB metadata. Same path as existing uploads.
- **State lifecycle:** If LLM extraction times out (Railway 5-min limit), document is partially processed — chunks exist but `requirements` is empty. Gap analysis on an empty-requirements baseline returns all Gap results. UI should warn if requirements count = 0.
- **API surface parity:** `lacuna upload` + UI both call the same endpoint. CLI should print the returned `doc_id` so it can be used in subsequent `lacuna gap` commands.

## Acceptance Criteria

- [ ] `lacuna upload --file <path> --name "Client AI Standard"` uploads the document and prints the `doc_id`
- [ ] Supported formats: `.pdf`, `.txt`, `.docx`
- [ ] Upload uses 600s timeout to survive LLM extraction
- [ ] UI upload card accepts drag-and-drop and click-to-browse
- [ ] UI shows a progress spinner during processing
- [ ] UI shows an error message if upload fails (413, 500, timeout)
- [ ] Baseline dropdown in gap analysis form is populated from `GET /documents` (dynamic, not hardcoded)
- [ ] Docs with `jurisdiction=ILLUSTRATIVE` appear in the baseline dropdown
- [ ] Uploaded doc with 0 requirements shows a warning badge in the dropdown ("⚠ No requirements extracted")
- [ ] `lacuna docs` table shows uploaded client docs with their display name

## Files to Touch

- `~/bin/lacuna` — add `upload` command
- `frontend/index.html` — add upload card, make baseline dropdown dynamic
- `pyproject.toml` — add `python-docx` dependency
- `backend/routes/documents.py` — no changes needed (reuse existing `/upload`)
- `backend/config.py` — no changes needed

## Dependencies & Risks

- **python-docx:** New dependency. Lightweight, pure Python, no system deps.
- **Railway timeout:** LLM extraction for large PDFs (50+ pages) can exceed 5 min. Mitigation: warn in UI, allow `no_llm=true` fallback via a checkbox ("Upload without requirement extraction").
- **Duplicate detection:** Existing endpoint returns 409 on duplicate content hash. CLI should print a helpful message: "Document already exists (doc_id=...)".

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md](docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md) — decision: CLI pre-load + UI live moment; jurisdiction=ILLUSTRATIVE for client docs
- Upload endpoint: `backend/routes/documents.py:17` — `POST /upload`
- Document service: `backend/services/document_service.py`
- Config: `backend/config.py` — `max_upload_mb = 20`
- Re-upload workflow: `CLAUDE.md` — 600s timeout pattern
