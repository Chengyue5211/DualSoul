"""Relationship router — the relationship body between two users.

The relationship body is an independent object that records the shared history
of a friendship: temperature, milestones, shared vocabulary, and status.
It belongs to the relationship, not to either individual user.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from dualsoul.auth import get_current_user
from dualsoul.database import gen_id, get_db
from dualsoul.twin_engine.relationship_body import (
    get_or_create_relationship,
    get_relationship_summary,
    update_relationship_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/relationship", tags=["Relationship"])


def _assert_friends(uid: str, fid: str) -> bool:
    """Check that uid and fid are accepted friends."""
    with get_db() as db:
        row = db.execute(
            """SELECT conn_id FROM social_connections
            WHERE status='accepted' AND
            ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
            (uid, fid, fid, uid),
        ).fetchone()
    return row is not None


@router.get("/{friend_id}")
async def get_relationship(friend_id: str, user=Depends(get_current_user)):
    """Get the full relationship archive with a friend."""
    uid = user["user_id"]
    if not _assert_friends(uid, friend_id):
        return {"success": False, "error": "Not friends"}

    # Auto-update status based on inactivity
    update_relationship_status(uid, friend_id)

    summary = get_relationship_summary(uid, friend_id)
    return {"success": True, "data": summary}


@router.get("/overview/all")
async def get_relationships_overview(user=Depends(get_current_user)):
    """Get temperature overview for all relationships, sorted by temperature."""
    uid = user["user_id"]

    with get_db() as db:
        # Get all accepted friends
        rows = db.execute(
            """SELECT u.user_id, u.display_name, u.username, u.avatar, u.twin_avatar
            FROM social_connections sc
            JOIN users u ON u.user_id = CASE
                WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
            WHERE (sc.user_id=? OR sc.friend_id=?) AND sc.status='accepted'""",
            (uid, uid, uid),
        ).fetchall()

    friends = [dict(r) for r in rows]
    if not friends:
        return {"success": True, "relationships": []}

    # Get relationship data for each friend
    result = []
    for f in friends:
        fid = f["user_id"]
        update_relationship_status(uid, fid)
        summary = get_relationship_summary(uid, fid)
        result.append({
            "friend_id": fid,
            "friend_name": f["display_name"] or f["username"],
            "avatar": f.get("avatar") or "",
            "twin_avatar": f.get("twin_avatar") or "",
            "temperature": summary["temperature"],
            "temperature_status": summary["temperature_status"],
            "total_messages": summary["total_messages"],
            "streak_days": summary["streak_days"],
            "last_interaction": summary["last_interaction"],
            "status": summary["status"],
            "relationship_label": summary["relationship_label"],
            "milestone_count": len(summary["milestones"]),
        })

    # Sort by temperature descending
    result.sort(key=lambda x: -x["temperature"])
    return {"success": True, "relationships": result}


@router.put("/{friend_id}/label")
async def set_relationship_label(
    friend_id: str,
    body: dict,
    user=Depends(get_current_user),
):
    """Set a relationship label (朋友/家人/恋人/同事 etc.)."""
    uid = user["user_id"]
    if not _assert_friends(uid, friend_id):
        return {"success": False, "error": "Not friends"}

    label = (body.get("label") or "").strip()[:20]
    valid_labels = {"朋友", "家人", "恋人", "同事", "同学", "伙伴", "导师", "粉丝", ""}
    # Allow custom labels up to 20 chars

    rel = get_or_create_relationship(uid, friend_id)
    a, b = (min(uid, friend_id), max(uid, friend_id))

    with get_db() as db:
        db.execute(
            "UPDATE relationship_bodies SET relationship_label=?, updated_at=? WHERE user_a=? AND user_b=?",
            (label, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
        )

    return {"success": True, "label": label}


@router.post("/{friend_id}/milestone")
async def add_manual_milestone(
    friend_id: str,
    body: dict,
    user=Depends(get_current_user),
):
    """Manually record a milestone in the relationship."""
    import json
    uid = user["user_id"]
    if not _assert_friends(uid, friend_id):
        return {"success": False, "error": "Not friends"}

    label = (body.get("label") or "").strip()
    if not label:
        return {"success": False, "error": "label required"}
    if len(label) > 50:
        return {"success": False, "error": "label too long (max 50)"}

    rel = get_or_create_relationship(uid, friend_id)
    a, b = (min(uid, friend_id), max(uid, friend_id))

    try:
        existing = json.loads(rel.get("milestones") or "[]")
    except Exception:
        existing = []

    # Prevent duplicate labels
    if any(m.get("label") == label for m in existing):
        return {"success": False, "error": "Milestone already exists"}

    milestone = {
        "type": "manual",
        "label": label,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "by": uid,
    }
    existing.append(milestone)

    with get_db() as db:
        db.execute(
            "UPDATE relationship_bodies SET milestones=?, updated_at=? WHERE user_a=? AND user_b=?",
            (json.dumps(existing), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
        )

    return {"success": True, "milestone": milestone}
