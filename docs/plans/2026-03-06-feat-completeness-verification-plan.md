---
title: "feat: Completeness Verification Workflow"
type: feat
status: active
date: 2026-03-06
origin: docs/brainstorms/2026-03-06-completeness-verification-brainstorm.md
---

# feat: Completeness Verification Workflow

## Overview

Add a two-step completeness gate to Lacuna's gap analysis workflow to address the **silent omission** failure mode: when the LLM misses a requirement buried in a regulatory circular, the gap report looks clean but has a hidden hole.

Two deliverables:
1. **`lacuna decompose <doc_id>`** — CLI command + `/decompose` endpoint that surfaces all atomic requirements extracted from a circular as a numbered, reviewable list anchored to source snippets. Tobin reviews this before running gap analysis.
2. **Adversarial completeness pass** — runs automatically after gap analysis; a second LLM call asks "what requirements in this circular are NOT reflected in our findings?" and surfaces additions as flagged items.

(see brainstorm: `docs/brainstorms/2026-03-06-completeness-verification-brainstorm.md`)

---

## Key Design Decisions (from brainstorm)

### Decision 1: Decompose reads stored requirements (not re-extraction)
Requirements are already extracted and stored in the `documents` DuckDB row at upload time (`doc["requirements"]`). The decompose endpoint reads these and reformats them as a numbered, indexed list. This is fast (no LLM call), free, and consistent with what gap analysis actually uses.

An optional `--fresh` flag triggers LLM re-extraction via `asyncio.to_thread()` (mirroring the existing pattern — see CLAUDE.md gotcha about sync OpenAI calls blocking uvicorn). Use `--fresh` sparingly; it has 2–5 min latency on large docs.

**Why not re-extract by default:** gap analysis reads stored requirements; showing Tobin a re-extracted list would create a discrepancy between what he reviewed and what the analysis actually ran against.

### Decision 2: Source anchoring via `source_snippet` + `chunk_index`
No paragraph IDs exist in the current schema. The closest handles are `source_snippet` (≤200 char quoted excerpt, stored per requirement) and `chunk_index` (from ChromaDB metadata). The `AtomicRequirement` model will expose both as the source anchor. A future improvement could add a `paragraph_ref` field during upload.

### Decision 3: Adversarial pass as an opt-in flag on gap analysis (not always-on)
Add `include_completeness_audit: bool = False` to `GapAnalysisRequest`. Default off to preserve demo latency. The CLI `lacuna gap` command gets `--audit` flag to turn it on. `lacuna decompose` will also call it standalone.

**Adversarial pass design (from learnings KB):** Use "Prescription Discipline" — the prompt must explicitly ask the LLM to list what it is *not* flagging as well as what it is, with a max-items cap (5) to prevent inclusion-bias flooding. Same model as gap analysis (`gap_analysis_model`).

### Decision 4: No section-coverage heuristic
(see brainstorm) — noisy signal, explicitly rejected.

---

## Acceptance Criteria

### `/decompose` endpoint
- [ ] `POST /decompose` accepts `{"doc_id": "<uuid_or_alias>", "fresh": false}`
- [ ] Returns `DecomposeResponse` with numbered `requirements` list (1-based `index`, `description`, `source_snippet`, `requirement_type`, `mandatory`)
- [ ] Fast path (stored requirements): responds in <500ms
- [ ] Fresh path: wraps LLM extraction in `asyncio.to_thread()`; responds within Railway's 5-min HTTP timeout
- [ ] Returns 404 if doc_id not found, 400 for bad input

### `lacuna decompose` CLI
- [ ] `lacuna decompose <doc_id>` renders a Rich numbered table (index, type, description, mandatory, source snippet)
- [ ] `--json` flag outputs raw JSON
- [ ] `--fresh` flag triggers re-extraction
- [ ] Aliases resolve (same as `lacuna gap` — uses `ALIASES` dict in CLI)
- [ ] Client timeout set to 300s (not default 30s) for `--fresh` path

