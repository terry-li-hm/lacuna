# Meridian — Demo Script for Tobin

**URL:** https://meridian-production-1bdb.up.railway.app
**Duration:** 5-7 minutes
**Context:** Day 1 at Capco. Tobin is HSBC Innovation Risk & Compliance Director. He tracks HKMA, MAS, EU AI Act, UK FCA/PRA. His pain: manual cross-jurisdiction regulatory change tracking.

---

## Setup (before the demo)

1. Open the URL in Chrome, full screen
2. Verify the dashboard loads with documents and stats
3. Have these queries ready to paste:
   - `What are HKMA's requirements for GenAI consumer protection?`
   - `What are the high-risk AI system requirements under the EU AI Act?`

---

## Act 1: The Problem (30s)

> "Tobin, I built something over the weekend that I think directly addresses the cross-jurisdiction tracking problem you mentioned. Let me show you."

Open Meridian. The dashboard loads showing:
- 8 real regulatory documents across 4 jurisdictions
- Overdue alerts badge in the corner
- The Regulatory Radar section at the top with a live HKMA/PCPD detection

> "This is Meridian — a regulatory intelligence platform that ingests actual circulars from HKMA, MAS, the EU AI Act, and FCA, then lets you query across all of them in natural language."

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

## Act 3: Cross-Jurisdiction Gap Analysis (90s)

Scroll to **Compare Jurisdictions**.

Set **Jurisdiction 1** to `Hong Kong`, **Jurisdiction 2** to `Singapore`. Submit.

The analysis will return a structured comparison:
- Common requirements (risk management, governance, ethical standards)
- Unique to HK (consumer protection specifics, sandbox requirements)
- Unique to SG (MAS model risk management, proportionality framework)

> "This is comparing every requirement we've extracted from HKMA documents against MAS documents. It finds where they align and where the gaps are. For a bank operating in both jurisdictions, this tells you which controls cover both and where you need jurisdiction-specific work."

**Key talking point:** "Today this takes a compliance team days of manual cross-referencing. This runs in seconds."

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

> "The next step would be connecting this to a client's actual policy library — upload their internal policies, and the gap analysis runs against both the regulatory requirements AND their existing controls. That's when it becomes audit-grade."

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
- The "Review Draft Analysis" button at the top works — it runs a real gap analysis (Consumer Protection vs Financial Services guidance) via Claude Sonnet. Takes ~30s. Use it if you want to show the agentic analysis, but be aware of the wait time.
- Don't show the API config section (bottom of page) — it exposes the infrastructure
- Don't try to explain the tech stack unless asked — lead with the business value
- Don't say "I built this in a weekend" — say "I've been working on this" (frames it as serious)
