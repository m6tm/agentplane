"""Market data service.

Reads from a local SQLite cache first, then falls back to the configured data
adapter (OANDA, static_data, etc.). Stores fetched bars back into the cache
for resilience and to reduce API calls.
"""

import json
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.registry import get_adapter
from agentplane.core.db import get_async_session
from agentplane.core.models import Agent, MarketData

logger = structlog.get_logger()


class MarketDataService:
    """Fetch and cache market data for agents."""

    DEFAULT_DATA_ADAPTER = "oanda"

    def __init__(self):
        self._adapter_cache: dict[str, Any] = {}

    async def fetch_history(
        self,
        agent: Agent,
        symbol: str,
        period: str = "5d",
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        """Return OHLCV records, preferring cache then adapter."""
        timeframe = self._interval_to_timeframe(interval)
        data_adapter_type = agent.adapter_config.get("data_adapter", self.DEFAULT_DATA_ADAPTER)

        cached = await self._get_cached(symbol, timeframe)
        if cached and self._is_fresh(cached, interval):
            logger.debug(
                "market_data.cache_hit",
                agent_id=agent.id,
                symbol=symbol,
                timeframe=timeframe,
                bars=len(cached),
            )
            return cached

        records = await self._fetch_from_adapter(
            agent, data_adapter_type, symbol, period, interval
        )
        if records:
            await self._store_records(symbol, timeframe, data_adapter_type, records)
            return records

        if cached:
            logger.warning(
                "market_data.adapter_failed_using_stale_cache",
                agent_id=agent.id,
                symbol=symbol,
                timeframe=timeframe,
            )
            return cached

        return []

    async def get_last_price(self, agent: Agent, symbol: str) -> float | None:
        """Return latest close price from cache or adapter."""
        timeframe = self._interval_to_timeframe("1d")
        cached = await self._get_cached(symbol, timeframe, limit=1, latest=True)
        if cached:
            return cached[0]["close"]

        data_adapter_type = agent.adapter_config.get("data_adapter", self.DEFAULT_DATA_ADAPTER)
        adapter = get_adapter(data_adapter_type)
        if adapter is None:
            return None

        ctx = AdapterContext(
            run_id=f"price-{agent.id}-{datetime.utcnow().isoformat()}",
            agent_id=agent.id,
            config={
                "action": "fetch_last_price",
                "symbol": symbol,
                **agent.adapter_config,
            },
        )
        result = await adapter.execute(ctx)
        if not result.success or not result.stdout:
            return None

        try:
            payload = json.loads(result.stdout)
            return float(payload.get("price", 0))
        except (json.JSONDecodeError, ValueError):
            return None

    async def _fetch_from_adapter(
        self,
        agent: Agent,
        adapter_type: str,
        symbol: str,
        period: str,
        interval: str,
    ) -> list[dict[str, Any]]:
        adapter = get_adapter(adapter_type)
        if adapter is None:
            logger.warning("market_data.unknown_adapter", adapter=adapter_type)
            return []

        ctx = AdapterContext(
            run_id=f"data-{agent.id}-{datetime.utcnow().isoformat()}",
            agent_id=agent.id,
            config={
                "action": "fetch_history",
                "symbol": symbol,
                "period": period,
                "interval": interval,
                **agent.adapter_config,
            },
        )
        result = await adapter.execute(ctx)
        if not result.success or not result.stdout:
            logger.warning("market_data.adapter_failed", stderr=result.stderr)
            return []

        try:
            payload = json.loads(result.stdout)
            return payload.get("records", [])
        except json.JSONDecodeError:
            logger.warning("market_data.invalid_json", stdout=result.stdout)
            return []

    async def _get_cached(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        latest: bool = False,
    ) -> list[dict[str, Any]]:
        async with get_async_session() as session:
            stmt = select(MarketData).where(
                MarketData.symbol == symbol, MarketData.timeframe == timeframe
            )
            if latest:
                stmt = stmt.order_by(MarketData.timestamp.desc())
            else:
                stmt = stmt.order_by(MarketData.timestamp.asc())
            if limit is not None:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            records = []
            for row in result.scalars().all():
                records.append({
                    "timestamp": row.timestamp.isoformat(),
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                })
            return records

    async def _store_records(
        self,
        symbol: str,
        timeframe: str,
        source: str,
        records: list[dict[str, Any]],
    ) -> None:
        async with get_async_session() as session:
            for record in records:
                try:
                    ts = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue

                # Avoid duplicates by checking timestamp
                existing = await session.execute(
                    select(MarketData).where(
                        MarketData.symbol == symbol,
                        MarketData.timeframe == timeframe,
                        MarketData.timestamp == ts,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                session.add(
                    MarketData(
                        symbol=symbol,
                        timeframe=timeframe,
                        source=source,
                        timestamp=ts,
                        open=float(record["open"]),
                        high=float(record["high"]),
                        low=float(record["low"]),
                        close=float(record["close"]),
                        volume=(
                            float(record["volume"])
                            if record.get("volume") is not None
                            else None
                        ),
                    )
                )
            await session.commit()

    def _is_fresh(self, records: list[dict[str, Any]], interval: str) -> bool:
        """Return True if the most recent cached bar is recent enough."""
        if not records:
            return False
        try:
            last_ts = datetime.fromisoformat(records[-1]["timestamp"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False

        now = datetime.utcnow()
        if interval in ("1d", "D"):
            max_age = timedelta(hours=4)
        elif interval in ("1h", "60m"):
            max_age = timedelta(minutes=30)
        else:
            max_age = timedelta(minutes=15)

        return now - last_ts <= max_age

    def _interval_to_timeframe(self, interval: str) -> str:
        """Map common interval names to canonical timeframe names."""
        mapping = {
            "1m": "1m",
            "1min": "1m",
            "5m": "5m",
            "5min": "5m",
            "15m": "15m",
            "15min": "15m",
            "1h": "1h",
            "60m": "1h",
            "1d": "1d",
            "D": "1d",
        }
        return mapping.get(interval, interval)
