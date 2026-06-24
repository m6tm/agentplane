"""Trading domain services: desks, strategies, skills."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from agentplane.core.db import get_async_session
from agentplane.core.models import (
    Skill,
    SkillCreate,
    SkillUpdate,
    Strategy,
    StrategyCreate,
    StrategyUpdate,
    TradingDesk,
    TradingDeskCreate,
    TradingDeskUpdate,
)


class TradingDeskService:
    """CRUD for trading desks."""

    async def create(self, data: TradingDeskCreate) -> TradingDesk:
        async with get_async_session() as session:
            desk = TradingDesk(
                name=data.name,
                goal=data.goal,
                mode=data.mode,
                initial_capital_usd=data.initial_capital_usd,
                current_capital_usd=data.initial_capital_usd,
                max_daily_loss_usd=data.max_daily_loss_usd,
                max_position_size_usd=data.max_position_size_usd,
                max_open_positions=data.max_open_positions,
            )
            session.add(desk)
            await session.commit()
            await session.refresh(desk)
            return desk

    async def list(self) -> list[TradingDesk]:
        async with get_async_session() as session:
            result = await session.execute(
                select(TradingDesk).options(selectinload(TradingDesk.agents))
            )
            return list(result.scalars().all())

    async def get(self, desk_id: str) -> TradingDesk | None:
        async with get_async_session() as session:
            result = await session.execute(
                select(TradingDesk).where(TradingDesk.id == desk_id).options(
                    selectinload(TradingDesk.agents)
                )
            )
            return result.scalar_one_or_none()

    async def update(self, desk_id: str, data: TradingDeskUpdate) -> TradingDesk | None:
        async with get_async_session() as session:
            result = await session.execute(select(TradingDesk).where(TradingDesk.id == desk_id))
            desk = result.scalar_one_or_none()
            if desk is None:
                return None
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(desk, key, value)
            session.add(desk)
            await session.commit()
            await session.refresh(desk)
            return desk

    async def delete(self, desk_id: str) -> bool:
        async with get_async_session() as session:
            result = await session.execute(select(TradingDesk).where(TradingDesk.id == desk_id))
            desk = result.scalar_one_or_none()
            if desk is None:
                return False
            await session.delete(desk)
            await session.commit()
            return True


class StrategyService:
    """CRUD for trading strategies."""

    async def create(self, data: StrategyCreate) -> Strategy:
        async with get_async_session() as session:
            strategy = Strategy(
                name=data.name,
                description=data.description,
                timeframe=data.timeframe,
                entry_rules=data.entry_rules,
                exit_rules=data.exit_rules,
                risk_per_trade_pct=data.risk_per_trade_pct,
                max_positions=data.max_positions,
            )
            session.add(strategy)
            await session.commit()
            await session.refresh(strategy)
            return strategy

    async def list(self) -> list[Strategy]:
        async with get_async_session() as session:
            result = await session.execute(select(Strategy))
            return list(result.scalars().all())

    async def get(self, strategy_id: str) -> Strategy | None:
        async with get_async_session() as session:
            result = await session.execute(
                select(Strategy).where(Strategy.id == strategy_id)
            )
            return result.scalar_one_or_none()

    async def update(self, strategy_id: str, data: StrategyUpdate) -> Strategy | None:
        async with get_async_session() as session:
            result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
            strategy = result.scalar_one_or_none()
            if strategy is None:
                return None
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(strategy, key, value)
            session.add(strategy)
            await session.commit()
            await session.refresh(strategy)
            return strategy

    async def delete(self, strategy_id: str) -> bool:
        async with get_async_session() as session:
            result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
            strategy = result.scalar_one_or_none()
            if strategy is None:
                return False
            await session.delete(strategy)
            await session.commit()
            return True


class SkillService:
    """CRUD for skills."""

    async def create(self, data: SkillCreate) -> Skill:
        async with get_async_session() as session:
            skill = Skill(
                name=data.name,
                description=data.description,
                category=data.category,
                prompt_injection=data.prompt_injection,
            )
            session.add(skill)
            await session.commit()
            await session.refresh(skill)
            return skill

    async def list(self) -> list[Skill]:
        async with get_async_session() as session:
            result = await session.execute(select(Skill))
            return list(result.scalars().all())

    async def get(self, skill_id: str) -> Skill | None:
        async with get_async_session() as session:
            result = await session.execute(select(Skill).where(Skill.id == skill_id))
            return result.scalar_one_or_none()

    async def update(self, skill_id: str, data: SkillUpdate) -> Skill | None:
        async with get_async_session() as session:
            result = await session.execute(select(Skill).where(Skill.id == skill_id))
            skill = result.scalar_one_or_none()
            if skill is None:
                return None
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(skill, key, value)
            session.add(skill)
            await session.commit()
            await session.refresh(skill)
            return skill

    async def delete(self, skill_id: str) -> bool:
        async with get_async_session() as session:
            result = await session.execute(select(Skill).where(Skill.id == skill_id))
            skill = result.scalar_one_or_none()
            if skill is None:
                return False
            await session.delete(skill)
            await session.commit()
            return True
