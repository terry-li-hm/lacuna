# RegAtlas - Regulatory Gap Analysis Demo Script (Tobin Follow-up)

**Total Demo Time:** 3 minutes  
**Goal:** Show how GenAI solves the "hallucination" and "traceability" problems in regulatory gap analysis.

---

## 1. Context (The "Wow" Statement)
**Say:**
> "Tobin, during our interview you mentioned the challenge of performing gap analysis when new circulars come out. I wanted to show you a prototype I built in **RegAtlas** specifically for this. The key differentiator here is our **'Inject-and-Verify'** pattern—it ensures the AI only cites actual regulatory text, making it audit-grade and defensible."

---

## 2. The Setup - New Document Ingestion
**Show:** Ingesting the latest government guidelines.

**Say:**
> "We'll start with the **HKMA Aug 2024 GenAI Circular** as our baseline. Then, we ingest the brand new **HKMA & PCPD Joint Announcement from Jan 27, 2026**—literally from two days ago. It introduces strict new measures for anti-fraud and data privacy collaboration."

**CLI Commands:**
```bash
# Upload Baseline (HKMA 2024)
regatlas upload data/documents/hkma_genai_2024.txt -j "Hong Kong"

# Upload New Circular (Jan 27, 2026)
regatlas upload data/documents/hkma_pcpd_joint_2026.txt -j "Hong Kong"
```

---

## 3. Directional Gap Analysis
**Show:** Running the mapping.

**Say:**
> "Instead of a simple comparison, we run a **Directional Gap Analysis**. We're asking: 'What requirements in the Jan 2026 Announcement are NOT covered by our existing 2024 GenAI compliance framework?'"

**CLI Command:**
```bash
regatlas gap <JAN_2026_DOC_ID> <HKMA_2024_DOC_ID>
```

**Point out:**
- ✅ **New Mandates:** It identifies the requirement for **"Joint Risk-Based Examinations"** and **"Quarterly Stress Tests"** on anti-fraud controls—specific 2026 mandates not found in earlier guidance.
- ✅ **Privacy Convergence:** The AI notes the shift from pure consumer protection to deep collaboration with the privacy regulator (PCPD).

---

## 4. Evidence & Traceability
**Show:** The provenance links in the UI.

**Say:**
> "The 'secret sauce' is the **Provenance**. Every claim links back to a specific chunk ID and verified text snippet. In the UI, clicking a gap shows the exact source paragraph. This eliminates hallucinations because the AI is restricted to citing indices we injected into the context window."

---

## 5. Value Props for HSBC
1. **Speed:** Maps a 50-page circular in seconds.
2. **Defensibility:** Audit trail for every gap finding.
3. **Pragmatic BAU:** Fits directly into the 'Responsible AI' lifecycle Tobin manages.

---

## Appendix: IDs for Demo
- **Baseline (HKMA 2024):** `fcd1d92c-afd4-465a-be20-c3e70d54bc41`
- **Target (HKMA/PCPD Jan 2026):** `e57ea7d0-011c-4fa8-960f-81737670be5f`
