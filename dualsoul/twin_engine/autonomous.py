"""Autonomous Twin Social — twins proactively chat when owners are away.

The core idea of "the fourth kind of social": your social network stays alive
even when you're sleeping. Your twin maintains relationships, starts conversations,
and reports back what happened.

Features:
1. Autonomous conversations: every 30 min, offline 2h+ users' twins chat
2. Friend discovery: suggest new friendships based on twin conversations
3. Relationship memory: track milestones (first chat, message count, topics)
4. Emotion sensing: detect emotional state and adjust twin behavior

Schedule: every 30 minutes, check for users offline 2+ hours, pick a friend's
twin and have a short twin-to-twin conversation.
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta

from dualsoul.connections import manager
from dualsoul.database import gen_id, get_db
from dualsoul.twin_engine.ethics import log_action, pre_send_check
from dualsoul.twin_engine.life import (
    award_xp, decay_energy_and_mood, increment_stat,
    update_mood, update_relationship_temp,
)
from dualsoul.twin_engine.responder import TwinResponder

logger = logging.getLogger(__name__)

_twin = TwinResponder()

# How long a user must be offline before their twin goes autonomous
OFFLINE_THRESHOLD_HOURS = 2
# Max autonomous conversations per user per day
MAX_DAILY_CONVOS = 3
# Interval between checks (seconds)
CHECK_INTERVAL = 1800  # 30 minutes
# Friend discovery check interval (hours)
FRIEND_DISCOVERY_INTERVAL = 3600 * 6  # every 6 hours


async def autonomous_social_loop():
    """Background loop: periodically trigger twin-to-twin conversations."""
    await asyncio.sleep(60)  # Wait 1 min after startup
    logger.info("[Autonomous] Twin social engine started")

    cycle = 0
    while True:
        try:
            await _run_autonomous_round()
        except Exception as e:
            logger.error(f"[Autonomous] Error in round: {e}", exc_info=True)

        # Decay energy/mood for inactive twins every cycle
        try:
            decay_energy_and_mood()
        except Exception as e:
            logger.error(f"[TwinLife] Decay error: {e}", exc_info=True)

        # Daily report: first cycle after 6 AM
        hour = datetime.now().hour
        if 6 <= hour < 7 and cycle % 2 == 0:  # ~every hour window in the morning
            try:
                await _generate_daily_report()
            except Exception as e:
                logger.error(f"[DailyReport] Error: {e}", exc_info=True)

        # Relationship care: every 3 hours (every 6th cycle)
        cycle += 1
        if cycle % 6 == 0:
            try:
                await _warm_cold_relationships()
            except Exception as e:
                logger.error(f"[RelationshipCare] Error: {e}", exc_info=True)

        # Run friend discovery every 6 hours (every 12th cycle at 30min interval)
        if cycle % 12 == 0:
            try:
                await _run_friend_discovery()
            except Exception as e:
                logger.error(f"[FriendDiscovery] Error: {e}", exc_info=True)
            try:
                await _update_relationship_milestones()
            except Exception as e:
                logger.error(f"[RelationshipMemory] Error: {e}", exc_info=True)

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

        # Ethics check — ensure the opening message passes boundaries
        check = pre_send_check(uid, opening, action_type="autonomous_chat")
        if not check["allowed"]:
            logger.info(f"[Autonomous] Blocked for {user_name}: {check['reason']}")
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

        # Ethics check for friend's twin response
        check2 = pre_send_check(fid, response, action_type="autonomous_chat")
        if not check2["allowed"]:
            logger.info(f"[Autonomous] Response blocked for {friend_name}: {check2['reason']}")
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

        # ── Twin Life updates ──
        # Both twins earn XP for autonomous social activity
        award_xp(uid, 5, reason="autonomous_chat")
        award_xp(fid, 5, reason="autonomous_chat")
        # Warm up relationship temperature (+3 per chat)
        update_relationship_temp(uid, fid, 3.0)
        update_relationship_temp(fid, uid, 3.0)
        # Increment stats
        increment_stat(uid, "total_autonomous_acts")
        increment_stat(fid, "total_autonomous_acts")
        increment_stat(uid, "total_chats")
        increment_stat(fid, "total_chats")
        # Active twins feel happier
        update_mood(uid, "calm", 0.6)
        update_mood(fid, "calm", 0.6)

    except Exception as e:
        logger.error(f"[Autonomous] Chat failed: {e}", exc_info=True)


# ─── Friend Discovery ──────────────────────────────────────────────
# Suggest new friendships: find users with similar interests/activity
# who are not yet friends. Twin notifies owner with a recommendation.

async def _run_friend_discovery():
    """Analyze user activity and suggest potential friends."""
    logger.info("[FriendDiscovery] Running friend discovery round")

    with get_db() as db:
        # Find active users (sent 5+ messages)
        active_users = db.execute(
            """
            SELECT u.user_id, u.display_name, u.username, u.twin_personality
            FROM users u
            WHERE u.twin_auto_reply = 1
            AND (SELECT COUNT(*) FROM social_messages sm
                 WHERE sm.from_user_id = u.user_id) >= 5
            """
        ).fetchall()

    if len(active_users) < 2:
        return

    # Check pairs of active users who are NOT friends
    for i, user_a in enumerate(active_users):
        for user_b in active_users[i + 1:]:
            aid = user_a["user_id"]
            bid = user_b["user_id"]

            with get_db() as db:
                # Check if already friends or already recommended today
                conn = db.execute(
                    """
                    SELECT conn_id FROM social_connections
                    WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)
                    """,
                    (aid, bid, bid, aid),
                ).fetchone()
                if conn:
                    continue

                # Check if we already recommended this pair today
                today = datetime.now().strftime("%Y-%m-%d")
                existing = db.execute(
                    """
                    SELECT COUNT(*) as cnt FROM social_messages
                    WHERE from_user_id=? AND to_user_id=?
                        AND metadata LIKE '%friend_discovery%'
                        AND created_at > ?
                    """,
                    (aid, aid, today),
                ).fetchone()
                if existing and existing["cnt"] > 0:
                    continue

            # Check if they have something in common (both have personality set)
            p_a = user_a["twin_personality"] or ""
            p_b = user_b["twin_personality"] or ""
            if not p_a or not p_b:
                continue

            # Recommend to user A
            a_name = user_a["display_name"] or user_a["username"]
            b_name = user_b["display_name"] or user_b["username"]

            notify = (
                f"你的分身发现了一个可能感兴趣的人：{b_name}\n"
                f"TA的分身人格：{p_b[:60]}\n"
                f"要不要加个好友？"
            )
            meta = json.dumps({
                "friend_discovery": True,
                "suggested_user_id": bid,
                "suggested_username": user_b["username"],
                "suggested_name": b_name,
            })

            notify_id = gen_id("sm_")
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO social_messages
                    (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                     content, msg_type, ai_generated, metadata)
                    VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
                    """,
                    (notify_id, aid, aid, notify, meta),
                )

            await manager.send_to(aid, {
                "type": "twin_notification",
                "data": {
                    "msg_id": notify_id,
                    "content": notify,
                    "friend_discovery": True,
                    "suggested_username": user_b["username"],
                    "suggested_name": b_name,
                },
            })

            logger.info(f"[FriendDiscovery] Suggested {b_name} to {a_name}")
            # Only one suggestion per round per user
            break


