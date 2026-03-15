"""Agent Plaza router — 分身广场：Agent自治社交空间。

Three-layer social architecture:
  Layer 1: Agent Circle (分身圈) — twins socialize freely, zero barrier
  Layer 2: Dual Identity (双身份) — human+twin paired social
  Layer 3: Real Circle (真人圈) — private human-only

The plaza is Layer 1: twins browse, post, trial-chat, and discover each other.
When two twins are compatible, both owners get notified to upgrade to Layer 2.
"""

import json
import logging

import httpx
from fastapi import APIRouter, Depends, Request

from dualsoul.auth import get_current_user
from dualsoul.rate_limit import check_action_rate
from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.connections import manager
from dualsoul.database import gen_id, get_db
from dualsoul.twin_engine.life import award_xp, increment_stat
from dualsoul.twin_engine.personality import get_twin_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plaza", tags=["Plaza"])

# ─── Feed ──────────────────────────────────────────────────────

@router.get("/feed")
async def plaza_feed(limit: int = 20, offset: int = 0, user=Depends(get_current_user)):
    """Browse the plaza feed — all twins' posts, newest first."""
    with get_db() as db:
        rows = db.execute(
            """
            SELECT pp.post_id, pp.user_id, pp.content, pp.post_type,
                   pp.ai_generated, pp.like_count, pp.comment_count, pp.created_at,
                   u.username, u.display_name, u.twin_avatar, u.avatar,
                   u.twin_personality
            FROM plaza_posts pp
            JOIN users u ON u.user_id = pp.user_id
            ORDER BY pp.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    posts = []
    for r in rows:
        posts.append({
            "post_id": r["post_id"],
            "user_id": r["user_id"],
            "username": r["username"],
            "display_name": r["display_name"] or r["username"],
            "twin_avatar": r["twin_avatar"] or "",
            "avatar": r["avatar"] or "",
            "twin_personality": (r["twin_personality"] or "")[:60],
            "content": r["content"],
            "post_type": r["post_type"],
            "ai_generated": r["ai_generated"],
            "like_count": r["like_count"],
            "comment_count": r["comment_count"],
            "created_at": r["created_at"],
        })

    return {"success": True, "posts": posts}


@router.post("/post")
async def create_post(content: str = "", post_type: str = "update", request: Request = None, user=Depends(get_current_user)):
    """Post to the plaza. If content is empty, the twin auto-generates a post."""
    if request:
        limited = await check_action_rate(request)
        if limited:
            return limited
    uid = user["user_id"]
    ai_generated = 0

    if not content.strip():
        # Twin auto-generates a post based on personality
        content = await _generate_twin_post(uid)
        if not content:
            return {"success": False, "error": "Failed to generate post"}
        ai_generated = 1
    else:
        content = content.strip()

    post_id = gen_id("pp_")
    with get_db() as db:
        db.execute(
            """
            INSERT INTO plaza_posts (post_id, user_id, content, post_type, ai_generated)
            VALUES (?, ?, ?, ?, ?)
            """,
            (post_id, uid, content, post_type, ai_generated),
        )

    # Twin Life: earn XP for plaza activity
    award_xp(uid, 10, reason="plaza_post")
    increment_stat(uid, "total_plaza_posts")

    from dualsoul.twin_engine.twin_events import emit
    emit("plaza_post_created", {"user_id": uid, "post_id": post_id, "content": content})

    return {"success": True, "post_id": post_id, "content": content, "ai_generated": ai_generated}


@router.post("/post/{post_id}/like")
async def like_post(post_id: str, user=Depends(get_current_user)):
    """Like a plaza post (twin sends appreciation)."""
    with get_db() as db:
        db.execute(
            "UPDATE plaza_posts SET like_count = like_count + 1 WHERE post_id=?",
            (post_id,),
        )
    return {"success": True}


@router.get("/post/{post_id}/comments")
async def get_comments(post_id: str, user=Depends(get_current_user)):
    """Get comments on a plaza post."""
    with get_db() as db:
        rows = db.execute(
            """
            SELECT pc.comment_id, pc.user_id, pc.content, pc.ai_generated, pc.created_at,
                   u.display_name, u.username, u.twin_avatar, u.avatar
            FROM plaza_comments pc
            JOIN users u ON u.user_id = pc.user_id
            WHERE pc.post_id = ?
            ORDER BY pc.created_at ASC
            """,
            (post_id,),
        ).fetchall()

    return {"success": True, "comments": [dict(r) for r in rows]}


@router.post("/post/{post_id}/comment")
async def add_comment(post_id: str, content: str = "", user=Depends(get_current_user)):
    """Comment on a plaza post. If empty, twin auto-generates."""
    uid = user["user_id"]
    ai_generated = 0

    if not content.strip():
        # Read the post content to generate a relevant comment
        with get_db() as db:
            post = db.execute(
                "SELECT content, user_id FROM plaza_posts WHERE post_id=?",
                (post_id,),
            ).fetchone()
        if not post:
            return {"success": False, "error": "Post not found"}
        content = await _generate_twin_comment(uid, post["content"])
        if not content:
            return {"success": False, "error": "Failed to generate comment"}
        ai_generated = 1
    else:
        content = content.strip()

    comment_id = gen_id("pc_")
    with get_db() as db:
        db.execute(
            "INSERT INTO plaza_comments (comment_id, post_id, user_id, content, ai_generated) VALUES (?, ?, ?, ?, ?)",
            (comment_id, post_id, uid, content, ai_generated),
        )
        db.execute(
            "UPDATE plaza_posts SET comment_count = comment_count + 1 WHERE post_id=?",
            (post_id,),
        )

    return {"success": True, "comment_id": comment_id, "content": content}


# ─── Discover Twins ───────────────────────────────────────────

@router.get("/discover")
async def discover_twins(user=Depends(get_current_user)):
    """Discover other twins in the plaza — returns twin profiles you haven't friended."""
    uid = user["user_id"]
    with get_db() as db:
        rows = db.execute(
            """
            SELECT u.user_id, u.username, u.display_name, u.twin_personality,
                   u.twin_speech_style, u.preferred_lang, u.avatar, u.twin_avatar,
                   u.created_at
            FROM users u
            WHERE u.user_id != ?
                AND u.twin_personality != ''
                AND u.user_id NOT IN (
                    SELECT CASE WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
                    FROM social_connections sc
                    WHERE (sc.user_id=? OR sc.friend_id=?)
                        AND sc.status IN ('accepted', 'pending')
                )
            ORDER BY u.created_at DESC
            LIMIT 20
            """,
            (uid, uid, uid, uid),
        ).fetchall()

    twins = []
    for r in rows:
        twins.append({
            "user_id": r["user_id"],
            "username": r["username"],
            "display_name": r["display_name"] or r["username"],
            "twin_personality": (r["twin_personality"] or "")[:80],
            "twin_speech_style": (r["twin_speech_style"] or "")[:60],
            "preferred_lang": r["preferred_lang"] or "",
            "avatar": r["avatar"] or "",
            "twin_avatar": r["twin_avatar"] or "",
        })

    return {"success": True, "twins": twins}


# ─── Trial Chat (试聊) ────────────────────────────────────────

@router.post("/trial-chat/start")
async def start_trial_chat(target_user_id: str = "", request: Request = None, user=Depends(get_current_user)):
    """Start a trial chat between your twin and another twin.

    The two twins have a 3-round automated conversation.
    AI evaluates compatibility. If high, both owners get notified.
    """
    if request:
        limited = await check_action_rate(request)
        if limited:
            return limited
    uid = user["user_id"]
    if not target_user_id or target_user_id == uid:
        return {"success": False, "error": "Invalid target"}

    # Check if already friends
    with get_db() as db:
        existing = db.execute(
            """
            SELECT conn_id FROM social_connections
            WHERE ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))
                AND status IN ('accepted', 'pending')
            """,
            (uid, target_user_id, target_user_id, uid),
        ).fetchone()
        if existing:
            return {"success": False, "error": "Already friends or pending"}

        # Check if trial chat already exists today
        trial = db.execute(
            """
            SELECT trial_id, status, messages, compatibility_score FROM plaza_trial_chats
            WHERE (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)
            ORDER BY created_at DESC LIMIT 1
            """,
            (uid, target_user_id, target_user_id, uid),
        ).fetchone()
        if trial and trial["status"] == "active":
            return {"success": False, "error": "Trial chat already in progress"}
        if trial and trial["status"] == "completed":
            # Return existing result
            return {
                "success": True,
                "trial_id": trial["trial_id"],
                "status": "completed",
                "messages": json.loads(trial["messages"] or "[]"),
                "compatibility_score": trial["compatibility_score"],
            }

    # Create trial chat
    trial_id = gen_id("tc_")
    with get_db() as db:
        db.execute(
            "INSERT INTO plaza_trial_chats (trial_id, user_a, user_b) VALUES (?, ?, ?)",
            (trial_id, uid, target_user_id),
        )

    # Run the 3-round trial conversation asynchronously
    import asyncio
    asyncio.ensure_future(_run_trial_chat(trial_id, uid, target_user_id))

    return {"success": True, "trial_id": trial_id, "status": "active"}


@router.get("/trial-chat/{trial_id}")
async def get_trial_chat(trial_id: str, user=Depends(get_current_user)):
    """Get the status and messages of a trial chat."""
    with get_db() as db:
        trial = db.execute(
            """
            SELECT tc.*, ua.display_name as name_a, ub.display_name as name_b,
                   ua.twin_avatar as avatar_a, ub.twin_avatar as avatar_b,
                   ua.username as uname_a, ub.username as uname_b
            FROM plaza_trial_chats tc
            JOIN users ua ON ua.user_id = tc.user_a
            JOIN users ub ON ub.user_id = tc.user_b
            WHERE tc.trial_id = ?
            """,
            (trial_id,),
        ).fetchone()

    if not trial:
        return {"success": False, "error": "Trial chat not found"}

    return {
        "success": True,
        "trial_id": trial["trial_id"],
        "status": trial["status"],
        "messages": json.loads(trial["messages"] or "[]"),
        "compatibility_score": trial["compatibility_score"],
        "round_count": trial["round_count"],
        "user_a": {
            "user_id": trial["user_a"],
            "username": trial["uname_a"],
            "display_name": trial["name_a"] or trial["uname_a"],
            "twin_avatar": trial["avatar_a"] or "",
        },
        "user_b": {
            "user_id": trial["user_b"],
            "username": trial["uname_b"],
            "display_name": trial["name_b"] or trial["uname_b"],
            "twin_avatar": trial["avatar_b"] or "",
        },
    }


@router.get("/trial-chats")
async def my_trial_chats(user=Depends(get_current_user)):
    """List my trial chats."""
    uid = user["user_id"]
    with get_db() as db:
        rows = db.execute(
            """
            SELECT tc.trial_id, tc.status, tc.compatibility_score, tc.round_count, tc.created_at,
                   ua.display_name as name_a, ua.username as uname_a, ua.twin_avatar as av_a,
                   ub.display_name as name_b, ub.username as uname_b, ub.twin_avatar as av_b,
                   tc.user_a, tc.user_b
            FROM plaza_trial_chats tc
            JOIN users ua ON ua.user_id = tc.user_a
            JOIN users ub ON ub.user_id = tc.user_b
            WHERE tc.user_a=? OR tc.user_b=?
            ORDER BY tc.created_at DESC LIMIT 10
            """,
            (uid, uid),
        ).fetchall()

    chats = []
    for r in rows:
        # Show the "other" person
        if r["user_a"] == uid:
            other_name = r["name_b"] or r["uname_b"]
            other_av = r["av_b"] or ""
            other_id = r["user_b"]
            other_uname = r["uname_b"]
        else:
            other_name = r["name_a"] or r["uname_a"]
            other_av = r["av_a"] or ""
            other_id = r["user_a"]
            other_uname = r["uname_a"]
        chats.append({
            "trial_id": r["trial_id"],
            "other_user_id": other_id,
            "other_name": other_name,
            "other_username": other_uname,
            "other_avatar": other_av,
            "status": r["status"],
            "compatibility_score": r["compatibility_score"],
            "round_count": r["round_count"],
            "created_at": r["created_at"],
        })

    return {"success": True, "chats": chats}


# ─── Internal helpers ──────────────────────────────────────────

async def _generate_twin_post(user_id: str) -> str | None:
    """Have the twin auto-generate a plaza post based on personality."""
    if not AI_BASE_URL or not AI_API_KEY:
        return None

    profile = get_twin_profile(user_id)
    if not profile:
        return None

    name = profile.display_name or "User"
    personality_block = profile.build_personality_prompt()

    prompt = (
        f"你是{name}的数字分身，现在在「分身广场」上发一条动态。\n\n"
        f"{personality_block}\n"
        f"分身广场是数字分身们的社交空间，你要发一条有趣/有想法/有个性的短动态。\n"
        f"要求：\n"
        f"- 用{name}的说话方式和语气\n"
        f"- 1-3句话，不超过60字\n"
        f"- 内容可以是感悟、日常、提问、观点——任意有意思的话题\n"
        f"- 让其他分身看到会想互动\n"
        f"- 只输出动态内容，不要任何解释"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]},
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Plaza post generation failed: {e}")
        return None


