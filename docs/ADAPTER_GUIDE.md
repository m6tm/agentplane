# Adapter Authoring Guide

## What is an Adapter?

An adapter bridges Agentplane to an external agent runtime. Examples:
- **process**: Runs a shell command
- **claude_local**: Runs `claude` CLI
- **kimi_local**: Runs `kimi` CLI
- **cursor_cloud**: Calls a remote agent service
- **openclaw_gateway**: Connects via WebSocket

## The Adapter Interface

Every adapter must inherit from `Adapter` and implement:

```python
class MyAdapter(Adapter):
    @property
    def type(self) -> str: ...

    @property
    def label(self) -> str: ...

    async def execute(self, ctx: AdapterContext, on_log=None) -> AdapterResult: ...

    async def probe(self, config: dict) -> dict: ...
```

## AdapterContext

| Field | Description |
|---|---|
| `run_id` | Unique execution ID |
| `agent_id` | Agent definition ID |
| `task_id` | Optional linked task |
| `task_id` | Optional linked task |
| `prompt` | The prompt / instruction |
| `config` | Agent's `adapter_config` dict |
| `env` | Runtime environment variables |
| `session_id` | Resumable session ID |
| `session_params` | Extra session context |

## AdapterResult

| Field | Description |
|---|---|
| `success` | True if execution succeeded |
| `exit_code` | Process exit code |
| `stdout` | Standard output |
| `stderr` | Standard error |
| `summary` | Short result summary |
| `session_id` | Session to resume next time |
| `session_params` | Session metadata |
| `input_tokens` / `output_tokens` | LLM usage |
| `cost_usd` | Estimated cost |
| `model` | Model used |

## Local CLI Adapters

For adapters that shell out to a local CLI, inherit from `LocalCliAdapter`:

```python
from agentplane.adapters.builtin._cli_base import LocalCliAdapter
from agentplane.adapters.registry import register_adapter

@register_adapter
class MyCliAdapter(LocalCliAdapter):
    @property
    def type(self) -> str:
        return "my_cli"

    @property
    def label(self) -> str:
        return "My CLI"

    @property
    def cli_command(self) -> str:
        return "my-cli"

    @property
    def default_model(self) -> str:
        return "default-model"

    async def execute(self, ctx, on_log=None):
        # LocalCliAdapter handles the subprocess
        # Just build args and call super logic if needed
        config = ctx.config or {}
        args = ["--print", ctx.prompt]
        if ctx.session_id:
            args.extend(["--resume", ctx.session_id])
        # ... or use the built-in _run_cli helper
        return await self._run_cli(
            self.cli_command,
            args,
            self._build_cwd(ctx),
            self._build_env(ctx),
            self._build_timeout(ctx),
            on_log,
        )
```

## Registration

Use the decorator:

```python
from agentplane.adapters.registry import register_adapter

@register_adapter
class MyAdapter(Adapter): ...
```

Or register at runtime:

```python
register_adapter(MyAdapter)
```

## External Plugins

Drop a `.py` file into the `adapters/` directory at project root:

```python
# adapters/my_custom.py
from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter

@register_adapter
class CustomAdapter(Adapter): ...
```

Then call `discover_external_adapters("./adapters")` at startup.

## Testing Your Adapter

```python
import pytest
from agentplane.adapters.registry import get_adapter
from agentplane.adapters.base import AdapterContext

@pytest.mark.asyncio
async def test_my_adapter():
    adapter = get_adapter("my_adapter")
    ctx = AdapterContext(
        run_id="test-1",
        agent_id="agent-1",
        task_id="task-1",
        config={"key": "value"},
    )
    result = await adapter.execute(ctx)
    assert result.success is True
```

## Session Resume

For adapters that support session resume:

1. Return `session_id` in `AdapterResult`
2. Check `ctx.session_id` on execute
3. Pass session ID to the underlying CLI/API

Example (Claude):
```python
if ctx.session_id:
    args.extend(["--resume", ctx.session_id])
# ... after execution
result.session_id = parsed_session_id or ctx.session_id
```

## Best Practices

- **Graceful degradation**: If CLI is not installed, `probe()` should return `available: false` with a helpful hint
- **Timeout handling**: Always respect the timeout; kill the subprocess if exceeded
- **Output streaming**: Use `on_log` callback to stream stdout/stderr in real-time
- **Security**: Never log API keys or sensitive env vars
- **Models list**: Provide `models` property for UI display
