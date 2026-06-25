"""Orchestrator service.

The orchestrator is a special agent that boots automatically and is responsible
for creating the initial team of traders. It persists its decisions in the
database so the team is recreated only once.
"""

from typing import Any

import structlog

from agentplane.core.models import (
    AgentCreate,
    AgentUpdate,
    MessageType,
    RiskProfile,
    StrategyCreate,
    StrategyTimeframe,
    TradingDeskCreate,
    TradingDeskMode,
)
from agentplane.services.agent_service import AgentService
from agentplane.services.llm_service import LLMService
from agentplane.services.message_service import MessageService
from agentplane.services.trading_service import StrategyService, TradingDeskService

logger = structlog.get_logger()

DEFAULT_ORCHESTRATOR_NAME = "Orchestrator"
DEFAULT_DESK_NAME = "Orchestrator Desk"

DEFAULT_TEAM = [
    {
        "name": "EURUSD Scalper",
        "role": "scalper",
        "symbol": "EUR_USD",
        "timeframe": "1h",
        "strategy_timeframe": StrategyTimeframe.SCALPING,
        "risk_profile": RiskProfile.AGGRESSIVE,
        "interval": "1h",
        "period": "5d",
        "heartbeat_interval_seconds": 30,
        "watchlist": [
            {"symbol": "EUR_USD", "interval": "1h", "period": "5d"},
            {"symbol": "GBP_USD", "interval": "1h", "period": "5d"},
            {"symbol": "USD_JPY", "interval": "1h", "period": "5d"},
            {"symbol": "EUR_GBP", "interval": "1h", "period": "5d"},
        ],
    },
    {
        "name": "GBPJPY Swing",
        "role": "swing",
        "symbol": "GBP_JPY",
        "timeframe": "4h",
        "strategy_timeframe": StrategyTimeframe.SWING,
        "risk_profile": RiskProfile.MODERATE,
        "interval": "4h",
        "period": "30d",
        "heartbeat_interval_seconds": 300,
        "watchlist": [
            {"symbol": "GBP_JPY", "interval": "4h", "period": "30d"},
            {"symbol": "EUR_JPY", "interval": "4h", "period": "30d"},
            {"symbol": "AUD_JPY", "interval": "4h", "period": "30d"},
            {"symbol": "USD_JPY", "interval": "4h", "period": "30d"},
        ],
    },
    {
        "name": "Risk Manager",
        "role": "risk_manager",
        "symbol": "EUR_USD",
        "timeframe": "1d",
        "strategy_timeframe": StrategyTimeframe.DAILY,
        "risk_profile": RiskProfile.CONSERVATIVE,
        "interval": "1d",
        "period": "5d",
        "heartbeat_interval_seconds": 600,
        "watchlist": [
            {"symbol": "EUR_USD", "interval": "1d", "period": "5d"},
            {"symbol": "GBP_USD", "interval": "1d", "period": "5d"},
            {"symbol": "USD_JPY", "interval": "1d", "period": "5d"},
            {"symbol": "AUD_USD", "interval": "1d", "period": "5d"},
        ],
    },
]


