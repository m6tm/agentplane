"""Risk management service.

Validates signals before execution and computes position sizes based on
strategy and desk risk limits.
"""

from typing import Any

from sqlalchemy import select

from agentplane.core.db import get_async_session
from agentplane.core.models import (
    Agent,
    Position,
    PositionStatus,
    Signal,
    TradingDesk,
)
from agentplane.services.memory_service import MemoryService


class RiskCheck:
    """Result of a risk validation."""

    def __init__(self, allowed: bool, reason: str | None = None, size: float | None = None):
        self.allowed = allowed
        self.reason = reason
        self.size = size

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "size": self.size,
        }


class RiskService:
    """Validate trading signals against desk and agent risk limits."""

    def __init__(self):
        self._memory_service = MemoryService()

    async def validate_signal(self, agent: Agent, signal: Signal) -> RiskCheck:
        """Validate a signal and return position size if allowed."""
        if agent.trading_desk_id is None:
            return RiskCheck(allowed=False, reason="Agent has no trading desk")

        async with get_async_session() as session:
            result = await session.execute(
                select(TradingDesk).where(TradingDesk.id == agent.trading_desk_id)
            )
            desk = result.scalar_one_or_none()
            if desk is None:
                return RiskCheck(allowed=False, reason="Trading desk not found")

            # Desk-level checks
            if desk.status != "active":
                return RiskCheck(allowed=False, reason=f"Desk is {desk.status}")

            open_positions_count = await self._count_open_positions(session, agent.id)
            if (
                desk.max_open_positions is not None
                and open_positions_count >= desk.max_open_positions
            ):
                return RiskCheck(allowed=False, reason="Max open positions reached")

            # Daily loss check
            daily_pnl = await self._daily_realized_pnl(session, agent.id)
            if desk.max_daily_loss_usd is not None and daily_pnl <= -desk.max_daily_loss_usd:
                return RiskCheck(allowed=False, reason="Max daily loss reached")

            # Agent budget check
            if agent.max_budget_usd is not None and agent.spent_budget_usd >= agent.max_budget_usd:
                return RiskCheck(allowed=False, reason="Agent budget exhausted")

            # Memory-driven setup blocking
            if await self._memory_service.is_setup_blocked(agent.id, signal.setup_name):
                return RiskCheck(
                    allowed=False,
                    reason="Blocked by active memory lesson for this setup pattern",
                )

            # Compute position size with memory risk multiplier
            risk_multiplier = await self._memory_service.get_risk_multiplier(agent.id)
            size = await self._compute_position_size(
                session, agent, desk, signal, risk_multiplier
            )
            if size <= 0:
                return RiskCheck(allowed=False, reason="Computed position size is zero")

            if desk.max_position_size_usd is not None:
                price = signal.market_data_snapshot.get("latest_close", 0)
                notional = size * price
                if notional > desk.max_position_size_usd:
                    size = desk.max_position_size_usd / price if price > 0 else 0

            if size <= 0:
                return RiskCheck(allowed=False, reason="Position size exceeds max position size")

            return RiskCheck(allowed=True, size=size)

    async def _count_open_positions(self, session, agent_id: str) -> int:
        result = await session.execute(
            select(Position).where(
                Position.agent_id == agent_id,
                Position.status == PositionStatus.OPEN,
            )
        )
        return len(result.scalars().all())

    async def _daily_realized_pnl(self, session, agent_id: str) -> float:
        # Approximation: we do not have per-order P&L yet, so return 0.0
        # This will be refined once order tracking includes realized P&L.
        return 0.0

    async def _compute_position_size(
        self,
        session,
        agent: Agent,
        desk: TradingDesk,
        signal: Signal,
        risk_multiplier: float = 1.0,
    ) -> float:
        """Compute position size in shares/contracts."""
        from agentplane.services.trading_service import StrategyService

        strategy = await StrategyService().get(agent.strategy_id) if agent.strategy_id else None
        risk_pct = strategy.risk_per_trade_pct if strategy else 1.0

        price = signal.market_data_snapshot.get("latest_close", 0)
        if price <= 0:
            return 0.0

        capital = desk.current_capital_usd
        risk_amount = capital * (risk_pct / 100) * risk_multiplier

        # Simplified sizing: risk amount = position notional
        # In a real system this would use stop distance.
        notional = risk_amount
        size = notional / price
        return round(size, 6)
