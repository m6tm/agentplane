"""Inter-agent communication service.

Agents can broadcast opportunities, share market insights, and coordinate
trading decisions through structured messages.
"""

from typing import Any

import structlog

from agentplane.core.models import AgentMessage, AgentStatus, MessageType
from agentplane.services.agent_service import AgentService
from agentplane.services.message_service import MessageService

logger = structlog.get_logger()


class AgentCommunicationService:
    """Enable communication and coordination between trading agents."""

    def __init__(self):
        self._message_service = MessageService()
        self._agent_service = AgentService()

    async def broadcast_opportunity(
        self,
        sender_agent_id: str,
        symbol: str,
        direction: str,
        confidence: float,
        timeframe: str,
        setup_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast a trading opportunity to all other agents.
        
        Agents can decide to act on it or ignore based on their strategy.
        """
        payload = {
            "event": "opportunity",
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "timeframe": timeframe,
            "setup": setup_name,
            "details": details or {},
        }
        
        await self._message_service.broadcast(
            sender_agent_id=sender_agent_id,
            message_type=MessageType.SIGNAL,
            payload=payload,
        )
        
        logger.info(
            "comm.opportunity_broadcast",
            sender=sender_agent_id,
            symbol=symbol,
            direction=direction,
        )

    async def share_market_insight(
        self,
        sender_agent_id: str,
        insight: str,
        category: str = "general",
        symbols: list[str] | None = None,
    ) -> None:
        """Share a market insight with the team."""
        payload = {
            "event": "insight",
            "insight": insight,
            "category": category,
            "symbols": symbols or [],
        }
        
        await self._message_service.broadcast(
            sender_agent_id=sender_agent_id,
            message_type=MessageType.STATUS,
            payload=payload,
        )
        
        logger.info(
            "comm.insight_shared",
            sender=sender_agent_id,
            category=category,
        )

    async def request_risk_check(
        self,
        sender_agent_id: str,
        symbol: str,
        direction: str,
        size: float,
    ) -> list[AgentMessage]:
        """Request a risk check from the Risk Manager agent.
        
        Returns the risk manager's response messages.
        """
        # Find the risk manager
        agents = await self._agent_service.list()
        risk_managers = [a for a in agents if a.role == "risk_manager"]
        
        if not risk_managers:
            logger.warning("comm.no_risk_manager", sender=sender_agent_id)
            return []
        
        risk_manager = risk_managers[0]
        
        payload = {
            "event": "risk_check",
            "symbol": symbol,
            "direction": direction,
            "size": size,
        }
        
        await self._message_service.send(
            sender_agent_id=sender_agent_id,
            recipient_agent_id=risk_manager.id,
            message_type=MessageType.ALERT,
            payload=payload,
        )
        
        logger.info(
            "comm.risk_check_requested",
            sender=sender_agent_id,
            risk_manager=risk_manager.id,
            symbol=symbol,
        )
        
        return await self._message_service.list_unread(risk_manager.id)

    async def process_inbox(self, agent_id: str) -> list[dict[str, Any]]:
        """Process incoming messages for an agent and return actionable items."""
        unread = await self._message_service.list_unread(agent_id)
        actions: list[dict[str, Any]] = []
        
        for msg in unread:
            logger.info(
                "comm.message_received",
                agent_id=agent_id,
                sender=msg.sender_agent_id,
                type=msg.message_type,
                payload=msg.payload,
            )
            
            if msg.message_type == MessageType.SIGNAL:
                # Another agent found an opportunity
                payload = msg.payload or {}
                if payload.get("event") == "opportunity":
                    actions.append({
                        "type": "opportunity",
                        "symbol": payload.get("symbol"),
                        "direction": payload.get("direction"),
                        "confidence": payload.get("confidence"),
                        "timeframe": payload.get("timeframe"),
                        "setup": payload.get("setup"),
                        "details": payload.get("details", {}),
                    })
            
            elif msg.message_type == MessageType.ALERT:
                # Risk alert or important notification
                actions.append({
                    "type": "alert",
                    "payload": msg.payload,
                })
            
            elif msg.message_type == MessageType.STATUS:
                # Team status update or insight
                payload = msg.payload or {}
                if payload.get("event") == "insight":
                    actions.append({
                        "type": "insight",
                        "insight": payload.get("insight"),
                        "category": payload.get("category"),
                        "symbols": payload.get("symbols", []),
                    })
            
            # Mark as read
            await self._message_service.mark_read(msg.id)
        
        return actions

    async def get_team_context(self, agent_id: str) -> dict[str, Any]:
        """Get context about what other team members are doing."""
        agents = await self._agent_service.list()
        team = [a for a in agents if a.id != agent_id]
        
        return {
            "team_size": len(team),
            "members": [
                {
                    "id": a.id,
                    "name": a.name,
                    "role": a.role,
                    "status": a.status,
                    "symbol": a.adapter_config.get("symbol"),
                    "interval": a.adapter_config.get("interval"),
                }
                for a in team
            ],
            "active_scalpers": [a.name for a in team if a.role == "scalper" and a.status == AgentStatus.SCANNING],
            "active_swings": [a.name for a in team if a.role == "swing" and a.status == AgentStatus.SCANNING],
            "risk_manager_online": any(a.role == "risk_manager" for a in team if a.status != AgentStatus.PAUSED),
        }
