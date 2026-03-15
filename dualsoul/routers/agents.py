"""Agent API — cross-platform agent interoperability.

Allows external agent platforms (OpenClaw, etc.) to:
1. Register API keys for their twins
2. Send messages and get twin replies
3. Export twin identity for cross-platform use
4. Query twin status and capabilities

Authentication: API key in Authorization header (Bearer agent_xxx)
"""

import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from dualsoul.auth import get_current_user
from dualsoul.database import gen_id, get_db
from dualsoul.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["Agents"])

# Rate limiter for agent API (60 requests/min per key)
_agent_limiter = RateLimiter(max_requests=60, window_seconds=60)


# --- Models ---

class AgentReplyRequest(BaseModel):
    incoming_msg: str
    sender_mode: str = "real"  # "real" or "twin"
    sender_id: str = ""  # External user/agent ID
    target_lang: str = ""  # Optional translation target
    context: str = ""  # "casual_chat", "auto_reply", "trial_chat"


class AgentKeyRequest(BaseModel):
    platform: str  # "openclaw", "custom", etc.
    expires_days: int = 90


# --- Auth helpers ---

def _get_agent_key_owner(api_key: str) -> dict | None:
    """Validate an agent API key and return its owner info."""
    with get_db() as db:
        row = db.execute(
            """SELECT ak.key_id, ak.twin_owner_id, ak.external_platform, ak.scopes,
                      ak.expires_at, u.display_name, u.username
               FROM agent_api_keys ak
               JOIN users u ON u.user_id = ak.twin_owner_id
               WHERE ak.api_key=?""",
            (api_key,),
        ).fetchone()

    if not row:
        return None

    # Check expiry
    if row["expires_at"]:
        try:
            exp = datetime.strptime(row["expires_at"][:19], "%Y-%m-%d %H:%M:%S")
            if exp < datetime.now():
                return None
        except ValueError:
            pass

    # Update last_used_at
    with get_db() as db:
        db.execute(
            "UPDATE agent_api_keys SET last_used_at=datetime('now','localtime') WHERE key_id=?",
            (row["key_id"],),
        )

    return dict(row)


async def get_agent_user(authorization: str = Header("")) -> dict:
    """FastAPI dependency — extract agent API key from Authorization header."""
    if not authorization.startswith("Bearer agent_"):
        raise HTTPException(status_code=401, detail="Invalid agent API key format")

    api_key = authorization.replace("Bearer ", "").strip()
    owner = _get_agent_key_owner(api_key)
    if not owner:
        raise HTTPException(status_code=401, detail="Invalid or expired agent API key")

    return owner


# --- Endpoints ---

