"""Paper broker adapter.

Simulates order execution for paper trading and backtesting.
No real money is moved.
"""

from datetime import datetime
from typing import Any

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter


@register_adapter
class PaperBrokerAdapter(Adapter):
    """Simulate a broker: execute buy/sell orders against provided prices."""

    @property
    def type(self) -> str:
        return "paper_broker"

    @property
    def label(self) -> str:
        return "Paper Broker"

    async def execute(
        self,
        ctx: AdapterContext,
        on_log: Any | None = None,
    ) -> AdapterResult:
        config = ctx.config or {}
        action = config.get("action", "buy")
        symbol = config.get("symbol", "")
        quantity = float(config.get("quantity", 0))
        price = config.get("price")
        slippage_pct = float(config.get("slippage_pct", 0.0))

        if not symbol:
            return AdapterResult(success=False, stderr="symbol is required")
        if quantity <= 0:
            return AdapterResult(success=False, stderr="quantity must be positive")
        if action not in ("buy", "sell"):
            return AdapterResult(success=False, stderr="action must be 'buy' or 'sell'")

        # If no price provided, simulate with a placeholder
        if price is None:
            price = 100.0
        price = float(price)

        # Apply slippage: buys fill higher, sells fill lower
        if action == "buy":
            fill_price = price * (1 + slippage_pct / 100)
        else:
            fill_price = price * (1 - slippage_pct / 100)

        commission = float(config.get("commission_usd", 0.0))
        notional = fill_price * quantity
        total_cost = notional + commission

        result = {
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "requested_price": price,
            "filled_price": round(fill_price, 4),
            "slippage_pct": slippage_pct,
            "commission_usd": commission,
            "notional_usd": round(notional, 4),
            "total_cost_usd": round(total_cost, 4),
            "filled_at": datetime.utcnow().isoformat(),
            "status": "filled",
        }

        summary = f"{action.upper()} {quantity} {symbol} @ {fill_price:.4f}"

        if on_log:
            await on_log("stdout", f"[paper_broker] {summary}\n")

        return AdapterResult(
            success=True,
            stdout=str(result),
            summary=summary,
            exit_code=0,
        )

    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "available": True,
            "note": "Paper broker is always available",
            "mode": "paper",
        }

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "supports": ["buy", "sell"],
            "mode": "paper",
        }
