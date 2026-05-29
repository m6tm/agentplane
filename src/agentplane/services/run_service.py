"""Run execution service."""

from datetime import datetime
from typing import Any

from sqlalchemy import select

from agentplane.core.db import get_async_session
from agentplane.core.models import Run, RunCreate, RunStatus, Agent
from agentplane.adapters.base import AdapterContext
from agentplane.adapters.registry import get_adapter


class RunService:
    """Execute agent runs and persist results."""

    async def create(self, agent_id: str, data: RunCreate) -> Run:
        async with get_async_session() as session:
            run = Run(
                agent_id=agent_id,
                task_id=data.task_id,
                prompt=data.prompt,
                timeout_seconds=data.timeout_seconds or 300,
                status=RunStatus.PENDING,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def get(self, run_id: str) -> Run | None:
        async with get_async_session() as session:
            result = await session.execute(select(Run).where(Run.id == run_id))
            return result.scalar_one_or_none()

    async def list_for_agent(self, agent_id: str) -> list[Run]:
        async with get_async_session() as session:
            result = await session.execute(
                select(Run).where(Run.agent_id == agent_id).order_by(Run.created_at.desc())
            )
            return list(result.scalars().all())

    async def execute(self, run_id: str) -> Run:
        async with get_async_session() as session:
            result = await session.execute(
                select(Run, Agent)
                .join(Agent, Run.agent_id == Agent.id)
                .where(Run.id == run_id)
            )
            row = result.one_or_none()
            if row is None:
                raise ValueError(f"Run {run_id} not found")
            run, agent = row

            adapter = get_adapter(agent.adapter_type)
            if adapter is None:
                run.status = RunStatus.FAILURE
                run.stderr = f"Unknown adapter: {agent.adapter_type}"
                run.finished_at = datetime.utcnow()
                session.add(run)
                await session.commit()
                return run

            run.status = RunStatus.RUNNING
            run.started_at = datetime.utcnow()
            session.add(run)
            await session.commit()

            ctx = AdapterContext(
                run_id=run.id,
                agent_id=agent.id,
                task_id=run.task_id,
                prompt=run.prompt or "",
                config=agent.adapter_config,
                session_id=agent.session_id,
                session_params=agent.session_params or {},
            )

            logs: list[str] = []

            async def on_log(stream: str, chunk: str) -> None:
                logs.append(f"[{stream}] {chunk}")

            try:
                result = await adapter.execute(ctx, on_log=on_log)

                run.status = RunStatus.SUCCESS if result.success else RunStatus.FAILURE
                run.stdout = result.stdout
                run.stderr = result.stderr or "\n".join(logs)
                run.summary = result.summary
                run.exit_code = result.exit_code
                run.session_id = result.session_id
                run.session_params = result.session_params
                run.input_tokens = result.input_tokens
                run.output_tokens = result.output_tokens
                run.cost_usd = result.cost_usd
                run.model = result.model

                # Update agent session for resume
                if result.session_id:
                    agent.session_id = result.session_id
                    agent.session_params = result.session_params
                    session.add(agent)

            except Exception as e:
                run.status = RunStatus.FAILURE
                run.stderr = str(e)

            run.finished_at = datetime.utcnow()
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run