@router.post("/keys")
async def create_agent_key(req: AgentKeyRequest, user=Depends(get_current_user)):
    """Create an API key for external agent platforms to access your twin.

    Returns the key ONCE — it cannot be retrieved later.
    """
    uid = user["user_id"]
    platform = req.platform.strip().lower()
    if not platform or len(platform) > 50:
        return {"success": False, "error": "Platform name required (max 50 chars)"}

    # Max 5 keys per user
    with get_db() as db:
        count = db.execute(
            "SELECT COUNT(*) as cnt FROM agent_api_keys WHERE twin_owner_id=?",
            (uid,),
        ).fetchone()
    if count and count["cnt"] >= 5:
        return {"success": False, "error": "Maximum 5 API keys per user"}

    key_id = gen_id("ak_")
    api_key = f"agent_{secrets.token_urlsafe(64)}"
    expires_at = (datetime.now() + timedelta(days=req.expires_days)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as db:
        db.execute(
            """INSERT INTO agent_api_keys
               (key_id, twin_owner_id, external_platform, api_key, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (key_id, uid, platform, api_key, expires_at),
        )

    logger.info(f"[AgentAPI] Created key {key_id} for {uid} on platform '{platform}'")

    return {
        "success": True,
        "data": {
            "key_id": key_id,
            "api_key": api_key,
            "platform": platform,
            "expires_at": expires_at,
            "scopes": "twin:reply",
            "warning": "Save this key — it cannot be retrieved later.",
        },
    }


@router.get("/keys")
async def list_agent_keys(user=Depends(get_current_user)):
    """List all agent API keys (keys are masked)."""
    uid = user["user_id"]
    with get_db() as db:
        rows = db.execute(
            """SELECT key_id, external_platform, api_key, scopes,
                      created_at, expires_at, last_used_at
               FROM agent_api_keys WHERE twin_owner_id=?
               ORDER BY created_at DESC""",
            (uid,),
        ).fetchall()

    keys = []
    for r in rows:
        keys.append({
            "key_id": r["key_id"],
            "platform": r["external_platform"],
            "key_preview": r["api_key"][:12] + "..." + r["api_key"][-4:],
            "scopes": r["scopes"],
            "created_at": r["created_at"],
            "expires_at": r["expires_at"],
            "last_used_at": r["last_used_at"] or "never",
        })

    return {"success": True, "keys": keys}


@router.delete("/keys/{key_id}")
async def revoke_agent_key(key_id: str, user=Depends(get_current_user)):
    """Revoke an agent API key."""
    uid = user["user_id"]
    with get_db() as db:
        result = db.execute(
            "DELETE FROM agent_api_keys WHERE key_id=? AND twin_owner_id=?",
            (key_id, uid),
        )
        if result.rowcount == 0:
            return {"success": False, "error": "Key not found"}

    return {"success": True}


@router.post("/reply")
async def agent_reply(req: AgentReplyRequest, request: Request, agent=Depends(get_agent_user)):
    """Send a message and get a twin reply.

    This is the core endpoint for agent-to-twin communication.
    External platforms call this to "talk to" a DualSoul twin.
    """
    # Rate limit
    if _agent_limiter.is_limited(request):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Scope check
    scopes = (agent.get("scopes") or "").split(",")
    if "twin:reply" not in scopes:
        raise HTTPException(status_code=403, detail="API key lacks 'twin:reply' scope")

    twin_owner_id = agent["twin_owner_id"]
    platform = agent["external_platform"]
    content = req.incoming_msg.strip()

    if not content:
        return {"success": False, "error": "Message cannot be empty"}
    if len(content) > 2000:
        return {"success": False, "error": "Message too long (max 2000 chars)"}

    # Namespace external sender ID
    external_sender = f"external:{platform}:{req.sender_id}" if req.sender_id else ""

    # Generate twin reply
    from dualsoul.twin_engine.responder import TwinResponder
    twin = TwinResponder()

    result = await twin.generate_reply(
        twin_owner_id=twin_owner_id,
        from_user_id=external_sender,
        incoming_msg=content,
        sender_mode=req.sender_mode,
        target_lang=req.target_lang,
        social_context=req.context or "auto_reply",
    )

    # Log the interaction
    log_id = gen_id("al_")
    reply_content = result["content"] if result else ""
    success = 1 if result else 0

    with get_db() as db:
        db.execute(
            """INSERT INTO agent_message_log
               (log_id, from_platform, to_twin_id, external_user_id,
                incoming_content, reply_content, success)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (log_id, platform, twin_owner_id, req.sender_id or "",
             content, reply_content, success),
        )

    if not result:
        return {"success": False, "error": "Twin reply generation failed"}

    return {
        "success": True,
        "data": {
            "reply": result["content"],
            "msg_id": result.get("msg_id", ""),
            "ai_generated": True,
            "target_lang": result.get("target_lang", ""),
            "translation_style": result.get("translation_style", ""),
        },
    }


@router.get("/twin/profile")
async def agent_get_twin_profile(agent=Depends(get_agent_user)):
    """Get the twin's public profile for display on external platforms."""
    twin_owner_id = agent["twin_owner_id"]

    from dualsoul.twin_engine.personality import get_twin_profile
    profile = get_twin_profile(twin_owner_id)
    if not profile:
        return {"success": False, "error": "Twin profile not found"}

    return {
        "success": True,
        "data": {
            "display_name": profile.display_name,
            "personality": profile.personality,
            "speech_style": profile.speech_style,
            "preferred_lang": profile.preferred_lang,
            "gender": profile.gender,
            "source": profile.twin_source,
            "capabilities": [
                "text_reply",
                "personality_preserving_translation",
                "emotion_aware_response",
                "narrative_memory",
            ],
        },
    }


@router.get("/twin/stats")
async def agent_get_twin_stats(agent=Depends(get_agent_user)):
    """Get the twin's activity stats for monitoring."""
    twin_owner_id = agent["twin_owner_id"]
    platform = agent["external_platform"]

    with get_db() as db:
        # Total agent interactions
        total = db.execute(
            "SELECT COUNT(*) as cnt FROM agent_message_log WHERE to_twin_id=? AND from_platform=?",
            (twin_owner_id, platform),
        ).fetchone()

        # Today's interactions
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = db.execute(
            "SELECT COUNT(*) as cnt FROM agent_message_log WHERE to_twin_id=? AND from_platform=? AND created_at>?",
            (twin_owner_id, platform, today),
        ).fetchone()

        # Success rate
        success_count = db.execute(
            "SELECT COUNT(*) as cnt FROM agent_message_log WHERE to_twin_id=? AND from_platform=? AND success=1",
            (twin_owner_id, platform),
        ).fetchone()

    total_n = total["cnt"] if total else 0
    success_n = success_count["cnt"] if success_count else 0

    return {
        "success": True,
        "data": {
            "total_interactions": total_n,
            "today_interactions": today_count["cnt"] if today_count else 0,
            "success_rate": round(success_n / total_n, 2) if total_n > 0 else 1.0,
            "platform": platform,
        },
    }
