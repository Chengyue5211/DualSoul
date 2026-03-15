"""Relationship Body — the memory and state of a relationship between two users.

Unlike personal twin memory (which belongs to one user), the relationship body
belongs to the relationship itself. It records shared history, milestones,
shared vocabulary, and relationship status from both sides.
"""

import json
import logging
from collections import Counter
from datetime import datetime, timedelta

from dualsoul.database import gen_id, get_db

logger = logging.getLogger(__name__)


def _canonical_pair(uid: str, fid: str) -> tuple[str, str]:
    """Return (min_id, max_id) for a canonical pair key."""
    return (min(uid, fid), max(uid, fid))


def get_or_create_relationship(uid: str, fid: str) -> dict:
    """Get or initialize the relationship body between two users."""
    a, b = _canonical_pair(uid, fid)
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM relationship_bodies WHERE user_a=? AND user_b=?",
            (a, b),
        ).fetchone()
        if row:
            return dict(row)

        # Create new relationship body
        rel_id = gen_id("rb_")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """INSERT INTO relationship_bodies
            (rel_id, user_a, user_b, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)""",
            (rel_id, a, b, now, now),
        )
        return {
            "rel_id": rel_id, "user_a": a, "user_b": b,
            "temperature": 50.0, "total_messages": 0, "streak_days": 0,
            "last_interaction": "", "milestones": "[]", "shared_words": "[]",
            "relationship_label": "", "status": "active",
            "created_at": now, "updated_at": now,
        }


def update_on_message(uid: str, fid: str, content: str):
    """Update relationship body whenever a message is sent between two users."""
    try:
        a, b = _canonical_pair(uid, fid)
        rel = get_or_create_relationship(uid, fid)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.now().strftime("%Y-%m-%d")

        new_total = rel["total_messages"] + 1

        # Update streak
        last_str = rel.get("last_interaction") or ""
        last_date = last_str[:10] if last_str else ""
        streak = rel.get("streak_days", 0)
        if last_date != today:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_date == yesterday:
                streak += 1
            elif last_date:
                streak = 1  # Reset if gap
            else:
                streak = 1  # First interaction

        # Temperature: each message warms the relationship
        current_temp = rel.get("temperature", 50.0)
        new_temp = min(100.0, current_temp + 0.8)

        # Update shared words periodically (every 10 messages)
        shared_words = rel.get("shared_words", "[]")
        if new_total % 10 == 0:
            try:
                recent_msgs = _fetch_recent_messages(uid, fid, limit=50)
                if recent_msgs:
                    new_words = extract_shared_words(recent_msgs)
                    shared_words = json.dumps(new_words)
            except Exception as e:
                logger.warning(f"[RelBody] Word extraction failed: {e}")

        with get_db() as db:
            db.execute(
                """UPDATE relationship_bodies SET
                    total_messages=?, streak_days=?, last_interaction=?,
                    temperature=?, shared_words=?, status='active', updated_at=?
                WHERE user_a=? AND user_b=?""",
                (new_total, streak, now, round(new_temp, 1),
                 shared_words, now, a, b),
            )

        # Check milestones after update
        check_and_record_milestone(uid, fid, new_total)

    except Exception as e:
        logger.error(f"[RelBody] update_on_message failed: {e}", exc_info=True)


def _fetch_recent_messages(uid: str, fid: str, limit: int = 50) -> list[str]:
    """Fetch recent message contents between two users."""
    with get_db() as db:
        rows = db.execute(
            """SELECT content FROM social_messages
            WHERE (from_user_id=? AND to_user_id=?)
               OR (from_user_id=? AND to_user_id=?)
            ORDER BY created_at DESC LIMIT ?""",
            (uid, fid, fid, uid, limit),
        ).fetchall()
    return [r["content"] for r in rows if r["content"]]


