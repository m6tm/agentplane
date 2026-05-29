# API Reference

Base URL: `http://localhost:3400/api`

## Health

### GET /api/health

Check server health.

**Response:**
```json
{
  "status": "ok",
  "service": "agentplane"
}
```

## Agents

### POST /api/agents

Create an agent.

**Request:**
```json
{
  "name": "claude-dev",
  "description": "Claude Code development agent",
  "adapter_type": "claude_local",
  "adapter_config": {
    "model": "claude-sonnet-4-6",
    "effort": "high"
  },
  "heartbeat_interval_seconds": 60,
  "max_budget_usd": 100.0
}
```

**Response:** `Agent`

### GET /api/agents

List all agents.

**Response:** `Agent[]`

### GET /api/agents/{agent_id}

Get an agent by ID.

**Response:** `Agent`

### PATCH /api/agents/{agent_id}

Update an agent.

**Request:**
```json
{
  "name": "new-name",
  "adapter_config": {"model": "claude-opus-4-7"}
}
```

**Response:** `Agent`

### DELETE /api/agents/{agent_id}

Delete an agent.

**Response:**
```json
{"deleted": true}
```

### POST /api/agents/{agent_id}/probe

Probe the adapter to check availability.

**Response:**
```json
{
  "available": true,
  "resolved_path": "/usr/local/bin/claude",
  "command": "claude"
}
```

## Runs

### POST /api/agents/{agent_id}/runs

Create a run.

**Request:**
```json
{
  "task_id": "optional-task-id",
  "prompt": "Implement a login page",
  "timeout_seconds": 300
}
```

**Response:** `Run`

### GET /api/agents/{agent_id}/runs

List runs for an agent.

**Response:** `Run[]`

### GET /api/runs/{run_id}

Get a run by ID.

**Response:** `Run`

### POST /api/runs/{run_id}/execute

Execute a pending run.

**Response:** `Run` (with updated status, stdout, stderr)

## Models

### Agent

```json
{
  "id": "uuid",
  "name": "string",
  "description": "string | null",
  "adapter_type": "string",
  "adapter_config": "object",
  "status": "idle | running | paused | error",
  "session_id": "string | null",
  "session_params": "object | null",
  "heartbeat_interval_seconds": 60,
  "max_budget_usd": "number | null",
  "spent_budget_usd": 0.0,
  "created_at": "2026-01-01T00:00:00",
  "updated_at": "2026-01-01T00:00:00"
}
```

### Run

```json
{
  "id": "uuid",
  "agent_id": "uuid",
  "task_id": "uuid | null",
  "status": "pending | running | success | failure | timeout | cancelled",
  "prompt": "string | null",
  "stdout": "string | null",
  "stderr": "string | null",
  "summary": "string | null",
  "exit_code": "number | null",
  "input_tokens": "number | null",
  "output_tokens": "number | null",
  "cost_usd": "number | null",
  "model": "string | null",
  "started_at": "datetime | null",
  "finished_at": "datetime | null",
  "timeout_seconds": 300,
  "session_id": "string | null",
  "session_params": "object | null",
  "created_at": "2026-01-01T00:00:00"
}
```

## Example Workflows

### Full execution flow

```bash
# 1. Create agent
AGENT=$(curl -s -X POST http://localhost:3400/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "echo-bot",
    "adapter_type": "process",
    "adapter_config": {"command": "echo", "args": ["hello"]}
  }' | jq -r '.id')

# 2. Probe agent
curl -s -X POST "http://localhost:3400/api/agents/${AGENT}/probe" | jq

# 3. Create run
RUN=$(curl -s -X POST "http://localhost:3400/api/agents/${AGENT}/runs" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "say hello"}' | jq -r '.id')

# 4. Execute run
curl -s -X POST "http://localhost:3400/api/runs/${RUN}/execute" | jq
```
