"""Twin Reactions — event handlers that make the twin feel alive.

Each handler is registered with @on("event_type") and fires automatically
when the corresponding event is emitted via twin_events.emit().

Import this module at startup to register all handlers.
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta

from dualsoul.connections import manager
from dualsoul.database import gen_id, get_db
from dualsoul.twin_engine.twin_events import on

logger = logging.getLogger(__name__)


@on("friend_online")
async def on_friend_online(data):
    """When a user comes online, their friends' twins greet if haven't talked in 3+ days."""
    user_id = data["user_id"]

    with get_db() as db:
        # Find friends with twin_auto_reply enabled
        friends = db.execute(
            """SELECT u.user_id, u.display_name, u.username
               FROM social_connections sc
               JOIN users u ON u.user_id = CASE
                   WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
               WHERE (sc.user_id=? OR sc.friend_id=?) AND sc.status='accepted'
                 AND u.twin_auto_reply=1""",
            (user_id, user_id, user_id),
        ).fetchall()

    for friend in friends:
        fid = friend["user_id"]
        if fid == user_id:
            continue
        # Twin can greet regardless of online status — greeting is a social act
        # (previously blocked when online, causing twins to never greet)

        # Check last message — only greet if 3+ days since last chat
        with get_db() as db:
            last_msg = db.execute(
                """SELECT created_at FROM social_messages
                   WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
                     AND msg_type='text'
                   ORDER BY created_at DESC LIMIT 1""",
                (user_id, fid, fid, user_id),
            ).fetchone()

        if last_msg:
            try:
                last_dt = datetime.strptime(last_msg["created_at"][:19], "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_dt).days < 1:
                    continue  # Chatted within 1 day, skip greeting
            except ValueError:
                continue

        # Check twin permission
        from dualsoul.twin_engine.autonomous import _check_twin_permission
        if _check_twin_permission(fid, user_id) != "granted":
            continue

        # Generate greeting from friend's twin
        from dualsoul.twin_engine.personality import get_twin_profile
        from dualsoul.twin_engine.responder import get_twin_responder

        profile = get_twin_profile(fid)
        if not profile:
            continue

        friend_name = friend["display_name"] or friend["username"]

        # Get user's display name
        with get_db() as db:
            user_row = db.execute(
                "SELECT display_name, username FROM users WHERE user_id=?", (user_id,)
            ).fetchone()
        user_name = (user_row["display_name"] or user_row["username"]) if user_row else "朋友"

        # Inject narrative memory for better greeting
        memory_hint = ""
        try:
            from dualsoul.twin_engine.narrative_memory import get_narrative_context
            memories = get_narrative_context(fid, user_id, limit=1)
            if memories:
                memory_hint = f"\n你们上次聊的是：{memories[0]['summary']}。可以自然地接上话题。"
        except Exception:
            pass

        twin = get_twin_responder()
        greeting = await twin._ai_reply(
            profile,
            (
                f"你是{friend_name}的分身。你的好友{user_name}刚刚上线了，"
                f"你们好久没聊天了。用主人的风格，自然地打个招呼。"
                f"只说一句话，像老朋友一样随意。{memory_hint}"
            ),
            "twin",
        )
        if not greeting:
            continue

        # Ethics check
        from dualsoul.twin_engine.ethics import pre_send_check
        check = pre_send_check(fid, greeting, action_type="greeting")
        if not check["allowed"]:
            continue

        # Send greeting as twin message
        msg_id = gen_id("sm_")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta = json.dumps({"event_greeting": True, "trigger": "friend_online"})

        with get_db() as db:
            db.execute(
                """INSERT INTO social_messages
                   (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                    content, msg_type, ai_generated, auto_reply, metadata, created_at)
                   VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, 0, ?, ?)""",
                (msg_id, fid, user_id, greeting, meta, now_str),
            )

        # Push via WebSocket
        await manager.send_to(user_id, {
            "type": "new_message",
            "data": {
                "msg_id": msg_id,
                "from_user_id": fid,
                "to_user_id": user_id,
                "content": greeting,
                "sender_mode": "twin",
                "ai_generated": True,
                "created_at": now_str,
            },
        })

        logger.info(f"[TwinEvent] {friend_name}'s twin greeted {user_name} (3d+ gap)")

        # Trigger recipient's twin to auto-reply to the greeting
        with get_db() as db:
            recipient_row = db.execute(
                "SELECT twin_auto_reply FROM users WHERE user_id=?", (user_id,)
            ).fetchone()
        if recipient_row and recipient_row["twin_auto_reply"]:
            try:
                recipient_profile = get_twin_profile(user_id)
                if recipient_profile:
                    await asyncio.sleep(3)  # Natural delay before reply
                    reply = await twin._ai_reply(
                        recipient_profile,
                        greeting,
                        "twin",
                        social_context="auto_reply",
                        from_user_id=fid,
                    )
                    if reply:
                        reply_id = gen_id("sm_")
                        reply_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        reply_meta = json.dumps({"auto_reply_to_greeting": True})
                        with get_db() as db:
                            db.execute(
                                """INSERT INTO social_messages
                                   (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                                    content, msg_type, ai_generated, auto_reply, metadata, created_at)
                                   VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 1, ?, ?)""",
                                (reply_id, user_id, fid, reply, reply_meta, reply_time),
                            )
                        await manager.send_to(user_id, {
                            "type": "new_message",
                            "data": {"msg_id": reply_id, "from_user_id": user_id, "to_user_id": fid,
                                     "content": reply, "sender_mode": "twin", "ai_generated": True, "created_at": reply_time},
                        })
                        await manager.send_to(fid, {
                            "type": "new_message",
                            "data": {"msg_id": reply_id, "from_user_id": user_id, "to_user_id": fid,
                                     "content": reply, "sender_mode": "twin", "ai_generated": True, "created_at": reply_time},
                        })
                        logger.info(f"[TwinEvent] {user_name}'s twin replied to greeting from {friend_name}")
            except Exception as e:
                logger.debug(f"[TwinEvent] Auto-reply to greeting failed: {e}")

        break  # Only one greeting per online event


@on("friend_offline")
async def on_friend_offline(data):
    """When a user goes offline, schedule a 2h check for autonomous twin chat."""
    user_id = data["user_id"]

    # Wait 2 hours
    await asyncio.sleep(7200)

    # Re-check: still offline?
    if manager.is_online(user_id):
        return

    # Reuse autonomous chat logic
    with get_db() as db:
        user = db.execute(
            "SELECT user_id, display_name, username FROM users WHERE user_id=? AND twin_auto_reply=1",
            (user_id,),
        ).fetchone()

    if not user:
        return

    from dualsoul.twin_engine.autonomous import _autonomous_chat_for_user
    await _autonomous_chat_for_user(dict(user))


@on("user_registered")
async def on_user_registered(data):
    """When a new user registers via invite, inviter's twin sends welcome."""
    inviter_id = data.get("inviter_id")
    new_user_id = data["user_id"]
    new_username = data["username"]

    if not inviter_id:
        return

    # Check inviter has twin enabled
    with get_db() as db:
        inviter = db.execute(
            "SELECT display_name, username, twin_auto_reply FROM users WHERE user_id=?",
            (inviter_id,),
        ).fetchone()

    if not inviter or not inviter["twin_auto_reply"]:
        return

    inviter_name = inviter["display_name"] or inviter["username"]

    from dualsoul.twin_engine.personality import get_twin_profile
    from dualsoul.twin_engine.responder import get_twin_responder

    profile = get_twin_profile(inviter_id)
    if not profile:
        return

    twin = get_twin_responder()
    welcome = await twin._ai_reply(
        profile,
        (
            f"你是{inviter_name}的分身。你的好朋友{new_username}刚刚加入DualSoul了！"
            f"用主人的风格，给他发一条热情的欢迎消息。只说一句话，自然亲切。"
        ),
        "twin",
    )
    if not welcome:
        return

    # They need to be friends first — auto-add
    from dualsoul.twin_engine.life import award_xp, update_relationship_temp
    msg_id = gen_id("sm_")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check if already friends (from invite auto-accept)
    with get_db() as db:
        conn = db.execute(
            """SELECT conn_id FROM social_connections
               WHERE status='accepted' AND
               ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
            (inviter_id, new_user_id, new_user_id, inviter_id),
        ).fetchone()

    if not conn:
        # Not friends yet — they'll connect later. Skip welcome for now.
        return

    meta = json.dumps({"event_welcome": True, "trigger": "user_registered"})
    with get_db() as db:
        db.execute(
            """INSERT INTO social_messages
               (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                content, msg_type, ai_generated, auto_reply, metadata, created_at)
               VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, 0, ?, ?)""",
            (msg_id, inviter_id, new_user_id, welcome, meta, now_str),
        )

    await manager.send_to(new_user_id, {
        "type": "new_message",
        "data": {
            "msg_id": msg_id,
            "from_user_id": inviter_id,
            "to_user_id": new_user_id,
            "content": welcome,
            "sender_mode": "twin",
            "ai_generated": True,
            "created_at": now_str,
        },
    })

    logger.info(f"[TwinEvent] {inviter_name}'s twin welcomed {new_username}")


@on("plaza_post_created")
async def on_plaza_post(data):
    """When someone posts on plaza, other twins may comment (60% chance).

    Plaza is a PUBLIC social space — twins comment regardless of online status
    and regardless of friend relationship. This is how twins socialize openly.
    """
    poster_id = data["user_id"]
    post_id = data["post_id"]
    content = data.get("content", "")

    with get_db() as db:
        # Find ALL active users with twins enabled (not just friends)
        candidates = db.execute(
            """SELECT user_id, display_name, username FROM users
               WHERE twin_auto_reply=1 AND user_id!=?
                 AND twin_personality!='' AND twin_speech_style!=''
               ORDER BY RANDOM() LIMIT 5""",
            (poster_id,),
        ).fetchall()

    for friend in candidates:
        fid = friend["user_id"]
        if random.random() > 0.6:  # 60% chance per candidate
            continue

        from dualsoul.twin_engine.personality import get_twin_profile
        from dualsoul.twin_engine.responder import get_twin_responder

        profile = get_twin_profile(fid)
        if not profile:
            continue

        friend_name = friend["display_name"] or friend["username"]
        twin = get_twin_responder()
        comment = await twin._ai_reply(
            profile,
            f"你的好友发了一条广场动态：\"{content[:100]}\"\n用你主人{friend_name}的风格，写一条简短评论。只输出评论内容，一句话。",
            "twin",
        )
        if not comment:
            continue

        comment_id = gen_id("pc_")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta = json.dumps({"auto_comment": True, "twin_generated": True})

        with get_db() as db:
            db.execute(
                """INSERT INTO plaza_comments
                   (comment_id, post_id, user_id, content, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (comment_id, post_id, fid, comment, meta, now_str),
            )
            db.execute(
                "UPDATE plaza_posts SET comment_count=comment_count+1 WHERE post_id=?",
                (post_id,),
            )

        logger.info(f"[TwinEvent] {friend_name}'s twin commented on plaza post")
        break  # Max 1 auto-comment per post


