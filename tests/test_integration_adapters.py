"""Integration tests for all adapters.

Verifies that every adapter registered in the system:
- Has correct metadata (type, label)
- Can be probed (gracefully handles missing CLI)
- Can be instantiated via the registry
"""

import pytest

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import list_adapters, get_adapter


# Expected adapters matching Paperclip's built-in set
EXPECTED_ADAPTERS = {
    "acpx_local": {"label": "ACPX (local)"},
    "claude_local": {"label": "Claude Code (local)", "models_count": 6},
    "codex_local": {"label": "Codex (local)", "models_count": 2},
    "cursor_local": {"label": "Cursor CLI (local)", "models_count": 8},
    "cursor_cloud": {"label": "Cursor Cloud"},
    "gemini_local": {"label": "Gemini CLI (local)", "models_count": 6},
    "grok_local": {"label": "Grok Build (local)", "models_count": 1},
    "kimi_local": {"label": "Kimi Code (local)", "models_count": 2},
    "openclaw_gateway": {"label": "OpenClaw Gateway"},
    "opencode_local": {"label": "OpenCode (local)", "models_count": 1},
    "pi_local": {"label": "Pi (local)", "models_count": 1},
    "process": {"label": "Local Process"},
}


class TestAdapterRegistry:
    """Verify all Paperclip adapters are present in the registry."""

    def test_all_expected_adapters_registered(self):
        registered = {a["type"] for a in list_adapters()}
        missing = set(EXPECTED_ADAPTERS.keys()) - registered
        assert not missing, f"Missing adapters: {missing}"

    def test_no_unexpected_adapters(self):
        registered = {a["type"] for a in list_adapters()}
        extra = registered - set(EXPECTED_ADAPTERS.keys())
        assert not extra, f"Unexpected adapters: {extra}"

    @pytest.mark.parametrize("adapter_type,expected", [
        (t, e) for t, e in EXPECTED_ADAPTERS.items()
    ])
    def test_adapter_metadata(self, adapter_type: str, expected: dict):
        adapter = get_adapter(adapter_type)
        assert adapter is not None, f"Adapter {adapter_type} not found"
        assert adapter.type == adapter_type
        assert adapter.label == expected["label"]

    @pytest.mark.parametrize("adapter_type", list(EXPECTED_ADAPTERS.keys()))
    @pytest.mark.asyncio
    async def test_adapter_probe_returns_dict(self, adapter_type: str):
        adapter = get_adapter(adapter_type)
        assert adapter is not None
        result = await adapter.probe({})
        assert isinstance(result, dict)
        assert "available" in result

    @pytest.mark.parametrize("adapter_type", list(EXPECTED_ADAPTERS.keys()))
    def test_adapter_describe(self, adapter_type: str):
        adapter = get_adapter(adapter_type)
        desc = adapter.describe()
        assert desc["type"] == adapter_type
        assert "label" in desc

    @pytest.mark.parametrize("adapter_type,expected_count", [
        ("claude_local", 6),
        ("codex_local", 2),
        ("cursor_local", 8),
        ("gemini_local", 6),
        ("grok_local", 1),
        ("kimi_local", 2),
        ("opencode_local", 1),
        ("pi_local", 1),
    ])
    def test_adapter_models_list(self, adapter_type: str, expected_count: int):
        adapter = get_adapter(adapter_type)
        desc = adapter.describe()
        assert "models" in desc
        assert len(desc["models"]) == expected_count


class TestLocalCliAdapters:
    """Integration tests for CLI-based adapters."""

    @pytest.mark.asyncio
    async def test_process_adapter_echo(self):
        adapter = get_adapter("process")
        ctx = AdapterContext(
            run_id="test-run-1",
            agent_id="test-agent",
            config={"command": "echo", "args": ["hello", "world"]},
        )
        result = await adapter.execute(ctx)
        assert result.success is True
        assert result.exit_code == 0
        assert "hello world" in result.stdout

    @pytest.mark.asyncio
    async def test_process_adapter_timeout(self):
        adapter = get_adapter("process")
        ctx = AdapterContext(
            run_id="test-run-2",
            agent_id="test-agent",
            config={"command": "sleep", "args": ["10"], "timeout_seconds": 1},
        )
        result = await adapter.execute(ctx)
        assert result.success is False
        assert "Timed out" in result.stderr

    @pytest.mark.asyncio
    async def test_claude_probe_no_cli(self):
        adapter = get_adapter("claude_local")
        result = await adapter.probe({})
        # On most CI/dev machines 'claude' is not installed
        assert isinstance(result["available"], bool)
        assert result["command"] == "claude"

    @pytest.mark.asyncio
    async def test_kimi_probe_no_cli(self):
        adapter = get_adapter("kimi_local")
        result = await adapter.probe({})
        assert isinstance(result["available"], bool)
        assert result["command"] == "kimi"


class TestCloudAdapters:
    """Integration tests for cloud/non-CLI adapters."""

    @pytest.mark.asyncio
    async def test_cursor_cloud_probe_without_key(self):
        adapter = get_adapter("cursor_cloud")
        result = await adapter.probe({})
        assert result["available"] is False
        assert "CURSOR_API_KEY" in result["note"]

    @pytest.mark.asyncio
    async def test_cursor_cloud_probe_with_key(self):
        adapter = get_adapter("cursor_cloud")
        result = await adapter.probe({"env": {"CURSOR_API_KEY": "test"}})
        assert result["available"] is True

    @pytest.mark.asyncio
    async def test_openclaw_probe_without_url(self):
        adapter = get_adapter("openclaw_gateway")
        result = await adapter.probe({})
        assert result["available"] is False

    @pytest.mark.asyncio
    async def test_openclaw_probe_with_url(self):
        adapter = get_adapter("openclaw_gateway")
        result = await adapter.probe({"url": "wss://example.com"})
        assert result["available"] is True
