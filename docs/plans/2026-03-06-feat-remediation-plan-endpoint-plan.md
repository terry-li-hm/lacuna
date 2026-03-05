---
title: "feat: Remediation Plan Endpoint"
type: feat
status: active
date: 2026-03-06
---

# feat: Remediation Plan Endpoint

## Overview

Add `GET /remediation/plan` — enriches a gap analysis result with each finding's current annotation status (from the existing requirements review system), producing a live remediation action plan. This closes the loop from "here are your gaps" to "here's who owns them and what's the status."

The annotation backend already exists (`POST /requirements/id/{req_id}/review`). This endpoint is the read side: join gap findings with their annotations and return a unified view.

## Proposed Solution

New file `backend/routes/remediation.py` with:

```
GET /remediation/plan?circular_doc_id=<id>&baseline_id=<id>
```

- Hits the gap analysis cache (same `_gap_cache` dict via a shared import); if miss, calls `gap_analysis_service.perform_gap_analysis()` directly
- For each finding's `circular_req_id`, fetches annotation from `requirement_service.get_requirement(circular_req_id)`
- Returns enriched findings: gap status + annotation status, owner, notes, tags
- Groups into buckets: `unaddressed` (Gap + no annotation), `in_progress`, `addressed`, `not_applicable`
- Summary: counts per bucket, % remediation complete

## New route to register in main.py

Add `remediation_router` to `backend/routes/__init__.py` and `backend/main.py`.

## Acceptance Criteria

- [ ] `GET /remediation/plan?circular_doc_id=X&baseline_id=Y` returns enriched findings
- [ ] Each finding includes: gap `status`, `reasoning`, annotation `review_status`, `reviewer`, `review_notes`
- [ ] Response includes summary: `unaddressed`, `in_progress`, `addressed`, `not_applicable` counts
- [ ] Returns 200 with empty annotations if no reviews have been added yet
- [ ] Reuses existing gap cache — no double LLM call

## Files to Touch

- `backend/routes/remediation.py` — new file
- `backend/routes/__init__.py` — export new router
- `backend/main.py` — register router

## Sources

- Existing review endpoint: `backend/routes/requirements.py:92`
- Gap analysis cache: `backend/routes/gap_analysis.py:19` — `_gap_cache` dict
- Schemas: `backend/models/schemas.py` — `GapRequirementMapping`, `GapAnalysisResponse`
