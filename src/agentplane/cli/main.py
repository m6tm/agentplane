"""Agentplane CLI."""

import asyncio
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentplane.adapters.registry import list_adapters
from agentplane.core.config import settings
from agentplane.core.db import init_db
from agentplane.core.models import (
    SkillCreate,
    StrategyCreate,
    TradingDeskCreate,
)
from agentplane.services.trading_service import (
    SkillService,
    StrategyService,
    TradingDeskService,
)

# Fix Windows console encoding for special characters
if os.name == "nt":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

console = Console()
app = typer.Typer(help="Agentplane - Agentic trading control plane")

# Trading sub-commands
trading_app = typer.Typer(help="Manage trading desks, strategies and skills")
app.add_typer(trading_app, name="trading")


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
                raise typer.Exit(1) from None

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
    db_status = "[green]OK[/green]" if db_path and db_path.exists() else "[yellow]MISSING[/yellow]"
    table.add_row("Database", db_status)
    table.add_row("Adapters", str(len(list_adapters())))

    console.print(table)

    if issues:
        for issue in issues:
            console.print(f"[red]- {issue}[/red]")
        console.print("\nRun [bold]agentplane init[/bold] to fix.")
        raise typer.Exit(1)


# Trading CLI commands

@trading_app.command("create-desk")
def create_desk(
    name: str = typer.Argument(..., help="Desk name"),
    capital: float = typer.Option(10000.0, help="Initial capital in USD"),
    mode: str = typer.Option("paper", help="paper | backtest | live"),
):
    """Create a trading desk."""
    async def _create():
        svc = TradingDeskService()
        desk = await svc.create(TradingDeskCreate(
            name=name,
            mode=mode,  # type: ignore[arg-type]
            initial_capital_usd=capital,
        ))
        return desk

    desk = asyncio.run(_create())
    msg = f"[green]Created desk[/green] {desk.name} ({desk.id}) with ${desk.initial_capital_usd}"
    console.print(msg)


@trading_app.command("desks")
def list_desks():
    """List trading desks."""
    async def _list():
        svc = TradingDeskService()
        return await svc.list()

    desks = asyncio.run(_list())
    table = Table(title="Trading Desks")
    table.add_column("Name", style="cyan")
    table.add_column("Mode", style="green")
    table.add_column("Capital", style="yellow")
    table.add_column("Agents", style="magenta")

    for desk in desks:
        table.add_row(
            desk.name,
            desk.mode,
            f"${desk.current_capital_usd:.2f}",
            str(len(desk.agents)),
        )
    console.print(table)


@trading_app.command("create-strategy")
def create_strategy(
    name: str = typer.Argument(..., help="Strategy name"),
    timeframe: str = typer.Option("daily", help="scalping | daily | swing"),
):
    """Create a trading strategy."""
    async def _create():
        svc = StrategyService()
        return await svc.create(StrategyCreate(
            name=name,
            timeframe=timeframe,  # type: ignore[arg-type]
        ))

    strategy = asyncio.run(_create())
    console.print(f"[green]Created strategy[/green] {strategy.name} ({strategy.id})")


@trading_app.command("create-skill")
def create_skill(
    name: str = typer.Argument(..., help="Skill name"),
    category: str = typer.Option("analysis", help="analysis | risk | execution | psychology"),
    injection: str = typer.Option("", help="Prompt injection text"),
):
    """Create a skill."""
    async def _create():
        svc = SkillService()
        return await svc.create(SkillCreate(
            name=name,
            category=category,  # type: ignore[arg-type]
            prompt_injection=injection,
        ))

    skill = asyncio.run(_create())
    console.print(f"[green]Created skill[/green] {skill.name} ({skill.id})")


if __name__ == "__main__":
    app()
