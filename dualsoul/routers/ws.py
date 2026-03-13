"""WebSocket router — real-time message push."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from dualsoul.auth import verify_token
from dualsoul.connections import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
    """WebSocket endpoint for real-time push.

    Connect with: ws://host/ws?token=JWT_TOKEN
    Receives JSON events:
      {"type": "new_message", "data": {...}}
      {"type": "friend_request", "data": {...}}
      {"type": "twin_reply", "data": {...}}
    """
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    try:
        user = verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = user["user_id"]
    await manager.connect(user_id, websocket)

    try:
        while True:
            # Keep connection alive; handle client pings
            data = await websocket.receive_text()
            manager.touch(user_id)
            # Client can send "ping" to keep alive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception:
        manager.disconnect(user_id)
