"""Tests for trade journal and lesson extraction."""

import pytest
from httpx import ASGITransport, AsyncClient

from agentplane.api.main import app
from agentplane.core.db import get_async_session, init_async_db
from agentplane.core.models import (
    AgentCreate,
    Signal,
    SignalDirection,
    SignalStatus,
    StrategyCreate,
    StrategyTimeframe,
    TradingDeskCreate,
)
from agentplane.services.agent_service import AgentService
from agentplane.services.journal_service import JournalService
from agentplane.services.lesson_service import LessonService
from agentplane.services.order_service import OrderService
from agentplane.services.position_service import PositionService
from agentplane.services.trading_service import StrategyService, TradingDeskService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_async_db()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def trading_setup():
    desk_service = TradingDeskService()
    strategy_service = StrategyService()
    agent_service = AgentService()

    desk = await desk_service.create(
        TradingDeskCreate(name="journal-desk", initial_capital_usd=10000)
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
            name="journal-trader",
            trading_desk_id=desk.id,
            strategy_id=strategy.id,
            adapter_type="paper_broker",
            adapter_config={"symbol": "AAPL", "broker_adapter": "paper_broker"},
        )
    )
    return {"desk": desk, "strategy": strategy, "agent": agent}


async def _create_signal(agent, symbol: str = "AAPL", price: float = 150.0) -> Signal:
    async with get_async_session() as session:
        signal = Signal(
            agent_id=agent.id,
            symbol=symbol,
            direction=SignalDirection.LONG,
            confidence=0.5,
            setup_name="test-setup",
            market_data_snapshot={"latest_close": price, "symbol": symbol},
            status=SignalStatus.DETECTED,
        )
        session.add(signal)
        await session.commit()
        await session.refresh(signal)
        return signal


@pytest.mark.asyncio
async def test_journal_service_creates_entry(trading_setup):
    agent = trading_setup["agent"]
    order_service = OrderService()
    position_service = PositionService()
    journal_service = JournalService()

    signal = await _create_signal(agent)
    result = await order_service.execute_signal(agent, signal, size=10)
    assert result.success is True

    trade = await position_service.close_position(agent, result.position.id, current_price=160.0)
    assert trade is not None

    journal = await journal_service.get_for_trade(trade.id)
    assert journal is not None
    assert journal.agent_id == agent.id
    assert "AAPL" in journal.pre_trade_notes
    assert journal.discipline_score is not None
    assert 1 <= journal.discipline_score <= 10
    assert trade.journal_entry_id == journal.id


@pytest.mark.asyncio
async def test_lesson_service_extracts_discipline_lesson(trading_setup):
    agent = trading_setup["agent"]
    order_service = OrderService()
    position_service = PositionService()
    lesson_service = LessonService()

    signal = await _create_signal(agent)
    result = await order_service.execute_signal(agent, signal, size=10)
    assert result.success is True

    # Close at a loss very quickly to trigger the discipline lesson
    trade = await position_service.close_position(agent, result.position.id, current_price=140.0)
    assert trade is not None
    assert trade.outcome == "loss"

    lessons = await lesson_service.list_for_agent(agent.id)
    assert len(lessons) >= 1
    categories = {lesson.category for lesson in lessons}
    assert "discipline" in categories or "risk_management" in categories


@pytest.mark.asyncio
async def test_api_list_journals_and_lessons(client: AsyncClient, trading_setup):
    agent = trading_setup["agent"]
    order_service = OrderService()
    position_service = PositionService()

    signal = await _create_signal(agent)
    result = await order_service.execute_signal(agent, signal, size=10)
    trade = await position_service.close_position(agent, result.position.id, current_price=140.0)
    assert trade is not None

    resp = await client.get(f"/api/agents/{agent.id}/journal")
    assert resp.status_code == 200
    journals = resp.json()
    assert len(journals) == 1
    assert journals[0]["agent_id"] == agent.id

    resp = await client.get(f"/api/agents/{agent.id}/lessons")
    assert resp.status_code == 200
    lessons = resp.json()
    assert len(lessons) >= 1


@pytest.mark.asyncio
async def test_api_get_trade_journal(client: AsyncClient, trading_setup):
    agent = trading_setup["agent"]
    order_service = OrderService()
    position_service = PositionService()

    signal = await _create_signal(agent)
    result = await order_service.execute_signal(agent, signal, size=5)
    trade = await position_service.close_position(agent, result.position.id, current_price=155.0)
    assert trade is not None

    resp = await client.get(f"/api/agents/{agent.id}/trades/{trade.id}/journal")
    assert resp.status_code == 200
    journal = resp.json()
    assert journal["trade_id"] == trade.id
