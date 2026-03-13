"""Identity router — switch mode, profile management, twin preview."""

import httpx
from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import get_db
from dualsoul.models import SwitchModeRequest, TwinPreviewRequest, UpdateProfileRequest

router = APIRouter(prefix="/api/identity", tags=["Identity"])


@router.post("/switch")
async def switch_mode(req: SwitchModeRequest, user=Depends(get_current_user)):
    """Switch between real self and digital twin mode."""
    uid = user["user_id"]
    if req.mode not in ("real", "twin"):
        return {"success": False, "error": "mode must be 'real' or 'twin'"}
    with get_db() as db:
        db.execute("UPDATE users SET current_mode=? WHERE user_id=?", (req.mode, uid))
    return {"success": True, "mode": req.mode}


@router.get("/me")
async def get_profile(user=Depends(get_current_user)):
    """Get current user's dual identity profile."""
    uid = user["user_id"]
    with get_db() as db:
        row = db.execute(
            "SELECT user_id, username, display_name, current_mode, "
            "twin_personality, twin_speech_style, preferred_lang, avatar, twin_avatar, "
            "twin_auto_reply FROM users WHERE user_id=?",
            (uid,),
        ).fetchone()
    if not row:
        return {"success": False, "error": "User not found"}
    return {
        "success": True,
        "data": {
            "user_id": row["user_id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "current_mode": row["current_mode"] or "real",
            "twin_personality": row["twin_personality"] or "",
            "twin_speech_style": row["twin_speech_style"] or "",
            "preferred_lang": row["preferred_lang"] or "",
            "avatar": row["avatar"] or "",
            "twin_avatar": row["twin_avatar"] or "",
            "twin_auto_reply": row["twin_auto_reply"] if "twin_auto_reply" in row.keys() else 0,
        },
    }


@router.put("/profile")
async def update_profile(req: UpdateProfileRequest, user=Depends(get_current_user)):
    """Update display name and twin personality settings."""
    uid = user["user_id"]
    updates = []
    params = []
    if req.display_name:
        updates.append("display_name=?")
        params.append(req.display_name)
    if req.twin_personality:
        updates.append("twin_personality=?")
        params.append(req.twin_personality)
    if req.twin_speech_style:
        updates.append("twin_speech_style=?")
        params.append(req.twin_speech_style)
    if req.preferred_lang:
        updates.append("preferred_lang=?")
        params.append(req.preferred_lang)
    if req.twin_auto_reply is not None:
        updates.append("twin_auto_reply=?")
        params.append(1 if req.twin_auto_reply else 0)
    if not updates:
        return {"success": False, "error": "Nothing to update"}
    params.append(uid)
    with get_db() as db:
        db.execute(f"UPDATE users SET {','.join(updates)} WHERE user_id=?", params)
    return {"success": True}


@router.post("/twin/preview")
async def twin_preview(req: TwinPreviewRequest, user=Depends(get_current_user)):
    """Generate a sample twin reply for onboarding — lets the user see their twin speak."""
    name = req.display_name or "User"
    personality = req.personality or "friendly and thoughtful"
    speech_style = req.speech_style or "natural and warm"

    prompt = (
        f"You are {name}'s digital twin.\n"
        f"Personality: {personality}\n"
        f"Speech style: {speech_style}\n\n"
        f'A friend asks: "Hey, are you free this weekend?"\n\n'
        f"Reply as {name}'s twin. Keep it under 30 words, natural and authentic. "
        f"Output only the reply text, nothing else."
    )

    if not AI_BASE_URL or not AI_API_KEY:
        # Fallback — template reply reflecting personality
        return {
            "success": True,
            "reply": f"Hey! This is {name}'s twin. {name} might be around this weekend — "
                     f"I'll let them know you asked!",
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]},
            )
            reply = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        reply = f"Hey! This is {name}'s twin — I think the weekend might work, let me check!"

    return {"success": True, "reply": reply}
