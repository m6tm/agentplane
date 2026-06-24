"""Static/synthetic data provider adapter.

Generates deterministic OHLCV bars without any network call. Useful for tests,
backtests and offline development.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class StaticDataAdapter(Adapter):
    """Generate deterministic market data for testing."""

    @property
    def type(self) -> str:
        return "static_data"

    @property
    def label(self) -> str:
        return "Static Data"

    async def execute(
        self,
        ctx: AdapterContext,
        on_log: Any | None = None,
    ) -> AdapterResult:
        config = ctx.config or {}
        action = config.get("action", "fetch_history")
        symbol = config.get("symbol", "EUR_USD")

        if action == "fetch_history":
            period = config.get("period", "5d")
            interval = config.get("interval", "1d")
            count = self._period_to_count(period, interval)
            records = self._generate_history(symbol, count, interval)
            return AdapterResult(
                success=True,
                stdout=json.dumps({
                    "symbol": symbol,
                    "period": period,
                    "interval": interval,
                    "records": records,
                }),
                summary=f"Generated {len(records)} static bars for {symbol}",
                exit_code=0,
            )

        if action == "fetch_last_price":
            price = self._generate_price(symbol, 0)
            return AdapterResult(
                success=True,
                stdout=json.dumps({"symbol": symbol, "price": price}),
                summary=f"Static last price for {symbol}: {price}",
                exit_code=0,
            )

        return AdapterResult(success=False, stderr=f"Unknown action: {action}")

    def _period_to_count(self, period: str, interval: str) -> int:
        """Approximate number of bars for a period/interval pair."""
        period_days = {
            "1d": 1,
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
        }
        days = period_days.get(period, 5)
        if interval in ("1m", "1min"):
            return min(days * 24 * 60, 5000)
        if interval in ("5m", "5min"):
            return min(days * 24 * 12, 5000)
        if interval in ("15m", "15min"):
            return min(days * 24 * 4, 5000)
        if interval in ("1h", "60m"):
            return days * 24
        return days

    def _generate_history(
        self,
        symbol: str,
        count: int,
        interval: str,
    ) -> list[dict[str, Any]]:
        """Generate a deterministic upward-trending series."""
        records = []
        base_price = self._base_price(symbol)
        step_minutes = self._interval_minutes(interval)
        now = datetime.utcnow().replace(second=0, microsecond=0)
        for i in range(count, 0, -1):
            idx = count - i
            ts = now - timedelta(minutes=i * step_minutes)
            price = self._generate_price(symbol, idx, base_price)
            records.append({
                "timestamp": ts.isoformat(),
                "open": round(price * 0.999, 5),
                "high": round(price * 1.002, 5),
                "low": round(price * 0.998, 5),
                "close": round(price, 5),
                "volume": 1000 + idx * 10,
            })
        return records

    def _generate_price(self, symbol: str, idx: int, base_price: float | None = None) -> float:
        """Generate a deterministic pseudo-price from symbol and index."""
        seed = sum(ord(c) for c in symbol)
        if base_price is None:
            base_price = self._base_price(symbol)
        # Deterministic small oscillation around a slight upward drift
        drift = idx * 0.0005
        oscillation = ((seed + idx) % 17 - 8) * 0.001
        return round(base_price * (1 + drift + oscillation), 5)

    def _base_price(self, symbol: str) -> float:
        """Derive a plausible base price from the symbol seed."""
        seed = sum(ord(c) for c in symbol)
        return round(1.0 + (seed % 100) / 100, 2)

    def _interval_minutes(self, interval: str) -> int:
        mapping = {
            "1m": 1,
            "1min": 1,
            "5m": 5,
            "5min": 5,
            "15m": 15,
            "15min": 15,
            "1h": 60,
            "60m": 60,
            "1d": 60 * 24,
            "D": 60 * 24,
        }
        return mapping.get(interval, 60 * 24)

    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "available": True,
            "note": "Static data provider is always available",
            "mode": "offline",
        }

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "actions": ["fetch_history", "fetch_last_price"],
            "default_action": "fetch_history",
            "mode": "offline",
        }
