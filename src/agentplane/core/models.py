"""Domain models for Agentplane trading control plane."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, Relationship, SQLModel


class TradingDeskMode(StrEnum):
    """Trading desk execution mode."""

    PAPER = "paper"
    BACKTEST = "backtest"
    LIVE = "live"


class TradingDeskStatus(StrEnum):
    """Trading desk lifecycle states."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class TradingDesk(SQLModel, table=True):
    """A trading desk: a container for capital, risk limits, and traders."""

    __tablename__ = "trading_desks"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    goal: str | None = None
    mode: TradingDeskMode = Field(default=TradingDeskMode.PAPER)
    status: TradingDeskStatus = Field(default=TradingDeskStatus.ACTIVE)

    # Capital
    initial_capital_usd: float = Field(default=10000.0)
    current_capital_usd: float = Field(default=10000.0)

    # Risk limits
    max_daily_loss_usd: float | None = None
    max_position_size_usd: float | None = None
    max_open_positions: int | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agents: list["Agent"] = Relationship(back_populates="trading_desk")


class StrategyTimeframe(StrEnum):
    """Trading timeframe."""

    SCALPING = "scalping"
    DAILY = "daily"
    SWING = "swing"


class Strategy(SQLModel, table=True):
    """A trading strategy with entry/exit rules and risk parameters."""

    __tablename__ = "strategies"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    timeframe: StrategyTimeframe = Field(default=StrategyTimeframe.DAILY)

    # Rules stored as flexible JSON
    entry_rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    exit_rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Risk
    risk_per_trade_pct: float = Field(default=1.0)
    max_positions: int = Field(default=1)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SkillCategory(StrEnum):
    """Skill category."""

    ANALYSIS = "analysis"
    RISK = "risk"
    EXECUTION = "execution"
    PSYCHOLOGY = "psychology"


class Skill(SQLModel, table=True):
    """A skill module that can be attached to an agent/trader."""

    __tablename__ = "skills"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    category: SkillCategory = Field(default=SkillCategory.ANALYSIS)
    version: int = Field(default=1)

    # Text injected into agent context at heartbeat time
    prompt_injection: str = ""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentStatus(StrEnum):
    """Agent lifecycle states."""

    IDLE = "idle"
    SCANNING = "scanning"
    TRADING = "trading"
    PAUSED = "paused"
    ERROR = "error"


class RiskProfile(StrEnum):
    """Agent risk profile."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class Agent(SQLModel, table=True):
    """An agent, specialized here as a trader."""

    __tablename__ = "agents"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    trading_desk_id: str | None = Field(default=None, foreign_key="trading_desks.id", index=True)
    strategy_id: str | None = Field(default=None, foreign_key="strategies.id", index=True)

    name: str = Field(index=True)
    description: str | None = None
    role: str | None = None  # e.g. scalper, swing_trader, risk_manager

    # Adapter configuration
    adapter_type: str = Field(default="process")
    adapter_config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Runtime
    status: AgentStatus = Field(default=AgentStatus.IDLE)
    session_id: str | None = None
    session_params: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    session_memory: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Trading specifics
    risk_profile: RiskProfile = Field(default=RiskProfile.MODERATE)
    skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Scheduling
    heartbeat_interval_seconds: int = Field(default=60)
    max_budget_usd: float | None = None
    spent_budget_usd: float = Field(default=0.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    trading_desk: TradingDesk | None = Relationship(back_populates="agents")
    runs: list["Run"] = Relationship(back_populates="agent")
    signals: list["Signal"] = Relationship(back_populates="agent")
    positions: list["Position"] = Relationship(back_populates="agent")
    trades: list["Trade"] = Relationship(back_populates="agent")
    lessons: list["Lesson"] = Relationship(back_populates="agent")


class TaskStatus(StrEnum):
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


class RunStatus(StrEnum):
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


class SignalStatus(StrEnum):
    """Signal lifecycle states."""

    DETECTED = "detected"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


class SignalDirection(StrEnum):
    """Signal direction."""

    LONG = "long"
    SHORT = "short"


class Signal(SQLModel, table=True):
    """A trading signal generated by an agent."""

    __tablename__ = "signals"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)

    symbol: str = Field(index=True)
    direction: SignalDirection
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=0.5)  # 0.0 to 1.0
    setup_name: str | None = None

    market_data_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: SignalStatus = Field(default=SignalStatus.DETECTED)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="signals")


class PositionStatus(StrEnum):
    """Position status."""

    OPEN = "open"
    CLOSED = "closed"


class Position(SQLModel, table=True):
    """An open or closed trading position."""

    __tablename__ = "positions"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)

    symbol: str = Field(index=True)
    direction: SignalDirection

    quantity: float
    entry_price: float
    current_price: float | None = None

    unrealized_pnl_usd: float | None = None
    unrealized_pnl_pct: float | None = None

    status: PositionStatus = Field(default=PositionStatus.OPEN)
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None

    # Relationships
    agent: Agent = Relationship(back_populates="positions")
    orders: list["Order"] = Relationship(back_populates="position")
    trade: Optional["Trade"] = Relationship(back_populates="position")


class OrderStatus(StrEnum):
    """Order status."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderSide(StrEnum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class Order(SQLModel, table=True):
    """A broker order."""

    __tablename__ = "orders"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    position_id: str | None = Field(default=None, foreign_key="positions.id", index=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)

    broker_order_id: str | None = None
    symbol: str = Field(index=True)
    side: OrderSide
    quantity: float
    order_type: str = Field(default="market")  # market, limit, stop
    limit_price: float | None = None
    stop_price: float | None = None

    status: OrderStatus = Field(default=OrderStatus.PENDING)
    filled_price: float | None = None
    filled_quantity: float | None = None
    commission_usd: float | None = None
    filled_at: datetime | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    position: Position | None = Relationship(back_populates="orders")


