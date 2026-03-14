"""Life router — twin life dashboard, daily summary, relationship map."""

from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.twin_engine.life import (
    award_xp,
    ensure_life_state,
    get_life_dashboard,
    update_mood,
    update_relationship_temp,
)
from dualsoul.database import get_db

router = APIRouter(prefix="/api/life", tags=["Life"])


@router.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    """Get the full twin life dashboard: mood, level, relationships, today's activity."""
    uid = user["user_id"]
    data = get_life_dashboard(uid)
    return {"success": True, "data": data}


@router.get("/relationships")
async def relationships(user=Depends(get_current_user)):
    """Get relationship temperature map with friend details."""
    uid = user["user_id"]
    data = get_life_dashboard(uid)
    return {"success": True, "data": data["relationships"]}


@router.post("/teach")
async def teach_twin(user=Depends(get_current_user)):
    """Owner 'teaches' the twin — awards XP for the interaction.

    Called when owner corrects or gives feedback to the twin in self-chat.
    The actual personality update happens via learner.py; this just
    tracks the social growth from the teaching moment.
    """
    uid = user["user_id"]
    result = award_xp(uid, 8, reason="owner_teaching")
    return {"success": True, "data": result}


@router.get("/daily-logs")
async def daily_logs(user=Depends(get_current_user), days: int = 7):
    """Get recent daily activity logs."""
    uid = user["user_id"]
    days = min(days, 30)
    with get_db() as db:
        logs = db.execute(
            """SELECT log_date, summary, mood_trend, chats_count, new_friends,
                      plaza_posts, autonomous_acts, xp_gained, highlights
            FROM twin_daily_log WHERE user_id=?
            ORDER BY log_date DESC LIMIT ?""",
            (uid, days),
        ).fetchall()
    return {"success": True, "data": [dict(l) for l in logs]}
