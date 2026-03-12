"""Identity router — switch mode, profile management."""

from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.database import get_db
from dualsoul.models import SwitchModeRequest, UpdateProfileRequest

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
            "twin_personality, twin_speech_style, preferred_lang, avatar, twin_avatar "
            "FROM users WHERE user_id=?",
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
    if not updates:
        return {"success": False, "error": "Nothing to update"}
    params.append(uid)
    with get_db() as db:
        db.execute(f"UPDATE users SET {','.join(updates)} WHERE user_id=?", params)
    return {"success": True}
