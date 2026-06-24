"""API integration tests."""

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


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_crud(client: AsyncClient):
    # Create
    resp = await client.post("/api/agents", json={
        "name": "test-agent",
        "adapter_type": "process",
        "adapter_config": {"command": "echo"},
    })
    assert resp.status_code == 200
    agent = resp.json()
    assert agent["name"] == "test-agent"

    # List
    resp = await client.get("/api/agents")
    assert len(resp.json()) >= 1

    # Get
    resp = await client.get(f"/api/agents/{agent['id']}")
    assert resp.json()["id"] == agent["id"]

    # Update
    resp = await client.patch(f"/api/agents/{agent['id']}", json={"name": "updated"})
    assert resp.json()["name"] == "updated"

    # Delete
    resp = await client.delete(f"/api/agents/{agent['id']}")
    assert resp.status_code == 200
