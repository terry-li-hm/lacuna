"""RegAtlas CLI - Main entry point."""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
from typing import Optional
import os

from cli.api import RegAtlasClient

app = typer.Typer(
    name="regatlas",
    help="RegAtlas CLI - Regulatory analytics tool",
    add_completion=False
)
console = Console()


def get_api_url() -> str:
    """Get API URL from environment or default."""
    return os.getenv("REGATLAS_API_URL", "https://reg-atlas.onrender.com")


@app.command()
def upload(
    file: Path = typer.Argument(..., help="Path to PDF or text file to upload"),
    jurisdiction: str = typer.Option(..., "--jurisdiction", "-j", help="Jurisdiction (e.g., 'Hong Kong', 'Singapore')"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL")
):
    """Upload a regulatory document for processing."""
    
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)
    
    url = api_url or get_api_url()
    client = RegAtlasClient(base_url=url)
    
    try:
        with console.status(f"[bold green]Uploading {file.name}..."):
            result = client.upload_document(file, jurisdiction)
        
        console.print(f"[green]✓[/green] Successfully uploaded {result['filename']}")
        console.print(f"[cyan]Document ID:[/cyan] {result['doc_id']}")
        console.print(f"[cyan]Jurisdiction:[/cyan] {result['jurisdiction']}")
        console.print(f"[cyan]Chunks Added:[/cyan] {result['chunks_added']}")
        
        if result.get('requirements') and result['requirements'].get('requirements'):
            console.print("\n[bold]Extracted Requirements:[/bold]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Type", style="cyan")
            table.add_column("Description", style="white")
            
            for req in result['requirements']['requirements'][:10]:  # Show first 10
                req_type = req.get('requirement_type', 'Unknown')
                desc = req.get('description', 'No description')[:80]
                table.add_row(req_type, desc)
            
            console.print(table)
            
            if len(result['requirements']['requirements']) > 10:
                console.print(f"[dim]... and {len(result['requirements']['requirements']) - 10} more[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command()
def query(
    question: str = typer.Argument(..., help="Query question"),
    jurisdiction: Optional[str] = typer.Option(None, "--jurisdiction", "-j", help="Filter by jurisdiction"),
    n_results: int = typer.Option(5, "--results", "-n", help="Number of results to return"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL")
):
    """Query regulatory documents."""
    
    url = api_url or get_api_url()
    client = RegAtlasClient(base_url=url)
    
    try:
        with console.status(f"[bold green]Searching for: {question}..."):
            result = client.query_documents(question, jurisdiction, n_results)
        
        console.print(f"[green]✓[/green] Found {len(result.get('results', []))} relevant chunks\n")
        
        if result.get('summary'):
            console.print("[bold cyan]Summary:[/bold cyan]")
            console.print(f"{result['summary']}\n")
        
        if result.get('results'):
            console.print("[bold]Relevant Sections:[/bold]")
            for i, doc in enumerate(result['results'], 1):
                meta = doc.get('metadata', {})
                jurisdiction_name = meta.get('jurisdiction', 'Unknown')
                filename = meta.get('filename', 'Unknown')
                
                console.print(f"\n[cyan]{i}. {jurisdiction_name} - {filename}[/cyan]")
                console.print(f"[dim]{doc['document'][:300]}...[/dim]")
        else:
            console.print("[yellow]No results found. Try uploading documents first.[/yellow]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command()
def compare(
    jurisdiction1: str = typer.Argument(..., help="First jurisdiction"),
    jurisdiction2: str = typer.Argument(..., help="Second jurisdiction"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL")
):
    """Compare regulatory requirements between two jurisdictions."""
    
    url = api_url or get_api_url()
    client = RegAtlasClient(base_url=url)
    
    try:
        with console.status(f"[bold green]Comparing {jurisdiction1} vs {jurisdiction2}..."):
            result = client.compare_jurisdictions(jurisdiction1, jurisdiction2)
        
        console.print(f"[green]✓[/green] Comparison complete\n")
        console.print(f"[bold cyan]Comparison: {result['jurisdiction1']} vs {result['jurisdiction2']}[/bold cyan]\n")
        console.print(result['comparison'])
        
        if result.get('documents_compared'):
            console.print(f"\n[dim]Documents compared: {result['documents_compared']}[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command()
def stats(
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL")
):
    """Show system statistics."""
    
    url = api_url or get_api_url()
    client = RegAtlasClient(base_url=url)
    
    try:
        result = client.stats()
        
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        
        table.add_row("Total Documents", str(result['total_documents']))
        table.add_row("Total Chunks", str(result['total_chunks']))
        table.add_row("Jurisdictions", ", ".join(result['jurisdictions']) if result['jurisdictions'] else "None")
        table.add_row("LLM Available", "Yes" if result.get('llm_available') else "No")
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command()
def list_docs(
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL")
):
    """List all processed documents."""
    
    url = api_url or get_api_url()
    client = RegAtlasClient(base_url=url)
    
    try:
        result = client.list_documents()
        documents = result.get('documents', [])
        
        if not documents:
            console.print("[yellow]No documents found.[/yellow]")
            return
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Filename", style="white")
        table.add_column("Jurisdiction", style="green")
        table.add_column("Chunks", justify="right", style="yellow")
        
        for doc in documents:
            table.add_row(
                doc['doc_id'][:8] + "...",
                doc['filename'],
                doc['jurisdiction'],
                str(doc['chunks_count'])
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {len(documents)} documents[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command()
def health(
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Override API URL")
):
    """Check API health status."""
    
    url = api_url or get_api_url()
    client = RegAtlasClient(base_url=url)
    
    try:
        result = client.health()
        
        console.print(f"[green]✓[/green] API is healthy")
        console.print(f"[cyan]App:[/cyan] {result.get('app', 'Unknown')}")
        console.print(f"[cyan]Version:[/cyan] {result.get('version', 'Unknown')}")
        console.print(f"[cyan]URL:[/cyan] {url}")
    
    except Exception as e:
        console.print(f"[red]✗ API is unhealthy[/red]")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    app()
