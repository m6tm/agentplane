"""Domain models shared across the system."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON


class AgentStatus(str, Enum):
    """Agent lifecycle states."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class Agent(SQLModel, table=True):
    """An agent definition."""

    __tablename__ = "agents"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: str | None = None

    # Adapter configuration
    adapter_type: str = Field(default="process")
    adapter_config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Runtime
    status: AgentStatus = Field(default=AgentStatus.IDLE)
    session_id: str | None = None
    session_params: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    # Scheduling
    heartbeat_interval_seconds: int = Field(default=60)
    max_budget_usd: float | None = None
    spent_budget_usd: float = Field(default=0.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    runs: list["Run"] = Relationship(back_populates="agent")


class TaskStatus(str, Enum):
    """Task lifecycle states."""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class Task(SQLModel, table=True):
    """A unit of work assigned to an agent."""

    __tablename__ = "tasks"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    agent_id: str | None = Field(default=None, foreign_key="agents.id", index=True)
    parent_id: str | None = Field(default=None, foreign_key="tasks.id")

    title: str
    description: str | None = None
    status: TaskStatus = Field(default=TaskStatus.BACKLOG)
    priority: int = Field(default=0)

    # Context
    context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    runs: list["Run"] = Relationship(back_populates="task")


class RunStatus(str, Enum):
    """Run lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Run(SQLModel, table=True):
    """A single execution of an agent."""

    __tablename__ = "runs"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)
    task_id: str | None = Field(default=None, foreign_key="tasks.id", index=True)

    status: RunStatus = Field(default=RunStatus.PENDING)
    prompt: str | None = None

    # Results
    stdout: str | None = None
    stderr: str | None = None
    summary: str | None = None
    exit_code: int | None = None

    # Usage / cost
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    model: str | None = None

    # Timing
    started_at: datetime | None = None
    finished_at: datetime | None = None
    timeout_seconds: int = Field(default=300)

    # Session resume
    session_id: str | None = None
    session_params: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="runs")
    task: Task | None = Relationship(back_populates="runs")


# API request/response schemas (not tables)
class AgentCreate(SQLModel):
    name: str
    description: str | None = None
    adapter_type: str = "process"
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    heartbeat_interval_seconds: int = 60
    max_budget_usd: float | None = None


class AgentUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    adapter_config: dict[str, Any] | None = None
    status: AgentStatus | None = None
    heartbeat_interval_seconds: int | None = None


class TaskCreate(SQLModel):
    title: str
    description: str | None = None
    agent_id: str | None = None
    status: TaskStatus = TaskStatus.BACKLOG
    priority: int = 0
    context: dict[str, Any] = Field(default_factory=dict)


class RunCreate(SQLModel):
    task_id: str | None = None
    prompt: str | None = None
    timeout_seconds: int | None = None
