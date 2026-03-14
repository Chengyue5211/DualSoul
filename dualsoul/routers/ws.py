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
            data = await websocket.receive_text()
            manager.touch(user_id)
            if data == "ping":
                await websocket.send_text("pong")
                continue

            # Handle JSON messages (call signaling)
            try:
                import json
                msg = json.loads(data)
            except Exception:
                continue

            msg_type = msg.get("type", "")
            target_id = msg.get("target", "")

            # Forward call signaling to the target user
            if msg_type in (
                "call_invite", "call_accept", "call_reject", "call_hangup",
                "call_offer", "call_answer", "call_ice",
            ) and target_id:
                msg["from"] = user_id
                await manager.send_to(target_id, msg)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception:
        manager.disconnect(user_id)
