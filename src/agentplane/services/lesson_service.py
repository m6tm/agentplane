"""Lesson extraction service.

Analyses completed trades and their journal entries to extract recurring
lessons. Lessons are stored so agents can remember past mistakes and improve
future decisions.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select

from agentplane.core.db import get_async_session
from agentplane.core.models import Lesson, LessonSeverity, Trade, TradeJournal


class LessonService:
    """Extract and retrieve lessons from completed trades."""

    LOSS_PCT_THRESHOLD = 0.02  # 2% loss considered significant
    FAST_LOSS_SECONDS = 60  # loss closed within 60s flags discipline

    async def extract_from_trade(
        self,
        trade: Trade,
        journal: TradeJournal,
    ) -> list[Lesson]:
        """Generate or update lessons from a trade and return created lessons."""
        candidates = self._build_candidates(trade, journal)
        extracted: list[Lesson] = []

        async with get_async_session() as session:
            for candidate in candidates:
                lesson = await self._find_existing(session, trade.agent_id, candidate)
                if lesson is None:
                    lesson = Lesson(
                        agent_id=trade.agent_id,
                        category=candidate["category"],
                        trigger_pattern=candidate["trigger_pattern"],
                        corrective_action=candidate["corrective_action"],
                        severity=candidate["severity"],
                        occurrence_count=1,
                        last_seen_at=datetime.utcnow(),
                        active=True,
                    )
                    session.add(lesson)
                else:
                    lesson.occurrence_count += 1
                    lesson.last_seen_at = datetime.utcnow()
                    lesson.active = True
                    session.add(lesson)

                await session.commit()
                await session.refresh(lesson)
                extracted.append(lesson)

        return extracted

    async def get(self, lesson_id: str) -> Lesson | None:
        """Get a lesson by ID."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Lesson).where(Lesson.id == lesson_id)
            )
            return result.scalar_one_or_none()

    async def list_for_agent(
        self,
        agent_id: str,
        active_only: bool = True,
    ) -> list[Lesson]:
        """List lessons for an agent, most recently seen first."""
        async with get_async_session() as session:
            stmt = select(Lesson).where(Lesson.agent_id == agent_id)
            if active_only:
                stmt = stmt.where(Lesson.active.is_(True))
            result = await session.execute(
                stmt.order_by(Lesson.last_seen_at.desc())
            )
            return list(result.scalars().all())

    async def deactivate(self, lesson_id: str) -> bool:
        """Deactivate a lesson (e.g. once it has been mastered)."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Lesson).where(Lesson.id == lesson_id)
            )
            lesson = result.scalar_one_or_none()
            if lesson is None:
                return False
            lesson.active = False
            session.add(lesson)
            await session.commit()
            return True

    async def _find_existing(
        self,
        session,
        agent_id: str,
        candidate: dict[str, Any],
    ) -> Lesson | None:
        """Find an existing matching lesson for this agent."""
        result = await session.execute(
            select(Lesson).where(
                Lesson.agent_id == agent_id,
                Lesson.category == candidate["category"],
                Lesson.trigger_pattern == candidate["trigger_pattern"],
            )
        )
        return result.scalar_one_or_none()

    def _build_candidates(
        self,
        trade: Trade,
        journal: TradeJournal,
    ) -> list[dict[str, Any]]:
        """Build candidate lessons from trade attributes."""
        candidates: list[dict[str, Any]] = []

        if trade.outcome == "loss":
            if (
                trade.duration_seconds is not None
                and trade.duration_seconds <= self.FAST_LOSS_SECONDS
            ):
                candidates.append(
                    {
                        "category": "discipline",
                        "trigger_pattern": "loss_closed_within_60s",
                        "corrective_action": (
                            "Do not panic-exit losing trades within the first minute; "
                            "respect the strategy stop loss."
                        ),
                        "severity": LessonSeverity.HIGH,
                    }
                )

            if (
                trade.realized_pnl_pct is not None
                and trade.realized_pnl_pct <= -self.LOSS_PCT_THRESHOLD
            ):
                candidates.append(
                    {
                        "category": "risk_management",
                        "trigger_pattern": "loss_exceeds_2pct",
                        "corrective_action": (
                            "Reduce position size or tighten stop loss to keep single-trade "
                            "loss below 2% of capital."
                        ),
                        "severity": LessonSeverity.CRITICAL,
                    }
                )

            if "undersized_position" in journal.mistakes:
                candidates.append(
                    {
                        "category": "sizing",
                        "trigger_pattern": "undersized_position_on_loss",
                        "corrective_action": (
                            "Size positions consistently with the strategy risk-per-trade; "
                            "avoid micro positions that add friction without edge."
                        ),
                        "severity": LessonSeverity.LOW,
                    }
                )

        if trade.outcome == "win" and (
            trade.realized_pnl_pct is not None and trade.realized_pnl_pct < 0.005
        ):
            candidates.append(
                {
                    "category": "opportunity_management",
                    "trigger_pattern": "winner_exited_too_early",
                    "corrective_action": (
                        "Review exit rules for winning trades; early exits may cap "
                        "expected returns."
                    ),
                    "severity": LessonSeverity.MEDIUM,
                }
            )

        if trade.outcome == "breakeven" and (
            trade.duration_seconds is not None and trade.duration_seconds < 60
        ):
            candidates.append(
                {
                    "category": "discipline",
                    "trigger_pattern": "breakeven_closed_too_quickly",
                    "corrective_action": (
                        "Avoid closing trades at breakeven out of fear; let the setup "
                        "reach its target or stop."
                    ),
                    "severity": LessonSeverity.MEDIUM,
                }
            )

        return candidates
