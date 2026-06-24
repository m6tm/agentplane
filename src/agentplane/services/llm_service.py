"""LLM decision service.

Every agent can be connected to an LLM adapter (default: kimi_local). This
service builds a prompt from market data / strategy / memory, calls the
adapter, and parses the decision.
"""

import json
import re
from typing import Any

import structlog

from agentplane.adapters.base import AdapterContext
from agentplane.adapters.registry import get_adapter
from agentplane.core.models import Agent, SignalDirection, Strategy

logger = structlog.get_logger()

DEFAULT_LLM_ADAPTER = "kimi_local"
DEFAULT_MODEL = "kimi-k2.6"

TRADING_PROMPT_TEMPLATE = """You are an autonomous trading agent.

Symbol: {symbol}
Strategy: {strategy_name}
Entry rules: {entry_rules}
Recent market data (latest first):
{market_data}
Memory context: {memory_context}

Based on the data above, respond with exactly one word: LONG, SHORT, or HOLD.
No explanation, just the decision."""

ORCHESTRATOR_PROMPT_TEMPLATE = """You are the Orchestrator agent managing a team of trading agents.

Incoming message:
- sender: {sender}
- type: {message_type}
- payload: {payload}

Current team size: {team_size}
Team members: {team_names}

Respond with a short status update in plain text. Keep it under 3 sentences."""


class LLMService:
    """Call an LLM adapter to take decisions."""

    def __init__(self, adapter_type: str | None = None):
        self.adapter_type = adapter_type or DEFAULT_LLM_ADAPTER

    async def decide_trade_direction(
        self,
        agent: Agent,
        strategy: Strategy,
        data: list[dict[str, Any]],
        memory_context: dict[str, Any],
    ) -> SignalDirection | None:
        """Ask the LLM for a trading decision.

        Falls back to None if the adapter is unavailable or the response cannot
        be parsed, so the caller can apply its own rules.
        """
        adapter = get_adapter(self.adapter_type)
        if adapter is None:
            logger.warning("llm.adapter_not_found", adapter=self.adapter_type)
            return None

        probe = await adapter.probe(agent.adapter_config)
        if not probe.get("available"):
            logger.warning(
                "llm.adapter_not_available",
                adapter=self.adapter_type,
                probe=probe,
            )
            return None

        prompt = TRADING_PROMPT_TEMPLATE.format(
            symbol=agent.adapter_config.get("symbol", "unknown"),
            strategy_name=strategy.name,
            entry_rules=json.dumps(strategy.entry_rules or {}),
            market_data=json.dumps(data[-10:], indent=2, default=str),
            memory_context=json.dumps(memory_context, default=str),
        )

        result = await adapter.execute(
            AdapterContext(
                run_id=f"llm-{agent.id}",
                agent_id=agent.id,
                prompt=prompt,
                config=agent.adapter_config.get("llm_config", {}),
            )
        )

        if not result.success:
            logger.warning(
                "llm.execution_failed",
                adapter=self.adapter_type,
                stderr=result.stderr,
            )
            return None

        return self._parse_direction(result.stdout or "")

    async def orchestrator_reply(
        self,
        orchestrator_id: str,
        sender: str,
        message_type: str,
        payload: dict[str, Any],
        team_size: int,
        team_names: list[str],
        config: dict[str, Any],
    ) -> str | None:
        """Generate a plain-text reply from the orchestrator.

        Returns None if the LLM adapter is unavailable.
        """
        adapter = get_adapter(self.adapter_type)
        if adapter is None:
            logger.warning("llm.adapter_not_found", adapter=self.adapter_type)
            return None

        probe = await adapter.probe(config)
        if not probe.get("available"):
            logger.warning(
                "llm.adapter_not_available",
                adapter=self.adapter_type,
                probe=probe,
            )
            return None

        prompt = ORCHESTRATOR_PROMPT_TEMPLATE.format(
            sender=sender,
            message_type=message_type,
            payload=json.dumps(payload, default=str),
            team_size=team_size,
            team_names=", ".join(team_names) if team_names else "none",
        )

        result = await adapter.execute(
            AdapterContext(
                run_id=f"llm-{orchestrator_id}",
                agent_id=orchestrator_id,
                prompt=prompt,
                config=config.get("llm_config", {}),
            )
        )

        if not result.success:
            logger.warning(
                "llm.execution_failed",
                adapter=self.adapter_type,
                stderr=result.stderr,
            )
            return None

        return (result.stdout or "").strip() or None

    def _parse_direction(self, text: str) -> SignalDirection | None:
        """Extract LONG/SHORT/HOLD from LLM output."""
        text = text.upper()
        # Remove Markdown code fences and punctuation
        text = re.sub(r"```[a-z]*\n?|```", "", text)
        text = re.sub(r"[^A-Z\s]", "", text)
        words = text.split()

        for word in words:
            if word == "LONG":
                return SignalDirection.LONG
            if word == "SHORT":
                return SignalDirection.SHORT
            if word == "HOLD":
                return None

        return None
