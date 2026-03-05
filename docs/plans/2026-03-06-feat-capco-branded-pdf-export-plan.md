---
title: "feat: Capco-Branded PDF Export"
type: feat
status: active
date: 2026-03-06
origin: docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md
---

# feat: Capco-Branded PDF Export

## Overview

Generate a polished, Capco-branded PDF report from a gap analysis — the compliance committee deliverable. Extends the existing `lacuna export` CLI command (markdown output) with a `--format pdf` flag, and adds an "Export PDF" button to the frontend gap analysis results view.

(see brainstorm: docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md — "server-side via WeasyPrint, Capco brand colours, cover page")

## Proposed Solution

1. **New backend endpoint `POST /gap-analysis/export`** — accepts same payload as `/gap-analysis`, runs the analysis (or hits cache), renders a WeasyPrint HTML template to PDF, returns the PDF blob as `application/pdf`.
2. **HTML/CSS template** — Capco brand colours, cover page with circular + baseline name + date, summary table, findings sections with colour-coded status badges, provenance in footnotes.
3. **CLI update** — `lacuna export --circular <> --baseline <> --format pdf --output report.pdf` calls the new endpoint and streams to file.
4. **UI button** — "Export PDF" appears in the gap analysis results panel after a successful run. Triggers the export endpoint and downloads.

## Technical Considerations

- **WeasyPrint:** Renders HTML+CSS to PDF. Pure Python, good table support, no headless browser needed. Add to `pyproject.toml`. Requires `libpango` system package — add to Dockerfile.
- **Template design:**
  - Cover: Capco wordmark (SVG inline), dark background (`#1D2329`), coral accent (`#E04E39`), white text. Circular name, baseline name, date, "Confidential — Prepared by Capco".
  - Summary: 3-cell coloured table — Full (green), Partial (amber), Gap (red).
  - Findings: One section per requirement. Status badge, description, reasoning paragraph, baseline match text (if any), provenance citations in smaller type.
  - Footer: Page numbers, "Lacuna | Capco AI Regulatory Practice".
- **Async:** WeasyPrint is synchronous. Wrap in `asyncio.to_thread()` to avoid blocking uvicorn (same pattern recommended in CLAUDE.md for future fixes).
- **Cache reuse:** Export endpoint checks the same `_gap_cache` dict in `gap_analysis.py` — no double LLM call if the pair was already run.
- **PDF size:** Typically 200-500KB for a standard gap analysis. No streaming needed — return as bytes response.

## System-Wide Impact

- **Interaction graph:** `POST /gap-analysis/export` → cache check → (if miss) `service.perform_gap_analysis()` → WeasyPrint render → PDF bytes response. No new state mutation.
- **Dockerfile change:** `RUN apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2` needed for WeasyPrint. Without this, WeasyPrint import fails at startup.
- **Railway build:** Adding libpango increases image size ~15MB. Acceptable.
- **Error handling:** If gap analysis returns 0 findings (e.g., no_llm baseline), PDF renders with an empty findings section — valid output, not an error.

## Acceptance Criteria

- [ ] `lacuna export --circular hkma-cp --baseline demo-baseline --format pdf --output report.pdf` produces a valid PDF
- [ ] PDF has Capco branding: dark cover page with wordmark, coral accents
- [ ] Cover page shows: circular name, baseline name, generated date, "Confidential — Prepared by Capco"
- [ ] Summary section shows Full/Partial/Gap counts with colour coding
- [ ] Each finding has: status badge, description, reasoning, baseline match (if present)
- [ ] Provenance citations appear for findings that have them
- [ ] Footer has page numbers and "Lacuna | Capco AI Regulatory Practice"
- [ ] UI "Export PDF" button appears after a gap analysis run and downloads the file
- [ ] Existing `lacuna export` (markdown, no `--format` flag) is unchanged
- [ ] WeasyPrint render runs in `asyncio.to_thread()` — doesn't block other requests
- [ ] Dockerfile includes `libpango` system packages

## Files to Touch

- `~/bin/lacuna` — add `--format pdf` option to `export` command
- `backend/routes/gap_analysis.py` — add `POST /gap-analysis/export` route
- `backend/templates/gap_report.html` — new WeasyPrint HTML template (create dir)
- `pyproject.toml` — add `weasyprint` dependency
- `Dockerfile` — add `libpango` apt packages
- `frontend/index.html` — add "Export PDF" button to gap analysis results section

## Dependencies & Risks

- **WeasyPrint system deps:** `libpango` must be in Dockerfile. If missed, Railway build fails at import. Verify locally first: `python -c "import weasyprint"`.
- **Capco logo:** No official logo asset available — use Capco wordmark as styled text (`font-family: sans-serif; font-weight: 700; letter-spacing: -0.5px`) or a simple SVG placeholder. Update when real asset is provided.
- **CSS print support:** WeasyPrint supports a subset of CSS. Avoid flexbox in headers (use table layout). Test with the actual findings HTML before delivery.
- **Confidentiality:** Template should always include "Confidential — Prepared by Capco" on cover. This is a consulting deliverable, not a public report.

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md](docs/brainstorms/2026-03-06-lacuna-commercialisation-brainstorm.md) — decision: WeasyPrint, Capco brand, server-side generation
- Gap analysis route: `backend/routes/gap_analysis.py` — cache pattern to reuse
- Gap analysis schema: `backend/models/schemas.py:84` — `GapRequirementMapping`, `GapAnalysisResponse`
- CLAUDE.md gotcha: "Large PDF uploads block the event loop — use asyncio.to_thread()"
- Dockerfile: `Dockerfile` — existing apt-get pattern to follow
