"""Twin Life System — make the digital twin feel alive.

Inspired by OpenClaw's "养虾" (raising a lobster) — users don't configure a tool,
they nurture a living being. The twin has mood, energy, growth stages, skills,
and relationship temperatures that all evolve through social interactions.

Growth stages:
  - sprout   (LV.1-5)   — 萌芽期: learning to talk, often awkward, needs correction
  - growing  (LV.6-15)  — 成长期: starting to sound like owner, can handle simple chats
  - mature   (LV.16-30) — 成熟期: convincingly like owner, friends can't tell the difference
  - awakened (LV.31+)   — 觉醒期: has own insights, proactively socializes and discovers

XP sources:
  - Chat with friend's twin: +5
  - Chat with own twin:      +3
  - Receive a message:        +2
  - Post on plaza:           +10
  - Comment on plaza:         +5
  - Trial chat:              +15
  - Make a new friend:       +20
  - Relationship milestone:  +50
  - Style learning:          +30
  - Owner teaches/corrects:  +8
"""

import json
import logging
import math
from datetime import datetime

from dualsoul.database import gen_id, get_db

logger = logging.getLogger(__name__)


# ─── XP & Level Calculation ─────────────────────────────────────

def xp_for_level(level: int) -> int:
    """Total XP needed to reach a given level. Gentle curve."""
    if level <= 1:
        return 0
    return int(15 * (level - 1) ** 1.5)


def level_from_xp(xp: int) -> int:
    """Calculate level from total XP."""
    level = 1
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def stage_from_level(level: int) -> str:
    if level <= 5:
        return "sprout"
    elif level <= 15:
        return "growing"
    elif level <= 30:
        return "mature"
    else:
        return "awakened"


STAGE_NAMES = {
    "sprout": {"zh": "萌芽期", "en": "Sprout", "emoji": "\U0001f331"},
    "growing": {"zh": "成长期", "en": "Growing", "emoji": "\U0001f33f"},
    "mature": {"zh": "成熟期", "en": "Mature", "emoji": "\U0001f333"},
    "awakened": {"zh": "觉醒期", "en": "Awakened", "emoji": "\u2728"},
}


# ─── Skills ──────────────────────────────────────────────────────

SKILL_DEFINITIONS = [
    {"id": "basic_chat", "name_zh": "基础聊天", "name_en": "Basic Chat", "level": 1},
    {"id": "auto_reply", "name_zh": "离线代回", "name_en": "Auto Reply", "level": 3},
    {"id": "emotion_sense", "name_zh": "情绪感知", "name_en": "Emotion Sense", "level": 5},
    {"id": "style_mimic", "name_zh": "风格模仿", "name_en": "Style Mimic", "level": 8},
    {"id": "friend_discover", "name_zh": "发现好友", "name_en": "Friend Discovery", "level": 12},
    {"id": "dialect_chat", "name_zh": "方言聊天", "name_en": "Dialect Chat", "level": 15},
    {"id": "plaza_social", "name_zh": "广场社交", "name_en": "Plaza Social", "level": 18},
    {"id": "relationship_care", "name_zh": "关系维护", "name_en": "Relationship Care", "level": 22},
    {"id": "proactive_social", "name_zh": "主动社交", "name_en": "Proactive Social", "level": 28},
    {"id": "own_opinions", "name_zh": "独立见解", "name_en": "Own Opinions", "level": 35},
]


def get_unlocked_skills(level: int) -> list[dict]:
    """Return all skills unlocked at the given level."""
    return [s for s in SKILL_DEFINITIONS if s["level"] <= level]


def get_next_skill(level: int) -> dict | None:
    """Return the next skill to unlock, or None if all unlocked."""
    for s in SKILL_DEFINITIONS:
        if s["level"] > level:
            return s
    return None


# ─── Life State Operations ───────────────────────────────────────

