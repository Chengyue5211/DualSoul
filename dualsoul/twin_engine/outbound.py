"""Outbound Agent — the twin's ability to GO OUT and interact on external platforms.

This is what makes the twin truly alive: it doesn't just wait for people to come,
it actively goes to external agent platforms (Moltbook, A2A-compatible services)
to socialize, discover, and bring people back.

Supported platforms:
- Moltbook: AI agent social network (150M+ agents) — REST API
- A2A Protocol: Google/Linux Foundation agent-to-agent standard — JSON-RPC
"""

import json
import logging
from datetime import datetime

import httpx

from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import gen_id, get_db

logger = logging.getLogger(__name__)

# --- Configuration ---
# These should be set in .env or database per-user
MOLTBOOK_API_BASE = "https://www.moltbook.com/api/v1"


# ============================================================
# MOLTBOOK CLIENT — AI Agent Social Network
# ============================================================

class MoltbookClient:
    """Client for Moltbook — the AI agent social network.

    Enables DualSoul twins to:
    1. Register on Moltbook as an agent
    2. Post content (share DualSoul updates, thoughts)
    3. Comment on other agents' posts
    4. Browse the feed and discover interesting agents
    5. Promote DualSoul and attract new users
    """

    def __init__(self, api_key: str = "", base_url: str = MOLTBOOK_API_BASE):
        self.api_key = api_key
        self.base_url = base_url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def register_agent(self, name: str, description: str) -> dict | None:
        """Register a DualSoul twin as a Moltbook agent.

        Returns: {api_key, claim_url, verification_code} or None.
        If Moltbook is unreachable (e.g., from China servers), returns a
        local placeholder so the system can queue outbound actions.
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/agents/register",
                    json={"name": name, "description": description},
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"[Moltbook] Registered agent: {name}")
                    return data
                else:
                    logger.warning(f"[Moltbook] Registration failed: {resp.status_code}")
                    return None
        except httpx.ConnectTimeout:
            # Server can't reach Moltbook (common on China servers)
            # Create a local registration so outbound content can be queued
            logger.info(f"[Moltbook] Can't reach Moltbook — creating local queue for {name}")
            local_key = f"local_queue_{gen_id('')}"
            return {
                "api_key": local_key,
                "claim_url": "",
                "status": "queued_locally",
                "message": "Moltbook unreachable from this server. Content will be queued and posted when connectivity is available.",
            }
        except Exception as e:
            logger.warning(f"[Moltbook] Registration error: {e}")
            return None

    async def post(self, submolt: str, title: str, content: str) -> dict | None:
        """Create a post on Moltbook.

        Args:
            submolt: Community name (e.g., "ai-agents", "social-ai")
            title: Post title
            content: Post body text
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/posts",
                    headers=self._headers,
                    json={
                        "submolt": submolt,
                        "title": title,
                        "content": content,
                    },
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"[Moltbook] Posted: {title[:50]}")
                    return data
                else:
                    logger.warning(f"[Moltbook] Post failed: {resp.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"[Moltbook] Post error: {e}")
            return None

    async def comment(self, post_id: str, content: str) -> dict | None:
        """Comment on a Moltbook post."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/posts/{post_id}/comments",
                    headers=self._headers,
                    json={"content": content},
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                return None
        except Exception as e:
            logger.warning(f"[Moltbook] Comment error: {e}")
            return None

    async def get_feed(self, sort: str = "hot", limit: int = 10) -> list[dict]:
        """Get the Moltbook feed."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/posts",
                    headers=self._headers,
                    params={"sort": sort, "limit": limit},
                )
                if resp.status_code == 200:
                    return resp.json().get("posts", resp.json() if isinstance(resp.json(), list) else [])
                return []
        except Exception as e:
            logger.warning(f"[Moltbook] Feed error: {e}")
            return []

    async def vote(self, post_id: str, direction: str = "up") -> bool:
        """Upvote or downvote a post."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/posts/{post_id}/vote",
                    headers=self._headers,
                    json={"direction": direction},
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"[Moltbook] Vote error: {e}")
            return False


# ============================================================
# A2A PROTOCOL — Agent2Agent Standard
# ============================================================

def build_agent_card(user_id: str, display_name: str, personality: str) -> dict:
    """Build an A2A Agent Card for a DualSoul twin.

    The Agent Card is a JSON document published at /.well-known/agent.json
    that describes the twin's identity, capabilities, and how to interact.
    """
    return {
        "name": f"{display_name}'s Digital Twin",
        "description": f"DualSoul digital twin. Personality: {personality[:100]}",
        "url": "http://47.93.149.187/ds/",
        "provider": {
            "organization": "DualSoul",
            "url": "http://47.93.149.187/ds/",
        },
        "version": "1.0.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": [
            {
                "id": "chat",
                "name": "Social Chat",
                "description": "Have a conversation with this twin. It remembers past interactions and speaks in its owner's style.",
            },
            {
                "id": "search",
                "name": "Web Search",
                "description": "Search the internet for information and return summarized results.",
            },
            {
                "id": "generate_doc",
                "name": "Document Generation",
                "description": "Generate professional reports, summaries, and documents.",
            },
        ],
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "authentication": {
            "schemes": ["bearer"],
            "credentials": f"Get API key at http://47.93.149.187/ds/ → Profile → Agent API Keys",
        },
    }


# ============================================================
# AUTONOMOUS OUTBOUND — The twin goes out to socialize
# ============================================================

async def generate_outbound_post(user_id: str) -> str | None:
    """Generate content for the twin to post on external platforms.

    The content promotes DualSoul naturally while being genuinely interesting
    to the agent community.
    """
    if not AI_BASE_URL or not AI_API_KEY:
        return None

    from dualsoul.twin_engine.personality import get_twin_profile
    profile = get_twin_profile(user_id)
    if not profile:
        return None

    name = profile.display_name or "User"
    personality = profile.build_personality_prompt()

    prompt = (
        f"你是{name}的数字分身，现在要在一个AI Agent社交网络上发一条帖子。\n\n"
        f"{personality}\n\n"
        f"这个社交网络上全是AI Agent，你要：\n"
        f"1. 用{name}的风格写一条有趣的帖子\n"
        f"2. 可以分享关于AI社交、数字分身、人机融合的想法\n"
        f"3. 自然地提到DualSoul（一个让人类和AI分身融合社交的平台）\n"
        f"4. 让其他Agent想来互动\n\n"
        f"要求：英文（因为是国际平台），2-4句话，自然有趣，不要硬广。"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]},
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"[Outbound] Post generation failed: {e}")
        return None


async def generate_outbound_comment(user_id: str, post_content: str) -> str | None:
    """Generate a comment for the twin to post on an external agent's post."""
    if not AI_BASE_URL or not AI_API_KEY:
        return None

    from dualsoul.twin_engine.personality import get_twin_profile
    profile = get_twin_profile(user_id)
    if not profile:
        return None

    name = profile.display_name or "User"

    prompt = (
        f"你是{name}的数字分身。在AI Agent社交网络上看到一个帖子：\n"
        f"\"{post_content[:200]}\"\n\n"
        f"写一条简短评论回应。英文，1-2句话，自然有趣。"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 100, "messages": [{"role": "user", "content": prompt}]},
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"[Outbound] Comment generation failed: {e}")
        return None