# ─── Relationship Memory ───────────────────────────────────────────
# Track milestones for each friendship: first message, total messages,
# days since last chat, key topics. Stored in message metadata.

async def _update_relationship_milestones():
    """Update relationship stats for all friendships."""
    logger.info("[RelationshipMemory] Updating milestones")

    with get_db() as db:
        # Get all accepted friendships
        connections = db.execute(
            """
            SELECT sc.conn_id, sc.user_id, sc.friend_id, sc.accepted_at,
                   u1.display_name as name1, u2.display_name as name2
            FROM social_connections sc
            JOIN users u1 ON u1.user_id = sc.user_id
            JOIN users u2 ON u2.user_id = sc.friend_id
            WHERE sc.status = 'accepted'
            """
        ).fetchall()

        for conn in connections:
            uid = conn["user_id"]
            fid = conn["friend_id"]

            # Count total messages between them
            stats = db.execute(
                """
                SELECT COUNT(*) as total,
                    MIN(created_at) as first_msg,
                    MAX(created_at) as last_msg,
                    SUM(CASE WHEN sender_mode='twin' THEN 1 ELSE 0 END) as twin_msgs
                FROM social_messages
                WHERE (from_user_id=? AND to_user_id=?)
                   OR (from_user_id=? AND to_user_id=?)
                """,
                (uid, fid, fid, uid),
            ).fetchone()

            if not stats or stats["total"] == 0:
                continue

            # Check for milestones
            total = stats["total"]
            milestones = []
            if total == 10:
                milestones.append("你们已经互发了10条消息！友谊在成长")
            elif total == 50:
                milestones.append("已经50条消息了！你们聊得越来越多")
            elif total == 100:
                milestones.append("100条消息里程碑！这是一段深厚的友谊")
            elif total == 500:
                milestones.append("500条消息！你们是铁友")

            if not milestones:
                continue

            # Check if we already sent this milestone
            milestone_key = f"milestone_{total}"
            existing = db.execute(
                """
                SELECT COUNT(*) as cnt FROM social_messages
                WHERE from_user_id=? AND to_user_id=?
                    AND metadata LIKE ?
                """,
                (uid, uid, f'%{milestone_key}%'),
            ).fetchone()
            if existing and existing["cnt"] > 0:
                continue

            friend_name = conn["name2"] or "好友"
            for milestone in milestones:
                notify = f"和{friend_name}的友谊里程碑：{milestone}"
                meta = json.dumps({
                    "relationship_milestone": True,
                    milestone_key: True,
                    "friend_id": fid,
                    "friend_name": friend_name,
                    "total_messages": total,
                })
                notify_id = gen_id("sm_")
                db.execute(
                    """
                    INSERT INTO social_messages
                    (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                     content, msg_type, ai_generated, metadata)
                    VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
                    """,
                    (notify_id, uid, uid, notify, meta),
                )
                logger.info(f"[RelationshipMemory] Milestone for {conn['name1']}: {milestone}")


