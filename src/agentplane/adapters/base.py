"""Abstract base for all agent adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class AdapterContext:
    """Runtime context passed to an adapter on execute()."""

    run_id: str
    agent_id: str
    company_id: str
    task_id: str | None = None
    prompt: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    session_id: str | None = None
    session_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResult:
    """Result of a single adapter execution."""

    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    summary: str | None = None
    session_id: str | None = None
    session_params: dict[str, Any] = field(default_factory=dict)

    # Usage metrics
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    model: str | None = None


class Adapter(ABC):
    """Abstract adapter that runs an agent."""

    @property
    @abstractmethod
    def type(self) -> str:
        """Unique adapter type identifier."""

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-readable label."""

    @abstractmethod
    async def execute(
        self,
        ctx: AdapterContext,
        on_log: Any | None = None,
    ) -> AdapterResult:
        """Execute the agent and return results."""

    @abstractmethod
    async def probe(self, config: dict[str, Any]) -> dict[str, Any]:
        """Health / readiness probe. Returns diagnostic info."""

    def describe(self) -> dict[str, Any]:
        """Return metadata about this adapter."""
        return {
            "type": self.type,
            "label": self.label,
        }
