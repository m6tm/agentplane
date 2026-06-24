"""Tests for the heartbeat scheduler and signal generation."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from agentplane.api.main import app
from agentplane.core.db import init_async_db
from agentplane.core.models import AgentStatus, AgentUpdate
from agentplane.services.agent_service import AgentService
from agentplane.services.state import scheduler


@pytest.fixture(autouse=True)
async def setup_db():
    await init_async_db()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_start_stop_heartbeat(client: AsyncClient):
    # Create desk
    resp = await client.post(
        "/api/trading-desks",
        json={"name": "scheduler-desk", "initial_capital_usd": 10000},
    )
    desk_id = resp.json()["id"]

    # Create strategy with simple rule
    resp = await client.post(
        "/api/strategies",
        json={
            "name": "always-long",
            "timeframe": "daily",
            "entry_rules": {"type": "always_long"},
        },
    )
    strategy_id = resp.json()["id"]

    # Create agent using static_data to avoid network calls
    resp = await client.post(
        "/api/agents",
        json={
            "name": "scheduler-trader",
            "trading_desk_id": desk_id,
            "strategy_id": strategy_id,
            "adapter_type": "paper_broker",
            "adapter_config": {
                "symbol": "EUR_USD",
                "data_adapter": "static_data",
                "interval": "1d",
                "period": "5d",
            },
            "heartbeat_interval_seconds": 1,
        },
    )
    agent_id = resp.json()["id"]

    # Start heartbeat
    resp = await client.post(f"/api/heartbeats/{agent_id}/start")
    assert resp.status_code == 200
    assert resp.json()["started"] is True

    # Wait for at least one heartbeat
    await asyncio.sleep(2)

    # Stop heartbeat
    resp = await client.post(f"/api/heartbeats/{agent_id}/stop")
    assert resp.status_code == 200
    assert resp.json()["stopped"] is True

    # Verify a signal was generated
    resp = await client.get(f"/api/agents/{agent_id}/signals")
    assert resp.status_code == 200
    signals = resp.json()
    assert len(signals) >= 1
    assert signals[0]["symbol"] == "EUR_USD"

    # Verify an order and position were created by execution
    resp = await client.get(f"/api/agents/{agent_id}/orders")
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) >= 1
    assert orders[0]["status"] == "filled"

    resp = await client.get(f"/api/agents/{agent_id}/positions")
    assert resp.status_code == 200
    positions = resp.json()
    assert len(positions) >= 1
    assert positions[0]["status"] == "open"


@pytest.mark.asyncio
async def test_list_heartbeats(client: AsyncClient):
    resp = await client.get("/api/heartbeats")
    assert resp.status_code == 200
    assert "running" in resp.json()


@pytest.mark.asyncio
async def test_autostart_heartbeats_on_startup(client: AsyncClient):
    # Create desk
    resp = await client.post(
        "/api/trading-desks",
        json={"name": "autostart-desk", "initial_capital_usd": 10000},
    )
    desk_id = resp.json()["id"]

    # Create strategy
    resp = await client.post(
        "/api/strategies",
        json={"name": "autostart-strategy", "timeframe": "daily"},
    )
    strategy_id = resp.json()["id"]

    # Create agent (status defaults to idle)
    resp = await client.post(
        "/api/agents",
        json={
            "name": "autostart-trader",
            "trading_desk_id": desk_id,
            "strategy_id": strategy_id,
            "adapter_type": "paper_broker",
            "adapter_config": {
                "symbol": "EUR_USD",
                "data_adapter": "static_data",
                "interval": "1d",
                "period": "5d",
            },
            "heartbeat_interval_seconds": 1,
        },
    )
    agent_id = resp.json()["id"]

    # Simulate server startup: autostart should pick up the idle agent
    started = await scheduler.start_all_active()
    assert agent_id in started

    # Wait for at least one heartbeat
    await asyncio.sleep(2)

    # Verify heartbeat ran
    resp = await client.get(f"/api/agents/{agent_id}/signals")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_autostart_skips_paused_agents(client: AsyncClient):
    # Create desk
    resp = await client.post(
        "/api/trading-desks",
        json={"name": "paused-desk", "initial_capital_usd": 10000},
    )
    desk_id = resp.json()["id"]

    # Create strategy
    resp = await client.post(
        "/api/strategies",
        json={"name": "paused-strategy", "timeframe": "daily"},
    )
    strategy_id = resp.json()["id"]

    # Create agent and mark it paused
    resp = await client.post(
        "/api/agents",
        json={
            "name": "paused-trader",
            "trading_desk_id": desk_id,
            "strategy_id": strategy_id,
            "adapter_type": "paper_broker",
            "adapter_config": {"symbol": "EUR_USD", "data_adapter": "static_data"},
        },
    )
    agent_id = resp.json()["id"]
    await AgentService().update(agent_id, AgentUpdate(status=AgentStatus.PAUSED))

    started = await scheduler.start_all_active()
    assert agent_id not in started


@pytest.fixture(autouse=True)
async def cleanup_scheduler():
    yield
    await scheduler.stop_all()
