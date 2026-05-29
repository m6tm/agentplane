"""Agent CRUD + probe routes."""

from fastapi import APIRouter, HTTPException

from agentplane.core.models import Agent, AgentCreate, AgentUpdate
from agentplane.services.agent_service import AgentService

service = AgentService()

# Company-scoped router (mounted under /api/companies/{company_id}/agents)
company_router = APIRouter()

@company_router.post("", response_model=Agent)
async def create_agent(company_id: str, data: AgentCreate):
    return await service.create(company_id, data)


@company_router.get("", response_model=list[Agent])
async def list_agents(company_id: str):
    return await service.list(company_id)


# Agent-scoped router (mounted under /api/agents)
agent_router = APIRouter()

@agent_router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    agent = await service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@agent_router.patch("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, data: AgentUpdate):
    agent = await service.update(agent_id, data)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@agent_router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    ok = await service.delete(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"deleted": True}


@agent_router.post("/{agent_id}/probe")
async def probe_agent(agent_id: str):
    return await service.probe(agent_id)
