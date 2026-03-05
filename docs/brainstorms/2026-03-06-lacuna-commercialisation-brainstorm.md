---
title: "Lacuna — Commercialisation Roadmap"
date: 2026-03-06
status: brainstorm
---

# Lacuna Commercialisation Brainstorm

## Strategic Framing

Lacuna is not being productized as standalone SaaS. The target market (banks, compliance teams) already has Reg.com / 4CRisk as a funded incumbent. Competing head-on is a losing battle.

**The play:** Lacuna as a Capco consulting engagement accelerator. The software opens doors and frames scope; Capco bills the transformation work. As it closes deals consistently, it formalizes into a Capco AI Regulatory Platform offering — white-labelled, partner-backed.

- **Near-term:** Demo asset to land engagements (HSBC and beyond)
- **Medium-term:** Formalized Capco IP / named offering within the AI practice
- **Not the plan:** Standalone SaaS, open source, personal side project

---

## Three Features to Close the Gap to a Second Client

### 1. Custom Baseline Upload (Priority 1 — the unlock)

**Problem:** Every client will ask "can we run this against our own document?" Right now the answer involves Codex Argentum, a Capco-authored illustrative baseline. That's a toy answer. The tool becomes genuinely useful the moment it handles the client's own messy internal language.

**Design:**
- **CLI:** `lacuna upload --file <path> --name "HSBC AI Standard" --jurisdiction HSBC` — pre-loads the client's doc the night before the demo. Uses the existing `/upload` API endpoint already in the backend.
- **UI:** Upload card on lacuna.sh — drag-and-drop PDF/Word/TXT, shows processing spinner, appears in the baseline dropdown once ready. The live demo moment: the client sees their own document already in the system.
- **Persistence:** Uploaded docs go to the Railway volume (already mounted at `/app/data`) — they survive service restarts, same as existing docs.
- **Formats:** PDF (primary), plain text, Word (.docx via python-docx extraction).

**Demo flow:** Pre-load client doc the night before via CLI. During demo, show it already in the baseline dropdown. If they ask to upload live — UI handles it.

### 2. Capco-Branded PDF Export (Priority 2 — makes it boardroom-ready)

**Problem:** Compliance committees run on Word/PDF deliverables, not browser tabs. The gap analysis finding doesn't travel without a polished output artifact.

**Design:**
- **Generation:** Server-side via WeasyPrint — renders an HTML template to PDF. Better control than Pandoc, native to Python.
- **Template:** Capco brand colours (coral/dark), Capco logo in header, client name + engagement date on cover page, findings table with colour-coded status badges, provenance citations in footnotes.
- **Trigger:** New backend endpoint `POST /gap-analysis/export` returns a PDF blob. CLI: `lacuna export --circular hkma-cp --baseline <client-doc> --format pdf --output report.pdf`. UI: "Export PDF" button on gap analysis results.
- **Capco logo:** Stored as base64 in the template — no external asset dependency.

### 3. Per-Client API Key Auth (Priority 3 — needed before any real pilot)

**Problem:** lacuna.sh is currently a public, unauthenticated URL. Any second engagement means client documents can't be on the same instance without isolation.

**Design:**
- **Mechanism:** `X-API-Key` header checked by FastAPI middleware on all routes. Unauthenticated requests return 401.
- **Key management:** Keys stored in a simple JSON config on the Railway volume (or env vars for simplicity). One key per engagement — revoke by deletion.
- **CLI:** `LACUNA_API_KEY=<key> lacuna gap ...` — env var passed through to httpx client.
- **UI:** Key entered once in a settings panel, stored in localStorage.
- **No user accounts, no login UI** — this is a consulting tool, not a consumer product.

---

## What This Unlocks

| Feature | Client conversation it enables |
|---------|-------------------------------|
| Custom baseline upload | "Yes, we can run this against your actual AI Standard right now" |
| PDF export | "Here's the deliverable for your compliance committee" |
| Auth | "Your documents are isolated — other clients cannot see them" |

Together these move Lacuna from "impressive demo" to "pilot-ready consulting tool."

---

## Out of Scope (for now)

- Multi-tenancy / SaaS billing (consult engagements don't need it)
- SSO / OAuth (overkill for a consulting access model)
- Corpus expansion (add jurisdictions on demand per client, not speculatively)
- On-premise deployment (address when a client specifically requires it)

---

## Open Questions

- What Capco brand assets are available and permitted for use in the PDF template?
- Should the PDF export be triggered from the CLI, the UI, or both? (Both assumed above)
- At what point does Lacuna get formally pitched to Capco's practice leadership as a named offering?
