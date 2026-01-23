---
title: feat: Add CLI Tool for RegAtlas API Testing
type: feat
date: 2026-01-23
---

# Add CLI Tool for RegAtlas API Testing

## Overview

Build a comprehensive CLI tool (`regatlas`) for rapid testing and iteration with the deployed RegAtlas API at https://reg-atlas.onrender.com. The CLI will provide a fast, developer-friendly interface for all API operations without needing to open a browser or write curl commands.

## Problem Statement / Motivation

Currently, testing the RegAtlas API requires:
- Opening the web UI in a browser
- Writing manual curl commands
- Managing multipart form data for file uploads
- Parsing JSON responses manually

For rapid development and testing cycles, especially during API iteration, a dedicated CLI tool will:
- Reduce testing friction from minutes to seconds
- Enable scripting and automation
- Provide better error messages and progress indicators
- Support both local (`localhost:8000`) and production (`reg-atlas.onrender.com`) endpoints
- Make the tool more accessible to technical users who prefer terminal interfaces

## Proposed Solution

Create a Python-based CLI tool using Typer that wraps all RegAtlas API endpoints with intuitive commands and beautiful output formatting.

### Core Commands

1. **upload** - Upload and process regulatory documents
2. **query** - Query documents with semantic search
3. **compare** - Compare requirements between jurisdictions
4. **stats** - Show system statistics
5. **list** - List all processed documents
6. **config** - Configure API endpoint and settings

### Technical Approach

- **CLI Framework**: Typer (modern, type-safe, great error messages)
- **HTTP Client**: httpx (async support, better than requests)
- **Progress**: Rich (beautiful terminal UI, progress bars, tables)
- **Config**: TOML file in `~/.config/regatlas/config.toml`
- **Installation**: `uv tool install` for global CLI command

## Technical Considerations

### Architecture

```
cli/
├── __init__.py
├── main.py              # Typer app and entry point
├── commands/
│   ├── __init__.py
│   ├── upload.py        # Upload command logic
│   ├── query.py         # Query command logic
│   ├── compare.py       # Compare command logic
│   ├── stats.py         # Stats and list commands
│   └── config.py        # Config management command
├── api/
│   ├── __init__.py
│   └── client.py        # API client wrapper
├── ui/
│   ├── __init__.py
│   └── display.py       # Rich formatters and displays
└── config.py            # Config file management
```

### Configuration Management

Store configuration in `~/.config/regatlas/config.toml`:

```toml
[api]
base_url = "https://reg-atlas.onrender.com"
timeout = 30

[display]
color = true
verbose = false
```

Support environment variable override: `REGATLAS_API_URL`

### File Upload Strategy

For PDF and text uploads:
1. Validate file exists and is readable
2. Detect file type from extension
3. Use httpx multipart upload with progress callback
4. Stream response for real-time feedback
5. Display extracted requirements in formatted table

### Error Handling

- Connection errors → Suggest checking API URL with helpful message
- 404 errors → Clear message about missing documents/jurisdictions
- 500 errors → Display server error with suggestion to retry
- Timeout errors → Show progress and allow interrupt with Ctrl+C
- File errors → Validate before upload, clear messages

### Output Formatting

Use Rich library for:
- **Tables**: Display query results, document lists, comparisons
- **Progress bars**: File uploads, long-running queries
- **Syntax highlighting**: JSON output in verbose mode
- **Colors**: Success (green), errors (red), info (blue)
- **Spinners**: Loading indicators for API calls

## Acceptance Criteria

### Functional Requirements

- [ ] `regatlas upload <file> --jurisdiction "Hong Kong"` uploads and displays requirements
- [ ] `regatlas query "capital requirements"` returns formatted results with summary
- [ ] `regatlas query "..." --jurisdiction "Singapore"` filters by jurisdiction
- [ ] `regatlas compare "Hong Kong" "Singapore"` shows comparison analysis
- [ ] `regatlas stats` displays document count, chunks, jurisdictions, LLM status
- [ ] `regatlas list` shows all documents in a table
- [ ] `regatlas config set api.base_url http://localhost:8000` updates config
- [ ] `regatlas config show` displays current configuration
- [ ] `regatlas --help` shows comprehensive help for all commands
- [ ] File upload shows progress bar for large files
- [ ] All errors display helpful, actionable messages

### Non-Functional Requirements

