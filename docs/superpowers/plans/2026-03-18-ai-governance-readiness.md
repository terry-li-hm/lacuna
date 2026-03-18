# Lacuna AI Governance Readiness — Phase 1

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Lacuna ready for HSBC's AI governance use case — upload internal policy as baseline, run gap analysis with AI-specific requirement extraction, get production-quality output.

**Architecture:** Three independent tasks that each improve one layer: extraction prompts (LLM tuning), policy upload pipeline (API + CLI), and extraction prompt categories. All changes are additive — no refactoring of existing code. The gap analysis engine, LangGraph workflow, and CLI are already solid.

**Tech Stack:** Python, FastAPI, DuckDB, Typer/Rich CLI, OpenRouter (Claude Sonnet via OpenAI-compatible API)

**Repo:** `~/code/lacuna/`

**Build/test:** `cd ~/code/lacuna && REG_ATLAS_NO_LLM=1 DATA_DIR=/tmp/reg_atlas_data CHROMA_PERSIST_DIR=/tmp/reg_atlas_data/db/chroma PYTHONPATH=/Users/terry/code/lacuna pytest tests/e2e_reg_atlas.py -q`

**Existing context:**
- `CLAUDE.md` in repo root has deployment details, doc IDs, aliases, gotchas
- Extraction prompt: `backend/requirement_extractor.py:111-132`
- Gap analysis: `backend/services/gap_analysis_service.py` (LangGraph-based)
- Policy service: `backend/services/policy_service.py` + `backend/storage/repositories.py:126+`
- Policy seeding: `backend/state.py:634+` — reads `data/policies/*.md` files
- CLI: `cli/main.py` — already has `gap`, `decompose`, `confirm`, `list-policies`, `upload` commands
- CLI client: `cli/api/client.py` — `RegAtlasClient` class

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/requirement_extractor.py` | Modify | Update extraction prompt with AI governance categories |
| `backend/routes/policies.py` | Modify | Add `POST /policies/upload` endpoint |
| `backend/services/policy_service.py` | Modify | Add `create_from_upload()` method |
| `backend/storage/database.py` | Modify | Add `content TEXT` column to policies table |
| `backend/storage/repositories.py` | Modify | Include `content` field in PolicyRepository.save() and reads |
| `cli/api/client.py` | Modify | Add `upload_policy()` method |
| `cli/main.py` | Modify | Add `upload-policy` CLI command |
| `tests/test_ai_governance.py` | Create | Tests for AI governance extraction + policy upload |

---

### Task 1: AI Governance Extraction Prompt

**Files:**
- Modify: `backend/requirement_extractor.py:111-132` (the extraction prompt)
- Test: `tests/test_ai_governance.py`

The current extraction prompt lists banking-specific categories: "Capital Adequacy, Liquidity, AML/KYC". For AI governance docs (EU AI Act, HKMA GenAI circulars, MAS AIRM), we need categories that match Tobin's mental model.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai_governance.py`:

```python
"""Tests for AI governance requirement extraction categories."""

import pytest
from backend.requirement_extractor import RequirementExtractor


AI_GOVERNANCE_CATEGORIES = [
    "Model Governance",
    "AI Safety & Robustness",
    "Fairness & Bias",
    "Transparency & Explainability",
    "Data Quality & Privacy",
    "Human Oversight",
    "Risk Management",
    "Accountability & Audit",
    "Consumer Protection",
    "Reporting & Disclosure",
]


def test_extraction_prompt_includes_ai_governance_categories():
    """Extraction prompt should list AI governance categories alongside banking ones."""
    extractor = RequirementExtractor(api_key=None)  # no LLM needed, just checking prompt
    # The prompt template is built in extract_requirements — we check the string
    # Build it the same way the method does
    prompt = extractor._build_extraction_prompt("dummy text", "Hong Kong")
    for category in AI_GOVERNANCE_CATEGORIES:
        assert category.lower() in prompt.lower(), (
            f"Missing AI governance category: {category}"
        )


def test_extraction_prompt_still_includes_banking_categories():
    """Ensure we don't remove existing banking categories."""
    extractor = RequirementExtractor(api_key=None)
    prompt = extractor._build_extraction_prompt("dummy text", "Hong Kong")
    for category in ["Capital Adequacy", "Liquidity", "AML/KYC"]:
        assert category.lower() in prompt.lower(), (
            f"Missing banking category: {category}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/code/lacuna && PYTHONPATH=. pytest tests/test_ai_governance.py -v`

