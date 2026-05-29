# CLI Reference

Entry point: `agentplane` (or `uv run agentplane` in dev)

## Commands

### `run`

Start the Agentplane server.

```bash
agentplane run [OPTIONS]
```

Options:
- `--host, -h TEXT` — Bind host (default: 127.0.0.1)
- `--port, -p INTEGER` — Bind port (default: 3400)
- `--reload` — Auto-reload on code changes

If the port is already in use, Agentplane auto-detects the next available port.

### `init`

Initialize the local data directory and database.

```bash
agentplane init
```

Creates:
- `./data/` directory
- SQLite database file

### `adapters`

List all registered adapters.

```bash
agentplane adapters
```

Output:
```
Registered Adapters
┌──────────────────┬──────────────────┐
│ Type             │ Label            │
├──────────────────┼──────────────────┤
│ claude_local     │ Claude Code (local) │
│ codex_local      │ Codex (local)       │
│ ...
```

### `doctor`

Run diagnostics.

```bash
agentplane doctor
```

Checks:
- Data directory exists
- Database initialized
- Adapters registered

## Environment Variables

All settings can be overridden via environment variables with the `AGENTPLANE_` prefix:

```bash
AGENTPLANE_HOST=0.0.0.0
AGENTPLANE_PORT=3400
AGENTPLANE_DATABASE_URL="postgresql+asyncpg://..."
AGENTPLANE_DEBUG=true
```

Or create a `.env` file:

```
AGENTPLANE_HOST=0.0.0.0
AGENTPLANE_PORT=3400
```
