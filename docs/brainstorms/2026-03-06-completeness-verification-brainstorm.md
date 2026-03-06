# Brainstorm: Completeness Verification Workflow

**Date:** 2026-03-06  
**Context:** Lacuna — pre-Tobin demo thinking  
**Author:** Terry + Claude

---

## What We're Building

A workflow that gives Tobin (HSBC AI Regulatory Management) confidence that no regulatory requirements were silently omitted during gap analysis. The core failure mode is **silent omission**: the LLM misses a requirement buried in the circular, and the gap report looks clean but has a hidden hole.

The completeness problem has two layers:
1. **Extraction completeness** — did we find all requirements in the circular?
2. **Assessment completeness** — did we correctly evaluate each one?

The primary concern is extraction. If the requirement list is wrong, everything downstream is untrustworthy.

---

## Why This Approach

Tobin is open to any level of engagement as long as the system is reliable. This means we don't need to optimise for minimum friction — we optimise for verifiability and trust. The right design separates the extraction step (tractable for human review) from the assessment step (tractable for LLMs), and puts the human at the accountability gate between them.

---

## Key Decisions

### Decision 1: Two-step decomposition gate as the primary workflow

Before gap analysis runs, the system produces an explicit numbered list of every atomic requirement extracted from the circular, each anchored to its source paragraph/section. Tobin reviews this list — confirming it's exhaustive, adding anything missing — before gap analysis runs against it.

**Why:** Makes extraction transparent and human-verified. The LLM's job in step 1 is tractable (extraction, not interpretation). Tobin's review is tractable (scanning a list against a document, not reading an AI verdict). Accountability is clear: the confirmed list is Tobin's artefact.

### Decision 2: Adversarial second pass as an automated complement

After gap analysis, automatically run a second LLM call with a contrastive prompt: *"Given this circular and our findings, what requirements in the circular are NOT reflected in this analysis?"* Any additions surfaced are flagged for Tobin's review.

**Why:** Catches stragglers with no extra user effort. Different prompt framing hits different failure modes than the initial extraction. Should not be the primary mechanism (LLM auditing its own work), but is a useful safety net.

### Decision 3: Don't build coverage-by-section as the primary signal

A "which sections were cited" audit is tempting but weak — an uncited section may legitimately contain no requirements. It produces noise that undermines trust rather than building it.

---

## Proposed UX Flow

```
1. Upload circular
2. [NEW] "Extract requirements" step
   → System returns numbered list, anchored to source paragraphs
   → Tobin reviews: confirm, add, delete
   → Confirmed list saved as a versioned artefact
3. Run gap analysis against confirmed list (not re-extracted on the fly)
4. [NEW] Adversarial pass runs automatically
   → Any uncovered requirements flagged as "review: possible omission"
5. Gap report output (Full / Partial / Gap) — same as today
6. Remediation tracking (annotate, assign owner) — same as today
```

---

## Open Questions

- **Doc structure variance:** HKMA docs vary — some have numbered sections, some are prose-heavy. May need prompt variants per doc type.
- **Confirmation UI:** Editable checklist vs. table vs. CLI-first? CLI matches existing Lacuna UX; browser UI later.
- **Versioning:** If Tobin edits the confirmed list, do we store the diff vs. LLM extraction? Useful for calibration over time.
- **Confidence indicators:** Should requirements found in only one chunk be flagged differently from those corroborated by multiple chunks?

---

## What We're Not Building (Yet)

- Automated re-extraction on circular updates
- Side-by-side diff against a previous circular version
- Cross-circular requirement deduplication

---

## Next Step

`/ce:plan` — design the decomposition endpoint, confirmed-list data model, adversarial pass prompt, and `lacuna decompose` CLI command.
