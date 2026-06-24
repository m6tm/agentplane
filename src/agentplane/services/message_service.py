"""Inter-agent messaging service."""

from datetime import datetime
from typing import Any

from sqlalchemy import select

from agentplane.core.db import get_async_session
from agentplane.core.models import AgentMessage, MessageType


class MessageService:
    """Send and read messages between agents."""

    async def send(
        self,
        sender_agent_id: str,
        recipient_agent_id: str | None,
        message_type: MessageType,
        payload: dict[str, Any],
    ) -> AgentMessage:
        """Send a message from one agent to another (or broadcast)."""
        async with get_async_session() as session:
            message = AgentMessage(
                sender_agent_id=sender_agent_id,
                recipient_agent_id=recipient_agent_id,
                message_type=message_type,
                payload=payload,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return message

    async def broadcast(
        self,
        sender_agent_id: str,
        message_type: MessageType,
        payload: dict[str, Any],
    ) -> AgentMessage:
        """Broadcast a message to all agents."""
        return await self.send(sender_agent_id, None, message_type, payload)

    async def list_unread(self, agent_id: str) -> list[AgentMessage]:
        """List unread messages for an agent (including broadcasts)."""
        async with get_async_session() as session:
            result = await session.execute(
                select(AgentMessage).where(
                    (AgentMessage.recipient_agent_id == agent_id)
                    | (AgentMessage.recipient_agent_id.is_(None))
                )
                .where(AgentMessage.read_at.is_(None))
                .order_by(AgentMessage.created_at.desc())
            )
            return list(result.scalars().all())

    async def mark_read(self, message_id: str) -> AgentMessage | None:
        """Mark a message as read."""
        async with get_async_session() as session:
            result = await session.execute(
                select(AgentMessage).where(AgentMessage.id == message_id)
            )
            message = result.scalar_one_or_none()
            if message is None:
                return None
            message.read_at = datetime.utcnow()
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return message
