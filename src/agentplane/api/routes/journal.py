"""Trade journal and lesson routes."""

from fastapi import APIRouter, HTTPException

from agentplane.core.models import Lesson, TradeJournal
from agentplane.services.agent_service import AgentService
from agentplane.services.journal_service import JournalService
from agentplane.services.lesson_service import LessonService
from agentplane.services.memory_service import MemoryService

agent_service = AgentService()
journal_service = JournalService()
lesson_service = LessonService()
memory_service = MemoryService()

journal_router = APIRouter()


@journal_router.get("/trades/{trade_id}/journal", response_model=TradeJournal)
async def get_trade_journal(agent_id: str, trade_id: str):
    """Get the journal entry for a specific trade."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    journal = await journal_service.get_for_trade(trade_id)
    if journal is None or journal.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return journal


@journal_router.get("/journal", response_model=list[TradeJournal])
async def list_agent_journals(agent_id: str):
    """List all journal entries for an agent."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await journal_service.list_for_agent(agent_id)


lesson_router = APIRouter()


@lesson_router.get("/lessons", response_model=list[Lesson])
async def list_agent_lessons(agent_id: str, active_only: bool = True):
    """List lessons learned by an agent."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await lesson_service.list_for_agent(agent_id, active_only=active_only)


@lesson_router.get("/lessons/{lesson_id}", response_model=Lesson)
async def get_agent_lesson(agent_id: str, lesson_id: str):
    """Get a specific lesson for an agent."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    lesson = await lesson_service.get(lesson_id)
    if lesson is None or lesson.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


memory_router = APIRouter()


@memory_router.get("/memory")
async def get_agent_memory(agent_id: str):
    """Get the current memory context for an agent."""
    agent = await agent_service.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await memory_service.compute_context(agent_id)
