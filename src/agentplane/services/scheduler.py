"""Heartbeat scheduler for autonomous traders.

Each agent gets its own asyncio task that wakes up every
`heartbeat_interval_seconds`, fetches market data, applies its strategy,
and generates signals.
"""

import asyncio
from contextlib import suppress

import structlog

from agentplane.core.db import get_async_session
from agentplane.core.models import AgentStatus, AgentUpdate, TradingDesk, TradingDeskStatus
from agentplane.services.agent_service import AgentService
from agentplane.services.agent_communication_service import AgentCommunicationService
from agentplane.services.agent_service import AgentService
from agentplane.services.autonomous_decision_service import AutonomousDecisionService
from agentplane.services.orchestrator_service import OrchestratorService
from agentplane.services.order_service import OrderService
from agentplane.services.position_service import PositionService
from agentplane.services.risk_service import RiskService
from agentplane.services.scanner_service import ScannerService
from agentplane.services.signal_service import SignalService
from agentplane.services.strategy_file_service import StrategyFileService

logger = structlog.get_logger()


class HeartbeatScheduler:
    """Schedule and run agent heartbeats."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._stop_events: dict[str, asyncio.Event] = {}
        self._agent_service = AgentService()
        self._signal_service = SignalService()
        self._risk_service = RiskService()
        self._order_service = OrderService()
        self._position_service = PositionService()
        self._scanner_service = ScannerService()
        self._comm_service = AgentCommunicationService()
        self._decision_service = AutonomousDecisionService()
        self._strategy_file_service = StrategyFileService()

    async def start_agent(self, agent_id: str) -> bool:
        """Start heartbeat loop for an agent."""
        if agent_id in self._tasks:
            return False

        agent = await self._agent_service.get(agent_id)
        if agent is None:
            return False

        stop_event = asyncio.Event()
        self._stop_events[agent_id] = stop_event
        task = asyncio.create_task(
            self._heartbeat_loop(agent_id, agent.heartbeat_interval_seconds, stop_event),
            name=f"heartbeat-{agent_id}",
        )
        self._tasks[agent_id] = task

        await self._agent_service.update(agent_id, AgentUpdate(status=AgentStatus.IDLE))
        logger.info(
            "heartbeat.started",
            agent_id=agent_id,
            interval=agent.heartbeat_interval_seconds,
        )
        return True

    async def stop_agent(self, agent_id: str) -> bool:
        """Stop heartbeat loop for an agent."""
        task = self._tasks.pop(agent_id, None)
        stop_event = self._stop_events.pop(agent_id, None)
        if task is None or stop_event is None:
            return False

        stop_event.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        await self._agent_service.update(agent_id, AgentUpdate(status=AgentStatus.PAUSED))
        logger.info("heartbeat.stopped", agent_id=agent_id)
        return True

    async def stop_all(self):
        """Stop all heartbeat loops.

        Errors during DB updates are logged but not raised so the scheduler
        can still shut down tasks when the database is already torn down.
        """
        for agent_id in list(self._tasks.keys()):
            try:
                await self.stop_agent(agent_id)
            except Exception as e:
                logger.warning("heartbeat.stop_all.error", agent_id=agent_id, error=str(e))
                # Make sure the task is cancelled even if the DB update failed
                task = self._tasks.pop(agent_id, None)
                if task is not None:
                    task.cancel()

    def list_running(self) -> list[str]:
        """Return IDs of agents with active heartbeats."""
        return list(self._tasks.keys())

    async def start_all_active(self) -> list[str]:
        """Start heartbeats for all agents that are not explicitly paused.

        Called at server startup so the control plane resumes autonomously.
        Only agents attached to an active desk are restarted.
        Ensures the orchestrator exists and has created the default team.
        """
        orchestrator_service = OrchestratorService()
        orchestrator_id, _ = await orchestrator_service.get_or_create_orchestrator()
        await orchestrator_service.mark_orchestrator_active(orchestrator_id)
        await orchestrator_service.ensure_team(orchestrator_id)

        started: list[str] = []
        agents = await self._agent_service.list()
        for agent in agents:
            if agent.status == AgentStatus.PAUSED:
                continue
            if not await self._is_desk_active(agent.trading_desk_id):
                logger.debug(
                    "heartbeat.autostart.skipped_inactive_desk",
                    agent_id=agent.id,
                    desk_id=agent.trading_desk_id,
                )
                continue
            if await self.start_agent(agent.id):
                started.append(agent.id)
        logger.info("heartbeat.autostart.complete", count=len(started), agents=started)
        return started

    async def _is_desk_active(self, desk_id: str | None) -> bool:
        """Check whether an agent's trading desk is active."""
        if desk_id is None:
            return False
        async with get_async_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(TradingDesk).where(TradingDesk.id == desk_id)
            )
            desk = result.scalar_one_or_none()
            return desk is not None and desk.status == TradingDeskStatus.ACTIVE

    async def _run_orchestrator_once(self, agent_id: str) -> None:
        """Run a single orchestrator heartbeat."""
        service = OrchestratorService()
        result = await service.run_once(agent_id)
        logger.info("orchestrator.heartbeat", agent_id=agent_id, result=result)

    async def _heartbeat_loop(
        self,
        agent_id: str,
        interval_seconds: int,
        stop_event: asyncio.Event,
    ) -> None:
        """Main heartbeat loop for one agent."""
        while not stop_event.is_set():
            try:
                await self._run_once(agent_id)
            except Exception as e:
                logger.error("heartbeat.error", agent_id=agent_id, error=str(e))
                await self._agent_service.update(agent_id, AgentUpdate(status=AgentStatus.ERROR))

            with suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)

    async def _run_once(self, agent_id: str) -> None:
        """Execute a single heartbeat for an agent."""
        agent = await self._agent_service.get(agent_id)
        if agent is None:
            return
        if not await self._is_desk_active(agent.trading_desk_id):
            return

        # Orchestrator has its own heartbeat logic
        if agent.adapter_type == "orchestrator":
            await self._run_orchestrator_once(agent_id)
            return

        # Read strategy file - if none exists, agent creates its own once
        strategy = self._strategy_file_service.read(agent_id)
        if strategy is None:
            # First heartbeat: agent creates its own strategy based on role
            logger.info(
                "strategy.creating_first_time",
                agent_id=agent_id,
                role=agent.role,
                message="Agent creating its initial strategy based on trading style"
            )
            self._strategy_file_service.create_default(agent)
            
            # Re-read after creation
            strategy = self._strategy_file_service.read(agent_id)
            if strategy is None:
                logger.error("strategy.creation_failed", agent_id=agent_id)
                await self._agent_service.update(agent_id, AgentUpdate(status=AgentStatus.ERROR))
                return
        
        # Strategy exists - agent reads it (read-only, no modification allowed)
        strategy_summary = self._strategy_file_service.get_strategy_summary(agent_id)
        logger.info(
            "heartbeat.strategy_loaded",
            agent_id=agent_id,
            strategy=strategy_summary["name"],
            version=strategy_summary["version"],
            pairs=strategy_summary["preferred_pairs"],
            timeframes=strategy_summary["preferred_timeframes"],
        )

        await self._agent_service.update(agent_id, AgentUpdate(status=AgentStatus.SCANNING))

        try:
            # 1. Check inbox for messages from other agents
            inbox_actions = await self._comm_service.process_inbox(agent_id)
            for action in inbox_actions:
                if action["type"] == "opportunity":
                    logger.info(
                        "heartbeat.opportunity_received",
                        agent_id=agent_id,
                        symbol=action["symbol"],
                        direction=action["direction"],
                        from_team=True,
                    )
                elif action["type"] == "insight":
                    logger.info(
                        "heartbeat.insight_received",
                        agent_id=agent_id,
                        insight=action["insight"][:100],
                    )

            # 2. Update mark-to-market for existing positions
            last_price = await self._signal_service.last_price(agent)
            if last_price is not None:
                await self._position_service.update_prices(
                    agent, agent.adapter_config.get("symbol", ""), last_price
                )

            # 3. Use strategy file to guide decisions
            preferred_pairs = strategy_summary.get("preferred_pairs", [])
            preferred_timeframes = strategy_summary.get("preferred_timeframes", [])
            max_positions = strategy_summary.get("max_positions", 3)
            risk_per_trade = strategy_summary.get("risk_per_trade_pct", 1.0)

            # Build watchlist from strategy preferences
            watchlist = [
                {"symbol": pair, "interval": tf, "period": "5d"}
                for pair in preferred_pairs
                for tf in preferred_timeframes
            ]

            if not watchlist:
                logger.warning("heartbeat.no_watchlist", agent_id=agent_id)
                return

            # Update agent's watchlist in DB
            await self._agent_service.update(
                agent_id, 
                AgentUpdate(watchlist=watchlist)
            )

            # 4. Scan next symbol/timeframe based on strategy
            signal = await self._scanner_service.scan_next(agent)
            
            if signal is None:
                # No signal found this heartbeat, that's ok
                return

            logger.info(
                "signal.generated",
                agent_id=agent_id,
                signal_id=signal.id,
                symbol=signal.symbol,
                direction=signal.direction,
                setup=signal.setup_name,
            )

            # 5. Broadcast opportunity to team
            await self._comm_service.broadcast_opportunity(
                sender_agent_id=agent_id,
                symbol=signal.symbol,
                direction=signal.direction,
                confidence=signal.confidence,
                timeframe=signal.market_data_snapshot.get("interval", "1h"),
                setup_name=signal.setup_name,
                details=signal.market_data_snapshot,
            )

            # 6. Request risk check from risk manager
            risk_messages = await self._comm_service.request_risk_check(
                sender_agent_id=agent_id,
                symbol=signal.symbol,
                direction=signal.direction,
                size=1.0,  # Will be refined by risk service
            )
            
            # 7. Validate risk locally too
            risk_check = await self._risk_service.validate_signal(agent, signal)
            if not risk_check.allowed:
                logger.warning(
                    "signal.rejected",
                    agent_id=agent_id,
                    signal_id=signal.id,
                    reason=risk_check.reason,
                )
                return

            # 8. Execute order
            logger.info(
                "signal.executing",
                agent_id=agent_id,
                signal_id=signal.id,
                size=risk_check.size,
            )
            result = await self._order_service.execute_signal(agent, signal, risk_check.size or 0)
            if result.success:
                logger.info(
                    "order.filled",
                    agent_id=agent_id,
                    order_id=result.order.id if result.order else None,
                    position_id=result.position.id if result.position else None,
                )
                
                # Share execution with team
                await self._comm_service.share_market_insight(
                    sender_agent_id=agent_id,
                    insight=f"Executed {signal.direction} on {signal.symbol} at {signal.market_data_snapshot.get('latest_close')}",
                    category="execution",
                    symbols=[signal.symbol],
                )
            else:
                logger.warning(
                    "order.failed",
                    agent_id=agent_id,
                    signal_id=signal.id,
                    reason=result.reason,
                )
        finally:
            await self._agent_service.update(agent_id, AgentUpdate(status=AgentStatus.IDLE))
