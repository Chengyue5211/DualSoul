"""Social router — friends, messages, and the four conversation modes."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.connections import manager
from dualsoul.database import gen_id, get_db
from dualsoul.models import AddFriendRequest, RespondFriendRequest, SendMessageRequest, TranslateRequest, TwinChatRequest
from dualsoul.twin_engine.responder import TwinResponder

router = APIRouter(prefix="/api/social", tags=["Social"])
_twin = TwinResponder()


@router.post("/friends/add")
async def add_friend(req: AddFriendRequest, user=Depends(get_current_user)):
    """Send a friend request by username."""
    uid = user["user_id"]
    username = req.friend_username.strip()
    if not username:
        return {"success": False, "error": "Username required"}

    with get_db() as db:
        friend = db.execute(
            "SELECT user_id FROM users WHERE username=? AND user_id!=?",
            (username, uid),
        ).fetchone()
        if not friend:
            return {"success": False, "error": "User not found"}
        fid = friend["user_id"]

        exists = db.execute(
            "SELECT conn_id, status FROM social_connections "
            "WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
            (uid, fid, fid, uid),
        ).fetchone()
        if exists:
            return {"success": False, "error": f"Connection already exists ({exists['status']})"}

        conn_id = gen_id("sc_")
        db.execute(
            "INSERT INTO social_connections (conn_id, user_id, friend_id, status) "
            "VALUES (?, ?, ?, 'pending')",
            (conn_id, uid, fid),
        )

    # Notify the recipient via WebSocket
    await manager.send_to(fid, {
        "type": "friend_request",
        "data": {"conn_id": conn_id, "from_user_id": uid, "username": username},
    })
    return {"success": True, "conn_id": conn_id}


@router.post("/friends/respond")
async def respond_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
    """Accept or block a friend request."""
    uid = user["user_id"]
    if req.action not in ("accept", "block"):
        return {"success": False, "error": "action must be 'accept' or 'block'"}

    with get_db() as db:
        conn = db.execute(
            "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
            (req.conn_id,),
        ).fetchone()
        if not conn:
            return {"success": False, "error": "Request not found"}
        if conn["friend_id"] != uid:
            return {"success": False, "error": "Not authorized"}
        if conn["status"] != "pending":
            return {"success": False, "error": f"Already processed ({conn['status']})"}

        new_status = "accepted" if req.action == "accept" else "blocked"
        accepted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if req.action == "accept" else None
        db.execute(
            "UPDATE social_connections SET status=?, accepted_at=? WHERE conn_id=?",
            (new_status, accepted_at, req.conn_id),
        )
    return {"success": True, "status": new_status}


@router.get("/friends")
async def list_friends(user=Depends(get_current_user)):
    """List all friends with their dual identity info."""
    uid = user["user_id"]
    with get_db() as db:
        rows = db.execute(
            """
            SELECT sc.conn_id, sc.status, sc.created_at, sc.accepted_at,
                   sc.user_id AS req_from, sc.friend_id AS req_to,
                   u.user_id, u.username, u.display_name, u.avatar,
                   u.current_mode, u.twin_avatar, u.reg_source
            FROM social_connections sc
            JOIN users u ON u.user_id = CASE
                WHEN sc.user_id=? THEN sc.friend_id
                ELSE sc.user_id END
            WHERE (sc.user_id=? OR sc.friend_id=?)
              AND sc.status IN ('pending', 'accepted')
            ORDER BY sc.accepted_at DESC, sc.created_at DESC
            """,
            (uid, uid, uid),
        ).fetchall()

    friends = []
    for r in rows:
        friends.append({
            "conn_id": r["conn_id"],
            "status": r["status"],
            "is_incoming": r["req_to"] == uid,
            "user_id": r["user_id"],
            "username": r["username"],
            "display_name": r["display_name"] or r["username"],
            "avatar": r["avatar"] or "",
            "twin_avatar": r["twin_avatar"] or "",
            "current_mode": r["current_mode"] or "real",
            "accepted_at": r["accepted_at"] or "",
            "reg_source": r["reg_source"] if "reg_source" in r.keys() else "dualsoul",
        })
    return {"success": True, "friends": friends}


@router.get("/messages")
async def get_messages(friend_id: str = "", limit: int = 50, user=Depends(get_current_user)):
    """Get conversation history with a friend."""
    uid = user["user_id"]
    if not friend_id:
        return {"success": False, "error": "friend_id required"}

    with get_db() as db:
        conn = db.execute(
            "SELECT conn_id FROM social_connections "
            "WHERE status='accepted' AND "
            "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
            (uid, friend_id, friend_id, uid),
        ).fetchone()
        if not conn:
            return {"success": False, "error": "Not friends"}

        rows = db.execute(
            """
            SELECT msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                   content, original_content, original_lang, target_lang,
                   translation_style, msg_type, is_read, ai_generated, created_at
            FROM social_messages
            WHERE (from_user_id=? AND to_user_id=?)
               OR (from_user_id=? AND to_user_id=?)
            ORDER BY created_at DESC LIMIT ?
            """,
            (uid, friend_id, friend_id, uid, limit),
        ).fetchall()

        # Mark as read
        db.execute(
            "UPDATE social_messages SET is_read=1 "
            "WHERE to_user_id=? AND from_user_id=? AND is_read=0",
            (uid, friend_id),
        )

    messages = [dict(r) for r in rows]
    messages.reverse()
    return {"success": True, "messages": messages}


@router.post("/messages/send")
async def send_message(req: SendMessageRequest, user=Depends(get_current_user)):
    """Send a message. If receiver_mode is 'twin', the recipient's twin auto-replies."""
    uid = user["user_id"]
    content = req.content.strip()
    if not content:
        return {"success": False, "error": "Content cannot be empty"}
    if req.sender_mode not in ("real", "twin"):
        return {"success": False, "error": "Invalid sender_mode"}
    if req.receiver_mode not in ("real", "twin"):
        return {"success": False, "error": "Invalid receiver_mode"}

    with get_db() as db:
        conn = db.execute(
            "SELECT conn_id FROM social_connections "
            "WHERE status='accepted' AND "
            "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
            (uid, req.to_user_id, req.to_user_id, uid),
        ).fetchone()
        if not conn:
            return {"success": False, "error": "Not friends"}

        msg_id = gen_id("sm_")
        db.execute(
            """
            INSERT INTO social_messages
            (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
             content, msg_type, ai_generated)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (msg_id, uid, req.to_user_id, req.sender_mode, req.receiver_mode, content, req.msg_type),
        )

    result = {"success": True, "msg_id": msg_id, "ai_reply": None}

    # Push the new message to the recipient via WebSocket
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await manager.send_to(req.to_user_id, {
        "type": "new_message",
        "data": {
            "msg_id": msg_id, "from_user_id": uid, "to_user_id": req.to_user_id,
            "sender_mode": req.sender_mode, "receiver_mode": req.receiver_mode,
            "content": content, "msg_type": req.msg_type,
            "ai_generated": 0, "created_at": now,
        },
    })

    # Auto-detect foreign language/dialect and push translation (async, non-blocking)
    if manager.is_online(req.to_user_id):
        asyncio.ensure_future(_auto_detect_and_push_translation(
            recipient_id=req.to_user_id,
            content=content,
            for_msg_id=msg_id,
        ))

    # Determine if twin should auto-reply:
    # 1. Explicit: receiver_mode is 'twin'
    # 2. Auto-reply enabled: twin_auto_reply is on (regardless of online status)
    should_twin_reply = req.receiver_mode == "twin"
    if not should_twin_reply and req.receiver_mode == "real":
        with get_db() as db:
            row = db.execute(
                "SELECT twin_auto_reply FROM users WHERE user_id=?", (req.to_user_id,)
            ).fetchone()
            if row and row["twin_auto_reply"]:
                should_twin_reply = True

    if should_twin_reply:
        try:
            reply = await _twin.generate_reply(
                twin_owner_id=req.to_user_id,
                from_user_id=uid,
                incoming_msg=content,
                sender_mode=req.sender_mode,
                target_lang=req.target_lang,
            )
            result["ai_reply"] = reply
            # Push twin reply to both sender and recipient
            if reply:
                twin_msg = {
                    "type": "new_message",
                    "data": {
                        "msg_id": reply["msg_id"], "from_user_id": req.to_user_id,
                        "to_user_id": uid, "sender_mode": "twin",
                        "receiver_mode": req.sender_mode,
                        "content": reply["content"], "msg_type": "text",
                        "ai_generated": 1, "created_at": now,
                    },
                }
                await manager.send_to(uid, twin_msg)
                await manager.send_to(req.to_user_id, twin_msg)
        except Exception:
            pass  # Twin reply is best-effort

    return result


@router.post("/translate")
async def translate(req: TranslateRequest, user=Depends(get_current_user)):
    """Personality-preserving translation — translate as if you wrote it in another language.

    Unlike generic machine translation, this preserves your humor, tone,
    and characteristic expressions.
    """
    uid = user["user_id"]
    content = req.content.strip()
    target_lang = req.target_lang
    if not content:
        return {"success": False, "error": "Content cannot be empty"}
    if not target_lang:
        return {"success": False, "error": "target_lang required"}

    result = await _twin.translate_message(
        owner_id=uid,
        content=content,
        source_lang=req.source_lang,
        target_lang=target_lang,
    )
    if not result:
        return {"success": False, "error": "Translation unavailable (no AI backend)"}
    return {"success": True, "data": result}


@router.post("/translate/detect")
async def detect_translate(req: TranslateRequest, user=Depends(get_current_user)):
    """Auto-detect if a message is in a foreign language or dialect and translate.

    Unlike /translate which requires explicit source/target, this automatically
    detects the language and only translates if it differs from the user's
    preferred language. Also handles Chinese dialects.
    """
    uid = user["user_id"]
    content = req.content.strip()
    if not content:
        return {"success": False, "error": "Content cannot be empty"}

    result = await _twin.detect_and_translate(
        owner_id=uid,
        content=content,
    )
    if not result:
        return {"success": True, "needs_translation": False}
    return {"success": True, "needs_translation": True, "data": result}


@router.post("/twin/chat")
async def twin_chat(req: TwinChatRequest, user=Depends(get_current_user)):
    """Chat with your own digital twin — the twin knows it IS you."""
    uid = user["user_id"]
    reply = await _twin.twin_self_chat(
        owner_id=uid,
        message=req.message,
        history=req.history,
        image_url=req.image,
    )
    if not reply:
        return {"success": False, "error": "Twin chat unavailable"}
    return {"success": True, "reply": reply}


@router.get("/unread")
async def unread_count(user=Depends(get_current_user)):
    """Get unread message count."""
    uid = user["user_id"]
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM social_messages WHERE to_user_id=? AND is_read=0",
            (uid,),
        ).fetchone()
    return {"count": row["cnt"] if row else 0}



async def _auto_detect_and_push_translation(recipient_id: str, content: str, for_msg_id: str):
    """Background task: detect foreign language/dialect and push translation via WebSocket."""
    try:
        result = await _twin.detect_and_translate(
            owner_id=recipient_id,
            content=content,
        )
        if result:
            await manager.send_to(recipient_id, {
                "type": "auto_translation",
                "data": {
                    "for_msg_id": for_msg_id,
                    "detected_lang": result["detected_lang"],
                    "translated_content": result["translated_content"],
                },
            })
    except Exception:
        pass  # Auto-detection is best-effort
