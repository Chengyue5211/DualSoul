"""Ethics router — twin boundaries, action log, and governance settings."""

from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.twin_engine.ethics import (
    get_action_log,
    get_boundaries,
    update_boundaries,
)

router = APIRouter(prefix="/api/ethics", tags=["Ethics"])


@router.get("/boundaries")
async def boundaries(user=Depends(get_current_user)):
    """Get current twin behavior boundaries."""
    uid = user["user_id"]
    data = get_boundaries(uid)
    return {"success": True, "data": data}


@router.put("/boundaries")
async def set_boundaries(changes: dict, user=Depends(get_current_user)):
    """Update specific boundary settings.

    Body: {"can_auto_reply": true, "can_discuss_money": false, ...}
    """
    uid = user["user_id"]
    updated = update_boundaries(uid, changes)
    return {"success": True, "data": updated}


@router.get("/action-log")
async def action_log(
    user=Depends(get_current_user),
    limit: int = 50,
    action_type: str = "",
):
    """Get twin's recent action log — everything the twin did."""
    uid = user["user_id"]
    limit = min(limit, 200)
    logs = get_action_log(uid, limit=limit, action_type=action_type)
    return {"success": True, "data": logs}
