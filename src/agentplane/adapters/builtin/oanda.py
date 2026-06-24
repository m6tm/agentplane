"""OANDA data provider adapter.

Fetches forex/CFD market data from the OANDA REST v3 API.
Supports demo (practice) and live environments.
"""

import json
from typing import Any

import httpx

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter
from agentplane.core.config import settings

PRACTICE_HOST = "api-fxpractice.oanda.com"
LIVE_HOST = "api-fxtrade.oanda.com"


@register_adapter
class OandaAdapter(Adapter):
    """Fetch market data from OANDA."""

    @property
    def type(self) -> str:
        return "oanda"

    @property
    def label(self) -> str:
        return "OANDA"

    def _host(self, environment: str | None) -> str:
        return PRACTICE_HOST if environment != "live" else LIVE_HOST

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _normalize_symbol(self, symbol: str) -> str:
        """Ensure OANDA instrument format: EUR_USD."""
        return symbol.upper().replace("/", "_")

    async def execute(
        self,
        ctx: AdapterContext,
        on_log: Any | None = None,
    ) -> AdapterResult:
        config = ctx.config or {}
        action = config.get("action", "fetch_history")
        symbol = self._normalize_symbol(config.get("symbol", ""))
        token = config.get("token") or settings.oanda_token or ""
        account_id = config.get("account_id") or settings.oanda_account_id or ""
        environment = config.get("environment", "practice")

        if not symbol:
            return AdapterResult(success=False, stderr="symbol is required")
        if not token:
            return AdapterResult(success=False, stderr="token is required")

        host = self._host(environment)

        try:
            if action == "fetch_history":
                return await self._fetch_history(host, token, symbol, config)
            if action == "fetch_last_price":
                if not account_id:
                    return AdapterResult(
                        success=False, stderr="account_id is required for pricing"
                    )
                return await self._fetch_last_price(host, token, account_id, symbol)
            return AdapterResult(success=False, stderr=f"Unknown action: {action}")
        except Exception as e:
            return AdapterResult(success=False, stderr=str(e))

    async def _fetch_history(
        self,
        host: str,
        token: str,
        symbol: str,
        config: dict[str, Any],
    ) -> AdapterResult:
        granularity = config.get("granularity", "D")  # OANDA granularity
        count = config.get("count", 100)

        url = f"https://{host}/v3/instruments/{symbol}/candles"
        params = {
            "price": "M",
            "granularity": granularity,
            "count": count,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=self._headers(token), params=params, timeout=30.0
            )
            response.raise_for_status()
            payload = response.json()

        records = self._parse_candles(payload.get("candles", []))
        return AdapterResult(
            success=True,
            stdout=json.dumps({
                "symbol": symbol,
                "granularity": granularity,
                "records": records,
            }),
            summary=f"Fetched {len(records)} candles for {symbol}",
            exit_code=0,
        )

    def _parse_candles(self, candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records = []
        for candle in candles:
            mid = candle.get("mid") or {}
            try:
                records.append({
                    "timestamp": candle["time"],
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                    "volume": int(candle.get("volume", 0)),
                    "complete": candle.get("complete", True),
                })
            except (KeyError, ValueError, TypeError):
                continue
        return records

    async def _fetch_last_price(
        self,
        host: str,
        token: str,
        account_id: str,
        symbol: str,
    ) -> AdapterResult:
        url = f"https://{host}/v3/accounts/{account_id}/pricing"
        params = {"instruments": symbol}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=self._headers(token), params=params, timeout=30.0
            )
            response.raise_for_status()
            payload = response.json()

        prices = payload.get("prices", [])
        if not prices:
            return AdapterResult(success=False, stderr="No pricing data returned")

        price_data = prices[0]
        bid = float(price_data.get("closeoutBid", 0))
        ask = float(price_data.get("closeoutAsk", 0))
        mid = round((bid + ask) / 2, 5) if bid and ask else (bid or ask)

        return AdapterResult(
            success=True,
            stdout=json.dumps({"symbol": symbol, "price": mid}),
            summary=f"Last price for {symbol}: {mid}",
            exit_code=0,
        )

    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        token = config.get("token") or ""
        account_id = config.get("account_id") or ""
        environment = config.get("environment", "practice")

        if not token:
            return {
                "available": False,
                "note": "OANDA token is missing",
            }

        host = self._host(environment)
        url = f"https://{host}/v3/accounts"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, headers=self._headers(token), timeout=10.0
                )
                response.raise_for_status()
            return {
                "available": True,
                "note": "OANDA API reachable",
                "environment": environment,
                "account_id_configured": bool(account_id),
            }
        except Exception as e:
            return {
                "available": False,
                "note": f"Could not reach OANDA: {e}",
            }

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "actions": ["fetch_history", "fetch_last_price"],
            "default_action": "fetch_history",
            "requires": ["token"],
            "optional": ["account_id", "environment"],
        }