def check_and_record_milestone(uid: str, fid: str, total_messages: int) -> list[str]:
    """Check if a message-count milestone was reached and record it."""
    a, b = _canonical_pair(uid, fid)
    new_milestones = []

    # Message count milestones
    msg_milestones = {
        1: "第一条消息",
        10: "10条消息",
        50: "50条消息",
        100: "100条消息",
        365: "365条消息",
        1000: "1000条消息",
    }
    if total_messages in msg_milestones:
        new_milestones.append({
            "type": "message_count",
            "value": total_messages,
            "label": msg_milestones[total_messages],
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    if not new_milestones:
        return []

    try:
        with get_db() as db:
            row = db.execute(
                "SELECT milestones FROM relationship_bodies WHERE user_a=? AND user_b=?",
                (a, b),
            ).fetchone()
            if not row:
                return []

            existing = json.loads(row["milestones"] or "[]")
            existing_labels = {m.get("label") for m in existing}
            to_add = [m for m in new_milestones if m["label"] not in existing_labels]
            if to_add:
                updated = existing + to_add
                db.execute(
                    "UPDATE relationship_bodies SET milestones=?, updated_at=? WHERE user_a=? AND user_b=?",
                    (json.dumps(updated), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
                )
                logger.info(f"[RelBody] Milestone recorded: {[m['label'] for m in to_add]}")
                return [m["label"] for m in to_add]
    except Exception as e:
        logger.error(f"[RelBody] check_and_record_milestone failed: {e}", exc_info=True)

    return []


def check_date_milestones(uid: str, fid: str):
    """Check time-based milestones (1/3/12 months since relationship started)."""
    try:
        a, b = _canonical_pair(uid, fid)
        rel = get_or_create_relationship(uid, fid)
        created_str = rel.get("created_at", "")
        if not created_str:
            return

        created = datetime.strptime(created_str[:19], "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        diff_days = (now - created).days

        date_milestones = {
            30: "认识满1个月",
            90: "认识满3个月",
            365: "认识满1年",
        }

        new_milestones = []
        for days, label in date_milestones.items():
            if diff_days >= days:
                new_milestones.append({
                    "type": "date",
                    "value": days,
                    "label": label,
                    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

        if not new_milestones:
            return

        with get_db() as db:
            row = db.execute(
                "SELECT milestones FROM relationship_bodies WHERE user_a=? AND user_b=?",
                (a, b),
            ).fetchone()
            if not row:
                return

            existing = json.loads(row["milestones"] or "[]")
            existing_labels = {m.get("label") for m in existing}
            to_add = [m for m in new_milestones if m["label"] not in existing_labels]
            if to_add:
                updated = existing + to_add
                db.execute(
                    "UPDATE relationship_bodies SET milestones=?, updated_at=? WHERE user_a=? AND user_b=?",
                    (json.dumps(updated), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
                )
    except Exception as e:
        logger.error(f"[RelBody] check_date_milestones failed: {e}", exc_info=True)


def get_relationship_summary(uid: str, fid: str) -> dict:
    """Return full relationship archive for the frontend."""
    rel = get_or_create_relationship(uid, fid)

    # Parse JSON fields
    milestones = []
    shared_words = []
    try:
        milestones = json.loads(rel.get("milestones") or "[]")
    except Exception as e:
        logger.debug(f"Failed to parse milestones JSON: {e}")
    try:
        shared_words = json.loads(rel.get("shared_words") or "[]")
    except Exception as e:
        logger.debug(f"Failed to parse shared_words JSON: {e}")

    temp = rel.get("temperature", 50.0)
    temp_status = (
        "hot" if temp >= 75 else
        "warm" if temp >= 45 else
        "cool" if temp >= 20 else
        "cold"
    )

    return {
        "rel_id": rel.get("rel_id"),
        "temperature": temp,
        "temperature_status": temp_status,
        "total_messages": rel.get("total_messages", 0),
        "streak_days": rel.get("streak_days", 0),
        "last_interaction": rel.get("last_interaction", ""),
        "milestones": milestones,
        "shared_words": shared_words[:20],  # Top 20
        "relationship_label": rel.get("relationship_label", ""),
        "status": rel.get("status", "active"),
        "created_at": rel.get("created_at", ""),
    }


def update_relationship_status(uid: str, fid: str):
    """Auto-update relationship status based on last interaction time."""
    try:
        a, b = _canonical_pair(uid, fid)
        rel = get_or_create_relationship(uid, fid)
        last_str = rel.get("last_interaction") or rel.get("created_at") or ""
        if not last_str:
            return

        try:
            last_dt = datetime.strptime(last_str[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return

        days_since = (datetime.now() - last_dt).days
        current_status = rel.get("status", "active")

        # Don't override frozen or memorial status
        if current_status in ("frozen", "memorial"):
            return

        new_status = current_status
        if days_since >= 30:
            new_status = "estranged"
        elif days_since >= 7:
            new_status = "cooling"
        else:
            new_status = "active"

        if new_status != current_status:
            # Also decay temperature
            temp = rel.get("temperature", 50.0)
            decay = min(temp, days_since * 0.5)
            new_temp = max(0.0, temp - decay)

            with get_db() as db:
                db.execute(
                    "UPDATE relationship_bodies SET status=?, temperature=?, updated_at=? WHERE user_a=? AND user_b=?",
                    (new_status, round(new_temp, 1),
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
                )
            logger.info(f"[RelBody] Status updated: {a}-{b} → {new_status} ({days_since} days)")

    except Exception as e:
        logger.error(f"[RelBody] update_relationship_status failed: {e}", exc_info=True)


def extract_shared_words(messages: list[str]) -> list[str]:
    """Extract high-frequency words/expressions from messages between two users.

    Filters out single common characters and returns top shared expressions.
    """
    # Common stop words/characters to filter out
    stop_chars = set("的了吗呢啊哦哈呀嗯嘛吧好是你我他她它们在有了没有很一个这那也就都还")
    stop_words = {"然后", "就是", "但是", "因为", "所以", "不是", "什么", "怎么", "这样", "那样"}

    word_counter: Counter = Counter()

    for msg in messages:
        if not msg or len(msg) < 2:
            continue
        # Extract 2-4 character sequences
        for n in range(2, 5):
            for i in range(len(msg) - n + 1):
                chunk = msg[i:i+n]
                # Skip if any stop char in chunk, or if all ASCII
                if any(c in stop_chars for c in chunk):
                    continue
                if chunk in stop_words:
                    continue
                if chunk.isascii() and not chunk.isalpha():
                    continue
                word_counter[chunk] += 1

    # Return phrases that appear 3+ times (shared expressions)
    shared = [word for word, count in word_counter.most_common(30) if count >= 3]
    return shared[:20]