- [ ] Upload completes in <5 seconds for typical regulatory documents (<5MB)
- [ ] Query results display within 2 seconds
- [ ] Configuration persists between sessions
- [ ] Works on macOS, Linux, and Windows
- [ ] Can switch between local and production APIs without reinstalling
- [ ] CLI can be installed globally: `uv tool install regatlas`
- [ ] Exit codes follow conventions (0 = success, 1 = error)

### Quality Gates

- [ ] All commands have comprehensive help text
- [ ] Type hints on all functions
- [ ] Error messages include suggested fixes
- [ ] Works without config file (uses defaults)
- [ ] Handles network interruptions gracefully

## Implementation Phases

### Phase 1: Foundation (Core Infrastructure)

**Tasks:**
1. Create project structure in `cli/` directory
2. Set up `pyproject.toml` with CLI entry point
3. Implement config file management (`cli/config.py`)
   - Read/write `~/.config/regatlas/config.toml`
   - Environment variable overrides
   - Validation
4. Create API client wrapper (`cli/api/client.py`)
   - Base HTTPx client with timeout/retry
   - Methods for each API endpoint
   - Error handling and response parsing
5. Basic Typer app structure in `cli/main.py`

**Success Criteria:**
- `regatlas --help` works
- Config file created on first run with defaults
- Can initialize API client with config

**Estimated Effort:** 2 hours

### Phase 2: Core Commands (Upload, Query, Stats)

**Tasks:**
1. Implement `upload` command (`cli/commands/upload.py`)
   - File validation
   - Multipart upload with progress
   - Display extracted requirements
2. Implement `query` command (`cli/commands/query.py`)
   - Text query input
   - Optional jurisdiction filter
   - Format results and summary
3. Implement `stats` command (`cli/commands/stats.py`)
   - Display system statistics
   - Show available jurisdictions
4. Implement `list` command (`cli/commands/stats.py`)
   - Table of all documents
5. Create display utilities (`cli/ui/display.py`)
   - Requirements table formatter
   - Query results formatter
   - Document list table

**Success Criteria:**
- Can upload a sample document and see requirements
- Can query and get formatted results
- Stats and list commands work

**Estimated Effort:** 3 hours

### Phase 3: Advanced Features (Compare, Config)

**Tasks:**
1. Implement `compare` command (`cli/commands/compare.py`)
   - Two jurisdiction inputs
   - Format comparison output (side-by-side or sections)
   - Highlight similarities and differences
2. Implement `config` command (`cli/commands/config.py`)
   - `config show` - Display current config
   - `config set <key> <value>` - Update settings
   - `config reset` - Reset to defaults
3. Add verbose mode (`--verbose` flag)
   - Show full JSON responses
   - Display API request details
4. Add output format options (`--format json|table`)
   - JSON for scripting
   - Table (default) for humans

**Success Criteria:**
- Compare command produces readable comparison
- Can change API URL and verify it works
- Verbose mode shows detailed info

**Estimated Effort:** 2 hours

### Phase 4: Polish & Documentation

**Tasks:**
1. Add comprehensive help text to all commands
2. Add examples to help text
3. Improve error messages with suggestions
4. Add progress indicators for all long operations
5. Create README-CLI.md with:
   - Installation instructions
   - Quick start guide
   - Command reference
   - Examples for each command
6. Test on both local and deployed APIs
7. Handle edge cases:
   - Empty query results
   - No documents uploaded
   - Invalid jurisdictions
   - Network timeouts

**Success Criteria:**
- All help text is clear and includes examples
- Works smoothly with deployed API
- Edge cases handled gracefully
- Documentation is complete

**Estimated Effort:** 2 hours

**Total Estimated Effort:** 9 hours

## Success Metrics

- Upload → Extract → View results: <10 seconds end-to-end
- Query response time: <3 seconds including display
- Configuration changes take effect immediately
- Zero crashes on common error conditions
- Positive developer feedback on usability

## Dependencies & Prerequisites

### Python Dependencies
```toml
dependencies = [
    "typer>=0.12.0",          # CLI framework
    "httpx>=0.27.0",          # HTTP client
    "rich>=13.7.0",           # Terminal formatting
    "tomli>=2.0.1",           # TOML parsing (Python <3.11)
    "tomli-w>=1.0.0",         # TOML writing
]
```

### System Requirements
- Python 3.10+
- Internet connection for API access
- Write access to `~/.config/` for config storage

### External Dependencies
- RegAtlas API must be running (local or deployed)
- For testing: sample documents in `data/documents/`