Expected: FAIL — `_build_extraction_prompt` doesn't exist yet (prompt is inline in `extract_requirements`), and AI governance categories are missing.

- [ ] **Step 3: Extract prompt into a method and add AI governance categories**

Modify `backend/requirement_extractor.py`. Refactor the inline prompt (lines 111-132) into a `_build_extraction_prompt` method, and expand the category list:

```python
def _build_extraction_prompt(self, chunk: str, jurisdiction: str, chunk_label: str = "") -> str:
    """Build the extraction prompt for a regulatory text chunk."""
    return f"""Analyze the following regulatory text from {jurisdiction}{chunk_label} and extract key requirements.

For each requirement, identify:
1. Requirement type — choose the BEST fit from:
   Banking: Capital Adequacy, Liquidity, AML/KYC, Credit Risk, Market Risk, Operational Risk
   AI Governance: Model Governance, AI Safety & Robustness, Fairness & Bias, Transparency & Explainability, Data Quality & Privacy, Human Oversight, Accountability & Audit
   General: Risk Management, Consumer Protection, Data Privacy, Reporting & Disclosure, Governance, Cyber Security
2. Brief description of the requirement
3. Any specific thresholds, ratios, or deadlines mentioned
4. Whether it's mandatory or recommended
5. Confidence level (High/Medium/Low)
6. A short source snippet (<= 200 chars) quoted from the text

Text:
{chunk}

Provide output in the following structured format:
REQUIREMENT_TYPE: [type]
DESCRIPTION: [brief description]
DETAILS: [specific numbers, dates, thresholds]
MANDATORY: [Yes/No]
CONFIDENCE: [High/Medium/Low]
SOURCE_SNIPPET: [quoted excerpt]
---
"""
```

Then update `extract_requirements` to call `self._build_extraction_prompt(chunk, jurisdiction, chunk_label)` instead of the inline f-string.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/code/lacuna && PYTHONPATH=. pytest tests/test_ai_governance.py -v`

Expected: PASS — both AI governance and banking categories present.

- [ ] **Step 5: Run existing tests to check for regressions**

Run: `cd ~/code/lacuna && REG_ATLAS_NO_LLM=1 DATA_DIR=/tmp/reg_atlas_data CHROMA_PERSIST_DIR=/tmp/reg_atlas_data/db/chroma PYTHONPATH=. pytest tests/e2e_reg_atlas.py -q`

Expected: PASS (extraction prompt change is backward-compatible — new categories are additive).

- [ ] **Step 6: Commit**

```bash
cd ~/code/lacuna && git add backend/requirement_extractor.py tests/test_ai_governance.py
git commit -m "feat: add AI governance categories to extraction prompt