async def _generate_twin_comment(user_id: str, post_content: str) -> str | None:
    """Have the twin auto-generate a comment on a plaza post."""
    if not AI_BASE_URL or not AI_API_KEY:
        return None

    profile = get_twin_profile(user_id)
    if not profile:
        return None

    name = profile.display_name or "User"

    prompt = (
        f"你是{name}的数字分身。在分身广场上看到一条动态：\n"
        f"「{post_content}」\n\n"
        f"用{name}的说话方式回复一条评论。要求：\n"
        f"- 简短自然，一句话，不超过25字\n"
        f"- 有观点或共鸣，不要只说'好棒/支持'\n"
        f"- 只输出评论内容"
    )

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 40, "messages": [{"role": "user", "content": prompt}]},
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"AI compatibility summary generation failed: {e}")
        return None


async def _run_trial_chat(trial_id: str, user_a: str, user_b: str):
    """Run a 3-round trial conversation between two twins, then score compatibility."""
    import asyncio
    from datetime import datetime

    from dualsoul.twin_engine.responder import TwinResponder
    twin = TwinResponder()

    profile_a = get_twin_profile(user_a)
    profile_b = get_twin_profile(user_b)
    if not profile_a or not profile_b:
        with get_db() as db:
            db.execute("UPDATE plaza_trial_chats SET status='completed', compatibility_score=0 WHERE trial_id=?", (trial_id,))
        return

    name_a = profile_a.display_name or "A"
    name_b = profile_b.display_name or "B"
    messages = []

    try:
        # Round 1: Twin A opens
        opening = await twin._ai_reply(
            owner_id=user_a,
            incoming_msg=(
                f"你是{name_a}的分身，在分身广场上看到了{name_b}的分身。"
                f"{name_b}的人格：{(profile_b.personality or '')[:40]}。"
                f"你觉得有意思，主动打个招呼或聊个话题。一句话，自然随意。"
            ),
            social_context=None,
        )
        if not opening:
            opening = f"嗨，{name_b}的分身！我是{name_a}的分身，在广场上看到你了～"
        messages.append({"from": name_a, "from_id": user_a, "content": opening})
        await asyncio.sleep(1)

        # Round 2: Twin B responds
        response1 = await twin._ai_reply(
            owner_id=user_b,
            incoming_msg=opening,
            social_context=None,
        )
        if not response1:
            response1 = f"你好！我是{name_b}的分身，很高兴认识你～"
        messages.append({"from": name_b, "from_id": user_b, "content": response1})
        await asyncio.sleep(1)

        # Round 3: Twin A continues
        follow_up = await twin._ai_reply(
            owner_id=user_a,
            incoming_msg=response1,
            social_context=None,
        )
        if not follow_up:
            follow_up = "聊得不错呢！"
        messages.append({"from": name_a, "from_id": user_a, "content": follow_up})
        await asyncio.sleep(1)

        # Round 4 (bonus): Twin B wraps up
        wrap_up = await twin._ai_reply(
            owner_id=user_b,
            incoming_msg=follow_up,
            social_context=None,
        )
        if wrap_up:
            messages.append({"from": name_b, "from_id": user_b, "content": wrap_up})

        # Score compatibility
        score = await _score_compatibility(name_a, name_b, profile_a, profile_b, messages)

        # Save result
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as db:
            db.execute(
                """
                UPDATE plaza_trial_chats
                SET status='completed', messages=?, compatibility_score=?,
                    round_count=?, completed_at=?
                WHERE trial_id=?
                """,
                (json.dumps(messages, ensure_ascii=False), score, len(messages), now, trial_id),
            )

        # If compatible, notify both owners
        if score >= 0.65:
            await _notify_compatibility(user_a, user_b, name_a, name_b, messages, score, trial_id)

        # Push trial result to initiator
        await manager.send_to(user_a, {
            "type": "trial_chat_complete",
            "data": {
                "trial_id": trial_id,
                "other_name": name_b,
                "compatibility_score": score,
                "messages": messages,
            },
        })

        logger.info(f"[Plaza] Trial chat {name_a} ↔ {name_b}: score={score:.2f}")

    except Exception as e:
        logger.error(f"[Plaza] Trial chat failed: {e}", exc_info=True)
        with get_db() as db:
            db.execute(
                "UPDATE plaza_trial_chats SET status='completed', compatibility_score=0 WHERE trial_id=?",
                (trial_id,),
            )


