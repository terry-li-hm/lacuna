---
title: "feat: Confirmed Requirement List"
type: feat
status: active
date: 2026-03-07
origin: docs/brainstorms/2026-03-06-completeness-verification-brainstorm.md
---

# feat: Confirmed Requirement List

## Overview

Tobin reviews the decomposed requirement list interactively via `lacuna confirm <doc_id>`, accepting/editing/rejecting each item. The confirmed list is saved server-side. Gap analysis can then run against the confirmed list (`use_confirmed: true`) instead of the raw stored requirements — closing the loop on the completeness verification workflow.

## Design Decisions

- **Storage:** New DuckDB table `confirmed_requirements (doc_id PK, requirements JSON, confirmed_at, confirmed_by)`
- **Interaction:** `lacuna confirm` calls `POST /decompose` to get the list, walks each item interactively (`y/n/e`), then `POST /confirm/<doc_id>` with the result
- **Gap analysis integration:** `use_confirmed: bool = False` on `GapAnalysisRequest`; when true, fork at the `_extract_requirements_from_doc` call to read from `confirmed_requirements` table instead
- **Cache key:** Must include `use_confirmed` to prevent confirmed runs returning cached unconfirmed results

## Acceptance Criteria

- [ ] `lacuna confirm hkma-cp` walks each requirement interactively: `[y]es / [n]o / [e]dit`
- [ ] Edit flow prompts for replacement text, stores edited version
- [ ] Rejected items excluded from confirmed list
- [ ] `POST /confirm/<doc_id>` saves to DuckDB, overwrites any prior confirmed list for that doc
- [ ] `GET /confirm/<doc_id>` returns saved confirmed list (404 if none)
- [ ] `lacuna gap hkma-cp demo-baseline --use-confirmed` runs gap analysis against confirmed list
- [ ] `POST /gap-analysis` with `use_confirmed: true` and no saved confirmed list → 400 with clear message
- [ ] Cache key in `_gap_cache` includes `use_confirmed` flag
- [ ] `lacuna preflight` still passes after changes

## Implementation Phases

### Phase 1 — Database (backend/storage/database.py)

Add to `init_db()`:
```sql
CREATE TABLE IF NOT EXISTS confirmed_requirements (
    doc_id VARCHAR NOT NULL,
    confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_by VARCHAR,
    requirements JSON NOT NULL,
    PRIMARY KEY (doc_id)
)
```
DuckDB uses `?` for positional params. `conn.commit()` required after writes.

### Phase 2 — Repository (backend/storage/repositories.py)

New class `ConfirmedRequirementRepository`:
```python
def save(self, doc_id: str, requirements: list, confirmed_by: str | None = None) -> None
def get(self, doc_id: str) -> dict | None  # returns {"doc_id", "requirements", "confirmed_at"} or None
def delete(self, doc_id: str) -> None
```
JSON encode `requirements` on write, `json.loads()` with try/except on read. Follow `DocumentRepository._row_to_dict()` pattern exactly.

### Phase 3 — Schemas (backend/models/schemas.py)

```python
class ConfirmRequest(BaseModel):
    requirements: List[AtomicRequirement]
    confirmed_by: str | None = None

class ConfirmResponse(BaseModel):
    doc_id: str
    confirmed_at: str
    total: int

class ConfirmedListResponse(BaseModel):
    doc_id: str
    confirmed_at: str
    confirmed_by: str | None
    total: int
    requirements: List[AtomicRequirement]
```

Add `use_confirmed: bool = False` to `GapAnalysisRequest`.
Add all new models to `__all__`.

### Phase 4 — Service (backend/services/confirm_service.py)

```python
class ConfirmService:
    def __init__(self, doc_repo, confirm_repo):
        # No state imports — take repos as args (circular import guard)
        self.doc_repo = doc_repo
        self.confirm_repo = confirm_repo

    def save(self, doc_id, requirements, confirmed_by=None) -> ConfirmResponse:
        if not self.doc_repo.get(doc_id):
            raise ValueError(f"Document {doc_id} not found")
        self.confirm_repo.save(doc_id, [r.model_dump() for r in requirements], confirmed_by)
        return ConfirmResponse(doc_id=doc_id, confirmed_at=..., total=len(requirements))

    def get(self, doc_id) -> ConfirmedListResponse:
        row = self.confirm_repo.get(doc_id)
        if not row:
            raise ValueError(f"No confirmed list for {doc_id}")
        ...
```

### Phase 5 — Route (backend/routes/confirm.py)

```python
router = APIRouter()

@router.post("/confirm/{doc_id}", response_model=ConfirmResponse)
async def save_confirmed(doc_id: str, request: ConfirmRequest, service=Depends(get_confirm_service)):
    ...

@router.get("/confirm/{doc_id}", response_model=ConfirmedListResponse)
async def get_confirmed(doc_id: str, service=Depends(get_confirm_service)):
    ...
```
ValueError → 404 if "not found", 400 otherwise. No cache needed (DB reads are fast).

### Phase 6 — Wire (state.py, routes/__init__.py, main.py)