### Adversarial completeness pass
- [ ] New method `RequirementExtractor.adversarial_completeness_check(circular_text, findings)` returns list of potential omissions (max 5)
- [ ] `POST /gap-analysis` with `include_completeness_audit: true` appends `completeness_audit` field to `GapAnalysisResponse`
- [ ] Prompt enforces "Prescription Discipline": includes explicit "what I am NOT flagging" section, hard cap of 5 items
- [ ] `lacuna gap --audit` flag enables it
- [ ] `lacuna gap --audit --verbose` includes reasoning per flagged item

### Wiring
- [ ] Route registered in `routes/__init__.py` and `main.py`
- [ ] Service wired in `state.py` with lazy-import DI pattern
- [ ] New schemas exported in `models/schemas.py` `__all__`
- [ ] All OpenRouter model IDs use `anthropic/claude-sonnet-4.6` format (not date suffix)

---

## Implementation Plan

### Phase 1: Schemas (backend/models/schemas.py)

Add to `backend/models/schemas.py`:

```python
class AtomicRequirement(BaseModel):
    index: int                           # 1-based sequence
    requirement_id: str
    requirement_type: str | None = None
    description: str
    source_snippet: str | None = None    # quoted anchor from circular
    chunk_index: int | None = None       # ChromaDB chunk handle
    mandatory: str | None = None         # "Yes"/"No"/"Unknown"
    confidence: str | None = None        # "High"/"Medium"/"Low"

class DecomposeRequest(BaseModel):
    doc_id: str
    fresh: bool = False                  # re-run LLM extraction vs read stored

class DecomposeResponse(BaseModel):
    doc_id: str
    generated_at: str
    total: int
    fresh: bool
    requirements: List[AtomicRequirement]

class CompletenessFlag(BaseModel):
    description: str                     # the suspected omission
    reasoning: str | None = None
    source_hint: str | None = None       # where in circular it might be

class CompletenessAudit(BaseModel):
    flagged: List[CompletenessFlag]
    not_flagged_rationale: str | None = None  # prescription discipline
    model: str
```

Update `GapAnalysisResponse` to add:
```python
completeness_audit: CompletenessAudit | None = None
```

Update `GapAnalysisRequest` to add:
```python
include_completeness_audit: bool = False
```

Add all new models to `__all__`.

---

### Phase 2: RequirementExtractor — adversarial_completeness_check()

Add to `backend/requirement_extractor.py`:

```python
def adversarial_completeness_check(
    self,
    circular_text: str,
    findings: List[Dict[str, Any]],
    force_basic: bool = False,
) -> Dict[str, Any]:
    """
    Adversarial pass: given the circular text and existing gap findings,
    identify regulatory requirements NOT reflected in the findings.
    Returns at most 5 flagged items with prescription discipline rationale.
    """
```

**Prompt design (critical — see learnings KB on inclusion bias):**

```
You are an adversarial regulatory auditor. Your job is to find what was MISSED.

Below is a regulatory circular and a gap analysis that has already been performed.
Identify requirements in the circular that are NOT addressed in the findings list.

Circular text:
{circular_text[:8000]}

Requirements already analyzed ({len(findings)} items):
{formatted_findings}

Instructions:
- List AT MOST 5 requirements you believe are missing from the analysis.
- For each, quote the relevant circular text (<100 chars).
- ALSO list 2-3 things you considered flagging but decided NOT to flag, and why.
  (This prevents false-positive flooding.)
- If you find nothing missing, say so explicitly — do not invent omissions.

Response format (JSON only):
{
  "flagged": [
    {"description": "...", "reasoning": "...", "source_hint": "quoted text"}
  ],
  "not_flagged_rationale": "Considered X but did not flag because ... Considered Y but ..."
}
```

---

### Phase 3: DecomposeService (new file)

**`backend/services/decompose_service.py`:**

