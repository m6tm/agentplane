"""Order execution service.

Creates and executes orders via the configured broker adapter.
"""

import json
from datetime import datetime
from typing import Any

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
    Signal,
    SignalDirection,
)


class OrderResult:
    """Result of an order execution."""

    def __init__(
        self,
        success: bool,
        order: Order | None = None,
        position: Position | None = None,
        reason: str | None = None,
    ):
        self.success = success
        self.order = order
        self.position = position
        self.reason = reason


class OrderService:
    """Execute orders for validated signals."""

    async def execute_signal(
        self,
        agent: Agent,
        signal: Signal,
        size: float,
    ) -> OrderResult:
        """Execute a signal by creating an order and a position."""
        broker_adapter_type = agent.adapter_config.get("broker_adapter", "paper_broker")
        adapter = get_adapter(broker_adapter_type)
        if adapter is None:
            return OrderResult(
                success=False, reason=f"Unknown broker adapter: {broker_adapter_type}"
            )

        price = signal.market_data_snapshot.get("latest_close", 0)
        side = OrderSide.BUY if signal.direction == SignalDirection.LONG else OrderSide.SELL

        async with get_async_session() as session:
            # Create pending order
            order = Order(
                agent_id=agent.id,
                symbol=signal.symbol,
                side=side,
                quantity=size,
                order_type="market",
                status=OrderStatus.PENDING,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            # Execute via broker adapter
            ctx = AdapterContext(
                run_id=f"order-{order.id}",
                agent_id=agent.id,
                config={
                    "action": "buy" if side == OrderSide.BUY else "sell",
                    "symbol": signal.symbol,
                    "quantity": size,
                    "price": price,
                    "slippage_pct": agent.adapter_config.get("slippage_pct", 0.05),
                    "commission_usd": agent.adapter_config.get("commission_usd", 0.0),
                },
            )
            adapter_result = await adapter.execute(ctx)

            if not adapter_result.success:
                order.status = OrderStatus.REJECTED
                order.filled_at = datetime.utcnow()
                await session.commit()
                return OrderResult(success=False, order=order, reason=adapter_result.stderr)

            # Parse fill details
            fill_details = self._parse_fill(adapter_result.stdout)
            order.status = OrderStatus.FILLED
            order.filled_price = fill_details.get("filled_price", price)
            order.filled_quantity = fill_details.get("quantity", size)
            order.commission_usd = fill_details.get("commission_usd", 0.0)
            order.filled_at = datetime.utcnow()
            session.add(order)

            # Create position
            position = Position(
                agent_id=agent.id,
                symbol=signal.symbol,
                direction=signal.direction,
                quantity=order.filled_quantity,
                entry_price=order.filled_price,
                current_price=order.filled_price,
                status=PositionStatus.OPEN,
            )
            session.add(position)
            await session.commit()
            await session.refresh(order)
            await session.refresh(position)

            return OrderResult(success=True, order=order, position=position)

    def _parse_fill(self, stdout: str | None) -> dict[str, Any]:
        """Parse broker adapter output for fill details."""
        if not stdout:
            return {}
        try:
            data = json.loads(stdout.replace("'", '"'))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    async def list_for_agent(self, agent_id: str) -> list[Order]:
        """List orders for an agent."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Order).where(Order.agent_id == agent_id).order_by(Order.created_at.desc())
            )
            return list(result.scalars().all())
