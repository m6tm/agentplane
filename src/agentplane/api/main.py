"""FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentplane.api.routes import (
    agents,
    health,
    heartbeat,
    journal,
    orchestrator,
    positions,
    runs,
    trading,
    websocket,
)
from agentplane.core.db import init_async_db
from agentplane.services.state import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    await init_async_db()
    await scheduler.start_all_active()
    yield
    await scheduler.stop_all()


app = FastAPI(
    title="Agentplane",
    description="Lightweight agent orchestration control plane",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(orchestrator.router, prefix="/api/orchestrator", tags=["Orchestrator"])
app.include_router(heartbeat.heartbeat_router, prefix="/api/heartbeats", tags=["Heartbeats"])
app.include_router(trading.desk_router, prefix="/api/trading-desks", tags=["Trading Desks"])
app.include_router(trading.strategy_router, prefix="/api/strategies", tags=["Strategies"])
app.include_router(trading.skill_router, prefix="/api/skills", tags=["Skills"])
app.include_router(agents.agent_router, prefix="/api/agents", tags=["Agents"])
app.include_router(runs.agent_router, prefix="/api/agents/{agent_id}", tags=["Runs"])
app.include_router(
    positions.position_router, prefix="/api/agents/{agent_id}/positions", tags=["Positions"]
)
app.include_router(
    positions.order_router, prefix="/api/agents/{agent_id}/orders", tags=["Orders"]
)
app.include_router(
    journal.journal_router, prefix="/api/agents/{agent_id}", tags=["Journal"]
)
app.include_router(
    journal.lesson_router, prefix="/api/agents/{agent_id}", tags=["Lessons"]
)
app.include_router(
    journal.memory_router, prefix="/api/agents/{agent_id}", tags=["Memory"]
)
app.include_router(runs.run_router, prefix="/api/runs", tags=["Runs"])
app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket"])