class Trade(SQLModel, table=True):
    """A completed trade (entry + exit)."""

    __tablename__ = "trades"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)
    position_id: str = Field(foreign_key="positions.id", index=True)

    symbol: str = Field(index=True)
    direction: SignalDirection

    entry_price: float
    exit_price: float | None = None
    quantity: float

    realized_pnl_usd: float | None = None
    realized_pnl_pct: float | None = None
    duration_seconds: int | None = None
    setup: str | None = None
    outcome: str | None = None  # win | loss | breakeven

    journal_entry_id: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None

    # Relationships
    agent: Agent = Relationship(back_populates="trades")
    position: Position = Relationship(back_populates="trade")


class TradeJournal(SQLModel, table=True):
    """Journal entry for a trade."""

    __tablename__ = "trade_journals"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    trade_id: str = Field(foreign_key="trades.id", index=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)

    pre_trade_notes: str | None = None
    post_trade_notes: str | None = None
    mistakes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    learnings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    discipline_score: int | None = None  # 1-10

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LessonSeverity(StrEnum):
    """Lesson severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Lesson(SQLModel, table=True):
    """A learned lesson extracted from past trades."""

    __tablename__ = "lessons"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", index=True)

    category: str  # e.g. risk_management, discipline, setup
    trigger_pattern: str
    corrective_action: str
    severity: LessonSeverity = Field(default=LessonSeverity.MEDIUM)

    occurrence_count: int = Field(default=1)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="lessons")


class MarketData(SQLModel, table=True):
    """OHLCV market data."""

    __tablename__ = "market_data"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    symbol: str = Field(index=True)
    timeframe: str = Field(index=True)  # 1m, 5m, 15m, 1h, 1d
    source: str = Field(default="oanda")  # oanda, alpaca, binance, static_data

    timestamp: datetime = Field(index=True)
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        Index("ix_market_data_symbol_timeframe_timestamp", "symbol", "timeframe", "timestamp"),
    )


class MessageType(StrEnum):
    """Type of inter-agent message."""

    SIGNAL = "signal"
    COMMAND = "command"
    STATUS = "status"
    ALERT = "alert"


class AgentMessage(SQLModel, table=True):
    """Message exchanged between agents."""

    __tablename__ = "agent_messages"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    sender_agent_id: str = Field(foreign_key="agents.id", index=True)
    recipient_agent_id: str | None = Field(
        default=None, foreign_key="agents.id", index=True
    )  # None = broadcast

    message_type: MessageType = Field(default=MessageType.STATUS)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    read_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# API request/response schemas (not tables)
class TradingDeskCreate(SQLModel):
    name: str
    goal: str | None = None
    mode: TradingDeskMode = TradingDeskMode.PAPER
    initial_capital_usd: float = 10000.0
    max_daily_loss_usd: float | None = None
    max_position_size_usd: float | None = None
    max_open_positions: int | None = None


class TradingDeskUpdate(SQLModel):
    name: str | None = None
    goal: str | None = None
    status: TradingDeskStatus | None = None
    current_capital_usd: float | None = None
    max_daily_loss_usd: float | None = None
    max_position_size_usd: float | None = None
    max_open_positions: int | None = None


class StrategyCreate(SQLModel):
    name: str
    description: str | None = None
    timeframe: StrategyTimeframe = StrategyTimeframe.DAILY
    entry_rules: dict[str, Any] = Field(default_factory=dict)
    exit_rules: dict[str, Any] = Field(default_factory=dict)
    risk_per_trade_pct: float = 1.0
    max_positions: int = 1


class StrategyUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    entry_rules: dict[str, Any] | None = None
    exit_rules: dict[str, Any] | None = None
    risk_per_trade_pct: float | None = None
    max_positions: int | None = None


class SkillCreate(SQLModel):
    name: str
    description: str | None = None
    category: SkillCategory = SkillCategory.ANALYSIS
    prompt_injection: str = ""


class SkillUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    category: SkillCategory | None = None
    prompt_injection: str | None = None


class AgentCreate(SQLModel):
    name: str
    description: str | None = None
    role: str | None = None
    trading_desk_id: str | None = None
    strategy_id: str | None = None
    adapter_type: str = "process"
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    risk_profile: RiskProfile = RiskProfile.MODERATE
    skills: list[str] = Field(default_factory=list)
    heartbeat_interval_seconds: int = 60
    max_budget_usd: float | None = None


class AgentUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    role: str | None = None
    trading_desk_id: str | None = None
    strategy_id: str | None = None
    adapter_config: dict[str, Any] | None = None
    status: AgentStatus | None = None
    risk_profile: RiskProfile | None = None
    skills: list[str] | None = None
    heartbeat_interval_seconds: int | None = None
    session_memory: dict[str, Any] | None = None


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
