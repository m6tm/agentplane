# Adapter Authoring Guide

## What is an Adapter?

An adapter bridges Agentplane to an external agent runtime. Examples:
- **process**: Runs a shell command
- **claude_local**: Runs `claude` CLI
- **kimi_local**: Runs `kimi` CLI
- **langchain**: Runs a LangChain agent
- **http**: Calls a remote agent service

## The Adapter Interface

```python
from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult

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
| `company_id` | Company scope |
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

## Registration

Use the decorator:

```python
from agentplane.adapters.registry import register_adapter

@register_adapter
class MyAdapter(Adapter): ...
```

Or register at runtime:

```python
from agentplane.adapters.registry import register_adapter
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
