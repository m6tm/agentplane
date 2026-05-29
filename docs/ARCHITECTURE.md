# Architecture

## Overview

Agentplane is structured as a layered control plane:

```
┌─────────────────────────────────────────┐
│  CLI (Typer)                            │
│  agentplane run | init | doctor         │
├─────────────────────────────────────────┤
│  API (FastAPI)                          │
│  /api/companies | /agents | /runs       │
├─────────────────────────────────────────┤
│  Services                               │
│  AgentService | RunService              │
├─────────────────────────────────────────┤
│  Core                                   │
│  Models (SQLModel) | DB | Config        │
├─────────────────────────────────────────┤
│  Adapters                               │
│  12 built-in + external plugins         │
└─────────────────────────────────────────┘
```

## Core Concepts

### Company

A company is the top-level organizational boundary. All agents, tasks, and runs are scoped to a company. This enables multi-tenant deployments.

### Agent

An agent is a configured runtime that maps to an adapter. It stores:
- Adapter type and configuration
- Session state (for resumable runs)
- Budget tracking
- Heartbeat scheduling

### Run

A run is a single execution of an agent. It captures:
- Prompt and context
- stdout/stderr
- Usage metrics (tokens, cost)
- Session ID for resume

### Task

A task is a unit of work that can be assigned to an agent. Tasks have a lifecycle: `backlog → todo → in_progress → review → done`.

## Data Flow

```
1. User creates Company
2. User creates Agent (specifies adapter_type + adapter_config)
3. User creates Run (linked to Agent, optional Task)
4. API calls RunService.execute()
5. Service loads adapter via registry
6. Adapter.execute(ctx) shells out to CLI or calls API
7. Results are persisted back to Run
8. Agent session is updated for resume
```

## Database

### SQLite (default)

Zero-config, file-based. Perfect for local development and small deployments.

### PostgreSQL (production)

Switch via environment variable:

```bash
AGENTPLANE_DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
```

### Schema

| Table | Purpose |
|---|---|
| `companies` | Organizations |
| `agents` | Agent definitions + config |
| `tasks` | Work items |
| `runs` | Execution records |

## Adapter System

### Discovery

Adapters are auto-discovered from:
1. `src/agentplane/adapters/builtin/` — built-in adapters
2. `./adapters/` — external plugin directory

### Registration

```python
from agentplane.adapters.registry import register_adapter

@register_adapter
class MyAdapter(Adapter): ...
```

### Lifecycle

1. **Probe** — Check if adapter is available (CLI installed, API key present)
2. **Execute** — Run the agent with context, capture output
3. **Resume** — Reuse session ID across heartbeats

## Async Design

All I/O is async:
- FastAPI handles concurrent HTTP requests
- Adapter execution uses `asyncio.subprocess` for non-blocking shell-outs
- Database uses `aiosqlite` / `asyncpg`

This means Agentplane can orchestrate hundreds of agents without blocking.