## Risk Analysis & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| API changes break CLI | High | Medium | Version-lock API contract, add integration tests |
| Network timeouts frustrate users | Medium | High | Clear timeout messages, retry logic, adjustable timeout |
| Config file corruption | Medium | Low | Validate on read, provide reset command |
| Large file uploads slow | Low | Medium | Stream uploads with progress, warn on large files |
| Rich library terminal compatibility | Medium | Low | Graceful degradation, plain text fallback |

## Alternative Approaches Considered

### 1. Bash script with curl
**Pros:** No dependencies, simple  
**Cons:** Poor error handling, hard to maintain, no progress bars, difficult multipart uploads  
**Decision:** Rejected - too basic for good UX

### 2. Click framework instead of Typer
**Pros:** More mature, wider adoption  
**Cons:** Less type-safe, more boilerplate, older design patterns  
**Decision:** Rejected - Typer provides better DX with less code

### 3. Requests library instead of HTTPx
**Pros:** More familiar, simpler  
**Cons:** No async support, less modern, smaller feature set  
**Decision:** Rejected - HTTPx is better for progress callbacks and future async support

### 4. Config in JSON instead of TOML
**Pros:** Built into Python stdlib  
**Cons:** Less human-friendly, no comments support  
**Decision:** Rejected - TOML is more readable and conventional for config

## Future Considerations

### Potential Extensions
- **Watch mode**: `regatlas watch <dir>` auto-uploads new documents
- **Batch operations**: `regatlas upload *.pdf --jurisdiction "Hong Kong"`
- **Export commands**: `regatlas export --format xlsx > report.xlsx`
- **Diff command**: `regatlas diff <doc1> <doc2>` compare two documents
- **Interactive mode**: TUI with navigation and selection
- **Shell completion**: Tab completion for commands and jurisdictions
- **Configuration profiles**: Switch between dev/staging/prod environments
- **Local caching**: Cache query results for faster repeat queries

### Extensibility Considerations
- Plugin architecture for custom formatters
- API client could be extracted as standalone library
- Support for multiple output formats (JSON, CSV, Excel)
- Configuration could include API authentication when added

## Documentation Plan

### README-CLI.md
Create comprehensive CLI documentation covering:
1. Installation (`uv tool install` and manual)
2. Quick start with 5-minute tutorial
3. Command reference with examples
4. Configuration guide
5. Troubleshooting common issues
6. Development setup for contributors

### In-app Help
Each command includes:
- Brief description
- Usage examples
- All options explained
- Related commands

### Project README Update
Add CLI section to main README.md:
- Link to README-CLI.md
- Quick installation command
- Simple usage example

## References & Research

### Internal References
- Main API: `backend/main.py` (lines 70-310)
- API endpoints and responses documented in code
- Sample documents: `data/documents/sample_*.txt`
- Configuration: `backend/config.py` for API settings reference

### External References
- Typer documentation: https://typer.tiangolo.com/
- Rich library: https://rich.readthedocs.io/
- HTTPx: https://www.python-httpx.org/
- Click (comparison): https://click.palletsprojects.com/

### Similar Tools (Inspiration)
- `gh` (GitHub CLI) - excellent command structure and help text
- `stripe-cli` - good progress indicators and error messages  
- `railway` - clean output and intuitive commands
- `heroku` - well-designed config management

### Related Work
- Current project uses FastAPI with auto-generated OpenAPI docs
- Web UI exists but not suitable for rapid testing
- No existing CLI or automation tools

## MVP (Minimal Examples)

### cli/main.py

```python
#!/usr/bin/env python3
"""RegAtlas CLI - Command-line interface for RegAtlas API."""

import typer
from typing import Optional
from pathlib import Path

from .commands import upload, query, compare, stats, config
from .config import load_config

app = typer.Typer(
    name="regatlas",
    help="RegAtlas - Cross-jurisdiction regulatory analytics CLI",
    no_args_is_help=True
)

# Register command groups
app.command()(upload.upload_command)
app.command()(query.query_command)
app.command()(compare.compare_command)
app.command()(stats.stats_command)
app.command()(stats.list_command)

# Config subcommand group
config_app = typer.Typer(help="Configure CLI settings")
config_app.command("show")(config.show_command)
config_app.command("set")(config.set_command)
config_app.command("reset")(config.reset_command)
app.add_typer(config_app, name="config")


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="REGATLAS_API_URL", help="Override API base URL")
):
    """RegAtlas CLI - Fast testing and interaction with RegAtlas API."""
    # Load config and store in context for commands to access
    cfg = load_config()
    
    # Override with command line options
    if api_url:
        cfg.api.base_url = api_url
    
    ctx.obj = {
        "config": cfg,
        "verbose": verbose
    }


if __name__ == "__main__":
    app()
```