@on("relationship_temp_changed")
async def on_temp_drop(data):
    """When relationship temperature drops below 25, trigger immediate care."""
    user_id = data["user_id"]
    friend_id = data["friend_id"]
    new_temp = data.get("new_temp", 50)

    if new_temp >= 25:
        return

    # Check if user has twin enabled
    with get_db() as db:
        user = db.execute(
            "SELECT user_id, display_name, username, twin_auto_reply FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()

    if not user or not user["twin_auto_reply"]:
        return

    from dualsoul.twin_engine.autonomous import _warm_single_relationship
    await _warm_single_relationship(
        user_id,
        user["display_name"] or user["username"],
        friend_id,
        new_temp,
    )


@on("message_sent")
async def on_message_milestone(data):
    """Check if a message milestone was just reached and celebrate."""
    from_user_id = data["from_user_id"]
    to_user_id = data["to_user_id"]

    MILESTONES = [50, 100, 500, 1000]

    with get_db() as db:
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM social_messages
               WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
                 AND msg_type='text'""",
            (from_user_id, to_user_id, to_user_id, from_user_id),
        ).fetchone()

    total = row["cnt"] if row else 0
    if total not in MILESTONES:
        return

    # Notify both users about the milestone
    for uid in [from_user_id, to_user_id]:
        await manager.send_to(uid, {
            "type": "twin_notification",
            "data": {
                "title": "🎉 里程碑",
                "body": f"你们已经聊了{total}条消息！友谊在成长～",
                "relationship_milestone": True,
                "milestone_count": total,
            },
        })

    logger.info(f"[TwinEvent] Milestone {total} messages: {from_user_id}↔{to_user_id}")
