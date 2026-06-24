"""Tests for the LLM decision service."""

import pytest

from agentplane.core.models import Agent, SignalDirection, Strategy
from agentplane.services.llm_service import LLMService


@pytest.mark.asyncio
async def test_llm_service_fallback_when_adapter_unavailable():
    """When the adapter is not installed, decide_trade_direction returns None."""
    agent = Agent(
        name="test",
        adapter_config={"symbol": "EUR_USD", "llm_adapter": "kimi_local"},
    )
    strategy = Strategy(name="test", entry_rules={"type": "always_long"})

    llm = LLMService(adapter_type="kimi_local")
    direction = await llm.decide_trade_direction(agent, strategy, [], {})
    assert direction is None


@pytest.mark.asyncio
async def test_llm_service_orchestrator_reply_fallback():
    """When the adapter is not installed, orchestrator_reply returns None."""
    llm = LLMService(adapter_type="kimi_local")
    reply = await llm.orchestrator_reply(
        orchestrator_id="orch-1",
        sender="user",
        message_type="command",
        payload={"action": "status"},
        team_size=0,
        team_names=[],
        config={},
    )
    assert reply is None


def test_parse_direction():
    llm = LLMService()
    assert llm._parse_direction("LONG") == SignalDirection.LONG
    assert llm._parse_direction("The decision is SHORT.") == SignalDirection.SHORT
    assert llm._parse_direction("```LONG```") == SignalDirection.LONG
    assert llm._parse_direction("HOLD") is None
    assert llm._parse_direction("I think we should wait") is None