### cli/api/client.py

```python
"""API client for RegAtlas."""

import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from rich.progress import Progress, SpinnerColumn, TextColumn


class RegAtlasClient:
    """Client for RegAtlas API."""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        response = self.client.get(f"{self.base_url}/")
        response.raise_for_status()
        return response.json()
    
    def upload_document(
        self, 
        file_path: Path, 
        jurisdiction: str,
        progress: Optional[Progress] = None
    ) -> Dict[str, Any]:
        """Upload and process a document."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            params = {"jurisdiction": jurisdiction}
            
            response = self.client.post(
                f"{self.base_url}/upload",
                files=files,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    def query_documents(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """Query documents."""
        payload = {
            "query": query,
            "n_results": n_results
        }
        if jurisdiction:
            payload["jurisdiction"] = jurisdiction
        
        response = self.client.post(
            f"{self.base_url}/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def compare_jurisdictions(
        self,
        jurisdiction1: str,
        jurisdiction2: str
    ) -> Dict[str, Any]:
        """Compare two jurisdictions."""
        payload = {
            "jurisdiction1": jurisdiction1,
            "jurisdiction2": jurisdiction2
        }
        
        response = self.client.post(
            f"{self.base_url}/compare",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        response = self.client.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()
    
    def list_documents(self) -> Dict[str, Any]:
        """List all documents."""
        response = self.client.get(f"{self.base_url}/documents")
        response.raise_for_status()
        return response.json()
    
    def close(self):
        """Close the client."""
        self.client.close()
```

### cli/commands/upload.py

```python
"""Upload command implementation."""

import typer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..api.client import RegAtlasClient
from ..ui.display import display_requirements

console = Console()


def upload_command(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Path to PDF or text file to upload"),
    jurisdiction: str = typer.Option(..., "--jurisdiction", "-j", help="Jurisdiction (e.g., 'Hong Kong', 'Singapore')"),
):
    """Upload and analyze a regulatory document.
    
    Examples:
        regatlas upload sample.pdf --jurisdiction "Hong Kong"
        regatlas upload ~/docs/regulation.txt -j "Singapore"
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    # Validate file
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)
    
    if file.suffix.lower() not in [".pdf", ".txt"]:
        console.print(f"[red]Error: File must be PDF or TXT, got: {file.suffix}[/red]")
        raise typer.Exit(1)
    
    # Upload with progress
    client = RegAtlasClient(config.api.base_url, config.api.timeout)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Uploading {file.name}...", total=None)
            
            result = client.upload_document(file, jurisdiction)
            
            progress.update(task, description=f"[green]✓[/green] Uploaded {file.name}")
        
        # Display results
        console.print(f"\n[bold green]✓ Document processed successfully[/bold green]")
        console.print(f"Document ID: {result['doc_id']}")
        console.print(f"Chunks added: {result['chunks_added']}")
        
        if verbose:
            console.print(f"\n[dim]{result}[/dim]")
        
        # Display extracted requirements
        if "requirements" in result:
            display_requirements(result["requirements"], console)
        
    except httpx.HTTPError as e:
        console.print(f"[red]API Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
```

### cli/commands/query.py

```python
"""Query command implementation."""

import typer
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..api.client import RegAtlasClient
from ..ui.display import display_query_results

console = Console()


def query_command(
    ctx: typer.Context,
    query_text: str = typer.Argument(..., help="Query text (e.g., 'capital requirements')"),
    jurisdiction: Optional[str] = typer.Option(None, "--jurisdiction", "-j", help="Filter by jurisdiction"),
    n_results: int = typer.Option(5, "--limit", "-n", help="Number of results to return"),
):
    """Query regulatory documents.
    
    Examples:
        regatlas query "What are capital requirements?"
        regatlas query "liquidity coverage" --jurisdiction "Singapore"
        regatlas query "risk management" -n 10
    """
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    client = RegAtlasClient(config.api.base_url, config.api.timeout)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Searching...", total=None)
            
            result = client.query_documents(query_text, jurisdiction, n_results)
            
            progress.update(task, description="[green]✓[/green] Search complete")
        
        # Display results
        display_query_results(result, console, verbose)
        
    except httpx.HTTPError as e:
        console.print(f"[red]API Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
```

### cli/ui/display.py