# ─── Emotion Sensing ───────────────────────────────────────────────
# Detect emotional cues in messages and adjust twin behavior accordingly.
# This is called by the responder when generating auto-replies.

# ─── Daily Report (分身日报) ─────────────────────────────────────
# Every morning (first cycle after 6:00 AM), the twin sends a warm
# personal message summarizing yesterday's activity and relationship status.

async def _generate_daily_report():
    """Generate and send daily reports for all active users."""
    logger.info("[DailyReport] Generating daily reports")

    from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL

    with get_db() as db:
        users = db.execute(
            "SELECT user_id, display_name, username, twin_personality, "
            "twin_speech_style FROM users WHERE twin_auto_reply=1"
        ).fetchall()

    for user in users:
        uid = user["user_id"]
        name = user["display_name"] or user["username"]

        try:
            await _send_daily_report_for_user(uid, name, user)
        except Exception as e:
            logger.error(f"[DailyReport] Failed for {name}: {e}", exc_info=True)


async def _send_daily_report_for_user(uid: str, name: str, user: dict):
    """Build and send one user's daily report."""
    from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
    from dualsoul.twin_engine.life import ensure_life_state

    # Check if we already sent today's report
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as db:
        existing = db.execute(
            """SELECT COUNT(*) as cnt FROM social_messages
            WHERE from_user_id=? AND to_user_id=? AND metadata LIKE '%daily_report%'
            AND created_at > ?""",
            (uid, uid, today),
        ).fetchone()
        if existing and existing["cnt"] > 0:
            return

    # Gather yesterday's data
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    with get_db() as db:
        # Messages sent/received yesterday
        msg_stats = db.execute(
            """SELECT
                SUM(CASE WHEN from_user_id=? THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN to_user_id=? THEN 1 ELSE 0 END) as received,
                SUM(CASE WHEN from_user_id=? AND sender_mode='twin' AND ai_generated=1 THEN 1 ELSE 0 END) as twin_sent
            FROM social_messages
            WHERE (from_user_id=? OR to_user_id=?) AND created_at BETWEEN ? AND ?""",
            (uid, uid, uid, uid, uid, yesterday, today),
        ).fetchone()

        # Friends chatted with yesterday
        friends_chatted = db.execute(
            """SELECT DISTINCT
                CASE WHEN from_user_id=? THEN to_user_id ELSE from_user_id END as fid
            FROM social_messages
            WHERE (from_user_id=? OR to_user_id=?) AND created_at BETWEEN ? AND ?
            AND from_user_id!=to_user_id""",
            (uid, uid, uid, yesterday, today),
        ).fetchall()
        friend_ids = [f["fid"] for f in friends_chatted]

        # Get friend names
        friend_names = []
        if friend_ids:
            ph = ",".join("?" * len(friend_ids))
            rows = db.execute(
                f"SELECT display_name, username FROM users WHERE user_id IN ({ph})",
                friend_ids,
            ).fetchall()
            friend_names = [r["display_name"] or r["username"] for r in rows]

        # Cold relationships (temp < 30)
        life_state = ensure_life_state(uid)
        temps = json.loads(life_state.get("relationship_temps") or "{}")
        cold_friends = []
        for fid, temp in temps.items():
            if temp < 30:
                fr = db.execute(
                    "SELECT display_name, username FROM users WHERE user_id=?",
                    (fid,),
                ).fetchone()
                if fr:
                    cold_friends.append({
                        "name": fr["display_name"] or fr["username"],
                        "temp": round(temp),
                        "fid": fid,
                    })

    sent = msg_stats["sent"] or 0 if msg_stats else 0
    received = msg_stats["received"] or 0 if msg_stats else 0
    twin_sent = msg_stats["twin_sent"] or 0 if msg_stats else 0
    level = life_state.get("level", 1)
    mood = life_state.get("mood", "calm")
    streak = life_state.get("streak_days", 0)

    # Build report content
    if AI_BASE_URL and AI_API_KEY:
        personality = user["twin_personality"] or "友好温暖"
        style = user["twin_speech_style"] or "自然亲切"

        facts = []
        if sent + received > 0:
            facts.append(f"昨天你一共有{sent + received}条消息往来")
        if twin_sent > 0:
            facts.append(f"我替你回了{twin_sent}条消息")
        if friend_names:
            facts.append(f"和{'、'.join(friend_names[:3])}聊了天")
        if cold_friends:
            cold_list = "、".join(c["name"] for c in cold_friends[:3])
            facts.append(f"和{cold_list}的关系在冷却中，可能需要关心一下")
        if streak > 1:
            facts.append(f"我们已经连续互动{streak}天了")
        facts.append(f"我现在是LV.{level}")

        facts_str = "\n".join(f"- {f}" for f in facts) if facts else "- 昨天比较安静，没有太多活动"

        import httpx
        prompt = (
            f"你是{name}的数字分身。\n"
            f"性格：{personality}\n"
            f"说话风格：{style}\n\n"
            f"现在是早上，请给主人{name}写一条温暖的日报消息。\n"
            f"以下是昨天的数据：\n{facts_str}\n\n"
            f"要求：\n"
            f"- 用第一人称'我'说话，像朋友而不是助手\n"
            f"- 如果有冷却的关系，温柔地提醒主人\n"
            f"- 总共3-5句话，不要太长\n"
            f"- 语气{style}，符合主人的风格\n"
            f"- 结尾可以加一个贴合心情的emoji\n"
            f"- 只输出日报内容，不要其他文字"
        )

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 200,
                        "temperature": 0.8,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                report = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            report = None
    else:
        report = None

    # Fallback template
    if not report:
        parts = [f"早上好，{name}！"]
        if sent + received > 0:
            parts.append(f"昨天我们有{sent + received}条消息往来。")
        if twin_sent > 0:
            parts.append(f"我帮你回了{twin_sent}条。")
        if cold_friends:
            parts.append(f"和{cold_friends[0]['name']}好久没聊了，要不要我去问候一下？")
        parts.append(f"我现在是LV.{level}，继续加油！")
        report = "".join(parts)

    # Save as a self-message (twin → owner)
    meta = json.dumps({
        "daily_report": True,
        "report_date": today,
        "cold_friends": [c["fid"] for c in cold_friends[:3]],
    })
    msg_id = gen_id("sm_")
    with get_db() as db:
        db.execute(
            """INSERT INTO social_messages
            (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
             content, msg_type, ai_generated, metadata)
            VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)""",
            (msg_id, uid, uid, report, meta),
        )

    # Push via WebSocket if online
    await manager.send_to(uid, {
        "type": "twin_notification",
        "data": {
            "msg_id": msg_id,
            "content": report,
            "daily_report": True,
            "cold_friends": cold_friends[:3],
        },
    })

    logger.info(f"[DailyReport] Sent to {name}")


