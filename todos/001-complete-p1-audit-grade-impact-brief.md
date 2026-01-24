---
status: complete
priority: p1
issue_id: "001"
tags: [fastapi, llm, compliance, auditability]
dependencies: []
---

# Audit-grade change impact brief

## Problem Statement
RegAtlas impact summaries are not audit-grade. We need a backend-first, evidence-dense impact brief with claim-level citations for demos and integrations.

## Findings
- Existing endpoint `/changes/{change_id}/ai-suggest` returns a short summary without structured citations.
- Evidence snippets exist on requirements via `_attach_evidence` and evidence APIs.

## Proposed Solutions
1) **New endpoint** `/changes/{id}/impact-brief` that returns a structured brief with claims + citations.
   - Pros: clean separation, no breaking changes.
   - Cons: additional endpoint to maintain.
2) **Extend `/ai-suggest`** to include the brief structure.
   - Pros: fewer endpoints.
   - Cons: risk breaking consumers and muddling responsibilities.

## Recommended Action
Implement a new endpoint `/changes/{id}/impact-brief` that generates a structured brief on-demand with strict citation density and deterministic fallback when LLM is unavailable.

## Acceptance Criteria
- [ ] New endpoint returns impact brief for a change ID.
- [ ] Every claim includes at least one citation or explicit “no evidence found”.
- [ ] Schema validation flags claims without citations.
- [ ] LLM-disabled mode returns deterministic brief with limitations.

## Work Log
### 2026-01-24 - Created todo

**By:** Codex

**Actions:**
- Created todo for implementing audit-grade impact brief.

**Learnings:**
- Keep v1 on-demand and citation-dense; defer persistence.

### 2026-01-24 - Implemented impact brief endpoint

**By:** Codex

**Actions:**
- Added `/changes/{change_id}/impact-brief` endpoint with claim-level citations.
- Added deterministic fallback and validation with evidence coverage ratio.
- Updated README API docs and e2e test.
- Ran `PYTHONPATH=/Users/terry/reg-atlas pytest tests/e2e_reg_atlas.py -q`.

**Learnings:**
- LLM output parsing needs a JSON-extraction fallback for robustness.
