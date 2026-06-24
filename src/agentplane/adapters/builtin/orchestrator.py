"""Orchestrator adapter.

Special adapter for the orchestrator agent. On each heartbeat it ensures the
default team of traders exists and broadcasts a status update to the team.
"""

from typing import Any

import structlog

from agentplane.adapters.base import Adapter, AdapterContext, AdapterResult
from agentplane.adapters.registry import register_adapter
from agentplane.services.orchestrator_service import OrchestratorService

logger = structlog.get_logger()


@register_adapter
class OrchestratorAdapter(Adapter):
    """Meta-adapter that manages the trading team."""

    @property
    def type(self) -> str:
        return "orchestrator"

    @property
    def label(self) -> str:
        return "Orchestrator"

    async def execute(
        self,
        ctx: AdapterContext,
        on_log: Any | None = None,
    ) -> AdapterResult:
        agent_id = ctx.agent_id
        service = OrchestratorService()

        async def log(stream: str, message: str) -> None:
            if on_log:
                await on_log(stream, message)
            logger.info("orchestrator.execute_log", stream=stream, message=message.strip())

        await log("stdout", f"Orchestrator heartbeat for {agent_id}\n")

        created = await service.ensure_team(agent_id)
        if created:
            await log("stdout", f"Created team: {created}\n")

        result = await service.run_once(agent_id)
        await log(
            "stdout",
            f"Team size: {result['team_size']}, message_id: {result['message_id']}\n",
        )

        return AdapterResult(
            success=True,
            exit_code=0,
            stdout=str(result),
            summary=f"Orchestrator heartbeat: team_size={result['team_size']}",
        )

    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "available": True,
            "note": "Orchestrator adapter is always available",
        }

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "supports": ["team_management", "heartbeat"],
        }
