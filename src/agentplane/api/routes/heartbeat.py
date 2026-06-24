"""Heartbeat control routes."""

from fastapi import APIRouter, HTTPException

from agentplane.services.state import scheduler

heartbeat_router = APIRouter()


@heartbeat_router.post("/{agent_id}/start")
async def start_heartbeat(agent_id: str):
    """Start the heartbeat scheduler for an agent."""
    started = await scheduler.start_agent(agent_id)
    if not started:
        raise HTTPException(status_code=400, detail="Agent not found or already running")
    return {"started": True, "agent_id": agent_id}


@heartbeat_router.post("/{agent_id}/stop")
async def stop_heartbeat(agent_id: str):
    """Stop the heartbeat scheduler for an agent."""
    stopped = await scheduler.stop_agent(agent_id)
    if not stopped:
        raise HTTPException(status_code=400, detail="Agent not running")
    return {"stopped": True, "agent_id": agent_id}


@heartbeat_router.get("")
async def list_heartbeats():
    """List agents with active heartbeats."""
    return {"running": scheduler.list_running()}
