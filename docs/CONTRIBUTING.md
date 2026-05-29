# Contributing to Agentplane

## Getting Started

```bash
git clone https://github.com/m6tm/agentplane.git
cd agentplane
uv sync --extra dev
uv run agentplane init
```

## Project Structure

```
src/agentplane/
├── core/           # Never import from here directly in adapters
├── adapters/       # Plugin system — keep it isolated
│   ├── base.py     # Abstract interface
│   ├── registry.py # Auto-discovery
│   └── builtin/    # Built-in adapters
├── api/            # FastAPI routes — thin layer
├── services/       # Business logic
└── cli/            # Typer CLI
```

## Adding a New Adapter

1. Create `src/agentplane/adapters/builtin/my_adapter.py`
2. Inherit from `Adapter` or `LocalCliAdapter`
3. Implement `type`, `label`, `execute()`, `probe()`
4. Add `@register_adapter` decorator
5. Add tests in `tests/test_integration_adapters.py`
6. Run `uv run pytest -v`

## Code Style

```bash
# Format
uv run ruff format src

# Lint
uv run ruff check src

# Type check
uv run mypy src

# Test
uv run pytest -v
```

## Testing

All changes must include tests. We use pytest with asyncio support.

### Adapter tests

Test your adapter's:
- Registration
- Metadata (`describe()`)
- Probe behavior
- Execution (mock CLI if needed)

### API tests

Use `httpx.AsyncClient` with `ASGITransport(app=app)`.

## Pull Request Process

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run the full test suite
5. Submit a PR with description

## Questions?

Open an issue on GitHub.
