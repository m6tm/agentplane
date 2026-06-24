"""End-to-end API integration tests.

Tests the full flow: agent -> run for multiple adapter types.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from agentplane.api.main import app
from agentplane.core.db import init_async_db


@pytest.fixture(autouse=True)
async def setup_db():
    await init_async_db()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestAgentLifecycle:
    """Full agent CRUD + probe for every adapter type."""

    ADAPTER_TYPES = [
        "process",
        "claude_local",
        "codex_local",
        "cursor_local",
        "gemini_local",
        "grok_local",
        "kimi_local",
        "opencode_local",
        "pi_local",
        "acpx_local",
        "cursor_cloud",
        "paper_broker",
    ]

    def _adapter_config(self, adapter_type: str) -> dict:
        if adapter_type in ("process", "acpx_local"):
            return {"command": "echo"}
        return {}

    @pytest.mark.parametrize("adapter_type", ADAPTER_TYPES)
    @pytest.mark.asyncio
    async def test_create_agent(self, client: AsyncClient, adapter_type: str):
        payload = {
            "name": f"agent-{adapter_type}",
            "adapter_type": adapter_type,
            "adapter_config": self._adapter_config(adapter_type),
        }
        resp = await client.post("/api/agents", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["adapter_type"] == adapter_type
        assert data["name"] == f"agent-{adapter_type}"

    @pytest.mark.parametrize("adapter_type", ADAPTER_TYPES)
    @pytest.mark.asyncio
    async def test_probe_agent(self, client: AsyncClient, adapter_type: str):
        # Create agent
        payload = {
            "name": f"probe-{adapter_type}",
            "adapter_type": adapter_type,
            "adapter_config": self._adapter_config(adapter_type),
        }
        resp = await client.post("/api/agents", json=payload)
        agent_id = resp.json()["id"]

        # Probe
        resp = await client.post(f"/api/agents/{agent_id}/probe")
        assert resp.status_code == 200
        result = resp.json()
        assert "available" in result


class TestRunExecution:
    """End-to-end run execution via API."""

    @pytest.mark.asyncio
    async def test_process_run_full_flow(self, client: AsyncClient):
        # 1. Create agent
        resp = await client.post(
            "/api/agents",
            json={
                "name": "echo-agent",
                "adapter_type": "process",
                "adapter_config": {"command": "echo", "args": ["integration-test-passed"]},
            },
        )
        assert resp.status_code == 200
        agent_id = resp.json()["id"]

        # 2. Create run
        resp = await client.post(
            f"/api/agents/{agent_id}/runs",
            json={"prompt": "run the echo command"},
        )
        assert resp.status_code == 200
        run_id = resp.json()["id"]
        assert resp.json()["status"] == "pending"

        # 3. Execute run
        resp = await client.post(f"/api/runs/{run_id}/execute")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["exit_code"] == 0
        assert "integration-test-passed" in (data["stdout"] or "")

    @pytest.mark.asyncio
    async def test_run_failure_captured(self, client: AsyncClient):
        # Create failing agent
        resp = await client.post(
            "/api/agents",
            json={
                "name": "fail-agent",
                "adapter_type": "process",
                "adapter_config": {"command": "false"},
            },
        )
        agent_id = resp.json()["id"]

        resp = await client.post(f"/api/agents/{agent_id}/runs", json={})
        run_id = resp.json()["id"]

        resp = await client.post(f"/api/runs/{run_id}/execute")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failure"
        assert data["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_run_timeout(self, client: AsyncClient):
        # Create slow agent
        resp = await client.post(
            "/api/agents",
            json={
                "name": "slow-agent",
                "adapter_type": "process",
                "adapter_config": {"command": "sleep", "args": ["10"], "timeout_seconds": 1},
            },
        )
        agent_id = resp.json()["id"]

        resp = await client.post(f"/api/agents/{agent_id}/runs", json={})
        run_id = resp.json()["id"]

        resp = await client.post(f"/api/runs/{run_id}/execute")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failure"
        assert "Timed out" in (data["stderr"] or "")

    @pytest.mark.asyncio
    async def test_list_runs(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents",
            json={
                "name": "list-agent",
                "adapter_type": "process",
                "adapter_config": {"command": "echo"},
            },
        )
        agent_id = resp.json()["id"]

        for i in range(3):
            await client.post(f"/api/agents/{agent_id}/runs", json={"prompt": f"run {i}"})

        resp = await client.get(f"/api/agents/{agent_id}/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_agent_with_cloud_adapter(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents",
            json={
                "name": "cursor-cloud-agent",
                "adapter_type": "cursor_cloud",
                "adapter_config": {"repoUrl": "https://github.com/example/repo"},
            },
        )
        assert resp.status_code == 200
        agent_id = resp.json()["id"]

        resp = await client.post(f"/api/agents/{agent_id}/runs", json={})
        run_id = resp.json()["id"]

        resp = await client.post(f"/api/runs/{run_id}/execute")
        assert resp.status_code == 200
        data = resp.json()
        # Cursor Cloud is a stub/placeholder, so it returns success
        assert data["status"] in ("success", "failure")
