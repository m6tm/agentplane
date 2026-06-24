"""Trading routes: desks, strategies, skills."""

from fastapi import APIRouter, HTTPException

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
from agentplane.services.trading_service import SkillService, StrategyService, TradingDeskService

desk_service = TradingDeskService()
strategy_service = StrategyService()
skill_service = SkillService()

# Trading desk router
desk_router = APIRouter()


@desk_router.post("", response_model=TradingDesk)
async def create_desk(data: TradingDeskCreate):
    return await desk_service.create(data)


@desk_router.get("", response_model=list[TradingDesk])
async def list_desks():
    return await desk_service.list()


@desk_router.get("/{desk_id}", response_model=TradingDesk)
async def get_desk(desk_id: str):
    desk = await desk_service.get(desk_id)
    if desk is None:
        raise HTTPException(status_code=404, detail="Trading desk not found")
    return desk


@desk_router.patch("/{desk_id}", response_model=TradingDesk)
async def update_desk(desk_id: str, data: TradingDeskUpdate):
    desk = await desk_service.update(desk_id, data)
    if desk is None:
        raise HTTPException(status_code=404, detail="Trading desk not found")
    return desk


@desk_router.delete("/{desk_id}")
async def delete_desk(desk_id: str):
    ok = await desk_service.delete(desk_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Trading desk not found")
    return {"deleted": True}


# Strategy router
strategy_router = APIRouter()


@strategy_router.post("", response_model=Strategy)
async def create_strategy(data: StrategyCreate):
    return await strategy_service.create(data)


@strategy_router.get("", response_model=list[Strategy])
async def list_strategies():
    return await strategy_service.list()


@strategy_router.get("/{strategy_id}", response_model=Strategy)
async def get_strategy(strategy_id: str):
    strategy = await strategy_service.get(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@strategy_router.patch("/{strategy_id}", response_model=Strategy)
async def update_strategy(strategy_id: str, data: StrategyUpdate):
    strategy = await strategy_service.update(strategy_id, data)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@strategy_router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    ok = await strategy_service.delete(strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"deleted": True}


# Skill router
skill_router = APIRouter()


@skill_router.post("", response_model=Skill)
async def create_skill(data: SkillCreate):
    return await skill_service.create(data)


@skill_router.get("", response_model=list[Skill])
async def list_skills():
    return await skill_service.list()


@skill_router.get("/{skill_id}", response_model=Skill)
async def get_skill(skill_id: str):
    skill = await skill_service.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@skill_router.patch("/{skill_id}", response_model=Skill)
async def update_skill(skill_id: str, data: SkillUpdate):
    skill = await skill_service.update(skill_id, data)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@skill_router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    ok = await skill_service.delete(skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"deleted": True}
