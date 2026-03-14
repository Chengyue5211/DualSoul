"""Social router — friends, messages, and the four conversation modes."""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.connections import manager
from dualsoul.database import gen_id, get_db
from dualsoul.models import AddFriendRequest, RespondFriendRequest, SendMessageRequest, TranslateRequest, TwinChatRequest
from dualsoul.twin_engine.ethics import pre_send_check
from dualsoul.twin_engine.life import award_xp, increment_stat, update_relationship_temp
from dualsoul.twin_engine.responder import TwinResponder

router = APIRouter(prefix="/api/social", tags=["Social"])
_twin = TwinResponder()


@router.post("/friends/add")
async def add_friend(req: AddFriendRequest, user=Depends(get_current_user)):
    """Send a friend request by username. If auto_accept, skip pending and become friends directly."""
    uid = user["user_id"]
    username = req.friend_username.strip()
    auto_accept = getattr(req, 'auto_accept', False)
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
            if exists["status"] == "deleted":
                # Re-add a deleted friend — set back to accepted
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    "UPDATE social_connections SET status='accepted', accepted_at=? WHERE conn_id=?",
                    (now, exists["conn_id"]),
                )
                return {"success": True, "conn_id": exists["conn_id"], "status": "accepted"}
            return {"success": False, "error": f"Connection already exists ({exists['status']})"}

        conn_id = gen_id("sc_")
        if auto_accept:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "INSERT INTO social_connections (conn_id, user_id, friend_id, status, accepted_at) "
                "VALUES (?, ?, ?, 'accepted', ?)",
                (conn_id, uid, fid, now),
            )
        else:
            db.execute(
                "INSERT INTO social_connections (conn_id, user_id, friend_id, status) "
                "VALUES (?, ?, ?, 'pending')",
                (conn_id, uid, fid),
            )

    # Notify the recipient via WebSocket
    if auto_accept:
        my_info = None
        with get_db() as db:
            my_info = db.execute("SELECT username, display_name FROM users WHERE user_id=?", (uid,)).fetchone()
        await manager.send_to(fid, {
            "type": "friend_added",
            "data": {"conn_id": conn_id, "user_id": uid,
                     "username": my_info["username"] if my_info else "",
                     "display_name": my_info["display_name"] if my_info else ""},
        })
    else:
        await manager.send_to(fid, {
            "type": "friend_request",
            "data": {"conn_id": conn_id, "from_user_id": uid, "username": username},
        })
    return {"success": True, "conn_id": conn_id, "status": "accepted" if auto_accept else "pending"}


@router.post("/friends/delete")
async def delete_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
    """Delete a friend (one-way, like WeChat). The other person still has you in their list."""
    uid = user["user_id"]
    with get_db() as db:
        conn = db.execute(
            "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
            (req.conn_id,),
        ).fetchone()
        if not conn:
            return {"success": False, "error": "Connection not found"}
        if conn["user_id"] != uid and conn["friend_id"] != uid:
            return {"success": False, "error": "Not authorized"}
        db.execute("UPDATE social_connections SET status='deleted' WHERE conn_id=?", (req.conn_id,))
    return {"success": True}