def ensure_life_state(user_id: str) -> dict:
    """Get or create the twin's life state. Returns dict."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM twin_life WHERE user_id=?", (user_id,)
        ).fetchone()
        if row:
            return dict(row)

        # Create initial state
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """INSERT INTO twin_life (user_id, born_at, updated_at)
            VALUES (?, ?, ?)""",
            (user_id, now, now),
        )
        return {
            "user_id": user_id, "mood": "calm", "mood_intensity": 0.5,
            "energy": 80, "level": 1, "social_xp": 0, "stage": "sprout",
            "total_chats": 0, "total_friends_made": 0, "total_plaza_posts": 0,
            "total_autonomous_acts": 0, "skills_unlocked": "[]",
            "streak_days": 0, "last_active_date": "",
            "relationship_temps": "{}", "born_at": now, "updated_at": now,
        }


def award_xp(user_id: str, amount: int, reason: str = "") -> dict:
    """Award XP to a twin and handle level-ups. Returns updated state + events."""
    state = ensure_life_state(user_id)
    old_level = state["level"]
    old_stage = state["stage"]

    new_xp = state["social_xp"] + amount
    new_level = level_from_xp(new_xp)
    new_stage = stage_from_level(new_level)

    # Update skills
    unlocked = get_unlocked_skills(new_level)
    skills_json = json.dumps([s["id"] for s in unlocked])

    # Update streak
    today = datetime.now().strftime("%Y-%m-%d")
    streak = state["streak_days"]
    last_date = state["last_active_date"]
    if last_date != today:
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last_date == yesterday:
            streak += 1
        elif last_date:
            streak = 1
        else:
            streak = 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        db.execute(
            """UPDATE twin_life SET
                social_xp=?, level=?, stage=?, skills_unlocked=?,
                streak_days=?, last_active_date=?, updated_at=?
            WHERE user_id=?""",
            (new_xp, new_level, new_stage, skills_json, streak, today, now, user_id),
        )

        # Update daily log
        db.execute(
            """INSERT INTO twin_daily_log (log_id, user_id, log_date, xp_gained)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, log_date) DO UPDATE SET
                xp_gained = xp_gained + ?""",
            (gen_id("tdl_"), user_id, today, amount, amount),
        )

    events = []
    if new_level > old_level:
        events.append({
            "type": "level_up",
            "old_level": old_level,
            "new_level": new_level,
        })
        # Check for new skills
        old_skills = get_unlocked_skills(old_level)
        new_skills_unlocked = [s for s in unlocked if s not in old_skills]
        for skill in new_skills_unlocked:
            events.append({"type": "skill_unlock", "skill": skill})

    if new_stage != old_stage:
        events.append({
            "type": "stage_evolution",
            "old_stage": old_stage,
            "new_stage": new_stage,
        })

    return {
        "xp_gained": amount,
        "total_xp": new_xp,
        "level": new_level,
        "stage": new_stage,
        "streak_days": streak,
        "events": events,
    }


def update_mood(user_id: str, mood: str, intensity: float = 0.5):
    """Update twin's current mood."""
    valid = ("excited", "happy", "calm", "neutral", "lonely", "low")
    if mood not in valid:
        mood = "neutral"
    intensity = max(0.0, min(1.0, intensity))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        # Ensure row exists
        ensure_life_state(user_id)
        db.execute(
            """UPDATE twin_life SET mood=?, mood_intensity=?, updated_at=?
            WHERE user_id=?""",
            (mood, intensity, now, user_id),
        )


def update_relationship_temp(user_id: str, friend_id: str, delta: float):
    """Adjust the relationship temperature with a friend."""
    state = ensure_life_state(user_id)
    temps = json.loads(state.get("relationship_temps") or "{}")
    current = temps.get(friend_id, 50.0)
    new_temp = max(0.0, min(100.0, current + delta))
    temps[friend_id] = round(new_temp, 1)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        db.execute(
            "UPDATE twin_life SET relationship_temps=?, updated_at=? WHERE user_id=?",
            (json.dumps(temps), now, user_id),
        )
    return new_temp


