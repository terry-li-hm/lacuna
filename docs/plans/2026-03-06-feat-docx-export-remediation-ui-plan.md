---
title: "feat: DOCX Export + Remediation Tracker UI/CLI"
type: feat
status: active
date: 2026-03-06
---

# feat: DOCX Export + Remediation Tracker UI/CLI

## Overview

Wave 4 — runs after wave 1 (upload + PDF) merges. Two parallel tasks:

### Task A: DOCX Export

Word document export of gap analysis — the editable format compliance teams use for policy amendment work. Extends the PDF export backend with a `POST /gap-analysis/export-docx` endpoint and adds `--format docx` to `lacuna export`.

**Design:**
- `python-docx` generates a `.docx` with: title page (Capco branding via heading styles), summary table, findings as styled sections (Heading 2 per requirement, body text for reasoning, blockquote for baseline match)
- New endpoint: `POST /gap-analysis/export-docx` — same payload as `/gap-analysis/export`, returns `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- CLI: `lacuna export --circular <> --baseline <> --format docx --output report.docx`
- UI: "Export Word" button alongside "Export PDF"
- Add `python-docx` to `pyproject.toml`

### Task B: Remediation Tracker UI + CLI

Surfaces the existing `POST /requirements/id/{req_id}/review` annotation API in the frontend and CLI.

**Frontend additions to `index.html`:**
- After gap analysis runs, each finding row gets a status dropdown: Open → In Progress → Addressed → Not Applicable
- Owner text field + notes textarea (inline expand on row click)
- "Save" button per row fires `POST /requirements/id/{circular_req_id}/review`
- Summary bar above findings: progress ring showing X/N requirements addressed

**CLI: `lacuna annotate` command:**
```
lacuna annotate --req-id <circular_req_id> --status addressed --owner "Compliance Team" --notes "Covered by §4.2"
```

## Acceptance Criteria

### DOCX Export
- [ ] `lacuna export --format docx` produces a valid .docx file
- [ ] .docx has title page, summary table, findings sections
- [ ] "Export Word" button downloads .docx from UI
- [ ] `python-docx` added to pyproject.toml

### Remediation Tracker
- [ ] Each gap finding row in UI has status dropdown + owner field
- [ ] Status changes persist via `POST /requirements/id/{req_id}/review`
- [ ] `lacuna annotate --req-id <> --status <> --owner <> --notes <>` works
- [ ] Summary bar shows X/N addressed count
- [ ] Status persists across page reload (re-fetched from requirements API)

## Files to Touch

**Task A (DOCX):**
- `backend/routes/gap_analysis.py` — add `/export-docx` route
- `pyproject.toml` — add `python-docx`
- `~/bin/lacuna` — add `--format docx` to export command
- `frontend/index.html` — add Export Word button

**Task B (Remediation UI):**
- `frontend/index.html` — annotation UX in gap findings table
- `~/bin/lacuna` — add `annotate` command

## Gate

Dispatch only after `feat/custom-baseline-upload` and `feat/pdf-export` branches are merged.
