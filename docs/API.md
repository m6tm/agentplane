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

## Companies

### POST /api/companies

Create a company.

**Request:**
```json
{
  "name": "Acme Corp",
  "description": "My company"
}
```

**Response:** `Company`

### GET /api/companies

List all companies.

**Response:** `Company[]`

### GET /api/companies/{company_id}

Get a company by ID.

**Response:** `Company`

### DELETE /api/companies/{company_id}

Delete a company.

**Response:**
```json
{"deleted": true}
```

## Agents

### POST /api/companies/{company_id}/agents

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

### GET /api/companies/{company_id}/agents

List agents for a company.

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

### Company

```json
{
  "id": "uuid",
  "name": "string",
  "description": "string | null",
  "created_at": "2026-01-01T00:00:00",
  "updated_at": "2026-01-01T00:00:00"
}
```

### Agent

```json
{
  "id": "uuid",
  "company_id": "uuid",
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
# 1. Create company
COMPANY=$(curl -s -X POST http://localhost:3400/api/companies \
  -H "Content-Type: application/json" \
  -d '{"name": "My Company"}' | jq -r '.id')

# 2. Create agent
AGENT=$(curl -s -X POST "http://localhost:3400/api/companies/${COMPANY}/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "echo-bot",
    "adapter_type": "process",
    "adapter_config": {"command": "echo", "args": ["hello"]}
  }' | jq -r '.id')

# 3. Probe agent
curl -s -X POST "http://localhost:3400/api/agents/${AGENT}/probe" | jq

# 4. Create run
RUN=$(curl -s -X POST "http://localhost:3400/api/agents/${AGENT}/runs" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "say hello"}' | jq -r '.id')

# 5. Execute run
curl -s -X POST "http://localhost:3400/api/runs/${RUN}/execute" | jq
```
