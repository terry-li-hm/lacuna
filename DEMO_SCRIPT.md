# Lacuna — Demo Script for Tobin

**URL:** https://lacuna.sh
**Duration:** 5-7 minutes
**Context:** Day 1 at Capco. Tobin is HSBC's AI Regulatory Management Lead (AIMS Responsible AI). His actual pain: when new regulation drops, how much does it add to what HSBC's existing AI Standard already covers? The existing standard covers previous requirements — the ongoing work is **delta analysis for new requirements**, with paragraph-level citations to drive policy amendments.

---

## Setup (before the demo)

1. `lacuna preflight` — full health check (API + docs + cache warmup). Expected: `PASS — demo ready.` with Full:0 Partial:5 Gap:2
2. Open https://lacuna.sh in Chrome, full screen
3. Verify the dashboard loads with documents and stats
4. Have these queries ready to paste:
   - `What are HKMA's requirements for GenAI consumer protection?`
   - `What are the high-risk AI system requirements under the EU AI Act?`

---

## Act 1: The Problem (30s)

> "Tobin, I built something I think directly addresses the delta problem — when a new circular drops, how much does it add to what your existing standard already covers?"

Open Lacuna. The dashboard loads showing:
- 9 real regulatory documents across 4 jurisdictions
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
- **Baseline:** Codex Argentum v1.1 (the illustrative policy baseline, already in the system)

Submit. Result returns instantly (pre-cached):

```
Full:    0
Partial: 6   ← Board accountability, human-in-loop, fairness/bias, disclosure, PDPO/data privacy, opt-out, model validation
Gap:     2   ← BDAI Guiding Principles (×2: apply principles + proactive consumer protection)
```

Click into a **Partial** finding — show the reasoning. Best one: **Board accountability**

> *"[Partial] The board and senior management must be accountable for GenAI-driven decisions. The baseline addresses governance mechanisms and requires a named AI System Owner at an appropriately senior level, and governance body approval for autonomous deployment. However, there is no specific provision establishing board and senior management accountability for GenAI-driven decisions. The baseline focuses on operational controls rather than executive-level accountability frameworks."*

Click into a **Gap** finding — **BDAI Guiding Principles**:

> *"[Gap] The circular requires institutions to apply and extend the 2019 BDAI Guiding Principles to the use of GenAI in customer-facing applications. The baseline contains detailed GenAI governance requirements but makes no reference to the 2019 BDAI Guiding Principles. While it includes ethical AI principles assessment, disclosure requirements, and third-party vendor management, it does not explicitly connect these controls to the BDAI Guiding Principles framework."*

> ⚠ **Full:0 Partial:6 Gap:2 is the calibrated result for Codex Argentum v1.1 as of Mar 6 2026 (post re-seed).** Re-run `lacuna preflight` before each demo to confirm counts haven't changed (cache resets on Railway restart).

> "The Partial findings are where the work actually lives. Each one isn't 'mostly fine' — each one is a governance decision: does the existing control language satisfy this requirement, or does it need to be amended? That question currently takes a compliance team days of manual cross-referencing. This produces the same output in seconds, with citations ready for the drafter."

**On the tool's approach — if Tobin probes:** "The tool identifies topical relevance and semantic coverage — it flags where the policy language addresses the regulatory requirement. Determining whether it's *legally equivalent* is your call. That's the division of labour: Lacuna gives you the paragraph-level map, you apply the legal judgment."

**If Tobin asks to run it against a real HSBC document:** "That's exactly the point. This baseline is illustrative — it's showing you the workflow. The moment you drop in your actual Chapter 5, the analysis runs the same way against real text. The interesting test is whether it performs just as cleanly on messier internal language. Happy to try that live if you have something accessible."

**If Tobin asks "can it suggest what to add?"** — run with amendments:

```bash
lacuna gap --circular hkma-cp --baseline demo-baseline --amendments
```

This re-runs the analysis and appends a draft amendment clause per Partial/Gap finding. Takes ~30s extra (one LLM call per finding). Show one:

> *"Draft amendment: The Board of Directors shall establish and maintain explicit accountability for the use of GenAI in customer-facing applications, including approval of the institution's GenAI governance framework and periodic review of GenAI-driven decision outcomes. Senior management shall designate a named executive responsible for GenAI risk, with escalation paths to the Board for material incidents or policy breaches."*

> "This isn't a final clause — it's a drafting prompt. Your policy team takes this, marks it up against your existing language, and that's the amendment. We've just compressed three days of gap identification into the input to a 30-minute drafting session."

The DOCX export includes these amendments — each finding has requirement, reasoning, citation, and draft clause. Ready to hand to the drafter.

**If asked — second credibility test:** Run `lacuna gap --circular hkma-cp --baseline mas-mrmf`. "This is the MAS AI Model Risk Management Framework — a document I had no hand in writing. The tool producing coherent findings on it is how you know it's not tuned for a single input."

---

## Act 3b: Export (30s — if Tobin wants to take something away)

After the gap analysis results render, click **Export Word** (or **Export PDF**).

> "The findings download as a Word document — ready for your policy drafting team to mark up directly. Each gap has the requirement text, the reasoning, and the baseline citation."

If he wants to email it to someone on the spot: it downloads as `lacuna-gap-report.docx`. Hand it over. This moment is more impactful than explaining it.

---

## Act 3c: Comparison Matrix (30s — if time permits)

Scroll to the **Comparison Matrix** section.

> "If you wanted to compare the Consumer Protection circular against multiple baselines at once — your current AI Standard *and* the MAS model risk framework — the matrix view runs all the gap analyses in parallel and shows you a heat map. Full/Partial/Gap across every combination."

This is the multi-jurisdiction view that matters for HSBC: same circular, compared against policies from different lines of business or jurisdictions.

---

## Act 3d: Credibility Test + Follow-up Hook (60s)

After the primary gap analysis, run against a second baseline to show the tool isn't tuned to a single input:

```bash
lacuna gap --circular hkma-cp --baseline mas-mrmf
```

> "This is the MAS AI Model Risk Management Framework — a document I had no hand in writing. The tool producing coherent findings on it is how you know it's not optimised for a specific input."

**The hook (close of Act 3):**

> "The natural next step is running this against your actual AI Standard — or a draft chapter of it. You upload it, same workflow, findings reference your policy language directly. Happy to set that up before our next conversation if you can share a chapter."

This is the ask — not "give me your document now" but "here's what the follow-up looks like." Plants the seed for a second meeting with real HSBC text.

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
- 1 Codex Argentum v1.1 illustrative baseline (Capco-authored)

**If Tobin asks about the export:** After showing gap results, click **Export PDF** or **Export Word** — downloads a branded report with findings and citations. "You can share this with the policy team directly — it's ready for a Word review."

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
