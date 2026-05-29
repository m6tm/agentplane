"""Run execution routes."""

from fastapi import APIRouter, HTTPException, BackgroundTasks

from agentplane.core.models import Run, RunCreate
from agentplane.services.run_service import RunService

router = APIRouter()
run_service = RunService()


@router.post("/{agent_id}/runs", response_model=Run)
async def create_run(agent_id: str, data: RunCreate):
    return await run_service.create(agent_id, data)


@router.get("/{agent_id}/runs", response_model=list[Run])
async def list_runs(agent_id: str):
    return await run_service.list_for_agent(agent_id)


@router.get("/{run_id}", response_model=Run)
async def get_run(run_id: str):
    run = await run_service.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/execute", response_model=Run)
async def execute_run(run_id: str, background_tasks: BackgroundTasks):
    run = await run_service.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    # Synchronous execution for simplicity; can be backgrounded
    return await run_service.execute(run_id)
