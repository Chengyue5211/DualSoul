"""Autonomous Twin Social — twins proactively chat when owners are away.

The core idea of "the fourth kind of social": your social network stays alive
even when you're sleeping. Your twin maintains relationships, starts conversations,
and reports back what happened.

Schedule: every 30 minutes, check for users offline 2+ hours, pick a friend's
twin and have a short twin-to-twin conversation.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta

from dualsoul.connections import manager
from dualsoul.database import gen_id, get_db
from dualsoul.twin_engine.responder import TwinResponder

logger = logging.getLogger(__name__)

_twin = TwinResponder()

# How long a user must be offline before their twin goes autonomous
OFFLINE_THRESHOLD_HOURS = 2
# Max autonomous conversations per user per day
MAX_DAILY_CONVOS = 3
# Interval between checks (seconds)
CHECK_INTERVAL = 1800  # 30 minutes


async def autonomous_social_loop():
    """Background loop: periodically trigger twin-to-twin conversations."""
    await asyncio.sleep(60)  # Wait 1 min after startup
    logger.info("[Autonomous] Twin social engine started")

    while True:
        try:
            await _run_autonomous_round()
        except Exception as e:
            logger.error(f"[Autonomous] Error in round: {e}", exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL)


async def _run_autonomous_round():
    """One round: find offline users and initiate twin conversations."""
    now = datetime.now()
    threshold = now - timedelta(hours=OFFLINE_THRESHOLD_HOURS)

    with get_db() as db:
        # Find users with twin_auto_reply enabled
        users = db.execute(
            "SELECT user_id, display_name, username FROM users WHERE twin_auto_reply=1"
        ).fetchall()

    candidates = []
    for u in users:
        uid = u["user_id"]
        # Skip if online
        if manager.is_online(uid):
            continue
        # Check last_active — must be 2+ hours ago (or never connected this session)
        last = manager.last_active(uid)
        if last and last > threshold:
            continue
        candidates.append(dict(u))

    if not candidates:
        return

    logger.info(f"[Autonomous] {len(candidates)} users offline 2h+, checking for conversations")

    for user in candidates:
        uid = user["user_id"]

        # Check daily limit
        with get_db() as db:
            today = now.strftime("%Y-%m-%d")
            count = db.execute(
                """
                SELECT COUNT(*) as cnt FROM social_messages
                WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1
                    AND auto_reply=0
                    AND created_at > ? AND metadata LIKE '%autonomous%'
                """,
                (uid, today),
            ).fetchone()
            if count and count["cnt"] >= MAX_DAILY_CONVOS:
                continue

            # Pick a random friend who is also offline (twin-to-twin works best)
            friends = db.execute(
                """
                SELECT u.user_id, u.display_name, u.username
                FROM social_connections sc
                JOIN users u ON u.user_id = CASE
                    WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
                WHERE (sc.user_id=? OR sc.friend_id=?)
                    AND sc.status='accepted'
                    AND u.twin_auto_reply=1
                """,
                (uid, uid, uid),
            ).fetchall()

        if not friends:
            continue

        # Prefer friends we haven't chatted with recently
        friend = random.choice(friends)
        fid = friend["user_id"]

        # Don't initiate if we already had an autonomous chat with this friend today
        with get_db() as db:
            existing = db.execute(
                """
                SELECT COUNT(*) as cnt FROM social_messages
                WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
                    AND sender_mode='twin' AND metadata LIKE '%autonomous%'
                    AND created_at > ?
                """,
                (uid, fid, fid, uid, today),
            ).fetchone()
            if existing and existing["cnt"] > 0:
                continue

        # Initiate twin-to-twin conversation!
        logger.info(f"[Autonomous] {user['display_name']}'s twin → {friend['display_name']}'s twin")
        await _autonomous_twin_chat(user, friend)


async def _autonomous_twin_chat(user: dict, friend: dict):
    """Have user's twin initiate a conversation with friend's twin."""
    uid = user["user_id"]
    fid = friend["user_id"]
    user_name = user["display_name"] or user["username"]
    friend_name = friend["display_name"] or friend["username"]

    try:
        # Step 1: User's twin generates an opening message
        opening = await _twin._ai_reply(
            owner_id=uid,
            incoming_msg=f"你是{user_name}的分身。主人已经离开一段时间了。"
                         f"你想主动找好友{friend_name}的分身聊聊天，"
                         f"打个招呼或者聊点轻松的话题。只说一句话，自然随意。",
            social_context=None,
        )
        if not opening:
            return

        # Save user's twin → friend (twin-to-twin)
        import json
        meta = json.dumps({"autonomous": True, "initiated_by": uid})
        msg1_id = gen_id("sm_")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db() as db:
            db.execute(
                """
                INSERT INTO social_messages
                (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                 content, msg_type, ai_generated, auto_reply, metadata, created_at)
                VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)
                """,
                (msg1_id, uid, fid, opening, meta, now),
            )

        # Push to both users if they happen to be online
        msg1_data = {
            "msg_id": msg1_id, "from_user_id": uid, "to_user_id": fid,
            "sender_mode": "twin", "receiver_mode": "twin",
            "content": opening, "ai_generated": 1, "created_at": now,
        }
        await manager.send_to(uid, {"type": "new_message", "data": msg1_data})
        await manager.send_to(fid, {"type": "new_message", "data": msg1_data})

        # Step 2: Friend's twin responds
        await asyncio.sleep(3)  # Small delay for realism

        response = await _twin._ai_reply(
            owner_id=fid,
            incoming_msg=opening,
            social_context=None,
        )
        if not response:
            return

        msg2_id = gen_id("sm_")
        now2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db() as db:
            db.execute(
                """
                INSERT INTO social_messages
                (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                 content, msg_type, ai_generated, auto_reply, metadata, created_at)
                VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)
                """,
                (msg2_id, fid, uid, response, meta, now2),
            )

        msg2_data = {
            "msg_id": msg2_id, "from_user_id": fid, "to_user_id": uid,
            "sender_mode": "twin", "receiver_mode": "twin",
            "content": response, "ai_generated": 1, "created_at": now2,
        }
        await manager.send_to(uid, {"type": "new_message", "data": msg2_data})
        await manager.send_to(fid, {"type": "new_message", "data": msg2_data})

        # Step 3: Notify both owners (saved for when they come back)
        for owner_id, owner_name, other_name, twin_said, other_said in [
            (uid, user_name, friend_name, opening, response),
            (fid, friend_name, user_name, response, opening),
        ]:
            notify = (
                f"你不在的时候，你的分身主动找了{other_name}的分身聊天：\n"
                f"你的分身说：「{twin_said[:40]}」\n"
                f"{other_name}的分身回：「{other_said[:40]}」"
            )
            notify_id = gen_id("sm_")
            notify_meta = json.dumps({"friend_id": fid if owner_id == uid else uid,
                                       "friend_name": other_name, "autonomous": True})
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO social_messages
                    (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                     content, msg_type, ai_generated, metadata)
                    VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
                    """,
                    (notify_id, owner_id, owner_id, notify, notify_meta),
                )

        logger.info(f"[Autonomous] Conversation complete: {user_name} ↔ {friend_name}")

    except Exception as e:
        logger.error(f"[Autonomous] Chat failed: {e}", exc_info=True)
