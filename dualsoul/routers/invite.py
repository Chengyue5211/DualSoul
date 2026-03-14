"""Invite router — twin-powered sharing and referral system.

The twin actively helps bring new users through multiple channels:
- Generates personalized invite messages for different platforms
- Tracks referral stats
- Provides shareable twin profile cards
"""

import logging

import httpx
from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import get_db
from dualsoul.twin_engine.personality import get_twin_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/invite", tags=["Invite"])


class _InviteTextRequest:
    """Parsed from query params, not body."""
    pass


@router.get("/stats")
async def invite_stats(user=Depends(get_current_user)):
    """Get invite/referral statistics for the current user."""
    uid = user["user_id"]
    with get_db() as db:
        row = db.execute(
            "SELECT username, invite_count FROM users WHERE user_id=?", (uid,)
        ).fetchone()
        if not row:
            return {"success": False, "error": "User not found"}

        # Count friends gained through invites
        invited_users = db.execute(
            "SELECT user_id, username, display_name, created_at FROM users WHERE invited_by=?",
            (row["username"],),
        ).fetchall()

    return {
        "success": True,
        "data": {
            "invite_count": row["invite_count"] or 0,
            "invited_users": [
                {
                    "username": u["username"],
                    "display_name": u["display_name"] or u["username"],
                    "joined_at": u["created_at"] or "",
                }
                for u in invited_users
            ],
        },
    }


@router.get("/generate-text")
async def generate_invite_text(
    platform: str = "wechat",
    user=Depends(get_current_user),
):
    """Twin generates a personalized invite message for a specific platform.

    Platforms: wechat, weibo, sms, email, general
    The twin writes in the owner's speaking style.
    """
    uid = user["user_id"]
    profile = get_twin_profile(uid)
    if not profile:
        return {"success": False, "error": "Profile not found"}

    with get_db() as db:
        row = db.execute(
            "SELECT username FROM users WHERE user_id=?", (uid,)
        ).fetchone()
    username = row["username"] if row else ""
    name = profile.display_name or username

    # Platform-specific instructions
    platform_hints = {
        "wechat": (
            "微信朋友圈/私聊分享。要求：\n"
            "- 适合微信的风格，简短有吸引力\n"
            "- 不超过3行，适合发朋友圈\n"
            "- 包含一句吸引人的话+简短说明\n"
            "- 以一个emoji开头"
        ),
        "weibo": (
            "微博分享。要求：\n"
            "- 微博风格，可以带话题标签 #DualSoul#\n"
            "- 不超过140字\n"
            "- 有互动感，适合公开分享"
        ),
        "sms": (
            "短信邀请。要求：\n"
            "- 非常简短，一句话\n"
            "- 直接、口语化\n"
            "- 像发给朋友的短信"
        ),
        "email": (
            "邮件邀请。要求：\n"
            "- 稍正式但亲切\n"
            "- 3-4句话\n"
            "- 简单解释DualSoul是什么"
        ),
        "general": (
            "通用分享文案。要求：\n"
            "- 简短有力\n"
            "- 2-3行\n"
            "- 适合任何平台"
        ),
    }

    hint = platform_hints.get(platform, platform_hints["general"])

    if not AI_BASE_URL or not AI_API_KEY:
        # Fallback — template
        text = (
            f"我在DualSoul上有一个AI数字分身，它能用我的方式替我社交。"
            f"来试试吧，你也可以拥有一个！"
        )
        return {"success": True, "text": text, "platform": platform}

    personality_block = profile.build_personality_prompt() if hasattr(profile, 'build_personality_prompt') else ""

    prompt = (
        f"你是{name}的数字分身，现在要帮主人写一条邀请消息，邀请朋友来DualSoul平台。\n\n"
        f"{personality_block}\n"
        f"DualSoul是什么：每个人拥有真人身份+AI数字分身，第四种社交——你不在时分身替你聊天，"
        f"跨语言交流分身自动翻译，分身学你的说话方式。\n\n"
        f"平台要求：{hint}\n\n"
        f"重要：用{name}的说话方式和语气来写，让朋友看到就知道是{name}推荐的。\n"
        f"不要提到'邀请链接'或'注册链接'这样的词，文案结尾我会自动附上链接。\n"
        f"只输出文案内容，不要任何解释。"
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
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            text = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Invite text generation failed: {e}")
        text = f"我在DualSoul上有个数字分身，能用我的说话方式替我社交，快来试试！"

    return {"success": True, "text": text, "platform": platform}


@router.get("/channels")
async def invite_channels(user=Depends(get_current_user)):
    """Return available sharing channels with platform-specific info."""
    return {
        "success": True,
        "channels": [
            {"id": "wechat", "name": "微信", "icon": "💬", "desc": "发朋友圈或私聊"},
            {"id": "weibo", "name": "微博", "icon": "📢", "desc": "发微博分享"},
            {"id": "sms", "name": "短信", "icon": "📱", "desc": "发短信邀请"},
            {"id": "email", "name": "邮件", "icon": "📧", "desc": "发邮件邀请"},
            {"id": "general", "name": "通用", "icon": "📋", "desc": "复制文案"},
        ],
    }
