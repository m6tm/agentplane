"""Agentplane CLI."""

import asyncio
import sys
from pathlib import Path

import typer
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentplane.core.config import settings
from agentplane.core.db import init_db
from agentplane.api.main import app as fastapi_app
from agentplane.adapters.registry import list_adapters

# Fix Windows console encoding for special characters
if os.name == "nt":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

console = Console()
app = typer.Typer(help="Agentplane - Lightweight agent orchestration control plane")


def _ensure_data_dir():
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)


@app.command()
def run(
    host: str = typer.Option(settings.host, "--host", "-h", help="Bind host"),
    port: int = typer.Option(settings.port, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
):
    """Start the Agentplane server."""
    _ensure_data_dir()
    init_db()

    import socket
    import uvicorn

    # Auto-detect free port if default is taken
    original_port = port
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                break
        except OSError:
            if port == original_port:
                console.print(f"[yellow]Port {port} is already in use.[/yellow]")
            port += 1
            if port > original_port + 100:
                console.print("[red]Could not find an available port.[/red]")
                raise typer.Exit(1)

    if port != original_port:
        console.print(f"[green]Auto-selected available port: {port}[/green]")

    console.print(Panel.fit(
        f"[bold green]Agentplane[/bold green] starting on [blue]http://{host}:{port}[/blue]",
        title="Server",
    ))
    console.print("(Press Ctrl+C to stop)")

    uvicorn.run(
        "agentplane.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def adapters():
    """List registered agent adapters."""
    table = Table(title="Registered Adapters")
    table.add_column("Type", style="cyan")
    table.add_column("Label", style="green")

    for meta in list_adapters():
        table.add_row(meta["type"], meta["label"])

    console.print(table)


@app.command()
def init():
    """Initialize the local data directory and database."""
    _ensure_data_dir()
    init_db()
    console.print(f"[green]OK[/green] Database ready at [bold]{settings.database_url}[/bold]")
    console.print(f"[green]OK[/green] Data directory: [bold]{settings.data_dir}[/bold]")


@app.command()
def doctor():
    """Run diagnostics."""
    issues = []

    # Check data dir
    if not Path(settings.data_dir).exists():
        issues.append(f"Data directory missing: {settings.data_dir}")

    # Check DB
    db_path = None
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        if not db_path.exists():
            issues.append(f"Database not initialized: {db_path}")

    table = Table(title="Diagnostics")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")

    table.add_row("Data directory", "[green]OK[/green]" if not issues else "[red]FAIL[/red]")
    table.add_row("Database", "[green]OK[/green]" if db_path and db_path.exists() else "[yellow]MISSING[/yellow]")
    table.add_row("Adapters", str(len(list_adapters())))

    console.print(table)

    if issues:
        for issue in issues:
            console.print(f"[red]- {issue}[/red]")
        console.print("\nRun [bold]agentplane init[/bold] to fix.")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