```python
class DecomposeService:
    def __init__(self, doc_repo, req_extractor):
        self.doc_repo = doc_repo
        self.req_extractor = req_extractor

    async def decompose(self, doc_id: str, fresh: bool = False) -> DecomposeResponse:
        doc = self.doc_repo.get(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        if fresh:
            # Re-run LLM extraction — wrap sync call
            import asyncio
            text = doc.get("raw_text") or doc.get("content", "")
            extracted = await asyncio.to_thread(
                self.req_extractor.extract_requirements,
                text,
                doc.get("jurisdiction", "Unknown")
            )
            requirements = extracted.get("requirements", [])
        else:
            # Read stored requirements (fast path)
            requirements = _extract_requirements_from_doc(doc)

        atomic = [
            AtomicRequirement(
                index=i + 1,
                requirement_id=req.get("requirement_id", str(uuid4())),
                requirement_type=req.get("requirement_type"),
                description=req.get("description", ""),
                source_snippet=req.get("source_snippet"),
                mandatory=req.get("mandatory"),
                confidence=req.get("confidence"),
            )
            for i, req in enumerate(requirements)
        ]
        return DecomposeResponse(
            doc_id=doc_id,
            generated_at=datetime.utcnow().isoformat(),
            total=len(atomic),
            fresh=fresh,
            requirements=atomic,
        )
```

Note: `_extract_requirements_from_doc` is already defined in `state.py:574` — import it or inline the logic.

---

### Phase 4: Route (new file)

**`backend/routes/decompose.py`:**

```python
from fastapi import APIRouter, HTTPException, Depends
from backend.state import get_decompose_service
from backend.models.schemas import DecomposeRequest, DecomposeResponse

router = APIRouter()
_decompose_cache: dict = {}

@router.post("/decompose", response_model=DecomposeResponse)
async def decompose(request: DecomposeRequest, service=Depends(get_decompose_service)):
    cache_key = (request.doc_id, request.fresh)
    if cache_key in _decompose_cache and not request.fresh:
        return _decompose_cache[cache_key]
    try:
        result = await service.decompose(request.doc_id, fresh=request.fresh)
        if not request.fresh:
            _decompose_cache[cache_key] = result
        return result
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 400, detail=str(e))
    except Exception as e:
        logger.error(f"Decompose error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

### Phase 5: Wire into state.py + main.py + routes/__init__.py

**`backend/state.py`** — add after existing service sentinels:
```python
_decompose_service: Optional[Any] = None

def get_decompose_service():
    global _decompose_service
    if _decompose_service is None:
        from backend.services.decompose_service import DecomposeService
        _decompose_service = DecomposeService(
            doc_repo=get_document_repo(),
            req_extractor=req_extractor,   # module-level global, already initialized
        )
    return _decompose_service
```

**`backend/routes/__init__.py`** — append:
```python
from .decompose import router as decompose_router
# add "decompose_router" to __all__
```

**`backend/main.py`** — append in imports and include_router block:
```python
from backend.routes import ..., decompose_router
app.include_router(decompose_router, tags=["decompose"])
```

---

### Phase 6: Wire adversarial pass into gap_analysis_service.py

In `gap_analysis_service.perform_gap_analysis()`, after building `findings`, add:

```python
completeness_audit = None
if include_completeness_audit:
    circular_text = circular_doc.get("content", "")
    findings_dicts = [f.model_dump() for f in gap_findings]
    raw = await asyncio.to_thread(
        self.req_extractor.adversarial_completeness_check,
        circular_text,
        findings_dicts,
    )
    completeness_audit = CompletenessAudit(
        flagged=[CompletenessFlag(**f) for f in raw.get("flagged", [])],
        not_flagged_rationale=raw.get("not_flagged_rationale"),
        model=self.req_extractor.gap_analysis_model,
    )
```

Pass `include_completeness_audit` through from the route to the service method signature.

---

### Phase 7: CLI — lacuna decompose command (cli/main.py + cli/api/client.py)

**`cli/api/client.py`** — add method:
```python
def decompose(self, doc_id: str, fresh: bool = False) -> Dict[str, Any]:
    response = self.client.post(
        f"{self.base_url}/decompose",
        json={"doc_id": doc_id, "fresh": fresh},
        timeout=300 if fresh else 30,   # fresh path can be slow
    )
    response.raise_for_status()
    return response.json()
