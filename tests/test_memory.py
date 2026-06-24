"""Tests for agentic memory: lessons influence future decisions."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from agentplane.api.main import app
from agentplane.core.db import get_async_session, init_async_db
from agentplane.core.models import (
    AgentCreate,
    Lesson,
    LessonSeverity,
    Signal,
    SignalDirection,
    SignalStatus,
    StrategyCreate,
    StrategyTimeframe,
    TradingDeskCreate,
)
from agentplane.services.agent_service import AgentService
from agentplane.services.risk_service import RiskService
from agentplane.services.trading_service import StrategyService, TradingDeskService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_async_db()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def memory_setup():
    desk_service = TradingDeskService()
    strategy_service = StrategyService()
    agent_service = AgentService()

    desk = await desk_service.create(
        TradingDeskCreate(name="memory-desk", initial_capital_usd=10000)
    )
    strategy = await strategy_service.create(
        StrategyCreate(
            name="always-long",
            timeframe=StrategyTimeframe.DAILY,
            entry_rules={"type": "always_long"},
        )
    )
    agent = await agent_service.create(
        AgentCreate(
            name="memory-trader",
            trading_desk_id=desk.id,
            strategy_id=strategy.id,
            adapter_type="paper_broker",
            adapter_config={"symbol": "AAPL", "broker_adapter": "paper_broker"},
        )
    )
    return {"desk": desk, "strategy": strategy, "agent": agent}


async def _create_signal(agent, setup_name: str = "always-long", price: float = 150.0) -> Signal:
    async with get_async_session() as session:
        signal = Signal(
            agent_id=agent.id,
            symbol="AAPL",
            direction=SignalDirection.LONG,
            confidence=0.5,
            setup_name=setup_name,
            market_data_snapshot={"latest_close": price, "symbol": "AAPL"},
            status=SignalStatus.DETECTED,
        )
        session.add(signal)
        await session.commit()
        await session.refresh(signal)
        return signal


async def _create_lesson(
    agent,
    category: str,
    trigger_pattern: str,
    occurrence_count: int,
    severity: LessonSeverity = LessonSeverity.HIGH,
):
    async with get_async_session() as session:
        lesson = Lesson(
            agent_id=agent.id,
            category=category,
            trigger_pattern=trigger_pattern,
            corrective_action="Test corrective action",
            severity=severity,
            occurrence_count=occurrence_count,
            active=True,
        )
        session.add(lesson)
        await session.commit()


@pytest.mark.asyncio
async def test_memory_blocks_setup_after_recurring_discipline(memory_setup):
    agent = memory_setup["agent"]
    await _create_lesson(agent, "discipline", "always-long", 3)

    signal = await _create_signal(agent)
    risk_service = RiskService()
    check = await risk_service.validate_signal(agent, signal)

    assert check.allowed is False
    assert "Blocked by active memory lesson" in (check.reason or "")


@pytest.mark.asyncio
async def test_memory_reduces_size_after_risk_management_lesson(memory_setup):
    agent = memory_setup["agent"]
    await _create_lesson(agent, "risk_management", "loss_exceeds_2pct", 2)

    signal = await _create_signal(agent, price=150.0)
    risk_service = RiskService()
    check = await risk_service.validate_signal(agent, signal)

    assert check.allowed is True
    # Without multiplier size would be ~0.6667 (1% of 10000 / 150)
    # With multiplier 0.5 it should be ~0.3333
    assert check.size is not None
    assert check.size < 0.5


@pytest.mark.asyncio
async def test_api_memory_context(client: AsyncClient, memory_setup):
    agent = memory_setup["agent"]
    await _create_lesson(agent, "discipline", "always-long", 3)
    await _create_lesson(agent, "risk_management", "loss_exceeds_2pct", 2)

    resp = await client.get(f"/api/agents/{agent.id}/memory")
    assert resp.status_code == 200
    context = resp.json()
    assert context["lesson_count"] == 2
    assert context["risk_multiplier"] < 1.0
    assert "always-long" in context["blocked_setups"]
    assert len(context["recommendations"]) == 2


@pytest.mark.asyncio
async def test_signal_service_includes_memory_context(memory_setup):
    agent = memory_setup["agent"]
    await _create_lesson(agent, "discipline", "always-long", 3, LessonSeverity.CRITICAL)
    await _create_lesson(agent, "risk_management", "loss_exceeds_2pct", 2)

    from agentplane.services.signal_service import SignalService

    service = SignalService()

    # Mock market data and memory is already loaded via the lessons above
    data = [
        {
            "timestamp": "2026-06-20",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1000,
        },
        {
            "timestamp": "2026-06-21",
            "open": 100,
            "high": 102,
            "low": 99,
            "close": 101,
            "volume": 1000,
        },
    ]

    with patch.object(service._market_data_service, "fetch_history", return_value=data):
        signal = await service.generate(agent)

    assert signal is not None
    assert "memory_context" in signal.market_data_snapshot
    assert signal.market_data_snapshot["memory_context"]["lesson_count"] == 2
    assert signal.confidence == 0.3  # critical lessons lower confidence
