# Lacuna — Demo Script for Tobin

**URL:** https://meridian-production-1bdb.up.railway.app
**Duration:** 5-7 minutes
**Context:** Day 1 at Capco. Tobin is HSBC's AI Regulatory Management Lead (AIMS Responsible AI). His actual pain: when new regulation drops, how much does it add to what HSBC's existing AI Standard already covers? The existing standard covers previous requirements — the ongoing work is **delta analysis for new requirements**, with paragraph-level citations to drive policy amendments.

---

## Setup (before the demo)

1. Open the URL in Chrome, full screen
2. Verify the dashboard loads with documents and stats
3. Pre-warm the gap analysis cache — run this once before the meeting:
   ```
   curl -s -X POST "https://meridian-production-1bdb.up.railway.app/gap-analysis" \
     -H "Content-Type: application/json" \
     -d '{"circular_doc_id":"7f247634-cdcb-455a-bd02-7083feb1ed6e","baseline_id":"ef3d9bff-a442-443f-97ca-9fc7d0108618","is_policy_baseline":false}'
   ```
   (First run ~30s via LLM; repeat runs return instantly from cache. Cache resets on Railway restart.)
4. Have these queries ready to paste:
   - `What are HKMA's requirements for GenAI consumer protection?`
   - `What are the high-risk AI system requirements under the EU AI Act?`

---

## Act 1: The Problem (30s)

> "Tobin, I built something I think directly addresses the delta problem — when a new circular drops, how much does it add to what your existing standard already covers?"

Open Lacuna. The dashboard loads showing:
- 8 real regulatory documents across 4 jurisdictions
- Overdue alerts badge in the corner
- The Regulatory Radar section at the top with a live HKMA/PCPD detection

> "This is Lacuna — it ingests regulatory circulars from HKMA, MAS, the EU AI Act, and FCA, extracts the specific requirements, and lets you compare them. The idea: your Global AI Standard is the baseline. New regulation comes in. Lacuna tells you exactly what's covered and what isn't — with citations back to the paragraph."

---

## Act 2: RAG Query — "Ask your regulator" (60s)

Scroll to the **Query Documents** section.

**Query 1:** `What are HKMA's requirements for GenAI consumer protection?`
Set jurisdiction to **Hong Kong**. Submit.

Wait for response. It will return:
- 5 relevant document chunks with provenance (filename, chunk ID)
- An LLM-generated summary citing specific HKMA requirements (governance, fairness, transparency, data privacy)

> "This isn't a chatbot making things up. Every answer traces back to the actual circular text — you can click through to see exactly which paragraph it came from. This is the HKMA Consumer Protection Circular from August 2024."

**Query 2** (optional, if time): `What are the high-risk AI system requirements under the EU AI Act?`
Set jurisdiction to **European Union**.

> "Same system, different jurisdiction. The EU AI Act is 144 pages — try reading that on a Monday morning."

---

## Act 3: Gap Analysis — Policy Delta (90s)

Navigate to the **Gap Analysis** section. Select:
- **Circular:** HKMA Consumer Protection 2024
- **Baseline:** Codex Argentum v1.0 (the illustrative policy baseline, already in the system)

Submit. Result returns instantly (pre-cached):

```
Full:    1   ← Transparency/disclosure — baseline covers this clearly
Partial: 5   ← Governance accountability, human-in-the-loop, fairness, opt-out, PDPO
Gap:     2   ← BDAI Guiding Principles reference, proactive consumer protection use
```

Click into a **Partial** finding — show the reasoning:

> *"[Partial] Customer opt-out — The baseline provides a human escalation pathway and states customers shall not be required to interact solely with an AI system. However, it does not explicitly address the HKMA's specific requirement for a customer-initiated opt-out from GenAI-generated decisions at their discretion, nor the alternative measures required where opt-out cannot be provided."*

Click into a **Gap** finding:

> *"[Gap] BDAI Guiding Principles — The baseline does not reference or incorporate the 2019 BDAI Guiding Principles. While it draws on publicly available frameworks, there is no explicit requirement to apply or extend the BDAI Guiding Principles to GenAI in customer-facing applications."*

> "The Partial findings are where the work actually lives. Each one isn't 'mostly fine' — each one is a governance decision: does the existing control language satisfy this requirement, or does it need to be amended? That question currently takes a compliance team days of manual cross-referencing. This produces the same output in seconds, with citations ready for the drafter."

