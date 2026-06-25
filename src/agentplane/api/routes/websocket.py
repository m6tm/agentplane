"""WebSocket endpoint for real-time agent data streaming.

Streams live data to connected clients:
- Agent status changes
- New signals
- Position updates
- Trading activity logs
- Heartbeat events
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agentplane.core.models import Agent, AgentStatus, Signal, SignalStatus
from agentplane.services.agent_service import AgentService
from agentplane.services.signal_service import SignalService
from agentplane.services.position_service import PositionService

router = APIRouter()

# Connected clients
connected_clients: set[WebSocket] = set()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]):
        """Broadcast message to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections.discard(conn)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time data."""
    await manager.connect(websocket)

    # Send initial data
    agent_service = AgentService()
    signal_service = SignalService()
    position_service = PositionService()

    agents = await agent_service.list_all()
    signals = await signal_service.list_all()
    positions = await position_service.list_all()

    await websocket.send_json({
        "type": "initial",
        "data": {
            "agents": [agent.model_dump() for agent in agents],
            "signals": [signal.model_dump() for signal in signals],
            "positions": [pos.model_dump() for pos in positions],
            "timestamp": asyncio.get_event_loop().time(),
        }
    })

    try:
        while True:
            # Wait for client messages (subscriptions, commands)
            message = await websocket.receive_json()

            if message.get("action") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": asyncio.get_event_loop().time()})

            elif message.get("action") == "subscribe":
                channel = message.get("channel", "all")
                await websocket.send_json({"type": "subscribed", "channel": channel})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def broadcast_agent_update(agent: Agent):
    """Broadcast agent status update to all clients."""
    await manager.broadcast({
        "type": "agent_update",
        "data": {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "status": agent.status.value if hasattr(agent.status, 'value') else str(agent.status),
            "symbol": agent.adapter_config.get("symbol", "") if agent.adapter_config else "",
            "watchlist_count": len(agent.watchlist) if agent.watchlist else 0,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }
    })


async def broadcast_signal(signal: Signal):
    """Broadcast new signal to all clients."""
    await manager.broadcast({
        "type": "signal",
        "data": {
            "id": signal.id,
            "agent_id": signal.agent_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction),
            "confidence": signal.confidence,
            "setup_name": signal.setup_name,
            "status": signal.status.value if hasattr(signal.status, 'value') else str(signal.status),
            "created_at": signal.created_at.isoformat() if signal.created_at else None,
        }
    })


async def broadcast_position_update(position: Any):
    """Broadcast position update to all clients."""
    await manager.broadcast({
        "type": "position_update",
        "data": {
            "id": position.id,
            "agent_id": position.agent_id,
            "symbol": position.symbol,
            "direction": position.direction,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "current_price": position.current_price if hasattr(position, 'current_price') else None,
            "unrealized_pnl_usd": position.unrealized_pnl_usd if hasattr(position, 'unrealized_pnl_usd') else None,
            "status": position.status.value if hasattr(position.status, 'value') else str(position.status),
            "updated_at": position.updated_at.isoformat() if hasattr(position, 'updated_at') else None,
        }
    })


async def broadcast_log(level: str, message: str, agent_id: str | None = None, extra: dict | None = None):
    """Broadcast log message to all clients."""
    await manager.broadcast({
        "type": "log",
        "data": {
            "level": level,
            "message": message,
            "agent_id": agent_id,
            "extra": extra or {},
            "timestamp": asyncio.get_event_loop().time(),
        }
    })


async def broadcast_heartbeat(agent_id: str, status: str, next_beat: float | None = None):
    """Broadcast heartbeat event to all clients."""
    await manager.broadcast({
        "type": "heartbeat",
        "data": {
            "agent_id": agent_id,
            "status": status,
            "next_beat": next_beat,
            "timestamp": asyncio.get_event_loop().time(),
        }
    })
