# Brainstorm: Live Upload — Making the "Try Your Own Doc" Demo Moment Work

**Date:** 2026-03-06
**Goal:** Make it viable to demo Lacuna with a real Tobin/HSBC document, rather than the illustrative Codex Argentum baseline.

---

## What We Learned (Benchmark Results)

**Gap analysis on no_llm baseline already works and produces good results.**
Running `lacuna gap --circular hkma-cp --baseline fca` (FCA was uploaded no_llm) returned Full:0, Partial:6, Gap:2 with coherent, citation-backed reasoning per finding. The system already does chunk-based gap analysis for docs without extracted requirements. Quality is demo-grade.

**But: upload is 5+ minutes even with --no-llm.**
Tested: `lacuna upload --file codex-argentum-v1.txt --no-llm` took **5:09** wall time. The bottleneck is not LLM extraction — it's sentence-transformer embedding generation for every chunk. This is happening server-side on Railway (CPU-only). Live upload during a meeting is not viable.

**Implication:** The right strategy is not "fix upload speed" — it's "pre-load Tobin's document before the meeting."

---

## What We're Building

A **pre-upload workflow** that enables the live demo moment without live upload:

1. Before the meeting: Terry asks Tobin for one policy document (or chapter) — frame it as "to make the demo more useful to you"
2. Upload overnight: `lacuna upload --file <tobin-doc> --name "HSBC AI Governance Chapter" --no-llm` — takes 5min but happens off-screen
3. Run gap analysis to verify results look coherent
4. During the demo (Act 3b): show it live as if it just happened — "I pre-loaded a chapter of your framework. Let me run the same analysis against it."

The gap analysis already works. Nothing new to build on the backend. The work is:
- **Demo script update:** Add the "pre-loaded doc" beat to Act 3 and remove the "don't upload live" anti-pattern caveat
- **Frontend UX (optional):** If uploading via the web UI, ensure the no_llm path is accessible (currently unclear if the frontend exposes this)

---

## Alternative: If Tobin Doesn't Share a Doc

If Tobin won't share an internal document before the meeting, use a **credible proxy**:
- Source a published bank AI governance standard (HSBC has published some AI principles publicly)
- Or use MAS AI Model Risk Management (already in system as `mas-mrmf`) as the "HSBC-adjacent" baseline
- Frame it: "I've pre-loaded the MAS AI Model Risk Management Framework — which covers similar ground to what you'd have internally. Let's run the gap analysis against that."

This is lower-stakes than asking for internal docs but still demonstrates the core point.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Upload timing | Before the meeting, not live | 5min upload is not viable live; pre-staging is clean |
| Upload mode | `--no-llm` | Fast enough overnight; gap analysis quality is already good |
| Demo framing | "I pre-loaded a chapter for you" | Honest, and still demonstrates the capability |
| Fallback if no doc | mas-mrmf as proxy | Already in system, credible, no new upload needed |
| Frontend UX change | Not required for demo | CLI upload works; frontend no_llm button is a nice-to-have |

---

## What This Unlocks in the Demo

Updated demo beat (Act 3 extension, replaces the "vision" framing):

> "Before we met, I asked if you could share a section of your AI Standard. I pre-loaded it and ran the same gap analysis against it. [Show results.] These are the findings against your actual framework — not the illustrative baseline."

If Tobin didn't share a doc:
> "I pre-loaded the MAS Model Risk Management Framework — it's structured similarly to what you'd have internally. The analysis runs the same way. When you're ready to run it against your own Standard, the upload takes a few minutes."

---

## What Would Actually Require Building

If we later want a truly seamless live upload (< 30s), the real fix is:
- **Replace sentence-transformers with a hosted embedding API** (OpenAI text-embedding-3-small, or similar) — embedding generation via API would be 2–5s rather than 5min on Railway CPU
- This is a meaningful backend change and out of scope for pre-demo

---

## Open Questions (Resolved)

- ~~Quality gap on no_llm baselines?~~ Resolved: quality is good, demo-grade
- ~~Token cost?~~ Non-issue for HKMA-CP (7 reqs)
- ~~Frontend changes needed?~~ Not required for demo path (CLI upload)
- ~~Background extraction?~~ Out of scope for demo

---

## Scope (Pre-Demo)

**In scope:**
- Update DEMO_SCRIPT.md: add Act 3b "pre-loaded doc" beat
- Coordinate with Tobin pre-meeting: request one policy document or chapter

**Out of scope (post-demo):**
- Fast embedding via API (> 30s upload fix)
- Frontend no_llm upload button
- Draft amendment generation

---

## Next Step

No code build needed before the demo. Action items:
1. Update DEMO_SCRIPT.md with the pre-loaded doc beat
2. Reach out to Tobin (or Simon) before the meeting: "If you can share a policy chapter, I can pre-load it for a more tailored demo"
3. As fallback: verify `mas-mrmf` produces coherent results vs HKMA-CP