```python
"""Display utilities for rich terminal output."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from typing import Dict, Any, List


def display_requirements(requirements: Dict[str, Any], console: Console):
    """Display extracted requirements in a formatted table."""
    if not requirements or "requirements" not in requirements:
        console.print("[yellow]No requirements extracted[/yellow]")
        return
    
    reqs = requirements["requirements"]
    
    if not reqs:
        console.print("[yellow]No requirements found[/yellow]")
        return
    
    table = Table(title="Extracted Requirements", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Requirement", style="white")
    
    for req in reqs:
        category = req.get("category", "Unknown")
        text = req.get("text", "")
        table.add_row(category, text[:100] + "..." if len(text) > 100 else text)
    
    console.print(table)


def display_query_results(result: Dict[str, Any], console: Console, verbose: bool = False):
    """Display query results with summary."""
    console.print(f"\n[bold]Query:[/bold] {result['query']}\n")
    
    if "summary" in result and result["summary"]:
        panel = Panel(
            result["summary"],
            title="Summary",
            border_style="green",
            padding=(1, 2)
        )
        console.print(panel)
        console.print()
    
    results = result.get("results", [])
    
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return
    
    console.print(f"[bold]Found {len(results)} results:[/bold]\n")
    
    for i, r in enumerate(results, 1):
        doc_text = r.get("document", "")
        distance = r.get("distance", 0)
        metadata = r.get("metadata", {})
        
        console.print(f"[bold cyan]{i}.[/bold cyan] [dim](relevance: {1 - distance:.2f})[/dim]")
        console.print(f"    Jurisdiction: {metadata.get('jurisdiction', 'Unknown')}")
        console.print(f"    {doc_text[:200]}...")
        console.print()
        
        if verbose:
            console.print(f"[dim]Metadata: {metadata}[/dim]\n")
```

### cli/config.py

```python
"""Configuration management."""

from pathlib import Path
from typing import Optional
import tomli
import tomli_w
from pydantic import BaseModel


class APIConfig(BaseModel):
    base_url: str = "https://reg-atlas.onrender.com"
    timeout: int = 30


class DisplayConfig(BaseModel):
    color: bool = True
    verbose: bool = False


class Config(BaseModel):
    api: APIConfig = APIConfig()
    display: DisplayConfig = DisplayConfig()


def get_config_path() -> Path:
    """Get path to config file."""
    config_dir = Path.home() / ".config" / "regatlas"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.toml"


def load_config() -> Config:
    """Load configuration from file or create default."""
    config_path = get_config_path()
    
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomli.load(f)
            return Config(**data)
    else:
        # Create default config
        config = Config()
        save_config(config)
        return config


def save_config(config: Config):
    """Save configuration to file."""
    config_path = get_config_path()
    
    with open(config_path, "wb") as f:
        tomli_w.dump(config.model_dump(), f)
```

### Updated pyproject.toml (CLI entry point)

```toml
[project]
name = "reg-atlas"
version = "0.1.0"
description = "RegAtlas - Cross-jurisdiction regulatory analytics platform"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "python-multipart>=0.0.6",
    "pypdf>=3.17.0",
    "chromadb>=0.4.22",
    "openai>=1.10.0",
    "python-dotenv>=1.0.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    # CLI dependencies
    "typer>=0.12.0",
    "httpx>=0.27.0",
    "rich>=13.7.0",
    "tomli>=2.0.1",
    "tomli-w>=1.0.0",
]

[project.scripts]
regatlas = "cli.main:app"

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "black>=23.12.0",
    "ruff>=0.1.0",
]

[tool.hatch.build.targets.wheel]
packages = ["backend", "cli"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## Installation & Usage Examples

### Installation
```bash
# Navigate to project
cd ~/reg-atlas

# Install with CLI support
uv pip install -e .

# Or install as global tool
uv tool install .

# Verify installation
regatlas --help
```

### Quick Start Usage

```bash
# Check API status
regatlas stats

# Upload a document
regatlas upload data/documents/sample_hkma_capital.txt --jurisdiction "Hong Kong"

# Query documents
regatlas query "What are capital requirements?"

# Query with filter
regatlas query "liquidity ratio" --jurisdiction "Singapore" --limit 10

# Compare jurisdictions
regatlas compare "Hong Kong" "Singapore"

# List all documents
regatlas list

# Use local API instead of production
regatlas --api-url http://localhost:8000 stats

# Or set it in config
regatlas config set api.base_url http://localhost:8000

# View config
regatlas config show

# Verbose mode for debugging
regatlas -v query "risk management"
```
