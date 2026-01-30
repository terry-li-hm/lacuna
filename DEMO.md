# RegAtlas - Capco Demo Script

**Total Demo Time:** 5 minutes  
**Prepared for:** Capco Live Engagement - Regulatory Analytics Use Case

---

## Setup (Before Demo - 30 seconds)

```bash
cd ~/reg-atlas
source .venv/bin/activate

# Verify service is live
python -m cli.main health
```

---

## Demo Flow

### 1. The Problem (30 seconds)

**Say:**
> "Banks operating across multiple jurisdictions face a major challenge: understanding and comparing regulatory requirements. Analysts spend days manually reading through hundreds of pages of HKMA circulars, MAS notices, FCA rulebooks, and trying to identify differences. This is slow, error-prone, and doesn't scale."

**Show:** A regulatory PDF document (lots of dense text)

---

### 2. The Solution - Document Ingestion (1 minute)

**Say:**
> "RegAtlas automates this. Let me show you. First, we upload regulatory documents from different jurisdictions."

**Command:**
```bash
python -m cli.main upload data/documents/sample_hkma_capital.txt -j "Hong Kong"
```

**Point out:**
- ✅ Uploaded in ~10 seconds
- ✅ AI automatically extracted 7+ requirements
- ✅ Categorized by type (Capital Adequacy, Liquidity, Reporting, etc.)
- ✅ Structured and ready for analysis

**Command:**
```bash
python -m cli.main upload data/documents/sample_mas_liquidity.txt -j "Singapore"
```

**Point out:**
- ✅ Second jurisdiction added
- ✅ Different regulatory focus (liquidity vs capital)
- ✅ All indexed for semantic search

---

### 3. Natural Language Queries (1.5 minutes)

**Say:**
> "Now analysts can ask questions in natural language instead of reading hundreds of pages."

**Query 1 - Specific Jurisdiction:**
```bash
python -m cli.main query "What is the liquidity coverage ratio requirement in Singapore?"
```

**Point out:**
- ✅ AI-generated summary: "Banks must maintain LCR of at least 100%"
- ✅ Shows exact regulatory text sections as evidence
- ✅ Includes jurisdiction and document source

**Query 2 - Cross-Jurisdiction:**
```bash
python -m cli.main query "What are the minimum capital requirements?" -j "Hong Kong"
```

**Point out:**
- ✅ Filtered to Hong Kong only
- ✅ Lists all three tiers: CET1 (4.5%), Tier 1 (6.0%), Total (8.0%)
- ✅ Plus capital buffers (2.5% conservation buffer, etc.)

---

### 4. Cross-Jurisdiction Comparison (1.5 minutes)

**Say:**
> "The real power is comparing requirements across jurisdictions automatically."

**Command:**
```bash
python -m cli.main compare "Hong Kong" "Singapore"
```

**Point out:**
- ✅ **Common Requirements:** Both focus on liquidity
- ✅ **Key Differences:**
  - Singapore has detailed HQLA asset classification (Level 1, 2A, 2B)
  - Singapore requires public disclosure
  - Singapore has FX exposure management rules
- ✅ **Analysis:** AI identifies Singapore as stricter in certain areas
- ✅ Generated in ~15 seconds vs days of manual work

---

### 5. System Overview (30 seconds)

**Command:**
```bash
python -m cli.main stats
python -m cli.main list-docs
```

**Say:**
> "The system scales - currently 2 documents, but works with 10, 50, 100+ documents across any number of jurisdictions. We also have a central requirements registry with evidence links and CSV export for downstream compliance workflows."

**Point out:**
- 13 chunks indexed
- 2 jurisdictions loaded
- LLM available for intelligent analysis

---

### 6. Regulatory Change Register (45 seconds)

**Show in UI:**
- Add a change item (HKMA circular, MAS notice)
- Assign owner and due date
- Export change log to CSV

**Say:**
> "This mirrors how compliance teams actually work: log regulatory updates, triage by severity, assign owners, track deadlines, and export audit-ready records."

---

### 7. GenAI Assist (30 seconds)

**Show in UI:**
- Use "AI Suggest" to draft impact assessment
- Auto-link related requirements

**Say:**
> "GenAI accelerates the analysis step—drafting impact summaries and mapping relevant obligations, while keeping humans in control."

---

### 8. Architecture & Value (30 seconds)

**Show:** Quick code walkthrough or architecture diagram

**Say:**
> "Built on production-grade stack:
> - FastAPI backend
> - OpenRouter for multi-model LLM access
> - ChromaDB vector database for semantic search
> - Deployed on Render with auto-scaling
> - CLI for analyst workflows
> - Web UI for business users"

