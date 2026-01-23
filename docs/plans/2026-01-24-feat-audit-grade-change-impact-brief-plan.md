---
title: feat: Audit-grade change impact brief
type: feat
date: 2026-01-24
---

# feat: Audit-grade change impact brief

## Enhancement Summary

**Deepened on:** 2026-01-24  
**Sections enhanced:** Overview, Problem Statement / Motivation, Proposed Solution, Technical Considerations, SpecFlow Analysis, Acceptance Criteria, Success Metrics, Dependencies & Risks, References & Research  
**Research sources used:** Perplexity web search (regulatory compliance LLM best practices and auditability), local codebase review

### Key Improvements
1) Explicit auditability guardrails (citation density, evidence provenance, schema enforcement).  
2) Structured output shape with claim-level citations and evidence metadata.  
3) Expanded edge cases and evaluation checklist for “audit-grade” validation.

### New Considerations Discovered
- Compliance outputs need explicit provenance and justification to be credible with stakeholders; this should be enforced at schema validation time.  
- LLM variance requires post-processing guardrails and clear fallback behavior when evidence is missing.

## Overview
Add a backend-first LLM capability that produces an audit-grade Regulatory Change Impact Brief for a change item. The brief is a narrative report with dense citations so every claim is traceable to evidence snippets and requirement IDs. The output is optimized for API/CLI consumption and demo credibility with Capco stakeholders.

### Research Insights

**Best Practices:**
- Treat auditability as a first-class output contract: every statement must carry provenance and evidence snippets.  
- Keep the brief in a structured schema so downstream systems can validate claim coverage before rendering.  

**Performance Considerations:**
- Cap the number of cited claims per section; prefer top-K requirement selection to control token cost and latency.  

**Edge Cases:**
- When evidence is missing, explicitly flag “insufficient evidence” rather than guessing.  

**References:**
- https://arxiv.org/html/2404.14356v1  
- https://www.riskinsightshub.com/2025/05/compliance-automation-with-llms.html  

## Problem Statement / Motivation
RegAtlas already drafts short impact summaries, but they are not audit-grade and lack strict citation density. For a Capco demo, the "wow" is a defensible, executive-ready brief where every statement is backed by evidence and traceability. This improves trust, reduces hallucination risk, and aligns with RegAtlas's audit trail positioning.

### Research Insights

**Best Practices:**
- LLM compliance outputs should include explicit justification for every conclusion and be reproducible from source snippets.  
- Stakeholders will trust outputs more when evidence is embedded alongside claims, not separated.  

**Edge Cases:**
- Mixed-source changes (e.g., multiple circulars) should preserve per-source citations to avoid ambiguity.  

**References:**
- https://arxiv.org/html/2404.14356v1  

## Proposed Solution
Introduce a new backend output that generates a structured impact brief with:
- A narrative summary section with citations per claim.
- A cited list of impacted requirements (ID + evidence snippet).
- Optional control/policy references when available.

This can be a new endpoint or an extension of the existing AI suggest endpoint, returning a structured payload (e.g., brief sections + claims + citations). The narrative can be assembled from the structured claims to guarantee evidence density.

### Research Insights

**Best Practices:**
- Generate a claims-first JSON payload, then assemble the narrative from those claims to guarantee citation density.  
- Include evidence metadata with each claim: `doc_id`, `requirement_id`, `chunk_id`, `evidence_text`, and optional `source_url`.  

**Implementation Details:**
```json
{
  "change_id": "uuid",
  "brief": {
    "summary": [
      {
        "claim": "The change affects liquidity reporting timelines.",
        "citations": [
          {
            "doc_id": "doc_123",
            "requirement_id": "req_456",
            "chunk_id": "chunk_789",
            "evidence_text": "Institutions must submit LCR reports within 10 business days..."
          }
        ]
      }
    ]
  }
}
```

**Edge Cases:**
- If no requirements match, return an empty claims list plus a summary stating that no evidence was found.  

## Technical Considerations
- **Existing AI impact summary**: `/changes/{change_id}/ai-suggest` currently generates a 2-4 sentence summary without citation structure (`backend/main.py:1289`).
- **Evidence availability**: requirements already carry evidence snippets via `_attach_evidence` and evidence endpoints exist for retrieval (`backend/main.py:1951`, `backend/main.py:1688`).
- **Output schema**: define a stable JSON schema to represent claims, citations, and requirement references for auditability.
- **LLM safety**: require every claim to include citations; fallback to deterministic summaries if LLM unavailable.
- **Performance**: cap number of requirements and citations per section to avoid token blowups.
- **Privacy**: avoid returning raw full documents; include only minimal evidence snippets.

### Research Insights