class OrchestratorService:
    """Manage the orchestrator agent and its team."""

    def __init__(self):
        self._desk_service = TradingDeskService()
        self._strategy_service = StrategyService()
        self._agent_service = AgentService()
        self._message_service = MessageService()

    async def ensure_infrastructure(self) -> tuple[str, dict[str, str]]:
        """Ensure orchestrator desk and base strategies exist.

        Returns (desk_id, mapping strategy_name -> strategy_id).
        """
        desks = await self._desk_service.list()
        desk = next((d for d in desks if d.name == DEFAULT_DESK_NAME), None)
        if desk is None:
            desk = await self._desk_service.create(
                TradingDeskCreate(
                    name=DEFAULT_DESK_NAME,
                    mode=TradingDeskMode.PAPER,
                    initial_capital_usd=100000.0,
                )
            )
            logger.info("orchestrator.desk_created", desk_id=desk.id)

        strategies: dict[str, str] = {}
        existing = {s.name: s.id for s in await self._strategy_service.list()}

        for name, timeframe in [
            ("Scalping Momentum", StrategyTimeframe.SCALPING),
            ("Swing Momentum", StrategyTimeframe.SWING),
            ("Daily Momentum", StrategyTimeframe.DAILY),
        ]:
            if name in existing:
                strategies[name] = existing[name]
                continue
            strategy = await self._strategy_service.create(
                StrategyCreate(
                    name=name,
                    timeframe=timeframe,
                    entry_rules={"type": "price_above_previous_close"},
                )
            )
            strategies[name] = strategy.id
            logger.info("orchestrator.strategy_created", strategy_id=strategy.id, name=name)

        return desk.id, strategies

    async def get_or_create_orchestrator(self) -> tuple[str, bool]:
        """Return (agent_id, created) for the orchestrator agent."""
        agents = await self._agent_service.list()
        for agent in agents:
            if agent.name == DEFAULT_ORCHESTRATOR_NAME:
                return agent.id, False

        desk_id, strategies = await self.ensure_infrastructure()
        orchestrator = await self._agent_service.create(
            AgentCreate(
                name=DEFAULT_ORCHESTRATOR_NAME,
                description="Meta-agent that manages the trading team.",
                role="orchestrator",
                trading_desk_id=desk_id,
                adapter_type="orchestrator",
                adapter_config={
                    "llm_adapter": "kimi_local",
                    "team": [
                        {"symbol": "EUR_USD", "timeframe": "1h", "role": "scalper"},
                        {"symbol": "GBP_JPY", "timeframe": "4h", "role": "swing"},
                    ],
                },
                heartbeat_interval_seconds=60,
            )
        )
        logger.info("orchestrator.created", agent_id=orchestrator.id)
        return orchestrator.id, True

    async def ensure_team(self, orchestrator_id: str) -> list[str]:
        """Create the default team if no other agents exist yet.

        Returns list of created agent IDs.
        """
        agents = await self._agent_service.list()
        non_orchestrator = [a for a in agents if a.id != orchestrator_id]
        if non_orchestrator:
            logger.info(
                "orchestrator.team_already_exists",
                count=len(non_orchestrator),
            )
            return []

        desk_id, strategies = await self.ensure_infrastructure()
        created: list[str] = []

        for spec in DEFAULT_TEAM:
            strategy_name = self._strategy_name_for_timeframe(spec["strategy_timeframe"])
            strategy_id = strategies.get(strategy_name)
            if strategy_id is None:
                logger.error("orchestrator.missing_strategy", name=strategy_name)
                continue

            agent = await self._agent_service.create(
                AgentCreate(
                    name=spec["name"],
                    role=spec["role"],
                    trading_desk_id=desk_id,
                    strategy_id=strategy_id,
                    adapter_type="paper_broker",
                    adapter_config={
                        "symbol": spec["symbol"],
                        "data_adapter": "oanda",
                        "broker_adapter": "paper_broker",
                        "llm_adapter": "kimi_local",
                        "environment": "practice",
                        "interval": spec["interval"],
                        "period": spec["period"],
                    },
                    risk_profile=spec["risk_profile"],
                    heartbeat_interval_seconds=spec["heartbeat_interval_seconds"],
                    watchlist=spec.get("watchlist", []),
                )
            )
            created.append(agent.id)
            logger.info(
                "orchestrator.team_member_created",
                agent_id=agent.id,
                name=agent.name,
            )

        if created:
            await self._message_service.broadcast(
                sender_agent_id=orchestrator_id,
                message_type=MessageType.STATUS,
                payload={
                    "event": "team_created",
                    "members": created,
                },
            )

        return created

    async def run_once(self, orchestrator_id: str) -> dict[str, Any]:
        """Single heartbeat tick for the orchestrator.

        Reads the inbox, logs incoming messages to the terminal, replies to
        senders, and broadcasts a status update to the team.
        """
        await self._process_inbox(orchestrator_id)

        agents = await self._agent_service.list()
        team = [a for a in agents if a.id != orchestrator_id]

        message = await self._message_service.broadcast(
            sender_agent_id=orchestrator_id,
            message_type=MessageType.STATUS,
            payload={
                "event": "heartbeat",
                "team_size": len(team),
                "running": True,
            },
        )

        return {
            "team_size": len(team),
            "message_id": message.id,
        }

    async def process_user_message(self, orchestrator_id: str) -> str | None:
        """Read the last user message and return the LLM reply.
        
        Used by the API to provide immediate conversational responses.
        """
        unread = await self._message_service.list_unread(orchestrator_id)
        
        # Find the most recent user message
        user_messages = [m for m in unread if m.sender_agent_id == "user"]
        if not user_messages:
            return None
        
        msg = user_messages[-1]  # Most recent
        
        agent = await self._agent_service.get(orchestrator_id)
        llm_config = agent.adapter_config if agent else {}
        llm_adapter = llm_config.get("llm_adapter", "kimi_local")

        agents = await self._agent_service.list()
        team = [a for a in agents if a.id != orchestrator_id]

        llm = LLMService(adapter_type=llm_adapter)
        reply_text = await llm.orchestrator_reply(
            orchestrator_id=orchestrator_id,
            sender=msg.sender_agent_id or "unknown",
            message_type=str(msg.message_type),
            payload=msg.payload,
            team_size=len(team),
            team_names=[a.name for a in team],
            config=llm_config,
        )

        if reply_text:
            # Extract clean text from kimi stream-json output
            clean_reply = self._extract_reply_text(reply_text)
            logger.info(
                "orchestrator.conversation_reply",
                message_id=msg.id,
                reply=clean_reply,
                adapter=llm_adapter,
            )
            await self._message_service.mark_read(msg.id)
            return clean_reply

        await self._message_service.mark_read(msg.id)
        return reply_text

    def _extract_reply_text(self, raw: str) -> str:
        """Extract clean assistant text from kimi stream-json output."""
        import json
        lines = raw.strip().split('\n')
        for line in lines:
            try:
                data = json.loads(line)
                if data.get('role') == 'assistant' and 'content' in data:
                    return data['content']
            except json.JSONDecodeError:
                continue
        return raw

    async def _process_inbox(self, orchestrator_id: str) -> list[str]:
        """Read and answer messages addressed to the orchestrator.

        The orchestrator uses the configured LLM adapter (default: kimi_local)
        to generate a plain-text answer. The answer is only logged to the
        terminal; it is not stored or returned via HTTP.
        """
        unread = await self._message_service.list_unread(orchestrator_id)
        handled: list[str] = []

        agent = await self._agent_service.get(orchestrator_id)
        llm_config = agent.adapter_config if agent else {}
        llm_adapter = llm_config.get("llm_adapter", "kimi_local")

        for msg in unread:
            logger.info(
                "orchestrator.received_message",
                message_id=msg.id,
                sender=msg.sender_agent_id,
                message_type=msg.message_type,
                payload=msg.payload,
            )

            agents = await self._agent_service.list()
            team = [a for a in agents if a.id != orchestrator_id]

            llm = LLMService(adapter_type=llm_adapter)
            reply_text = await llm.orchestrator_reply(
                orchestrator_id=orchestrator_id,
                sender=msg.sender_agent_id or "unknown",
                message_type=str(msg.message_type),
                payload=msg.payload,
                team_size=len(team),
                team_names=[a.name for a in team],
                config=llm_config,
            )

            if reply_text:
                logger.info(
                    "orchestrator.terminal_reply",
                    message_id=msg.id,
                    reply=reply_text,
                    adapter=llm_adapter,
                )

            await self._message_service.mark_read(msg.id)
            handled.append(msg.id)

        return handled

    async def mark_orchestrator_active(self, orchestrator_id: str) -> None:
        """Set orchestrator status to idle so it can be autostarted."""
        from agentplane.core.models import AgentStatus

        await self._agent_service.update(
            orchestrator_id,
            AgentUpdate(status=AgentStatus.IDLE),
        )

    def _strategy_name_for_timeframe(self, timeframe: StrategyTimeframe) -> str:
        mapping = {
            StrategyTimeframe.SCALPING: "Scalping Momentum",
            StrategyTimeframe.SWING: "Swing Momentum",
            StrategyTimeframe.DAILY: "Daily Momentum",
        }
        return mapping[timeframe]
