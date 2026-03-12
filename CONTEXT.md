# Lacuna Context
<!-- Updated: 2026-03-12 -->

## What it does
Regulatory gap analysis platform — maps new circulars against baseline frameworks using LangGraph parallel fan-out, with human-in-the-loop review and cross-jurisdiction synthesis.

## State
Fully functional on Railway (https://lacuna.sh). CLI + web UI. Three LangGraph features shipped: parallel gap analysis, HITL interactive review, cross-jurisdiction synthesis. All features exposed in both CLI and web UI.

## Last session
Fixed two production bugs: (1) LangGraph 1.1 changed interrupt() — no longer raises GraphInterrupt, returns `__interrupt__` key in ainvoke() result instead; (2) claude-sonnet-4.6 appends trailing content after JSON, fixed with raw_decode + trim-to-{. Added HITL toggle and synthesis card to web UI. Deployed to Railway.

## Next
- Browser-verify web UI HITL + synthesis at lacuna.sh
- Pre-warm gap cache before Tobin demo: `lacuna gap --circular hkma-cp --baseline demo-baseline`
- MemorySaver is in-memory — wipes on every Railway restart; warn before demo day

## Open questions
- Demo timing with Tobin — when is it?
- MemorySaver → SQLite persistence (future) if demo requires resuming across sessions
