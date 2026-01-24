---
module: Development Workflow
date: 2026-01-24
problem_type: best_practice
component: tooling
symptoms:
  - "Impact summaries lacked claim-level citations"
  - "No audit-grade impact brief endpoint for change items"
root_cause: missing_tooling
resolution_type: code_fix
severity: medium
tags: [audit-grade, impact-brief, citations, llm]
---

# Troubleshooting: Missing audit-grade impact brief endpoint

## Problem
RegAtlas could generate short impact summaries, but they were not audit-grade and had no claim-level citations. There was no endpoint to produce a defensible impact brief for change items.

## Environment
- Module: Development Workflow
- Rails Version: N/A (FastAPI)
- Affected Component: Backend API tooling
- Date: 2026-01-24

## Symptoms
- Impact summaries lacked claim-level citations.
- No audit-grade impact brief endpoint for change items.

## What Didn't Work

**Direct solution:** The problem was identified and fixed on the first attempt.

## Solution

Add a dedicated endpoint `/changes/{change_id}/impact-brief` that returns a structured impact brief with claim-level citations, deterministic fallback, and validation.

**Code changes** (excerpt):
```python
# backend/main.py
@app.post("/changes/{change_id}/impact-brief")
async def generate_change_impact_brief(change_id: str, request: ChangeImpactBriefRequest):
    """Generate an audit-grade impact brief with claim-level citations."""
    change = change_db.get(change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    results = vector_store.query(query_text=query_text, n_results=request.n_results)
    matched_requirements = _collect_matched_requirements(results)
    requirements_context = _requirements_context(matched_requirements, max_items=request.max_claims_per_section)

    if use_llm and requirements_context:
        payload = _extract_json_payload(raw) or {}
        summary_claims = payload.get("summary", [])

    if not summary_claims:
        summary_claims = _deterministic_claims(change, matched_requirements, max_claims=request.max_claims_per_section)

    validated = _validate_claims(summary_claims, max_citations=request.max_citations)
    validation = _claim_validation_summary(validated)

    return {"brief": {"summary": validated}, "validation": validation}
```

**Commands run**:
```bash
PYTHONPATH=/Users/terry/reg-atlas pytest tests/e2e_reg_atlas.py -q
```

## Why This Works
The root cause was missing tooling for audit-grade outputs. The new endpoint enforces a structured schema with claim-level citations and validates coverage before returning results. Deterministic fallback ensures the brief still renders when LLMs are disabled, while evidence coverage metrics make auditability measurable.

## Prevention
- Define auditability requirements (claim-level citations) as part of the API contract.
- Always include schema validation for LLM outputs.
- Add an e2e test that asserts the brief structure and citation coverage.

## Related Issues
No related issues documented yet.