```

**`cli/main.py`** — add command (mirror `gap` pattern):
```python
@app.command()
def decompose(
    doc_id: str = typer.Argument(..., help="Document ID or alias to decompose"),
    fresh: bool = typer.Option(False, "--fresh", help="Re-run LLM extraction (slow)"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL"),
):
    """List all atomic requirements extracted from a regulatory circular."""
    url = api_url or get_api_url()
    doc_id = ALIASES.get(doc_id, doc_id)   # resolve alias
    client = RegAtlasClient(base_url=url)
    try:
        with console.status(f"[bold green]Decomposing {doc_id}..."):
            result = client.decompose(doc_id, fresh=fresh)
        if json_output:
            console.print_json(json.dumps(result))
            return
        # Rich table: index | type | mandatory | description | source snippet
        table = Table(title=f"Requirements — {doc_id} ({result['total']} total{'  [fresh]' if fresh else ''})")
        table.add_column("#", style="dim", width=4)
        table.add_column("Type", width=20)
        table.add_column("Mand.", width=6)
        table.add_column("Description")
        table.add_column("Source (excerpt)", style="dim", width=40)
        for req in result["requirements"]:
            table.add_row(
                str(req["index"]),
                req.get("requirement_type") or "—",
                req.get("mandatory") or "—",
                req["description"],
                (req.get("source_snippet") or "")[:60],
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
```

Also add `--audit` flag to the existing `gap` command:
```python
audit: bool = typer.Option(False, "--audit", help="Run adversarial completeness check after gap analysis"),
```
Pass through to `client.gap_analysis(..., include_completeness_audit=audit)` and render audit findings below the main table if present.

---

## System-Wide Impact

### Interaction graph
`POST /decompose` → `DecomposeService.decompose()` → `DocumentRepository.get()` → (fast path) read `doc["requirements"]` → format. Fresh path: `asyncio.to_thread(req_extractor.extract_requirements)` → this is the same code path as upload-time extraction. No side effects on the stored document unless you add a "save fresh results" option (not in scope).

`POST /gap-analysis` with `include_completeness_audit=true` → `perform_gap_analysis()` (existing chain) → `asyncio.to_thread(adversarial_completeness_check)` after findings are built. Adds one extra LLM call (~$0.002 on Sonnet 4.6 for a typical circular).

### Error propagation
- If adversarial pass fails, the gap analysis result should still return — catch the exception inside `perform_gap_analysis` and set `completeness_audit=None` with a warning log. Don't let an audit failure break the primary response.
- If decompose `--fresh` times out (Railway 5-min limit), the client raises `httpx.ReadTimeout` — CLI should catch and print a friendly "Try without --fresh or wait for Railway warmup" message.

### State lifecycle risks
Fresh path re-runs extraction but does NOT overwrite stored requirements in DuckDB. The stored requirements are the source of truth for gap analysis. This is intentional — avoids inconsistency between what Tobin reviewed and what gap analysis ran against.

### Integration test scenarios
1. `lacuna decompose hkma-cp` → should return 7 requirements (matching known count for that doc)
2. `lacuna gap hkma-cp demo-baseline --audit` → should return gap results + `completeness_audit` with 0–5 flagged items
3. Fresh path on small doc → should return requirements, possibly different count from stored
4. Decompose on unknown doc_id → should return 404
5. Adversarial pass on all-Full gap result → should return `flagged: []` with explicit not_flagged_rationale

---

## Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `backend/models/schemas.py` | Modify | Add `AtomicRequirement`, `DecomposeRequest`, `DecomposeResponse`, `CompletenessFlag`, `CompletenessAudit`; extend `GapAnalysisRequest` + `GapAnalysisResponse` |
| `backend/routes/decompose.py` | **Create** | New route file with in-memory cache |
| `backend/routes/__init__.py` | Modify | Export `decompose_router` |
| `backend/main.py` | Modify | Import + register `decompose_router` |
| `backend/services/decompose_service.py` | **Create** | `DecomposeService.decompose()` |
| `backend/requirement_extractor.py` | Modify | Add `adversarial_completeness_check()` |
| `backend/services/gap_analysis_service.py` | Modify | Wire `include_completeness_audit` param + adversarial pass call |
| `backend/state.py` | Modify | Add `_decompose_service` sentinel + `get_decompose_service()` |
| `cli/api/client.py` | Modify | Add `decompose()` method (300s timeout on fresh) |
| `cli/main.py` | Modify | Add `decompose` command; add `--audit` to `gap` command |

---

## Gotchas (from research)

1. **Sync LLM calls block uvicorn** — all LLM calls in the decompose/adversarial paths MUST use `asyncio.to_thread()`. This is documented in `CLAUDE.md`. The `extract_requirements()` and `adversarial_completeness_check()` methods on `RequirementExtractor` are sync; wrap them in the service layer.
2. **OpenRouter model IDs** — use `anthropic/claude-sonnet-4.6` not `anthropic/claude-sonnet-4-20250514`. Wrong ID = silent all-Gap results. See `~/docs/solutions/openrouter-model-ids.md`.
3. **3-step router registration** — route file → `routes/__init__.py` → `main.py`. Miss any step and the endpoint simply doesn't exist (no error).
4. **CLI client default timeout is 30s** — the fresh decompose path needs 300s. Set per-method, not globally.
5. **`_extract_requirements_from_doc` lives in `state.py:574`** — import it into `decompose_service.py` from `backend.state` to avoid duplicating the JSON-parsing logic.
6. **Adversarial inclusion bias** — the prompt MUST include "what I am NOT flagging" section and a hard cap of 5 items. Without this, the LLM floods Tobin with false positives. See `~/docs/solutions/ai-tooling/llm-council-judge-over-aggregation.md`.
7. **Cache invalidation** — `_decompose_cache` and `_gap_cache` are in-memory and reset on Railway restart. This is the existing pattern; no change needed.
8. **`raw_text`/`content` field for adversarial pass** — verify which field stores the full circular text on the document record. It may be `raw_extraction` (the chunked extraction log) rather than the original text. Check `documents` DuckDB schema before implementing.

---

## Dependencies & Risks

- **No new PyPI deps** — uses existing `openai` (OpenRouter), `fastapi`, `typer`, `rich`, `httpx`.
- **No Railway config changes** — no new env vars needed.
- **Risk: circular text not stored on document record** — if the full text isn't in DuckDB, the adversarial pass has nothing to work with. Mitigation: check `doc` dict fields during implementation; fall back to concatenated `source_snippet` values from the findings as a proxy.
- **Risk: fresh path timeout** — mitigated by Railway's 5-min timeout and 300s client timeout. Document as a known limitation in the skill file.

---

## Sources & References

### Origin
- **Brainstorm:** `docs/brainstorms/2026-03-06-completeness-verification-brainstorm.md`
  - Key decisions carried forward: two-step decomposition gate; adversarial second pass; no section-coverage heuristic; reliability over convenience.

### Internal References
- `backend/services/gap_analysis_service.py` — service pattern to follow
- `backend/routes/gap_analysis.py` — route + cache pattern
- `backend/state.py:574` — `_extract_requirements_from_doc` helper
- `cli/main.py` — `gap` command as CLI pattern template
- `CLAUDE.md` — sync LLM call gotcha, Railway timeout, OpenRouter model IDs

### Institutional Learnings
- `~/docs/solutions/openrouter-model-ids.md` — model ID format critical
- `~/docs/solutions/ai-tooling/llm-council-judge-over-aggregation.md` — adversarial prompt design
- `~/docs/solutions/railway.md` — Railway deployment gotchas
