"""Trade journal service.

Creates structured journal entries when a position is closed and a trade record
is produced. The journal captures context, mistakes, learnings and a discipline
score so agents can review their performance.
"""

from sqlalchemy import select

from agentplane.core.db import get_async_session
from agentplane.core.models import Agent, Position, Trade, TradeJournal


class JournalService:
    """Create and retrieve trade journal entries."""

    async def create_from_trade(
        self,
        trade: Trade,
        position: Position,
        agent: Agent,
    ) -> TradeJournal:
        """Build a journal entry from a completed trade and link it to the trade."""
        pre_notes = self._pre_trade_notes(position, agent)
        post_notes = self._post_trade_notes(trade)
        mistakes = self._detect_mistakes(trade, position)
        learnings = self._detect_learnings(trade, mistakes)
        discipline_score = self._discipline_score(trade, mistakes)

        async with get_async_session() as session:
            journal = TradeJournal(
                trade_id=trade.id,
                agent_id=agent.id,
                pre_trade_notes=pre_notes,
                post_trade_notes=post_notes,
                mistakes=mistakes,
                learnings=learnings,
                discipline_score=discipline_score,
            )
            session.add(journal)
            await session.commit()
            await session.refresh(journal)

            trade.journal_entry_id = journal.id
            session.add(trade)
            await session.commit()

            return journal

    async def get(self, journal_id: str) -> TradeJournal | None:
        """Get a journal entry by ID."""
        async with get_async_session() as session:
            result = await session.execute(
                select(TradeJournal).where(TradeJournal.id == journal_id)
            )
            return result.scalar_one_or_none()

    async def get_for_trade(self, trade_id: str) -> TradeJournal | None:
        """Get the journal entry associated with a trade."""
        async with get_async_session() as session:
            result = await session.execute(
                select(TradeJournal).where(TradeJournal.trade_id == trade_id)
            )
            return result.scalar_one_or_none()

    async def list_for_agent(self, agent_id: str) -> list[TradeJournal]:
        """List journal entries for an agent, most recent first."""
        async with get_async_session() as session:
            result = await session.execute(
                select(TradeJournal)
                .where(TradeJournal.agent_id == agent_id)
                .order_by(TradeJournal.created_at.desc())
            )
            return list(result.scalars().all())

    def _pre_trade_notes(self, position: Position, agent: Agent) -> str:
        """Describe the context before the trade was entered."""
        return (
            f"Entered {position.direction} {position.symbol} "
            f"at {position.entry_price:.4f} "
            f"(qty={position.quantity:.4f})."
        )

    def _post_trade_notes(self, trade: Trade) -> str:
        """Describe the trade outcome."""
        duration_text = ""
        if trade.duration_seconds is not None:
            duration_text = f" Duration: {trade.duration_seconds}s."
        return (
            f"Exited at {trade.exit_price:.4f} with outcome {trade.outcome}. "
            f"Realized P&L: ${trade.realized_pnl_usd:.4f} "
            f"({trade.realized_pnl_pct * 100:.2f}%).{duration_text}"
        )

    def _detect_mistakes(self, trade: Trade, position: Position) -> list[str]:
        """Return a list of mistake tags based on trade attributes."""
        mistakes: list[str] = []

        if trade.outcome == "loss":
            mistakes.append("trade_closed_at_loss")
            if trade.duration_seconds is not None and trade.duration_seconds < 60:
                mistakes.append("impatient_exit")

        if trade.duration_seconds is not None and trade.duration_seconds < 30:
            mistakes.append("very_short_hold")

        # Very small position suggests under-commitment or sizing issue
        if position.quantity < 1:
            mistakes.append("undersized_position")

        return mistakes

    def _detect_learnings(self, trade: Trade, mistakes: list[str]) -> list[str]:
        """Return positive learnings / takeaways from the trade."""
        learnings: list[str] = []

        if trade.outcome == "win":
            learnings.append("followed_setup_and_captured_edge")

        if (
            "impatient_exit" not in mistakes
            and trade.duration_seconds
            and trade.duration_seconds >= 60
        ):
            learnings.append("allowed_trade_time_to_work")

        if trade.outcome == "breakeven":
            learnings.append("protected_capital_no_major_loss")

        return learnings

    def _discipline_score(self, trade: Trade, mistakes: list[str]) -> int:
        """Compute a 1-10 discipline score for the trade."""
        score = 7

        if trade.outcome == "win":
            score += 2
        elif trade.outcome == "loss":
            score -= 2

        if "impatient_exit" in mistakes:
            score -= 2
        if "very_short_hold" in mistakes:
            score -= 1
        if "undersized_position" in mistakes:
            score -= 1

        return max(1, min(10, score))