**Key Value Props:**
- ⚡ **Speed:** Minutes → Seconds
- 🎯 **Accuracy:** AI-powered extraction and comparison
- 📈 **Scalability:** Handles multiple jurisdictions easily
- 🔌 **Integration:** API-first, can integrate with existing systems
- 💰 **Cost-effective:** Runs on free tier for demos, affordable for production
- ✅ **Audit-ready:** Evidence links + audit trail support
- 🧭 **Governance:** Risk scoring, escalation flags, approvals workflow

---

## Alternative Demo Paths

### Path A: CLI-Only Demo (Technical Audience)
- Focus on terminal commands
- Show JSON responses
- Emphasize API-first design
- **Best for:** Developer teams, technical decision makers

### Path B: Web UI Demo (Business Audience)
- Open frontend/index.html
- Click through upload → query → compare
- Visual interface
- **Best for:** Business stakeholders, compliance teams

### Path C: Hybrid Demo (Recommended)
- Start with Web UI to show end-user experience
- Switch to CLI to show developer workflow
- Emphasize both audiences served
- **Best for:** Mixed technical + business audience

---

## Questions to Anticipate

### Q: "How accurate is the extraction?"
**A:** "Uses GPT-3.5-turbo via OpenRouter - same LLM banks use for compliance. Can upgrade to GPT-4 or Claude for even higher accuracy. Also shows source text for verification."

### Q: "Can it handle our specific jurisdiction?"
**A:** "Yes - architecture is jurisdiction-agnostic. Just upload your regulatory documents (HKMA, MAS, FCA, Fed, EBA, etc.) and it works."

### Q: "What about regulatory updates?"
**A:** "Current version requires manual upload. Production version could include automated monitoring of regulatory websites, RSS feeds, and change detection."

### Q: "How does it integrate with our systems?"
**A:** "RESTful API - easy to integrate. Can push extracted requirements to your compliance database, trigger alerts, or feed into risk models."

### Q: "Cost to run this?"
**A:** "Demo runs on free tier. Production would be ~$50-200/month depending on usage. Much cheaper than analyst time."

### Q: "Can we customize the extraction?"
**A:** "Yes - prompts are configurable. Can train for your specific requirement types, add custom validation rules, integrate domain-specific taxonomies."

---

## Post-Demo Actions

1. **Offer to share repo:** "I can grant access to the private GitHub repository for your team to review"

2. **Discuss next steps:**
   - POC with client's actual regulatory documents?
   - Integration with specific compliance systems?
   - Custom requirement taxonomies?

3. **Follow-up:**
   - Send demo video/recording
   - Share GitHub access
   - Schedule technical deep-dive if interested

---

## Emergency Backup (If Service is Down)

**If Render service is sleeping/down:**

1. **Start local backend:**
   ```bash
   cd ~/reg-atlas
   ./run.sh
   # Wait 30 seconds for embedding model to load
   ```

2. **Use CLI with local:**
   ```bash
   python -m cli.main health --api-url http://localhost:8000
   python -m cli.main upload data/documents/sample_hkma_capital.txt -j "Hong Kong" --api-url http://localhost:8000
   # etc.
   ```

3. **Explain:**
   > "Running locally now to avoid cold start - production deployment is at reg-atlas.onrender.com"

---

## Demo Checklist

**Before Demo:**
- [ ] Verify service is live: `python -m cli.main health`
- [ ] Check documents are loaded: `python -m cli.main stats`
- [ ] Test query works: `python -m cli.main query "test"`
- [ ] Have sample PDFs ready if showing live upload
- [ ] Terminal font size readable on screen share
- [ ] Browser tabs ready (if showing web UI)

**During Demo:**
- [ ] Speak slowly and clearly
- [ ] Pause after each command to let output sink in
- [ ] Highlight AI-generated summaries
- [ ] Emphasize time savings (seconds vs days)
- [ ] Show both CLI and web UI if time permits

**After Demo:**
- [ ] Ask for questions
- [ ] Offer to share repository
- [ ] Discuss customization opportunities
- [ ] Schedule follow-up if interested

---

## Key Talking Points

1. **"This solves the exact problem Bertie mentioned"** - Cross-market regulatory analytics
2. **"Production-ready architecture"** - Not a Jupyter notebook, real API
3. **"Tested and deployed"** - Live service at reg-atlas.onrender.com
4. **"Fast iteration"** - Built in one afternoon, shows agility
5. **"Scalable approach"** - Works for 2 jurisdictions or 50

**Confidence Statement:**
> "This demonstrates how we'd approach your regulatory analytics engagement - rapid prototyping, production-quality code, and clear business value from day one."
