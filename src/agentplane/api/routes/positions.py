"""Position and order routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentplane.core.models import Order, Position, Trade
from agentplane.services.agent_service import AgentService
from agentplane.services.order_service import OrderService
from agentplane.services.position_service import PositionService

agent_service = AgentService()
order_service = OrderService()
position_service = PositionService()

position_router = APIRouter()


class ClosePositionRequest(BaseModel):
    current_price: float | None = None


@position_router.get("", response_model=list[Position])
async def list_agent_positions(agent_id: str):
    """List positions for an agent."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await position_service.list_for_agent(agent_id)


@position_router.get("/{position_id}", response_model=Position)
async def get_position(position_id: str, agent_id: str):
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    position = await position_service.get(position_id)
    if position is None or position.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@position_router.post("/{position_id}/close", response_model=Trade)
async def close_position(position_id: str, agent_id: str, body: ClosePositionRequest | None = None):
    """Close an open position."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    current_price = body.current_price if body else None
    trade = await position_service.close_position(agent, position_id, current_price=current_price)
    if trade is None:
        raise HTTPException(status_code=400, detail="Could not close position")
    return trade


order_router = APIRouter()


@order_router.get("", response_model=list[Order])
async def list_agent_orders(agent_id: str):
    """List orders for an agent."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await order_service.list_for_agent(agent_id)
