"""Tests for the orchestrator service and adapter."""

import pytest
from httpx import ASGITransport, AsyncClient

from agentplane.adapters.registry import get_adapter
from agentplane.api.main import app
from agentplane.core.db import init_async_db
from agentplane.core.models import MessageType
from agentplane.services.agent_service import AgentService
from agentplane.services.message_service import MessageService
from agentplane.services.orchestrator_service import (
    DEFAULT_ORCHESTRATOR_NAME,
    OrchestratorService,
)
from agentplane.services.state import scheduler


@pytest.fixture(autouse=True)
async def setup_and_cleanup():
    await init_async_db()
    yield
    await scheduler.stop_all()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_orchestrator_creates_desk_strategies_and_agent():
    service = OrchestratorService()
    agent_id, created = await service.get_or_create_orchestrator()

    assert created is True
    assert agent_id

    agent = await AgentService().get(agent_id)
    assert agent is not None
    assert agent.name == DEFAULT_ORCHESTRATOR_NAME
    assert agent.adapter_type == "orchestrator"
    assert agent.trading_desk_id is not None

    # Second call should return existing orchestrator
    agent_id2, created2 = await service.get_or_create_orchestrator()
    assert created2 is False
    assert agent_id2 == agent_id


@pytest.mark.asyncio
async def test_orchestrator_creates_default_team():
    service = OrchestratorService()
    orchestrator_id, _ = await service.get_or_create_orchestrator()

    created = await service.ensure_team(orchestrator_id)
    assert len(created) == 3

    agents = await AgentService().list()
    names = {a.name for a in agents}
    assert "EURUSD Scalper" in names
    assert "GBPJPY Swing" in names
    assert "Risk Manager" in names

    # Calling again should be idempotent
    created2 = await service.ensure_team(orchestrator_id)
    assert created2 == []


@pytest.mark.asyncio
async def test_orchestrator_run_once_broadcasts_status():
    service = OrchestratorService()
    orchestrator_id, _ = await service.get_or_create_orchestrator()
    await service.ensure_team(orchestrator_id)

    await service.ensure_team(orchestrator_id)
    result = await service.run_once(orchestrator_id)
    assert result["team_size"] == 3
    assert result["message_id"]

    team = [a for a in await AgentService().list() if a.id != orchestrator_id]
    messages = await MessageService().list_unread(team[0].id)
    assert any(m.message_type == MessageType.STATUS for m in messages)


@pytest.mark.asyncio
async def test_orchestrator_adapter_execute():
    adapter = get_adapter("orchestrator")
    assert adapter is not None
    assert adapter.type == "orchestrator"

    service = OrchestratorService()
    orchestrator_id, _ = await service.get_or_create_orchestrator()

    from agentplane.adapters.base import AdapterContext

    ctx = AdapterContext(
        run_id="test-run",
        agent_id=orchestrator_id,
        config={},
    )
    result = await adapter.execute(ctx)
    assert result.success is True
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_send_message_to_orchestrator_route(client: AsyncClient):
    service = OrchestratorService()
    orchestrator_id, _ = await service.get_or_create_orchestrator()

    resp = await client.post(
        "/api/orchestrator/messages",
        json={
            "message_type": "command",
            "payload": {"action": "status"},
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"sent": True}

    # Message should be in the orchestrator inbox
    inbox_before = await MessageService().list_unread(orchestrator_id)
    assert any(m.payload.get("action") == "status" for m in inbox_before)

    # Simulate orchestrator heartbeat processing the inbox
    result = await service.run_once(orchestrator_id)
    assert result["team_size"] == 0  # no team created yet in this test

    # Message should now be marked as read
    inbox_after = await MessageService().list_unread(orchestrator_id)
    assert not any(m.payload.get("action") == "status" for m in inbox_after)


@pytest.mark.asyncio
async def test_scheduler_autostarts_orchestrator(client: AsyncClient):
    started = await scheduler.start_all_active()

    service = OrchestratorService()
    orchestrator_id, _ = await service.get_or_create_orchestrator()

    assert orchestrator_id in started

    agents = await AgentService().list()
    non_orchestrator = [a for a in agents if a.id != orchestrator_id]
    assert len(non_orchestrator) == 3

    await scheduler.stop_all()
