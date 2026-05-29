# Agentplane

Lightweight, extensible agent orchestration control plane. Inspired by [Paperclip](https://github.com/paperclipai/paperclip), built for contributors.

## Philosophy

- **Zero-config by default** — SQLite, no Docker required, runs on a laptop.
- **Plugin-based adapters** — Bring any agent runtime (Claude Code, Kimi, custom scripts).
- **Async-first** — Handles hundreds of concurrent agent heartbeats without blocking.
- **Contributor-friendly** — Pure Python, minimal deps, clear module boundaries.

## Quick Start

```bash
# 1. Install UV (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Setup project
uv sync

# 3. Init database
uv run agentplane init

# 4. Start server
uv run agentplane run
```

Server is now at `http://127.0.0.1:3400`.

## API Usage

```bash
# Create a company
curl -X POST http://localhost:3400/api/companies \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp"}'

# Create an agent (using the built-in process adapter)
curl -X POST "http://localhost:3400/api/companies/{company_id}/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello-agent",
    "adapter_type": "process",
    "adapter_config": {
      "command": "echo",
      "args": ["Hello from agent!"]
    }
  }'

# Create and execute a run
curl -X POST "http://localhost:3400/api/agents/{agent_id}/runs" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello"}'

curl -X POST "http://localhost:3400/api/runs/{run_id}/execute"
```

## Architecture

```
agentplane/
├── src/agentplane/
│   ├── core/           # Config, DB (SQLModel), shared models
│   ├── adapters/       # Plugin system for agent runtimes
│   │   ├── base.py     # Abstract Adapter interface
│   │   ├── registry.py # Auto-discovery of built-in + external adapters
│   │   └── builtin/
│   │       └── process.py   # Local shell command adapter
│   ├── api/            # FastAPI routes
│   ├── services/       # Business logic ( AgentService, RunService)
│   └── cli/            # Typer CLI
├── adapters/           # Drop external adapter plugins here
├── tests/
└── data/               # Local SQLite + runtime files
```

## Writing a Custom Adapter

Create `adapters/my_adapter.py` (or drop it in `src/agentplane/adapters/builtin/`):

```python
from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter

@register_adapter
class MyAdapter(Adapter):
    @property
    def type(self) -> str:
        return "my_adapter"

    @property
    def label(self) -> str:
        return "My Custom Adapter"

    async def execute(self, ctx: AdapterContext, on_log=None) -> AdapterResult:
        # Your execution logic here
        return AdapterResult(success=True, stdout="Done!")

    async def probe(self, config: dict) -> dict:
        return {"available": True}
```

Restart the server — your adapter appears automatically.

## Scaling Up

| Scale | Change |
|---|---|
| **Local dev** | SQLite (default) |
| **Team** | Swap `database_url` to PostgreSQL |
| **Production** | Run behind Uvicorn workers / Gunicorn |
| **Many agents** | Deploy multiple instances, shared DB |
| **Custom runtimes** | Add adapters for Claude, Kimi, LangChain, etc. |

Environment variables:

```bash
AGENTPLANE_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/agentplane"
AGENTPLANE_HOST=0.0.0.0
AGENTPLANE_PORT=3400
```

## Development

```bash
# Run tests
uv run pytest

# Type check
uv run mypy src

# Lint
uv run ruff check src
uv run ruff format src
```

## License

MIT
