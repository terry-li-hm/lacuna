---
date: 2026-01-24
topic: reg-atlas-llm-wow
---

# RegAtlas LLM Wow Features

## What We're Building
A backend-first LLM capability that generates an audit-grade “Regulatory Change Impact Brief.” It takes a new change item (source document + extracted requirements) and produces an executive narrative with dense citations for every claim. The brief is designed to be defensible in front of audit/compliance: each statement is linked to evidence snippets from the source text and existing requirement IDs. The output is optimized for rapid demo and integration (API/CLI), not UI, and should feel like an expert compliance analyst wrote it with full traceability.

## Why This Approach
Auditability is the primary “wow” for a Capco audience. A polished narrative is impressive, but trust hinges on traceable evidence and explainable reasoning. This approach maximizes perceived credibility, reduces hallucination risk, and gives a clean demo moment: “Every sentence is sourced.” It also aligns with RegAtlas’s existing evidence and requirement registry without needing new front-end work. More advanced cross-jurisdiction mapping can layer on later.

## Key Decisions
- **Primary output is an executive narrative with strict citations.** This keeps the first release sharp and demo-ready.
- **Backend-first delivery.** Focus on API/CLI responses that can be showcased in workflows or integrations.
- **Evidence-dense output.** Every key claim must link to source snippets and requirement IDs.
- **Minimal scope for v1.** Avoid building full control mapping or workflow automation until impact briefs are proven.

## Open Questions
- What is the target output schema (pure text vs. structured JSON with sections)?
- Should confidence scoring be included per claim, and how should it be computed?
- How to handle conflicting or ambiguous requirements across sources?
- What evaluation criteria define “audit-grade” for Capco stakeholders?

## Next Steps
→ `/workflows:plan` for implementation details
