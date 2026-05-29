"""Agent business logic."""

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from agentplane.core.db import get_async_session
from agentplane.core.models import Agent, AgentCreate, AgentUpdate, Run, RunStatus
from agentplane.adapters.registry import get_adapter


class AgentService:
    """CRUD and execution for agents."""

    async def create(self, data: AgentCreate) -> Agent:
        async with get_async_session() as session:
            agent = Agent(
                name=data.name,
                description=data.description,
                adapter_type=data.adapter_type,
                adapter_config=data.adapter_config,
                heartbeat_interval_seconds=data.heartbeat_interval_seconds,
                max_budget_usd=data.max_budget_usd,
            )
            session.add(agent)
            await session.commit()
            await session.refresh(agent)
            return agent

    async def list(self) -> list[Agent]:
        async with get_async_session() as session:
            result = await session.execute(
                select(Agent).options(selectinload(Agent.runs))
            )
            return list(result.scalars().all())

    async def get(self, agent_id: str) -> Agent | None:
        async with get_async_session() as session:
            result = await session.execute(
                select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.runs))
            )
            return result.scalar_one_or_none()

    async def update(self, agent_id: str, data: AgentUpdate) -> Agent | None:
        async with get_async_session() as session:
            result = await session.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent is None:
                return None
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(agent, key, value)
            session.add(agent)
            await session.commit()
            await session.refresh(agent)
            return agent

    async def delete(self, agent_id: str) -> bool:
        async with get_async_session() as session:
            result = await session.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent is None:
                return False
            await session.delete(agent)
            await session.commit()
            return True

    async def probe(self, agent_id: str) -> dict[str, Any]:
        agent = await self.get(agent_id)
        if agent is None:
            return {"error": "Agent not found"}
        adapter = get_adapter(agent.adapter_type)
        if adapter is None:
            return {"error": f"Unknown adapter type: {agent.adapter_type}"}
        return await adapter.probe(agent.adapter_config)
