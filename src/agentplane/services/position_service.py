"""Position tracking service.

Manages open positions, updates mark-to-market P&L, and closes positions
into completed trades.
"""

from datetime import datetime

from sqlalchemy import select

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.registry import get_adapter
from agentplane.core.db import get_async_session
from agentplane.core.models import (
    Agent,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    PositionStatus,
    Trade,
)
from agentplane.services.journal_service import JournalService
from agentplane.services.lesson_service import LessonService


class PositionService:
    """Track and close trading positions."""

    async def list_for_agent(self, agent_id: str) -> list[Position]:
        """List positions for an agent."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Position)
                .where(Position.agent_id == agent_id)
                .order_by(Position.opened_at.desc())
            )
            return list(result.scalars().all())

    async def get(self, position_id: str) -> Position | None:
        """Get a position by ID."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Position).where(Position.id == position_id)
            )
            return result.scalar_one_or_none()

    async def update_prices(self, agent: Agent, symbol: str, current_price: float) -> None:
        """Update current price and unrealized P&L for open positions."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Position).where(
                    Position.agent_id == agent.id,
                    Position.symbol == symbol,
                    Position.status == PositionStatus.OPEN,
                )
            )
            positions = result.scalars().all()
            for position in positions:
                position.current_price = current_price
                if position.direction == "long":
                    pnl_pct = (current_price - position.entry_price) / position.entry_price
                else:
                    pnl_pct = (position.entry_price - current_price) / position.entry_price
                position.unrealized_pnl_pct = round(pnl_pct, 6)
                position.unrealized_pnl_usd = round(
                    pnl_pct * position.entry_price * position.quantity, 6
                )
                session.add(position)
            await session.commit()

    async def close_position(
        self,
        agent: Agent,
        position_id: str,
        current_price: float | None = None,
    ) -> Trade | None:
        """Close an open position and create a trade record."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Position).where(
                    Position.id == position_id,
                    Position.status == PositionStatus.OPEN,
                )
            )
            position = result.scalar_one_or_none()
            if position is None:
                return None

            close_price = current_price or position.current_price or position.entry_price
            side = OrderSide.SELL if position.direction == "long" else OrderSide.BUY

            # Execute closing order via broker adapter
            broker_adapter_type = agent.adapter_config.get("broker_adapter", "paper_broker")
            adapter = get_adapter(broker_adapter_type)
            if adapter is None:
                return None

            ctx = AdapterContext(
                run_id=f"close-{position.id}",
                agent_id=agent.id,
                config={
                    "action": "sell" if side == OrderSide.SELL else "buy",
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "price": close_price,
                    "slippage_pct": agent.adapter_config.get("slippage_pct", 0.05),
                    "commission_usd": agent.adapter_config.get("commission_usd", 0.0),
                },
            )
            adapter_result = await adapter.execute(ctx)
            if not adapter_result.success:
                return None

            # Create closing order
            closing_order = Order(
                position_id=position.id,
                agent_id=agent.id,
                symbol=position.symbol,
                side=side,
                quantity=position.quantity,
                order_type="market",
                status=OrderStatus.FILLED,
                filled_price=close_price,
                filled_quantity=position.quantity,
                filled_at=datetime.utcnow(),
            )
            session.add(closing_order)

            # Close position
            position.status = PositionStatus.CLOSED
            position.closed_at = datetime.utcnow()
            session.add(position)

            # Compute realized P&L
            if position.direction == "long":
                pnl_usd = (close_price - position.entry_price) * position.quantity
                pnl_pct = (close_price - position.entry_price) / position.entry_price
            else:
                pnl_usd = (position.entry_price - close_price) * position.quantity
                pnl_pct = (position.entry_price - close_price) / position.entry_price

            duration = None
            if position.closed_at and position.opened_at:
                duration = int((position.closed_at - position.opened_at).total_seconds())

            outcome = "win" if pnl_usd > 0 else ("loss" if pnl_usd < 0 else "breakeven")

            trade = Trade(
                agent_id=agent.id,
                position_id=position.id,
                symbol=position.symbol,
                direction=position.direction,
                entry_price=position.entry_price,
                exit_price=close_price,
                quantity=position.quantity,
                realized_pnl_usd=round(pnl_usd, 6),
                realized_pnl_pct=round(pnl_pct, 6),
                duration_seconds=duration,
                outcome=outcome,
                closed_at=datetime.utcnow(),
            )
            session.add(trade)
            await session.commit()
            await session.refresh(trade)

        # Create journal and extract lessons outside the main session so the
        # trade object is detached and safe to pass around.
        journal_service = JournalService()
        lesson_service = LessonService()
        journal = await journal_service.create_from_trade(trade, position, agent)
        await lesson_service.extract_from_trade(trade, journal)

        return trade
