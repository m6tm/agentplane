"""Tests for the market data service and cache."""

import pytest

from agentplane.core.db import get_async_session, init_async_db
from agentplane.core.models import (
    AgentCreate,
    MarketData,
    StrategyCreate,
    StrategyTimeframe,
    TradingDeskCreate,
)
from agentplane.services.agent_service import AgentService
from agentplane.services.market_data_service import MarketDataService
from agentplane.services.trading_service import StrategyService, TradingDeskService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_async_db()
    async with get_async_session() as session:
        from sqlalchemy import delete
        await session.execute(delete(MarketData))
        await session.commit()


@pytest.fixture
async def agent():
    desk_service = TradingDeskService()
    strategy_service = StrategyService()
    agent_service = AgentService()

    desk = await desk_service.create(
        TradingDeskCreate(name="data-desk", initial_capital_usd=10000)
    )
    strategy = await strategy_service.create(
        StrategyCreate(
            name="always-long",
            timeframe=StrategyTimeframe.DAILY,
            entry_rules={"type": "always_long"},
        )
    )
    return await agent_service.create(
        AgentCreate(
            name="data-trader",
            trading_desk_id=desk.id,
            strategy_id=strategy.id,
            adapter_type="paper_broker",
            adapter_config={"symbol": "EUR_USD", "data_adapter": "static_data"},
        )
    )


@pytest.mark.asyncio
async def test_fetch_history_with_static_data(agent):
    service = MarketDataService()
    records = await service.fetch_history(agent, "EUR_USD", period="5d", interval="1d")

    assert len(records) >= 2
    assert "timestamp" in records[0]
    assert "close" in records[0]


@pytest.mark.asyncio
async def test_cache_stores_records(agent):
    service = MarketDataService()
    records = await service.fetch_history(agent, "EUR_USD", period="5d", interval="1d")
    assert len(records) > 0

    cached = await service._get_cached("EUR_USD", "1d")
    assert len(cached) == len(records)
    assert cached[-1]["close"] == records[-1]["close"]


@pytest.mark.asyncio
async def test_get_last_price_from_cache(agent):
    service = MarketDataService()
    records = await service.fetch_history(agent, "EUR_USD", period="5d", interval="1d")

    price = await service.get_last_price(agent, "EUR_USD")
    assert price is not None
    assert price == records[-1]["close"]


@pytest.mark.asyncio
async def test_adapter_failure_falls_back_to_cache(agent):
    service = MarketDataService()
    records = await service.fetch_history(agent, "EUR_USD", period="5d", interval="1d")
    assert len(records) > 0

    # Force an unknown adapter to simulate failure
    agent.adapter_config["data_adapter"] = "nonexistent_adapter"
    fallback_records = await service.fetch_history(agent, "EUR_USD", period="5d", interval="1d")

    assert len(fallback_records) == len(records)