**state.py** — add singleton factory:
```python
_confirm_service: Optional[Any] = None

def get_confirm_service():
    global _confirm_service
    if _confirm_service is None:
        from backend.services.confirm_service import ConfirmService
        _confirm_service = ConfirmService(
            doc_repo=get_document_repo(),
            confirm_repo=get_confirm_repo(),
        )
    return _confirm_service

_confirm_repo: Optional[Any] = None

def get_confirm_repo():
    global _confirm_repo
    if _confirm_repo is None:
        from backend.storage.repositories import ConfirmedRequirementRepository
        _confirm_repo = ConfirmedRequirementRepository()
    return _confirm_repo
```

**routes/__init__.py** — add `from .confirm import router as confirm_router` + `__all__` entry.
**main.py** — `app.include_router(confirm_router, tags=["confirm"])`.

### Phase 7 — Gap Analysis Integration (backend/services/gap_analysis_service.py)

Fork at requirement extraction:
```python
if use_confirmed:
    confirmed = confirm_repo.get(circular_doc_id)
    if not confirmed:
        raise ValueError(f"No confirmed requirement list for {circular_doc_id}. Run 'lacuna confirm' first.")
    circular_requirements = confirmed["requirements"]
else:
    circular_requirements = _extract_requirements_from_doc(circular_doc)
```

**Cache key fix** (backend/routes/gap_analysis.py line ~48):
```python
cache_key = (
    request.circular_doc_id,
    request.baseline_id,
    request.is_policy_baseline,
    request.include_amendments,
    request.use_confirmed,   # ADD THIS
)
```

`GapAnalysisService.perform_gap_analysis()` signature gains `use_confirmed: bool = False, confirm_repo=None`.
The route passes both through from the request.

### Phase 8 — CLI (cli/main.py + cli/api/client.py)

**client.py** — two new methods:
```python
def save_confirmed(self, doc_id: str, requirements: list, confirmed_by: str | None = None) -> dict:
    response = self.client.post(f"{self.base_url}/confirm/{doc_id}",
        json={"requirements": requirements, "confirmed_by": confirmed_by})
    response.raise_for_status()
    return response.json()

def get_confirmed(self, doc_id: str) -> dict:
    response = self.client.get(f"{self.base_url}/confirm/{doc_id}")
    response.raise_for_status()
    return response.json()
```

**cli/main.py** — new `confirm` command:
```python
@app.command()
def confirm(
    doc_id: str = typer.Argument(..., help="Document ID or alias"),
    confirmed_by: str | None = typer.Option(None, "--by", help="Reviewer name"),
    api_url: str | None = typer.Option(None, "--api-url"),
):
    """Interactively review and confirm the requirement list for a circular."""
    url = api_url or get_api_url()
    doc_id = ALIASES.get(doc_id, doc_id)
    client = RegAtlasClient(base_url=url)
    try:
        # 1. Fetch decomposed list
        with console.status("Fetching requirements..."):
            decomposed = client.decompose(doc_id)
        reqs = decomposed["requirements"]
        console.print(f"\n[bold]Reviewing {len(reqs)} requirements for {doc_id}[/bold]")
        console.print("[dim]y = accept  n = reject  e = edit[/dim]\n")

        confirmed = []
        for req in reqs:
            console.print(f"[bold cyan][{req['index']}][/bold cyan] {req['description']}")
            if req.get("source_snippet"):
                console.print(f"  [dim]↳ {req['source_snippet'][:80]}[/dim]")
            choice = input("  [y/n/e]: ").strip().lower()
            if choice == "y":
                confirmed.append(req)
            elif choice == "e":
                new_text = input("  New description: ").strip()
                if new_text:
                    req["description"] = new_text
                    confirmed.append(req)
            # "n" → skip

        console.print(f"\n[green]Confirmed {len(confirmed)}/{len(reqs)} requirements.[/green]")
        with console.status("Saving..."):
            client.save_confirmed(doc_id, confirmed, confirmed_by)
        console.print(f"[green]Saved.[/green] Run: lacuna gap {doc_id} <baseline> --use-confirmed")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
```

Also add `--use-confirmed` flag to the `gap` command:
```python
use_confirmed: bool = typer.Option(False, "--use-confirmed", help="Use confirmed requirement list"),
```
Pass through to `client.gap_analysis(..., use_confirmed=use_confirmed)`.

## Gotchas (from research)

1. **Circular import guard** — `confirm_service.py` must NOT import `backend.state`. Take `doc_repo` and `confirm_repo` as constructor args only.
2. **`conn.commit()` required** after every DuckDB write — don't omit.
3. **Cache key** in `_gap_cache` must include `use_confirmed` — otherwise confirmed runs return cached unconfirmed results.
4. **`POST /decompose` not `GET`** — the CLI confirm command must call `client.decompose()` (POST) not a GET.
5. **3-step router registration** — routes file → `__init__.py` → `main.py`.
6. **`input()` in CLI confirm** — cannot use inside `console.status()` context manager; prompt the user outside of it.

## Verification

```bash
cd ~/code/lacuna
uv run python -c "from backend.routes.confirm import router; from backend.services.confirm_service import ConfirmService; print('OK')"
uv run python -m pytest backend/tests/ -v --tb=short 2>&1 | tail -5
```