**On the tool's approach — if Tobin probes:** "The tool identifies topical relevance and semantic coverage — it flags where the policy language addresses the regulatory requirement. Determining whether it's *legally equivalent* is your call. That's the division of labour: Lacuna gives you the paragraph-level map, you apply the legal judgment."

**If Tobin asks to run it against a real HSBC document:** "That's exactly the point. This baseline is illustrative — it's showing you the workflow. The moment you drop in your actual Chapter 5, the analysis runs the same way against real text. The interesting test is whether it performs just as cleanly on messier internal language. Happy to try that live if you have something accessible."

**If asked — second credibility test:** Run the same HKMA circular against the NIST AI RMF (already loaded — baseline_id: `b55c5916`). "This is the NIST AI Risk Management Framework — a document I had no hand in writing. The tool handling it with the same precision is how you know it's not optimised for a specific input."

---

## Act 4: Change Tracking & Alerts (60s)

Scroll to the **Regulatory Change Register**.

Show the 3 change items:
- HKMA GenAI Consumer Protection — **overdue** (red), assigned to Compliance Team
- MAS AI Risk Management Consultation — **overdue** (red), assigned to Regulatory Affairs
- EU AI Act High-Risk Classification — upcoming (30 days), critical severity, unassigned

> "This is the change register. Two items are overdue — the system flags these automatically. In production, this would trigger email alerts and escalation to the responsible owner."

Scroll to **Overdue Alerts** section to show the escalation view:
- Days overdue
- Escalation required flag

> "Monday morning: your team opens this, they know exactly what's slipped and who owns it."

---

## Act 5: Horizon Scanning (30s)

Briefly mention the RSS feed sources:

> "We're also monitoring HKMA, MAS, and EUR-Lex RSS feeds. When a new circular drops, it automatically creates a change item in the register. No one has to manually check regulator websites."

---

## Act 6: The Vision (60s)

> "What you're seeing is a working system, not a mockup. Real HKMA circulars, real MAS consultations, real EU AI Act text. The extraction, the gap analysis, the change tracking — it all runs end to end."

> "The natural next step: instead of comparing two regulatory documents, you compare an incoming regulation against HSBC's actual AI Standard — or a draft chapter of it. Upload the Standard, upload the new circular, get a gap register with paragraph-level citations. That becomes the input to the policy amendment workstream."

> "It's not replacing the lawyer's judgment — Tobin, you'd still own the interpretation. But instead of spending three days manually cross-referencing, you spend three hours reviewing a cited gap report."

**If Tobin asks about data sources:**
- 4 HKMA documents (GenAI Consumer Protection, SPM CA-G-1, Sandbox Arrangement, GenAI in Financial Services)
- 2 MAS documents (AI Model Risk Management, AI Risk Management Consultation)
- 1 EU AI Act (full Regulation 2024/1689, 144 pages)
- 1 FCA AI Update (2024)

**If Tobin asks about the AI model:**
- Extraction: GPT-4o-mini via OpenRouter (fast, cost-effective)
- Gap analysis: Claude Sonnet (best for structured regulatory reasoning)
- Vector search: ChromaDB with sentence-transformer embeddings
- All configurable — can swap in enterprise models or on-prem deployment

**If Tobin asks about cost:**
- Current: ~$5/month Railway hosting + ~$0.01 per query (OpenRouter)
- Enterprise: would run on client infrastructure with their model licenses

---

## Anti-patterns — Don't Do This

- Don't upload a document live (takes 30s-2min for LLM extraction, awkward silence)
- Don't show the API config section (bottom of page) — it exposes the infrastructure
- Don't try to explain the tech stack unless asked — lead with the business value
- Don't say "I built this in a weekend" — say "I've been working on this" (frames it as serious)
- **Don't present the Codex Argentum as if it reflects real HSBC policy.** It's a demo input. If Tobin asks about it: "It's a Capco-authored illustrative baseline — structured like what a policy chapter would look like, so the gap analysis has something realistic to work against. The real test is running it against your actual standard."
- **Don't let the output leave the meeting without context.** If Tobin wants to share the gap analysis results, make sure the framing travels with it: "This is a demo run against the Codex Argentum illustrative baseline, not an assessment of HSBC's actual compliance position."
- **Don't claim legal equivalence.** If a finding says "Partial," that's a signal for human review — not a determination that the policy partially satisfies a legal obligation. Make this explicit if Tobin probes the methodology.
