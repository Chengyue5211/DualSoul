"""WebSocket router — real-time message push."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from dualsoul.auth import verify_token
from dualsoul.connections import manager
from dualsoul.database import get_db
from dualsoul.twin_engine.twin_state import TwinState, get_state_display

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


async def _broadcast_twin_state(user_id: str, state: str):
    """Broadcast state change to all accepted friends."""
    try:
        with get_db() as db:
            friends = db.execute(
                """SELECT CASE WHEN user_id=? THEN friend_id ELSE user_id END as fid
                FROM social_connections
                WHERE (user_id=? OR friend_id=?) AND status='accepted'""",
                (user_id, user_id, user_id),
            ).fetchall()

        state_info = get_state_display(state, lang="zh")
        for f in friends:
            await manager.send_to(f["fid"], {
                "type": "twin_state_change",
                "data": {
                    "user_id": user_id,
                    "state": state,
                    "icon": state_info["icon"],
                    "label": state_info["label"],
                    "color": state_info["color"],
                },
            })
    except Exception as e:
        logger.warning(f"[TwinState] broadcast failed: {e}")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
    """WebSocket endpoint for real-time push.

    Connect with: ws://host/ws?token=JWT_TOKEN
    Receives JSON events:
      {"type": "new_message", "data": {...}}
      {"type": "friend_request", "data": {...}}
      {"type": "twin_reply", "data": {...}}
      {"type": "twin_state_change", "data": {...}}
      {"type": "twin_permission_request", "data": {...}}
      {"type": "twin_permission_response", "data": {...}}
    """
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    try:
        user = verify_token(token)
    except Exception as e:
        logger.debug(f"WS token validation failed: {e}")
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = user["user_id"]
    await manager.connect(user_id, websocket)

    # Broadcast "human_active" state to friends
    await _broadcast_twin_state(user_id, TwinState.HUMAN_ACTIVE)

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
            except Exception as e:
                logger.debug(f"WS JSON parse failed: {e}")
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
        # Determine offline state and broadcast
        try:
            with get_db() as db:
                row = db.execute(
                    "SELECT twin_auto_reply FROM users WHERE user_id=?", (user_id,)
                ).fetchone()
            auto_reply = bool(row and row["twin_auto_reply"])
            offline_state = (
                TwinState.TWIN_RECEPTIONIST if auto_reply else TwinState.TWIN_STANDBY
            )
            await _broadcast_twin_state(user_id, offline_state)
        except Exception as e:
            logger.warning(f"[TwinState] offline broadcast failed: {e}")
    except Exception as e:
        logger.warning(f"[WS] Unexpected error for user {user_id}: {e}", exc_info=True)
        manager.disconnect(user_id)
