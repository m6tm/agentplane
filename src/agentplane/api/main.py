"""FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentplane.core.db import init_async_db
from agentplane.api.routes import health, companies, agents, runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    await init_async_db()
    yield


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
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(runs.router, prefix="/api/runs", tags=["Runs"])
