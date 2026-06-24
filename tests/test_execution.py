"""Tests for order execution and position tracking."""

import pytest
from httpx import ASGITransport, AsyncClient

from agentplane.api.main import app
from agentplane.core.db import get_async_session, init_async_db
from agentplane.core.models import (
    AgentCreate,
    OrderSide,
    OrderStatus,
    PositionStatus,
    Signal,
    SignalDirection,
    SignalStatus,
    StrategyCreate,
    StrategyTimeframe,
    TradingDeskCreate,
)
from agentplane.services.agent_service import AgentService
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
        TradingDeskCreate(name="exec-desk", initial_capital_usd=10000)
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
            name="exec-trader",
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
async def test_order_service_executes_signal(trading_setup):
    agent = trading_setup["agent"]
    signal = await _create_signal(agent)

    order_service = OrderService()
    result = await order_service.execute_signal(agent, signal, size=10)

    assert result.success is True
    assert result.order is not None
    assert result.order.status == OrderStatus.FILLED
    assert result.order.side == OrderSide.BUY
    assert result.position is not None
    assert result.position.status == PositionStatus.OPEN
    assert result.position.quantity == 10


@pytest.mark.asyncio
async def test_position_service_close_position(trading_setup):
    agent = trading_setup["agent"]
    order_service = OrderService()
    position_service = PositionService()

    signal = await _create_signal(agent)
    result = await order_service.execute_signal(agent, signal, size=10)
    assert result.success is True
    position_id = result.position.id

    trade = await position_service.close_position(agent, position_id, current_price=160.0)
    assert trade is not None
    assert trade.realized_pnl_usd > 0
    assert trade.outcome == "win"

    position = await position_service.get(position_id)
    assert position.status == PositionStatus.CLOSED


@pytest.mark.asyncio
async def test_api_list_positions_and_orders(client: AsyncClient, trading_setup):
    agent = trading_setup["agent"]
    order_service = OrderService()

    signal = await _create_signal(agent)
    await order_service.execute_signal(agent, signal, size=5)

    resp = await client.get(f"/api/agents/{agent.id}/positions")
    assert resp.status_code == 200
    positions = resp.json()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"

    resp = await client.get(f"/api/agents/{agent.id}/orders")
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) == 1
    assert orders[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_api_close_position(client: AsyncClient, trading_setup):
    agent = trading_setup["agent"]
    order_service = OrderService()

    signal = await _create_signal(agent)
    result = await order_service.execute_signal(agent, signal, size=5)
    position_id = result.position.id

    resp = await client.post(
        f"/api/agents/{agent.id}/positions/{position_id}/close",
        json={"current_price": 160.0},
    )
    assert resp.status_code == 200
    trade = resp.json()
    assert trade["symbol"] == "AAPL"
    assert trade["outcome"] == "win"