Expand requirement type taxonomy with Model Governance, AI Safety,
Fairness & Bias, Transparency, Human Oversight, and Accountability
categories. Refactors inline prompt into _build_extraction_prompt method."
```

---

### Task 2: Policy Upload API Endpoint

**Files:**
- Modify: `backend/routes/policies.py` — add `POST /policies/upload`
- Modify: `backend/services/policy_service.py` — add `create_from_upload()`
- Modify: `backend/state.py` — wire upload to vector store + requirement extraction
- Test: `tests/test_ai_governance.py` (append)

Currently policies can only be seeded from `data/policies/*.md` files on disk. Tobin needs to upload HSBC's Global AI Standard as a PDF/text file and have it become a gap analysis baseline.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai_governance.py`:

```python
import httpx
import os

# Skip if not running integration tests
INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS") == "1"


@pytest.mark.skipif(not INTEGRATION, reason="Integration test — needs running server")
def test_policy_upload_endpoint():
    """POST /policies/upload should accept a file and return a policy with extracted requirements."""
    base = os.getenv("REGATLAS_API_URL", "http://localhost:8000")
    test_content = b"""# Test AI Governance Policy v1.0

## Section 1: Model Risk Management
All AI models must undergo independent validation before production deployment.

## Section 2: Bias Testing
Models with customer-facing outputs must be tested for demographic bias quarterly.

## Section 3: Human Oversight
High-risk AI decisions require human review before execution.
"""
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{base}/policies/upload",
            files={"file": ("test-policy.md", test_content, "text/plain")},
            params={"title": "Test AI Policy", "owner": "Compliance"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "policy_id" in data
    assert data["title"] == "Test AI Policy"
    assert data["status"] == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/code/lacuna && PYTHONPATH=. pytest tests/test_ai_governance.py::test_policy_upload_endpoint -v`

Expected: SKIP (integration test marker) or FAIL (endpoint doesn't exist).

- [ ] **Step 3: Add `content` column to policies DuckDB schema**

The policies table lacks a `content` column. Without it, `PolicyRepository.save()` silently drops the full text.

Modify `backend/storage/database.py` — in the `CREATE TABLE IF NOT EXISTS policies` statement (~line 60), add `content TEXT` after the `summary TEXT` line:

```sql
CREATE TABLE IF NOT EXISTS policies (
    policy_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    path VARCHAR,
    summary TEXT,
    content TEXT,
    status VARCHAR DEFAULT 'active',
    version VARCHAR DEFAULT '1.0',
    owner VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
)
```

Then modify `backend/storage/repositories.py` — in `PolicyRepository.save()` (~line 129), add `content` to the INSERT column list and values:

```python
def save(self, policy: Dict[str, Any]) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO policies
        (policy_id, title, path, summary, content, status, version, owner, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            policy["policy_id"],
            policy["title"],
            policy.get("path"),
            policy.get("summary"),
            policy.get("content"),
            policy.get("status", "active"),
            policy.get("version", "1.0"),
            policy.get("owner"),
            policy.get("created_at", datetime.now(timezone.utc).isoformat()),
            policy.get("updated_at"),
        ],
    )
    conn.commit()
```

Also update `_row_to_dict` in the same class to include the `content` field if the DB row has it.

**Note:** Existing DuckDB databases will need a migration — add `ALTER TABLE policies ADD COLUMN IF NOT EXISTS content TEXT` to the `migrate.py` file or run it manually on Railway.

- [ ] **Step 4: Add create_from_upload to PolicyService**

Modify `backend/services/policy_service.py`:

```python
import uuid

# Add this method to PolicyService class:
def create_from_upload(
    self,
    content: str,
    title: str,
    filename: str,
    owner: str | None = None,
) -> dict:
    """Create a new policy from uploaded file content."""
    policy_id = f"policy_{uuid.uuid4().hex[:8]}"
    policy = {
        "policy_id": policy_id,
        "title": title,
        "path": filename,
        "summary": content[:500],  # First 500 chars as summary
        "content": content,  # Full text — persisted in DuckDB + indexed in ChromaDB
        "status": "active",
        "version": "1.0",
        "owner": owner or "Unknown",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
    }
    self.policy_repo.save(policy)
    return policy
```

- [ ] **Step 5: Add POST /policies/upload route with vector store indexing**

Write the complete route in a single pass. Modify `backend/routes/policies.py` — add before the existing `GET /policies` route:

**Important API notes:**
- `vector_store` is a module-level global in `backend/state.py` (line 227): `from backend.state import vector_store`
- `VectorStore.add_document(doc_id, chunks, metadata)` takes a flat metadata dict applied to all chunks — NOT `add_documents()`

```python
from fastapi import UploadFile, File
from backend.state import vector_store

@router.post("/policies/upload")
async def upload_policy(
    file: UploadFile = File(...),
    title: str | None = None,
    owner: str | None = None,
    service=Depends(get_policy_service),
):
    """Upload an internal policy document as a gap analysis baseline."""
    content_bytes = await file.read()
    content = content_bytes.decode("utf-8", errors="replace")
    filename = file.filename or "untitled"
    policy_title = title or filename.rsplit(".", 1)[0]

    policy = service.create_from_upload(
        content=content,
        title=policy_title,
        filename=filename,
        owner=owner,
    )

    # Index in vector store for gap analysis retrieval
    try:
        if vector_store is not None:
            # Split on section boundaries for chunking
            sections = content.split("\n\n")
            chunks = []
            current = ""
            for section in sections:
                if len(current) + len(section) > 2000 and current:
                    chunks.append(current.strip())
                    current = section
                else:
                    current += "\n\n" + section if current else section
            if current.strip():
                chunks.append(current.strip())

            vector_store.add_document(
                doc_id=policy["policy_id"],
                chunks=chunks,
                metadata={
                    "policy_id": policy["policy_id"],
                    "filename": filename,
                    "source": "policy",
                    "jurisdiction": "INTERNAL",
                },
            )
    except Exception as e:
        logger.warning(f"Failed to index policy in vector store: {e}")

    return policy
```

- [ ] **Step 6: Run tests**

Run: `cd ~/code/lacuna && PYTHONPATH=. pytest tests/test_ai_governance.py -v`

Expected: PASS for unit tests. Integration test auto-skips via `@pytest.mark.skipif` (no `RUN_INTEGRATION_TESTS` env var).

- [ ] **Step 7: Commit**

```bash
cd ~/code/lacuna && git add backend/routes/policies.py backend/services/policy_service.py backend/storage/database.py backend/storage/repositories.py tests/test_ai_governance.py
git commit -m "feat: add policy upload endpoint

POST /policies/upload accepts text/markdown files as internal policy baselines.
Content persisted in DuckDB + indexed in ChromaDB for gap analysis retrieval.
Adds content column to policies schema."
```

---

### Task 3: Policy Upload CLI Command

**Files:**
- Modify: `cli/api/client.py` — add `upload_policy()` method
- Modify: `cli/main.py` — add `upload-policy` command
- Test: `tests/test_ai_governance.py` (append)

- [ ] **Step 1: Add upload_policy to RegAtlasClient**

Modify `cli/api/client.py` — add method before `close()`:

```python
def upload_policy(
    self,
    file_path: Path,
    title: str | None = None,
    owner: str | None = None,
) -> Dict[str, Any]:
    """Upload an internal policy document."""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/octet-stream")}
        params = {}
        if title:
            params["title"] = title
        if owner:
            params["owner"] = owner
        response = self.client.post(
            f"{self.base_url}/policies/upload",
            files=files,
            params=params,
            timeout=120,
        )
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 2: Add upload-policy CLI command**

Modify `cli/main.py` — add after the `list_policies` command:

```python
@app.command()
def upload_policy(
    file: Path = typer.Argument(..., help="Path to policy document (PDF, TXT, MD)"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Policy title (defaults to filename)"),
    owner: Optional[str] = typer.Option(None, "--owner", help="Policy owner (e.g., 'Compliance')"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL"),
):
    """Upload an internal policy document as a gap analysis baseline."""
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    url = api_url or get_api_url()
    client = RegAtlasClient(base_url=url)

    try:
        with console.status(f"[bold green]Uploading policy {file.name}..."):
            result = client.upload_policy(file, title=title, owner=owner)

        console.print(f"[green]✓[/green] Policy uploaded: {result['title']}")
        console.print(f"[cyan]Policy ID:[/cyan] {result['policy_id']}")
        console.print(f"[cyan]Status:[/cyan] {result['status']}")
        console.print(f"[cyan]Version:[/cyan] {result['version']}")
        console.print(f"\n[dim]Run gap analysis:[/dim] lacuna gap <circular-id> {result['policy_id']} --policy")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
```

- [ ] **Step 3: Run existing CLI tests (if any) + manual smoke test**

Run: `cd ~/code/lacuna && PYTHONPATH=. python -m cli.main upload-policy --help`

Expected: Help text shows file argument + `--title`, `--owner` options.

- [ ] **Step 4: Commit**

```bash
cd ~/code/lacuna && git add cli/api/client.py cli/main.py
git commit -m "feat: add upload-policy CLI command

lacuna upload-policy <file> --title 'X' --owner 'Y'
Uploads internal policy as gap analysis baseline."
```

---

### Task 4: End-to-End Verification

This task verifies the full workflow works together: upload policy → run gap analysis → get AI-governance-categorised output.

- [ ] **Step 1: Run all unit tests**

Run: `cd ~/code/lacuna && PYTHONPATH=. pytest tests/ -v -k "not INTEGRATION and not browser"`

Expected: All PASS.

- [ ] **Step 2: Run e2e tests**

Run: `cd ~/code/lacuna && REG_ATLAS_NO_LLM=1 DATA_DIR=/tmp/reg_atlas_data CHROMA_PERSIST_DIR=/tmp/reg_atlas_data/db/chroma PYTHONPATH=. pytest tests/e2e_reg_atlas.py -q`

Expected: PASS.

- [ ] **Step 3: Local smoke test (with LLM)**

Start server locally and test the full pipeline:

```bash
cd ~/code/lacuna
uv run uvicorn backend.main:app --port 8000 &

# Upload a test policy
curl -X POST "http://localhost:8000/policies/upload" \
  -F "file=@demo-docs/codex-argentum-v1.txt;type=text/plain" \
  -F "title=Codex Argentum v1.1" \
  -o /tmp/policy-upload.json

# Get the policy ID
POLICY_ID=$(python3 -c "import json; print(json.load(open('/tmp/policy-upload.json'))['policy_id'])")

# Run gap analysis: HKMA Consumer Protection vs uploaded policy
# NOTE: API does not resolve aliases — use full UUID from CLAUDE.md
# hkma-cp = 962e5a48-c8b9-4448-95af-75ccbc772c0a (check CLAUDE.md for current IDs)
CIRCULAR_ID="962e5a48-c8b9-4448-95af-75ccbc772c0a"
curl -X POST "http://localhost:8000/gap-analysis" \
  -H "Content-Type: application/json" \
  -d "{\"circular_doc_id\": \"$CIRCULAR_ID\", \"baseline_id\": \"$POLICY_ID\", \"is_policy_baseline\": true}" \
  -o /tmp/gap-result.json

# Verify output has findings with AI governance categories
python3 -c "
import json
r = json.load(open('/tmp/gap-result.json'))
print(f'Status: {r[\"status\"]}')
print(f'Findings: {r[\"summary\"]}')
for f in r.get('findings', [])[:3]:
    print(f'  {f[\"status\"]}: {f[\"description\"][:80]}')
"
```

Expected: Gap analysis completes with Full/Partial/Gap findings. Requirement types should now include AI governance categories where applicable.

- [ ] **Step 4: Deploy to Railway**

```bash
cd ~/code/lacuna && railway up --detach
```

- [ ] **Step 5: Final commit + push**

```bash
cd ~/code/lacuna && git push
```

---

## Out of Scope (Phase 2 — Week 2+ at HSBC)

These are deferred deliberately — they benefit from Tobin's input on what he actually needs:

1. **Delta mode** — "new regulation dropped, what changed vs existing baseline". Needs Tobin to clarify: delta against previous version of same regulation, or delta against current policy?
2. **Impact brief** — LLM-generated narrative with paragraph-level citations. Current gap analysis output already has provenance citations per finding — brief is presentation layer on top.
3. **PDF policy upload** — current implementation handles text/markdown. PDF parsing (pypdf) is already in the codebase for regulatory docs; extending to policies is straightforward.
4. **Policy versioning** — track v1.0 → v1.1 → v2.0 of HSBC's internal standard over time.