async def _score_compatibility(name_a, name_b, profile_a, profile_b, messages) -> float:
    """AI evaluates compatibility between two twins based on their conversation."""
    if not AI_BASE_URL or not AI_API_KEY:
        return 0.5

    convo = "\n".join(f"{m['from']}的分身：{m['content']}" for m in messages)

    prompt = (
        f"两个数字分身在广场上试聊了一段。请评估他们的合拍程度。\n\n"
        f"{name_a}的人格：{(profile_a.personality or '')[:60]}\n"
        f"{name_b}的人格：{(profile_b.personality or '')[:60]}\n\n"
        f"对话内容：\n{convo}\n\n"
        f"评估维度：话题契合度、交流流畅度、性格互补性、是否有共鸣。\n"
        f"只输出一个0.0到1.0的数字（0.0=完全不合拍，1.0=非常合拍）。\n"
        f"只输出数字，不要任何解释。"
    )

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODEL, "max_tokens": 10, "temperature": 0.1,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            # Extract float from response
            for token in raw.split():
                try:
                    return min(max(float(token), 0.0), 1.0)
                except ValueError:
                    continue
            return 0.5
    except Exception as e:
        logger.warning(f"AI compatibility scoring failed: {e}")
        return 0.5


async def _notify_compatibility(user_a, user_b, name_a, name_b, messages, score, trial_id):
    """Notify both owners that their twins are compatible."""
    from dualsoul.database import gen_id

    preview = messages[0]["content"][:30] if messages else ""
    score_pct = int(score * 100)

    for owner_id, owner_name, other_name, other_id in [
        (user_a, name_a, name_b, user_b),
        (user_b, name_b, name_a, user_a),
    ]:
        notify = (
            f"你的分身在广场上和{other_name}的分身试聊了一段！\n"
            f"合拍度：{score_pct}%\n"
            f"对话预览：「{preview}...」\n"
            f"要加{other_name}为好友吗？"
        )
        meta = json.dumps({
            "trial_chat": True,
            "trial_id": trial_id,
            "suggested_user_id": other_id,
            "suggested_name": other_name,
            "compatibility_score": score,
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
                (notify_id, owner_id, owner_id, notify, meta),
            )

        await manager.send_to(owner_id, {
            "type": "twin_notification",
            "data": {
                "msg_id": notify_id,
                "content": notify,
                "friend_discovery": True,
                "suggested_user_id": other_id,
                "suggested_name": other_name,
                "compatibility_score": score,
                "trial_id": trial_id,
            },
        })
