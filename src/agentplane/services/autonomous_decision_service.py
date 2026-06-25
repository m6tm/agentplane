"""Autonomous decision service.

Uses LLM to make trading decisions like a human trader:
- Which pair to scan
- Which timeframe to use
- Whether to enter/exit a position
- Risk management decisions
"""

import json
from datetime import datetime
from typing import Any

import structlog

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.registry import get_adapter
from agentplane.core.models import Agent
from agentplane.services.agent_communication_service import AgentCommunicationService
from agentplane.services.market_data_service import MarketDataService

logger = structlog.get_logger()

# Available pairs and timeframes for autonomous selection
AVAILABLE_PAIRS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "EUR_GBP", "AUD_USD",
    "USD_CAD", "EUR_JPY", "GBP_JPY", "AUD_JPY", "EUR_CHF",
    "GBP_CHF", "USD_CHF", "NZD_USD", "EUR_AUD", "GBP_AUD",
]

AVAILABLE_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

DECISION_PROMPT = """You are an autonomous {role} trader. Your job is to analyze the market and make trading decisions.

Current Context:
- Your role: {role}
- Current time: {current_time}
- Team members: {team_context}
- Recent market insights from team: {insights}
- Your current positions: {positions}
- Recent performance: {performance}

Available forex pairs: {pairs}
Available timeframes: {timeframes}

Based on your role as a {role}:
- Scalper: Look for quick opportunities on short timeframes (1m-1h), focus on major pairs with tight spreads
- Swing trader: Look for medium-term trends (4h-1d), can trade more exotic pairs
- Risk Manager: Monitor overall portfolio risk, suggest position sizing and hedging

What should you do next? Respond with a JSON object containing:
{{
    "action": "scan" | "trade" | "wait" | "hedge",
    "symbol": "PAIR_NAME",
    "timeframe": "TIMEFRAME",
    "reasoning": "Your detailed reasoning here",
    "confidence": 0.0-1.0,
    "direction": "long" | "short" | null,
    "size_suggestion": "small" | "medium" | "large",
    "risk_level": "low" | "medium" | "high"
}}

Be specific and justify your decision based on market conditions and your role."""


class AutonomousDecisionService:
    """Make autonomous trading decisions using LLM."""

    def __init__(self):
        self._market_data_service = MarketDataService()
        self._comm_service = AgentCommunicationService()

    async def decide_next_action(self, agent: Agent) -> dict[str, Any]:
        """Ask the LLM what the agent should do next."""
        llm_adapter = agent.adapter_config.get("llm_adapter", "kimi_local")
        adapter = get_adapter(llm_adapter)
        
        if adapter is None:
            logger.warning("decision.no_adapter", agent_id=agent.id, adapter=llm_adapter)
            return self._default_decision()

        # Gather context
        team_context = await self._comm_service.get_team_context(agent.id)
        insights = await self._get_recent_insights(agent.id)
        positions = await self._get_position_summary(agent)
        performance = await self._get_performance_summary(agent)

        prompt = DECISION_PROMPT.format(
            role=agent.role or "trader",
            current_time=datetime.utcnow().isoformat(),
            team_context=json.dumps(team_context, default=str),
            insights=json.dumps(insights, default=str),
            positions=json.dumps(positions, default=str),
            performance=json.dumps(performance, default=str),
            pairs=", ".join(AVAILABLE_PAIRS),
            timeframes=", ".join(AVAILABLE_TIMEFRAMES),
        )

        result = await adapter.execute(
            AdapterContext(
                run_id=f"decision-{agent.id}",
                agent_id=agent.id,
                prompt=prompt,
                config=agent.adapter_config.get("llm_config", {}),
            )
        )

        if not result.success:
            logger.warning(
                "decision.llm_failed",
                agent_id=agent.id,
                stderr=result.stderr,
            )
            return self._default_decision()

        return self._parse_decision(result.stdout or "")

    def _parse_decision(self, raw: str) -> dict[str, Any]:
        """Parse LLM output into a structured decision."""
        # Try to extract JSON from the response
        try:
            # Look for JSON block
            lines = raw.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    decision = json.loads(line)
                    return self._validate_decision(decision)
            
            # Try the whole response as JSON
            decision = json.loads(raw)
            return self._validate_decision(decision)
        except json.JSONDecodeError:
            logger.warning("decision.parse_failed", raw=raw[:200])
            return self._default_decision()

    def _validate_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize a decision."""
        valid_actions = ["scan", "trade", "wait", "hedge"]
        valid_directions = ["long", "short", None]
        valid_sizes = ["small", "medium", "large"]
        valid_risks = ["low", "medium", "high"]

        action = decision.get("action", "wait")
        if action not in valid_actions:
            action = "wait"

        symbol = decision.get("symbol", "")
        if symbol not in AVAILABLE_PAIRS:
            symbol = "EUR_USD"  # Default to major pair

        timeframe = decision.get("timeframe", "1h")
        if timeframe not in AVAILABLE_TIMEFRAMES:
            timeframe = "1h"

        direction = decision.get("direction")
        if direction not in valid_directions:
            direction = None

        size = decision.get("size_suggestion", "small")
        if size not in valid_sizes:
            size = "small"

        risk = decision.get("risk_level", "medium")
        if risk not in valid_risks:
            risk = "medium"

        confidence = float(decision.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return {
            "action": action,
            "symbol": symbol,
            "timeframe": timeframe,
            "reasoning": decision.get("reasoning", "No reasoning provided"),
            "confidence": confidence,
            "direction": direction,
            "size_suggestion": size,
            "risk_level": risk,
        }

    def _default_decision(self) -> dict[str, Any]:
        """Default decision when LLM fails."""
        return {
            "action": "scan",
            "symbol": "EUR_USD",
            "timeframe": "1h",
            "reasoning": "Default decision due to LLM failure",
            "confidence": 0.3,
            "direction": None,
            "size_suggestion": "small",
            "risk_level": "low",
        }

    async def _get_recent_insights(self, agent_id: str) -> list[dict[str, Any]]:
        """Get recent insights from team messages."""
        # This would fetch from message history
        # For now, return empty list
        return []

    async def _get_position_summary(self, agent: Agent) -> dict[str, Any]:
        """Get summary of current positions."""
        from agentplane.services.position_service import PositionService
        positions = await PositionService().list_for_agent(agent.id)
        return {
            "count": len(positions),
            "symbols": list(set(p.symbol for p in positions)),
            "total_pnl": sum(p.unrealized_pnl_usd or 0 for p in positions),
        }

    async def _get_performance_summary(self, agent: Agent) -> dict[str, Any]:
        """Get recent performance summary."""
        from agentplane.services.trading_service import TradeService
        trades = await TradeService().list_for_agent(agent.id)
        recent_trades = trades[:10] if trades else []
        wins = [t for t in recent_trades if t.outcome == "win"]
        losses = [t for t in recent_trades if t.outcome == "loss"]
        return {
            "total_trades": len(trades),
            "recent_win_rate": len(wins) / len(recent_trades) if recent_trades else 0,
            "recent_trades_count": len(recent_trades),
        }