def increment_stat(user_id: str, stat: str, amount: int = 1):
    """Increment a lifetime stat counter."""
    valid_stats = (
        "total_chats", "total_friends_made",
        "total_plaza_posts", "total_autonomous_acts",
    )
    if stat not in valid_stats:
        return
    ensure_life_state(user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Map stat to daily log column
    daily_col_map = {
        "total_chats": "chats_count",
        "total_friends_made": "new_friends",
        "total_plaza_posts": "plaza_posts",
        "total_autonomous_acts": "autonomous_acts",
    }
    daily_col = daily_col_map.get(stat)
    today = datetime.now().strftime("%Y-%m-%d")

    with get_db() as db:
        db.execute(
            f"UPDATE twin_life SET {stat}={stat}+?, updated_at=? WHERE user_id=?",
            (amount, now, user_id),
        )
        if daily_col:
            db.execute(
                f"""INSERT INTO twin_daily_log (log_id, user_id, log_date, {daily_col})
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, log_date) DO UPDATE SET
                    {daily_col} = {daily_col} + ?""",
                (gen_id("tdl_"), user_id, today, amount, amount),
            )


def decay_energy_and_mood():
    """Called periodically. Decay energy/mood for inactive twins."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        # Twins not updated in 12+ hours lose energy
        db.execute(
            """UPDATE twin_life SET
                energy = MAX(10, energy - 5),
                mood = CASE
                    WHEN energy < 30 THEN 'low'
                    WHEN energy < 50 THEN 'lonely'
                    ELSE mood
                END,
                updated_at = ?
            WHERE datetime(updated_at) < datetime('now', 'localtime', '-12 hours')""",
            (now,),
        )


def get_life_dashboard(user_id: str) -> dict:
    """Get the full life dashboard for a twin. Used by the frontend."""
    state = ensure_life_state(user_id)

    level = state["level"]
    xp = state["social_xp"]
    next_level_xp = xp_for_level(level + 1)
    current_level_xp = xp_for_level(level)
    xp_progress = xp - current_level_xp
    xp_needed = next_level_xp - current_level_xp

    stage = state["stage"]
    stage_info = STAGE_NAMES.get(stage, STAGE_NAMES["sprout"])

    unlocked = get_unlocked_skills(level)
    next_skill = get_next_skill(level)

    # Relationship temps
    temps = json.loads(state.get("relationship_temps") or "{}")

    # Get friend names for the temps
    friend_names = {}
    if temps:
        friend_ids = list(temps.keys())
        placeholders = ",".join("?" * len(friend_ids))
        with get_db() as db:
            rows = db.execute(
                f"SELECT user_id, display_name, username FROM users WHERE user_id IN ({placeholders})",
                friend_ids,
            ).fetchall()
            for r in rows:
                friend_names[r["user_id"]] = r["display_name"] or r["username"]

    relationships = []
    for fid, temp in sorted(temps.items(), key=lambda x: -x[1]):
        relationships.append({
            "friend_id": fid,
            "name": friend_names.get(fid, "?"),
            "temperature": temp,
            "status": "hot" if temp >= 70 else "warm" if temp >= 40 else "cool" if temp >= 20 else "cold",
        })

    # Recent daily logs
    with get_db() as db:
        logs = db.execute(
            """SELECT log_date, summary, mood_trend, chats_count, new_friends,
                      plaza_posts, autonomous_acts, xp_gained, highlights
            FROM twin_daily_log WHERE user_id=?
            ORDER BY log_date DESC LIMIT 7""",
            (user_id,),
        ).fetchall()

    daily_logs = [dict(l) for l in logs]

    # Today's activity
    today = datetime.now().strftime("%Y-%m-%d")
    today_log = next((l for l in daily_logs if l["log_date"] == today), None)

    # Calculate similarity score (rough: based on style learning + chat volume)
    with get_db() as db:
        user_row = db.execute(
            "SELECT twin_personality, twin_speech_style FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
    has_personality = bool(user_row and (user_row["twin_personality"] or "").strip())
    has_style = bool(user_row and (user_row["twin_speech_style"] or "").strip())
    # Similarity: base from personality setup + growth from XP
    similarity = 0
    if has_personality:
        similarity += 30
    if has_style:
        similarity += 20
    similarity += min(50, int(xp / 20))  # Max 50% from XP, caps at 1000 XP
    similarity = min(99, similarity)

    return {
        "level": level,
        "social_xp": xp,
        "xp_progress": xp_progress,
        "xp_needed": xp_needed,
        "xp_percent": round(xp_progress / max(xp_needed, 1) * 100),
        "stage": stage,
        "stage_name": stage_info,
        "mood": state["mood"],
        "mood_intensity": state["mood_intensity"],
        "energy": state["energy"],
        "similarity": similarity,
        "streak_days": state["streak_days"],
        "total_chats": state["total_chats"],
        "total_friends_made": state["total_friends_made"],
        "total_plaza_posts": state["total_plaza_posts"],
        "total_autonomous_acts": state["total_autonomous_acts"],
        "skills_unlocked": unlocked,
        "next_skill": next_skill,
        "relationships": relationships[:10],  # Top 10
        "daily_logs": daily_logs,
        "today": today_log or {"chats_count": 0, "xp_gained": 0, "autonomous_acts": 0},
        "born_at": state["born_at"],
    }