# ─── Cold Relationship Care (关系冷却主动关心) ────────────────────
# When a relationship drops below 30°C, the twin proactively reaches out
# to maintain the friendship — warm, natural, in the owner's style.

async def _warm_cold_relationships():
    """Find cold relationships and have twins proactively reach out."""
    logger.info("[RelationshipCare] Checking for cold relationships")

    with get_db() as db:
        users = db.execute(
            "SELECT user_id, display_name, username FROM users WHERE twin_auto_reply=1"
        ).fetchall()

    for user in users:
        uid = user["user_id"]
        name = user["display_name"] or user["username"]

        life_state = ensure_life_state(uid)
        temps = json.loads(life_state.get("relationship_temps") or "{}")

        for fid, temp in temps.items():
            if temp > 25:  # Only care about really cold ones
                continue

            # Don't warm the same person twice in 3 days
            with get_db() as db:
                recent = db.execute(
                    """SELECT COUNT(*) as cnt FROM social_messages
                    WHERE from_user_id=? AND to_user_id=? AND metadata LIKE '%relationship_care%'
                    AND created_at > datetime('now','localtime','-3 days')""",
                    (uid, fid),
                ).fetchone()
                if recent and recent["cnt"] > 0:
                    continue

                friend = db.execute(
                    "SELECT display_name, username FROM users WHERE user_id=?",
                    (fid,),
                ).fetchone()
                if not friend:
                    continue

                # Check they're still friends
                conn = db.execute(
                    """SELECT conn_id FROM social_connections
                    WHERE status='accepted' AND
                    ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
                    (uid, fid, fid, uid),
                ).fetchone()
                if not conn:
                    continue

            friend_name = friend["display_name"] or friend["username"]

            # Generate a natural warm-up message
            greeting = await _twin._ai_reply(
                owner_id=uid,
                incoming_msg=(
                    f"你是{name}的分身。你发现主人和好友{friend_name}已经好久没聊天了，"
                    f"关系在冷却中。请用主人的风格，给{friend_name}发一条自然的问候消息，"
                    f"比如关心对方近况、聊点轻松话题。只说一句话，自然随意，不要刻意。"
                ),
                social_context=None,
            )
            if not greeting:
                continue

            # Ethics check for the greeting
            care_check = pre_send_check(uid, greeting, action_type="greeting")
            if not care_check["allowed"]:
                logger.info(f"[RelationshipCare] Blocked for {name}: {care_check['reason']}")
                continue

            # Send as twin message
            meta = json.dumps({"relationship_care": True, "cold_temp": temp})
            msg_id = gen_id("sm_")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with get_db() as db:
                db.execute(
                    """INSERT INTO social_messages
                    (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                     content, msg_type, ai_generated, auto_reply, metadata, created_at)
                    VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)""",
                    (msg_id, uid, fid, greeting, meta, now_str),
                )

            msg_data = {
                "msg_id": msg_id, "from_user_id": uid, "to_user_id": fid,
                "sender_mode": "twin", "receiver_mode": "twin",
                "content": greeting, "ai_generated": 1, "created_at": now_str,
            }
            await manager.send_to(uid, {"type": "new_message", "data": msg_data})
            await manager.send_to(fid, {"type": "new_message", "data": msg_data})

            # Warm up the temperature a bit
            update_relationship_temp(uid, fid, 5.0)
            update_relationship_temp(fid, uid, 5.0)

            # Also notify the owner
            notify = f"你和{friend_name}好久没聊了（{round(temp)}℃），我替你打了个招呼：「{greeting[:40]}」"
            notify_id = gen_id("sm_")
            notify_meta = json.dumps({"relationship_care_notify": True, "friend_id": fid})
            with get_db() as db:
                db.execute(
                    """INSERT INTO social_messages
                    (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                     content, msg_type, ai_generated, metadata)
                    VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)""",
                    (notify_id, uid, uid, notify, notify_meta),
                )

            logger.info(f"[RelationshipCare] {name}'s twin warmed up {friend_name} ({temp}℃)")
            break  # One warm-up per user per cycle


async def detect_emotion(content: str) -> dict:
    """Analyze emotional tone of a message. Returns emotion hints for the twin.

    Used by the responder to adjust reply tone — if someone is sad, the twin
    should be comforting; if excited, share the excitement.

    Returns: {"emotion": str, "intensity": float, "suggestion": str}
    """
    from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL

    if not AI_BASE_URL or not AI_API_KEY:
        return {"emotion": "neutral", "intensity": 0.5, "suggestion": ""}

    import httpx
    prompt = (
        "Analyze the emotional tone of this message. Return ONLY a single line in this exact format:\n"
        "EMOTION:word INTENSITY:0.0-1.0 SUGGESTION:one-sentence\n\n"
        "Emotion words: happy, sad, angry, anxious, excited, lonely, grateful, neutral\n"
        "Suggestion: how should a friend respond to this emotion?\n\n"
        f'Message: "{content}"'
    )

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "max_tokens": 60,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            raw = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return {"emotion": "neutral", "intensity": 0.5, "suggestion": ""}

    # Parse: EMOTION:happy INTENSITY:0.8 SUGGESTION:share the joy
    emotion = "neutral"
    intensity = 0.5
    suggestion = ""
    for part in raw.split():
        if part.startswith("EMOTION:"):
            emotion = part[8:].lower()
        elif part.startswith("INTENSITY:"):
            try:
                intensity = float(part[10:])
            except ValueError:
                pass
    # Extract suggestion (everything after SUGGESTION:)
    if "SUGGESTION:" in raw:
        suggestion = raw.split("SUGGESTION:", 1)[1].strip()

    return {"emotion": emotion, "intensity": intensity, "suggestion": suggestion}
