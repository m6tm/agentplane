"""Adapter tests."""

import pytest

from agentplane.adapters.base import AdapterContext, AdapterResult
from agentplane.adapters.builtin.process import ProcessAdapter
from agentplane.adapters.registry import list_adapters, get_adapter


@pytest.fixture
def adapter():
    return ProcessAdapter()


@pytest.mark.asyncio
async def test_process_adapter_echo(adapter):
    ctx = AdapterContext(
        run_id="test-1",
        agent_id="agent-1",
        config={"command": "echo", "args": ["hello"]},
    )
    result = await adapter.execute(ctx)
    assert result.success is True
    assert "hello" in result.stdout


@pytest.mark.asyncio
async def test_process_adapter_probe(adapter):
    result = await adapter.probe({"command": "echo"})
    assert result["available"] is True


def test_registry_has_process():
    types = [a["type"] for a in list_adapters()]
    assert "process" in types
    assert get_adapter("process") is not None
