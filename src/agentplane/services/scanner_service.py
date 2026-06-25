"""Multi-pair scanner service.

Allows agents to scan multiple symbols and timeframes in rotation,
looking for opportunities that match their trading style.
"""

from typing import Any

import structlog

from agentplane.core.models import Agent, Signal, SignalDirection, SignalStatus, AgentUpdate
from agentplane.services.market_data_service import MarketDataService
from agentplane.services.memory_service import MemoryService
from agentplane.services.llm_service import LLMService
from agentplane.core.db import get_async_session

logger = structlog.get_logger()


class ScannerService:
    """Scan multiple pairs/timeframes for trading opportunities."""

    def __init__(self):
        self._market_data_service = MarketDataService()
        self._memory_service = MemoryService()

    async def scan_next(self, agent: Agent) -> Signal | None:
        """Scan the next item in the agent's watchlist.
        
        Rotates through the watchlist and returns a signal if found.
        """
        watchlist = agent.watchlist or []
        if not watchlist:
            # Fallback to single symbol from adapter_config
            symbol = agent.adapter_config.get("symbol")
            interval = agent.adapter_config.get("interval", "1h")
            period = agent.adapter_config.get("period", "5d")
            if symbol:
                watchlist = [{"symbol": symbol, "interval": interval, "period": period}]
            else:
                logger.warning("scanner.no_watchlist", agent_id=agent.id)
                return None

        # Get current scan position
        scan_index = agent.scan_index or 0
        if scan_index >= len(watchlist):
            scan_index = 0

        item = watchlist[scan_index]
        symbol = item.get("symbol")
        interval = item.get("interval", "1h")
        period = item.get("period", "5d")

        if not symbol:
            logger.warning("scanner.invalid_item", agent_id=agent.id, item=item)
            return None

        logger.info(
            "scanner.checking",
            agent_id=agent.id,
            symbol=symbol,
            interval=interval,
            index=scan_index,
            total=len(watchlist),
        )

        # Fetch market data for this symbol/interval
        data = await self._market_data_service.fetch_history(
            agent,
            symbol,
            period=period,
            interval=interval,
        )

        if not data or len(data) < 2:
            logger.warning("scanner.no_data", agent_id=agent.id, symbol=symbol, interval=interval)
            return None

        # Simple strategy: price above/below previous close
        direction = self._evaluate_price_action(data)
        
        if direction is None:
            # Advance to next item for next heartbeat
            await self._advance_scan_index(agent, len(watchlist))
            return None

        # Found a signal!
        memory_context = await self._memory_service.compute_context(agent.id)
        confidence = 0.3 if memory_context["critical_count"] > 0 else 0.5

        snapshot = {
            "symbol": symbol,
            "interval": interval,
            "latest_close": data[-1]["close"],
            "previous_close": data[-2]["close"] if len(data) > 1 else None,
            "latest_timestamp": data[-1]["timestamp"],
        }

        async with get_async_session() as session:
            signal = Signal(
                agent_id=agent.id,
                symbol=symbol,
                direction=direction,
                confidence=confidence,
                setup_name=f"{agent.role}_{interval}",
                market_data_snapshot=snapshot,
                status=SignalStatus.DETECTED,
            )
            session.add(signal)
            await session.commit()
            await session.refresh(signal)

        logger.info(
            "scanner.signal_found",
            agent_id=agent.id,
            signal_id=signal.id,
            symbol=symbol,
            interval=interval,
            direction=direction,
        )

        # Advance to next item
        await self._advance_scan_index(agent, len(watchlist))
        
        return signal

    def _evaluate_price_action(self, data: list[dict[str, Any]]) -> SignalDirection | None:
        """Simple price action evaluation."""
        if len(data) < 2:
            return None
        
        current = data[-1]["close"]
        previous = data[-2]["close"]
        
        # Require a minimum move of 0.1% to avoid noise
        threshold = previous * 0.001
        
        if current > previous + threshold:
            return SignalDirection.LONG
        elif current < previous - threshold:
            return SignalDirection.SHORT
        
        return None

    async def _advance_scan_index(self, agent: Agent, watchlist_size: int) -> None:
        """Advance the scan index to the next item."""
        from agentplane.services.agent_service import AgentService
        
        next_index = (agent.scan_index + 1) % watchlist_size if watchlist_size > 0 else 0
        await AgentService().update(agent.id, AgentUpdate(scan_index=next_index))
        
        logger.debug(
            "scanner.advanced",
            agent_id=agent.id,
            old_index=agent.scan_index,
            new_index=next_index,
        )
