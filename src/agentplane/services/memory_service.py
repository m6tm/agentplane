"""Agent memory service.

Aggregates active lessons into a decision-making context that other services
(risk, signal generation) can use to adapt behavior based on past mistakes.
"""

from collections import Counter
from typing import Any

from sqlalchemy import select

from agentplane.core.db import get_async_session
from agentplane.core.models import Lesson


class MemoryService:
    """Build a memory context from an agent's active lessons."""

    SETUP_BLOCK_OCCURRENCE = 3
    RISK_REDUCTION_OCCURRENCE = 2
    MIN_RISK_MULTIPLIER = 0.25
    MAX_RISK_MULTIPLIER = 1.0

    async def get_active_lessons(self, agent_id: str) -> list[Lesson]:
        """Return active lessons for an agent, most recently seen first."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Lesson)
                .where(Lesson.agent_id == agent_id, Lesson.active.is_(True))
                .order_by(Lesson.last_seen_at.desc())
            )
            return list(result.scalars().all())

    async def compute_context(self, agent_id: str) -> dict[str, Any]:
        """Compute a memory context from active lessons."""
        lessons = await self.get_active_lessons(agent_id)

        categories = Counter(lesson.category for lesson in lessons)
        critical_count = sum(
            1 for lesson in lessons if lesson.severity.value == "critical"
        )

        return {
            "lesson_count": len(lessons),
            "critical_count": critical_count,
            "top_categories": categories.most_common(),
            "risk_multiplier": self._risk_multiplier(lessons),
            "blocked_setups": self._blocked_setups(lessons),
            "recommendations": [lesson.corrective_action for lesson in lessons],
        }

    async def is_setup_blocked(self, agent_id: str, setup_name: str | None) -> bool:
        """Return True if a setup should be avoided based on active lessons."""
        lessons = await self.get_active_lessons(agent_id)
        blocked = self._blocked_setups(lessons)
        if not setup_name:
            return bool(blocked)
        return setup_name in blocked

    async def get_risk_multiplier(self, agent_id: str) -> float:
        """Return the position-size multiplier for an agent."""
        lessons = await self.get_active_lessons(agent_id)
        return self._risk_multiplier(lessons)

    def _risk_multiplier(self, lessons: list[Lesson]) -> float:
        """Reduce risk exposure when risk-management lessons recur."""
        multiplier = self.MAX_RISK_MULTIPLIER

        for lesson in lessons:
            if lesson.category == "risk_management" and lesson.active:
                if lesson.occurrence_count >= self.RISK_REDUCTION_OCCURRENCE:
                    multiplier = min(multiplier, 0.5)
                else:
                    multiplier = min(multiplier, 0.75)

            if lesson.severity.value == "critical" and lesson.occurrence_count >= 2:
                multiplier = min(multiplier, 0.5)

        return max(self.MIN_RISK_MULTIPLIER, multiplier)

    def _blocked_setups(self, lessons: list[Lesson]) -> list[str]:
        """Return setups that should be skipped because of recurring mistakes."""
        blocked: list[str] = []
        for lesson in lessons:
            if (
                lesson.category in ("discipline", "setup_quality")
                and lesson.active
                and lesson.occurrence_count >= self.SETUP_BLOCK_OCCURRENCE
            ):
                blocked.append(lesson.trigger_pattern)
        return blocked