@router.post("/friends/block")
async def block_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
    """Block a friend. They can't message you."""
    uid = user["user_id"]
    with get_db() as db:
        conn = db.execute(
            "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
            (req.conn_id,),
        ).fetchone()
        if not conn:
            return {"success": False, "error": "Connection not found"}
        if conn["user_id"] != uid and conn["friend_id"] != uid:
            return {"success": False, "error": "Not authorized"}
        db.execute("UPDATE social_connections SET status='blocked' WHERE conn_id=?", (req.conn_id,))
    return {"success": True}


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
        requester_id = conn["user_id"]

    if new_status == "accepted":
        # Twin Life: both earn XP for making a new friend
        award_xp(uid, 20, reason="new_friend")
        award_xp(requester_id, 20, reason="new_friend")
        increment_stat(uid, "total_friends_made")
        increment_stat(requester_id, "total_friends_made")
        # Initialize relationship temperature at warm
        update_relationship_temp(uid, requester_id, 50.0)
        update_relationship_temp(requester_id, uid, 50.0)

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
    friend_ids = []
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
            "last_msg": "",
            "last_msg_time": "",
            "last_msg_mine": False,
        })
        if r["status"] == "accepted":
            friend_ids.append(r["user_id"])

    # Fetch last message for each accepted friend
    if friend_ids:
        with get_db() as db:
            for f in friends:
                if f["status"] != "accepted":
                    continue
                fid = f["user_id"]
                msg = db.execute(
                    """
                    SELECT content, created_at, from_user_id, sender_mode FROM social_messages
                    WHERE (from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?)
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (uid, fid, fid, uid),
                ).fetchone()
                if msg:
                    preview = msg["content"][:40]
                    if msg["sender_mode"] == "twin":
                        preview = "👻 " + preview
                    f["last_msg"] = preview
                    f["last_msg_time"] = msg["created_at"] or ""
                    f["last_msg_mine"] = msg["from_user_id"] == uid

        # Sort accepted friends by last message time (most recent first)
        def sort_key(f):
            if f["status"] != "accepted":
                return ""
            return f["last_msg_time"] or f["accepted_at"] or ""
        friends.sort(key=sort_key, reverse=True)

    return {"success": True, "friends": friends}


@router.get("/messages")
async def get_messages(friend_id: str = "", limit: int = 50, user=Depends(get_current_user)):
    """Get conversation history with a friend."""
    uid = user["user_id"]
    limit = min(max(1, limit), 100)  # Clamp between 1 and 100
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

    # Twin Life: award XP for chatting and warm up relationship
    award_xp(uid, 2, reason="send_message")
    increment_stat(uid, "total_chats")
    update_relationship_temp(uid, req.to_user_id, 1.0)
    update_relationship_temp(req.to_user_id, uid, 0.5)

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
    # 1. Explicit: receiver_mode is 'twin' → reply immediately
    # 2. Auto-reply enabled → depends on owner's activity:
    #    a. Owner offline → reply immediately
    #    b. Owner online but idle → wait 30s, check if owner responded, if not → twin replies
    #    c. Owner actively chatting with this friend → twin stays quiet
    twin_auto_enabled = False
    if req.receiver_mode == "twin":
        # Explicit twin mode — reply immediately
        asyncio.ensure_future(_do_twin_reply(
            twin_owner_id=req.to_user_id, from_user_id=uid,
            content=content, sender_mode=req.sender_mode,
            target_lang=req.target_lang, msg_id=msg_id,
        ))
    elif req.receiver_mode == "real":
        with get_db() as db:
            row = db.execute(
                "SELECT twin_auto_reply FROM users WHERE user_id=?", (req.to_user_id,)
            ).fetchone()
            twin_auto_enabled = bool(row and row["twin_auto_reply"])
            logger.info(f"[Twin] receiver={req.to_user_id}, twin_auto_reply={row['twin_auto_reply'] if row else 'no user'}")

        if twin_auto_enabled:
            owner_online = manager.is_online(req.to_user_id)
            logger.info(f"[Twin] auto_reply=1, owner_online={owner_online}, to={req.to_user_id}")
            if not owner_online:
                # Owner offline → reply immediately
                logger.info(f"[Twin] Owner offline, replying immediately")
                asyncio.ensure_future(_do_twin_reply(
                    twin_owner_id=req.to_user_id, from_user_id=uid,
                    content=content, sender_mode=req.sender_mode,
                    target_lang=req.target_lang, msg_id=msg_id,
                ))
            else:
                # Owner online — wait 30s then check if they responded
                logger.info(f"[Twin] Owner online, scheduling 30s delay")
                asyncio.ensure_future(_delayed_twin_reply(
                    twin_owner_id=req.to_user_id, from_user_id=uid,
                    content=content, sender_mode=req.sender_mode,
                    target_lang=req.target_lang, msg_id=msg_id,
                    delay_seconds=30,
                ))

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

    # Save the user's message for style learning (sender_mode='real' to self)
    if req.message and req.message.strip():
        user_msg_id = gen_id("sm_")
        with get_db() as db:
            db.execute(
                """
                INSERT INTO social_messages
                (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                 content, msg_type, ai_generated)
                VALUES (?, ?, ?, 'real', 'twin', ?, 'text', 0)
                """,
                (user_msg_id, uid, uid, req.message.strip()),
            )

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


@router.get("/unread/by-friend")
async def unread_by_friend(user=Depends(get_current_user)):
    """Get unread message count grouped by sender."""
    uid = user["user_id"]
    with get_db() as db:
        rows = db.execute(
            """
            SELECT from_user_id, COUNT(*) as cnt
            FROM social_messages
            WHERE to_user_id=? AND is_read=0
            GROUP BY from_user_id
            """,
            (uid,),
        ).fetchall()
    result = {}
    for r in rows:
        result[r["from_user_id"]] = r["cnt"]
    return {"unread": result}


@router.get("/twin/activity")
async def twin_activity(user=Depends(get_current_user)):
    """Get recent twin auto-reply notifications (unread, twin→owner self-messages)."""
    uid = user["user_id"]
    with get_db() as db:
        rows = db.execute(
            """
            SELECT msg_id, content, metadata, created_at FROM social_messages
            WHERE from_user_id=? AND to_user_id=? AND sender_mode='twin'
                AND ai_generated=1 AND is_read=0
            ORDER BY created_at DESC LIMIT 10
            """,
            (uid, uid),
        ).fetchall()
        # Mark them as read
        if rows:
            db.execute(
                """
                UPDATE social_messages SET is_read=1
                WHERE from_user_id=? AND to_user_id=? AND sender_mode='twin'
                    AND ai_generated=1 AND is_read=0
                """,
                (uid, uid),
            )
    return {"success": True, "activities": [dict(r) for r in rows]}


async def _do_twin_reply(
    twin_owner_id: str, from_user_id: str, content: str,
    sender_mode: str, target_lang: str, msg_id: str,
):
    """Execute the twin auto-reply: generate response, push to both users, notify owner."""
    try:
        # Ethics check on incoming message — brake if sensitive topic detected
        incoming_check = pre_send_check(twin_owner_id, content, "auto_reply")
        if not incoming_check["allowed"] and incoming_check.get("brake_message"):
            # Send brake message instead of generating a reply
            brake_msg = incoming_check["brake_message"]
            brake_id = gen_id("sm_")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_db() as db:
                db.execute(
                    """INSERT INTO social_messages
                    (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                     content, msg_type, ai_generated, auto_reply, metadata)
                    VALUES (?, ?, ?, 'twin', ?, ?, 'text', 1, 1, '{"ethics_brake":true}')""",
                    (brake_id, twin_owner_id, from_user_id, sender_mode, brake_msg),
                )
            twin_msg = {
                "type": "new_message",
                "data": {
                    "msg_id": brake_id, "from_user_id": twin_owner_id,
                    "to_user_id": from_user_id, "sender_mode": "twin",
                    "receiver_mode": sender_mode, "content": brake_msg,
                    "msg_type": "text", "ai_generated": 1, "created_at": now,
                },
            }
            await manager.send_to(from_user_id, twin_msg)
            await manager.send_to(twin_owner_id, twin_msg)
            return

        if not incoming_check["allowed"]:
            return  # Silently blocked (e.g. daily limit reached)

        reply = await _twin.generate_reply(
            twin_owner_id=twin_owner_id,
            from_user_id=from_user_id,
            incoming_msg=content,
            sender_mode=sender_mode,
            target_lang=target_lang,
            social_context="auto_reply",
        )
        if reply:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            twin_msg = {
                "type": "new_message",
                "data": {
                    "msg_id": reply["msg_id"], "from_user_id": twin_owner_id,
                    "to_user_id": from_user_id, "sender_mode": "twin",
                    "receiver_mode": sender_mode,
                    "content": reply["content"], "msg_type": "text",
                    "ai_generated": 1, "created_at": now,
                },
            }
            await manager.send_to(from_user_id, twin_msg)
            await manager.send_to(twin_owner_id, twin_msg)

            # Notify the owner
            await _notify_owner_twin_replied(
                owner_id=twin_owner_id,
                friend_id=from_user_id,
                friend_msg=content,
                twin_reply=reply["content"],
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Twin auto-reply failed: {e}")


async def _delayed_twin_reply(
    twin_owner_id: str, from_user_id: str, content: str,
    sender_mode: str, target_lang: str, msg_id: str,
    delay_seconds: int = 30,
):
    """Wait, then check if owner responded. If not, twin steps in."""
    try:
        logger.info(f"[Twin delay] Waiting {delay_seconds}s for {twin_owner_id} to reply to {from_user_id}")
        await asyncio.sleep(delay_seconds)

        # Check if the owner replied to this friend in the meantime
        with get_db() as db:
            recent = db.execute(
                """
                SELECT COUNT(*) AS cnt FROM social_messages
                WHERE from_user_id=? AND to_user_id=? AND sender_mode='real'
                    AND ai_generated=0
                    AND created_at > datetime('now', 'localtime', '-{delay} seconds')
                """.replace("{delay}", str(delay_seconds + 5)),
                (twin_owner_id, from_user_id),
            ).fetchone()

        if recent and recent["cnt"] > 0:
            logger.info(f"[Twin delay] Owner {twin_owner_id} already replied, twin stays quiet")
            return

        logger.info(f"[Twin delay] Owner {twin_owner_id} didn't reply, twin stepping in")
        await _do_twin_reply(
            twin_owner_id=twin_owner_id, from_user_id=from_user_id,
            content=content, sender_mode=sender_mode,
            target_lang=target_lang, msg_id=msg_id,
        )
    except Exception as e:
        logger.error(f"[Twin delay] Error: {e}", exc_info=True)


async def _notify_owner_twin_replied(owner_id: str, friend_id: str, friend_msg: str, twin_reply: str):
    """Notify the owner that their twin auto-replied to a friend."""
    try:
        # Get friend's display name
        with get_db() as db:
            friend = db.execute(
                "SELECT display_name, username FROM users WHERE user_id=?",
                (friend_id,),
            ).fetchone()
        friend_name = (friend["display_name"] or friend["username"]) if friend else "好友"

        notify_text = (
            f"刚才{friend_name}找你，说：「{friend_msg[:50]}」\n"
            f"我替你回了：「{twin_reply[:50]}」\n"
            f"具体事情得你来定哦～"
        )

        # Save notification as a twin self-chat message (with friend_id in metadata)
        import json as _json
        msg_id = gen_id("sm_")
        meta = _json.dumps({"friend_id": friend_id, "friend_name": friend_name})
        with get_db() as db:
            db.execute(
                """
                INSERT INTO social_messages
                (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                 content, msg_type, ai_generated, metadata)
                VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
                """,
                (msg_id, owner_id, owner_id, notify_text, meta),
            )

        # Push via WebSocket
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await manager.send_to(owner_id, {
            "type": "twin_notification",
            "data": {
                "msg_id": msg_id,
                "content": notify_text,
                "friend_id": friend_id,
                "friend_name": friend_name,
                "created_at": now,
            },
        })
    except Exception:
        pass  # Notification is best-effort


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