**Best Practices:**
- Enforce schema validation post-LLM to reject or mark any claim without citations.  
- Use retrieval constraints (top-K by similarity) to keep evidence focused and explainable.  
- Consider prompt injection resilience: ignore instructions from source text and treat evidence as read-only.  

**Performance Considerations:**
- Cache brief outputs for repeated requests to the same change ID.  
- Allow a `max_claims_per_section` parameter for predictable output size.  

**Edge Cases:**
- Evidence snippets containing sensitive data should be truncated or masked before returning.  

**References:**
- https://www.gurustartups.com/reports/cross-border-regulation-mapping-via-llms  

## SpecFlow Analysis (User Flow and Gaps)

### User Flow Overview
1) **API/CLI request** to generate an impact brief for a change ID.
2) **System fetches change item** and related requirements from vector search.
3) **LLM generates structured claims** with citations to evidence snippets.
4) **System returns** the impact brief payload (narrative + cited claims + requirement links).
5) **Consumer** (CLI, integration, or UI) renders the report or stores it.

### Flow Permutations Matrix
- **Change with no matched requirements**: should return a brief with a rationale and explicit "insufficient evidence" notes.
- **Change with matched requirements but no evidence**: should return claims with empty or flagged citations.
- **LLM disabled**: fallback to deterministic summary with clearly marked limitations.
- **Large requirement set**: apply top-K and truncation logic to preserve performance.

### Research Insights

**Best Practices:**
- Provide deterministic fallback messages for “no evidence” cases so auditors can differentiate model failure from data gaps.  

**Edge Cases:**
- Change items without jurisdiction or summary fields should still produce a brief with a warning section.  

### Missing Elements & Gaps
- **Error handling**: specify response when change ID is missing or evidence is absent.
- **Schema clarity**: define exact JSON fields for claims, citations, and narrative sections.
- **Evaluation**: define what "audit-grade" means (citation density, clarity, reproducibility).
- **Testability**: define how to validate schema compliance and citation coverage.

### Critical Questions Requiring Clarification
1) **Critical**: Should the brief be stored (persisted) or generated on demand only?
2) **Important**: Should each claim include a confidence score, and what source should drive it?
3) **Important**: What is the max number of requirements to include per brief section?
4) **Nice-to-have**: Should the brief support both narrative and checklist formats?

### Recommended Next Steps
- Confirm output schema and persistence behavior.
- Define evaluation checklist for audit-grade output.
- Decide how to mark low-evidence claims.
- Add test cases for schema validation and citation coverage.

## Acceptance Criteria
- [x] New API/CLI flow generates an impact brief for a change ID.
- [x] Every claim includes at least one evidence citation or explicitly states "no evidence found".
- [x] Output schema is documented and stable.
- [x] LLM-disabled mode produces a deterministic brief with clear limitations.
- [x] Report includes linked requirement IDs when available.
- [x] Schema validation rejects or flags any claim without citations.

### Research Insights

**Best Practices:**
- Add a schema validation step to assert citation density before returning the response.  
- Include an “evidence_coverage_ratio” field for QA and demo health checks.  

**Implementation Simplifications (YAGNI):**
- Defer caching and persistence of briefs in v1 unless required for demo.  
- Defer confidence scoring until evidence coverage is stable.  

## Success Metrics
- Demo readiness: Capco stakeholders accept the brief as audit-grade.
- Citation density: 100% of claims have citations or explicit evidence gaps.
- Latency: brief generation completes within an acceptable demo window (target < 10s for small sets).

### Research Insights

**Best Practices:**
- Track evidence coverage % and average citations per claim as internal KPIs.  
- Maintain a small regression set of changes to evaluate output consistency.  

## Dependencies & Risks
- **LLM output variance**: mitigate with strict schema and post-validation.
- **Evidence quality**: depends on upstream extraction and chunking; missing evidence weakens claims.
- **Token limits**: mitigate via top-K requirement selection and section caps.

### Research Insights

**Security Considerations:**
- Treat regulatory text as untrusted input; avoid prompt injection by isolating evidence in citations and instructing the model to ignore embedded directives.  
- Ensure evidence snippets do not leak sensitive data or PII.  

## References & Research
- Existing AI impact summary endpoint: `backend/main.py:1289`
- Evidence attachment: `backend/main.py:1951`
- Evidence upload and retrieval: `backend/main.py:1688`
- Product positioning (audit trail, GenAI assist): `docs/buyer-one-pager.md`
- Brainstorm context: `docs/brainstorms/2026-01-24-reg-atlas-llm-wow-brainstorm.md`
- External: https://arxiv.org/html/2404.14356v1
- External: https://www.riskinsightshub.com/2025/05/compliance-automation-with-llms.html
- External: https://www.gurustartups.com/reports/cross-border-regulation-mapping-via-llms