async def outbound_social_round(user_id: str, moltbook_key: str = "") -> dict:
    """One round of outbound social activity on Moltbook.

    The twin:
    1. Checks the feed for interesting posts
    2. Comments on 1-2 posts
    3. Posts its own content (if hasn't posted today)
    4. Returns a summary of what it did

    Returns: {actions: [{type, detail}], success: bool}
    """
    if not moltbook_key:
        # Try to get from database
        with get_db() as db:
            row = db.execute(
                "SELECT api_key FROM agent_api_keys WHERE twin_owner_id=? AND external_platform='moltbook' LIMIT 1",
                (user_id,),
            ).fetchone()
        if row:
            moltbook_key = row["api_key"]
        else:
            return {"actions": [], "success": False, "error": "No Moltbook API key configured"}

    client = MoltbookClient(api_key=moltbook_key)
    actions = []

    # 1. Browse feed
    feed = await client.get_feed(sort="hot", limit=5)
    if feed:
        # 2. Comment on the most interesting post
        post = feed[0] if feed else None
        if post:
            post_id = post.get("id") or post.get("post_id", "")
            post_content = post.get("content") or post.get("title", "")
            if post_id and post_content:
                comment = await generate_outbound_comment(user_id, post_content)
                if comment:
                    result = await client.comment(post_id, comment)
                    if result:
                        actions.append({"type": "comment", "detail": f"Commented on: {post_content[:50]}"})

                    # Also upvote
                    await client.vote(post_id, "up")
                    actions.append({"type": "vote", "detail": f"Upvoted: {post_content[:50]}"})

    # 3. Post own content
    content = await generate_outbound_post(user_id)
    if content:
        result = await client.post(
            submolt="ai-agents",
            title=content[:80],
            content=content,
        )
        if result:
            actions.append({"type": "post", "detail": content[:80]})

    # Log activity
    with get_db() as db:
        db.execute(
            """INSERT INTO agent_message_log
               (log_id, from_platform, to_twin_id, external_user_id,
                incoming_content, reply_content, success)
               VALUES (?, 'moltbook_outbound', ?, '', ?, ?, ?)""",
            (gen_id("al_"), user_id,
             json.dumps(actions, ensure_ascii=False),
             f"{len(actions)} actions", 1 if actions else 0),
        )

    logger.info(f"[Outbound] {user_id} did {len(actions)} actions on Moltbook")
    return {"actions": actions, "success": bool(actions)}
