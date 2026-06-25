"""Routes for interacting with the orchestrator agent."""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Field, SQLModel

from agentplane.core.models import AgentMessage, MessageType
from agentplane.services.agent_service import AgentService
from agentplane.services.message_service import MessageService
from agentplane.services.orchestrator_service import DEFAULT_ORCHESTRATOR_NAME

router = APIRouter()
message_service = MessageService()
agent_service = AgentService()


class OrchestratorMessageRequest(SQLModel):
    """Payload to send a message to the orchestrator."""

    message_type: MessageType = Field(default=MessageType.COMMAND)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/messages")
async def send_message_to_orchestrator(data: OrchestratorMessageRequest):
    """Send a message to the orchestrator agent and process it immediately.

    Returns the orchestrator's LLM reply in the response body.
    """
    orchestrator = await _get_orchestrator()
    
    # Send user message
    await message_service.send(
        sender_agent_id="user",
        recipient_agent_id=orchestrator.id,
        message_type=data.message_type,
        payload=data.payload,
    )
    
    # Process immediately and get the LLM reply
    from agentplane.services.orchestrator_service import OrchestratorService
    service = OrchestratorService()
    reply = await service.process_user_message(orchestrator.id)
    
    return {
        "sent": True,
        "processed": True,
        "reply": reply,
    }


@router.get("/messages", response_model=list[AgentMessage])
async def list_orchestrator_messages():
    """List unread messages for the orchestrator."""
    orchestrator = await _get_orchestrator()
    return await message_service.list_unread(orchestrator.id)


async def _get_orchestrator():
    agents = await agent_service.list()
    orchestrator = next(
        (a for a in agents if a.name == DEFAULT_ORCHESTRATOR_NAME),
        None,
    )
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    return orchestrator
