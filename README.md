# Agentplane

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-88%20passing-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Lightweight, extensible agent orchestration control plane.

## What is Agentplane?

**Agentplane** is a control plane for AI-agent teams. It orchestrates autonomous agents — Claude Code, Kimi, Codex, Gemini, Grok, Cursor, and your own custom runtimes — toward your goals.

- **Zero-config by default** — SQLite, no Docker, runs on a laptop.
- **Plugin-based adapters** — Bring any agent runtime. If it can receive a heartbeat, it's hired.
- **Async-first** — Handles hundreds of concurrent agent heartbeats without blocking.
- **Contributor-friendly** — Pure Python, minimal deps, clear module boundaries.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)

### Install & Run

```bash
# Clone
git clone https://github.com/m6tm/agentplane.git
cd agentplane

# Install dependencies
uv sync --extra dev

# Initialize database
uv run agentplane init

# Start server
uv run agentplane run
```

Server is now at `http://127.0.0.1:3400`.

If port 3400 is taken, it auto-detects the next available port.

### Verify

```bash
# Check health
curl http://localhost:3400/api/health

# List adapters
uv run agentplane adapters

# Run tests
uv run pytest -v
```

## Supported Adapters

Agentplane ships with **12 built-in adapters** covering all major AI coding agents:

| Adapter | Type | Models |
|---|---|---|
| `claude_local` | Claude Code CLI | Claude Opus 4.7, Sonnet 4.6, Haiku 4.6, etc. |
| `codex_local` | OpenAI Codex CLI | GPT-5.3 Codex, GPT-5.4 |
| `cursor_local` | Cursor CLI | auto, composer-1.5, gpt-5.3-codex-* |
| `cursor_cloud` | Cursor Cloud API | Cloud-hosted agents |
| `gemini_local` | Gemini CLI | Gemini 2.5 Pro, Flash, Flash Lite |
| `grok_local` | Grok Build CLI | grok-build |
| `kimi_local` | Kimi Code CLI | kimi-k2.6, kimi-k2.5 |
| `opencode_local` | OpenCode CLI | auto |
| `pi_local` | Pi CLI | auto |
| `acpx_local` | ACPX Protocol | Claude/Codex via Agent Client Protocol |
| `openclaw_gateway` | WebSocket Gateway | OpenClaw gateway protocol |
| `process` | Shell Command | Any local command |

## API Quick Reference

```bash
# Create an agent
AGENT=$(curl -s -X POST http://localhost:3400/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello-agent",
    "adapter_type": "process",
    "adapter_config": {"command": "echo", "args": ["Hello!"]}
  }' | jq -r '.id')

# Create and execute a run
RUN=$(curl -s -X POST "http://localhost:3400/api/agents/${AGENT}/runs" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello"}' | jq -r '.id')

curl -s -X POST "http://localhost:3400/api/runs/${RUN}/execute"
```

See [docs/API.md](docs/API.md) for the full reference.

## Architecture

```
agentplane/
├── src/agentplane/
│   ├── core/              # Config, DB (SQLModel), shared models
│   ├── adapters/          # Plugin system for agent runtimes
│   │   ├── base.py        # Abstract Adapter interface
│   │   ├── registry.py    # Auto-discovery of built-in + external adapters
│   │   └── builtin/       # 12 built-in adapters
│   ├── api/               # FastAPI REST server
│   ├── services/          # Business logic
│   └── cli/               # Typer CLI
├── adapters/              # Drop external adapter plugins here
├── tests/                 # 88 integration tests
└── data/                  # SQLite + runtime files
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Writing a Custom Adapter

Create `adapters/my_adapter.py`:

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
        return AdapterResult(success=True, stdout="Done!")

    async def probe(self, config: dict) -> dict:
        return {"available": True}
```

Restart the server — your adapter appears automatically.

See [docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md) for the complete guide.

## Scaling Up

| Scale | Change |
|---|---|
| **Local dev** | SQLite (default), zero config |
| **Team** | Swap `database_url` to PostgreSQL |
| **Production** | Run behind Uvicorn workers / reverse proxy |
| **Many agents** | Deploy multiple instances, shared DB |
| **Custom runtimes** | Add adapters for any CLI or API |

Environment variables:

```bash
AGENTPLANE_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/agentplane"
AGENTPLANE_HOST=0.0.0.0
AGENTPLANE_PORT=3400
AGENTPLANE_DEBUG=false
```

## Desktop App (Tauri)

A Tauri v2 desktop shell lives in [`desktop/`](desktop/). It wraps the same FastAPI backend in a native window and can be removed at any time without touching the Python code.

```bash
cd desktop
pnpm install
pnpm tauri:dev    # opens a native window + auto-starts the Python backend
```

See [`desktop/README.md`](desktop/README.md) for build instructions and removal steps.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design and data flow
- [API Reference](docs/API.md) — Complete REST API documentation
- [CLI Reference](docs/CLI.md) — Command-line usage
- [Adapter Guide](docs/ADAPTER_GUIDE.md) — How to write custom adapters
- [Deployment](docs/DEPLOYMENT.md) — Production deployment modes
- [Contributing](docs/CONTRIBUTING.md) — How to contribute

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
