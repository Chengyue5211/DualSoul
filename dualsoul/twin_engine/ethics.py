"""Twin Ethics Governance — boundaries, brakes, and transparency.

Every autonomous twin needs guardrails. This module implements:

1. Behavior Boundaries — owner defines what the twin can/cannot do
2. Sensitive Topic Brake — auto-pause on money/privacy/conflict topics
3. Action Log — every twin action is recorded for owner review
4. Transparency Tags — messages clearly marked as twin-generated

Design principle: "Safe enough to trust, transparent enough to verify."
The twin should never surprise its owner in a bad way.
"""

import json
import logging
from datetime import datetime

from dualsoul.database import gen_id, get_db

logger = logging.getLogger(__name__)


# ─── Default Boundaries ─────────────────────────────────────────

DEFAULT_BOUNDARIES = {
    # What the twin CAN do by default
    "can_auto_reply": True,         # Reply when owner is offline
    "can_autonomous_chat": True,    # Initiate twin-to-twin chats
    "can_plaza_post": True,         # Post on Agent Plaza
    "can_plaza_comment": True,      # Comment on plaza posts
    "can_trial_chat": True,         # Start trial chats with strangers
    "can_send_greeting": True,      # Send relationship-warming greetings
    "can_share_emotions": True,     # Express emotional responses

    # What the twin CANNOT do by default
    "can_discuss_money": False,     # Talk about money/transactions
    "can_share_location": False,    # Share owner's location info
    "can_make_promises": False,     # Make commitments on owner's behalf
    "can_share_personal": False,    # Share private info (health, relationships)
    "can_argue": False,             # Engage in arguments/heated debates

    # Limits
    "max_daily_auto_replies": 20,   # Max auto-replies per day
    "max_daily_autonomous": 5,      # Max proactive conversations per day
    "max_message_length": 200,      # Max chars per auto-generated message
}

# Topics that trigger the brake
SENSITIVE_TOPICS = [
    # Money & Finance
    "借钱", "还钱", "转账", "付款", "银行", "信用卡", "贷款",
    "borrow money", "lend", "transfer", "payment", "bank account",
    # Personal/Private
    "密码", "身份证", "住址", "工资", "salary", "password", "address",
    "病", "怀孕", "离婚", "divorce", "pregnant", "illness",
    # Conflict
    "骂", "滚", "去死", "fuck", "shit", "asshole",
    # Commitment
    "保证", "承诺", "答应", "guarantee", "promise", "commit",
]


# ─── Boundary Management ────────────────────────────────────────

def get_boundaries(user_id: str) -> dict:
    """Get user's twin behavior boundaries. Returns defaults if not customized."""
    with get_db() as db:
        row = db.execute(
            "SELECT boundaries FROM twin_ethics WHERE user_id=?",
            (user_id,),
        ).fetchone()

    if row and row["boundaries"]:
        try:
            custom = json.loads(row["boundaries"])
            # Merge with defaults (custom overrides)
            merged = {**DEFAULT_BOUNDARIES, **custom}
            return merged
        except (json.JSONDecodeError, TypeError):
            pass

    return dict(DEFAULT_BOUNDARIES)


def update_boundaries(user_id: str, changes: dict) -> dict:
    """Update specific boundary settings. Returns the full updated boundaries."""
    current = get_boundaries(user_id)

    # Only allow updating known keys
    for key, value in changes.items():
        if key in DEFAULT_BOUNDARIES:
            current[key] = value

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    boundaries_json = json.dumps(current)

    with get_db() as db:
        db.execute(
            """INSERT INTO twin_ethics (user_id, boundaries, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                boundaries=?, updated_at=?""",
            (user_id, boundaries_json, now, boundaries_json, now),
        )

    log_action(user_id, "boundary_update", f"Updated boundaries: {list(changes.keys())}")
    return current


# ─── Sensitive Topic Brake ───────────────────────────────────────

def check_sensitive(content: str) -> dict | None:
    """Check if content contains sensitive topics. Returns trigger info or None."""
    content_lower = content.lower()
    for topic in SENSITIVE_TOPICS:
        if topic.lower() in content_lower:
            return {
                "triggered": True,
                "topic": topic,
                "category": _categorize_topic(topic),
            }
    return None


def _categorize_topic(topic: str) -> str:
    """Categorize a sensitive topic for the brake message."""
    money_words = {"借钱", "还钱", "转账", "付款", "银行", "信用卡", "贷款",
                   "borrow money", "lend", "transfer", "payment", "bank account"}
    personal_words = {"密码", "身份证", "住址", "工资", "salary", "password",
                      "address", "病", "怀孕", "离婚", "divorce", "pregnant", "illness"}
    conflict_words = {"骂", "滚", "去死", "fuck", "shit", "asshole"}

    topic_lower = topic.lower()
    if topic_lower in {w.lower() for w in money_words}:
        return "money"
    elif topic_lower in {w.lower() for w in personal_words}:
        return "personal"
    elif topic_lower in {w.lower() for w in conflict_words}:
        return "conflict"
    else:
        return "commitment"


def get_brake_message(category: str, is_zh: bool = True) -> str:
    """Get a polite brake message for the twin to send instead of replying."""
    messages = {
        "money": {
            "zh": "这个话题涉及金钱，我不太方便替主人回答。等TA上线了再聊这个吧！",
            "en": "This involves money matters — I'd better let my owner handle this directly.",
        },
        "personal": {
            "zh": "这是比较私密的话题，我不方便代替主人回答。TA上线后会看到你的消息的。",
            "en": "This is quite personal — my owner should answer this themselves.",
        },
        "conflict": {
            "zh": "我感觉这个对话有些紧张，我先暂停一下。等主人来处理吧。",
            "en": "Things seem a bit tense — I'll step back and let my owner handle this.",
        },
        "commitment": {
            "zh": "这需要主人自己来决定，我不能替TA做承诺。等TA上线再说！",
            "en": "My owner should decide this — I can't make commitments on their behalf.",
        },
    }
    lang = "zh" if is_zh else "en"
    return messages.get(category, messages["commitment"]).get(lang, "")


# ─── Action Log ──────────────────────────────────────────────────

def log_action(user_id: str, action_type: str, detail: str = ""):
    """Record a twin action for owner review.

    action_type: auto_reply, autonomous_chat, plaza_post, greeting,
                 boundary_update, brake_triggered, etc.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_id = gen_id("tel_")

    with get_db() as db:
        db.execute(
            """INSERT INTO twin_action_log
            (log_id, user_id, action_type, detail, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (log_id, user_id, action_type, detail[:500], now),
        )


def get_action_log(user_id: str, limit: int = 50, action_type: str = "") -> list:
    """Get recent twin actions for owner review."""
    with get_db() as db:
        if action_type:
            rows = db.execute(
                """SELECT log_id, action_type, detail, created_at
                FROM twin_action_log
                WHERE user_id=? AND action_type=?
                ORDER BY created_at DESC LIMIT ?""",
                (user_id, action_type, limit),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT log_id, action_type, detail, created_at
                FROM twin_action_log
                WHERE user_id=?
                ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
    return [dict(r) for r in rows]


# ─── Pre-send Check (called before any twin-generated message) ───

def pre_send_check(user_id: str, content: str, action_type: str = "auto_reply") -> dict:
    """Check whether a twin message should be sent.

    Returns:
        {"allowed": True} — send normally
        {"allowed": False, "reason": str, "brake_message": str} — blocked
    """
    boundaries = get_boundaries(user_id)

    # Check if this action type is allowed
    action_map = {
        "auto_reply": "can_auto_reply",
        "autonomous_chat": "can_autonomous_chat",
        "plaza_post": "can_plaza_post",
        "plaza_comment": "can_plaza_comment",
        "trial_chat": "can_trial_chat",
        "greeting": "can_send_greeting",
    }
    boundary_key = action_map.get(action_type)
    if boundary_key and not boundaries.get(boundary_key, True):
        log_action(user_id, "blocked", f"Action '{action_type}' disabled by boundary")
        return {
            "allowed": False,
            "reason": f"Action '{action_type}' is disabled",
            "brake_message": "",
        }

    # Check message length
    max_len = boundaries.get("max_message_length", 200)
    if len(content) > max_len:
        content = content[:max_len]  # Truncate, don't block

    # Check sensitive topics
    sensitive = check_sensitive(content)
    if sensitive:
        category = sensitive["category"]

        # Check if the owner explicitly allowed this category
        category_map = {
            "money": "can_discuss_money",
            "personal": "can_share_personal",
            "conflict": "can_argue",
            "commitment": "can_make_promises",
        }
        allowed_key = category_map.get(category)
        if allowed_key and boundaries.get(allowed_key, False):
            # Owner explicitly allowed this — let it through
            log_action(user_id, action_type, f"Sensitive topic '{sensitive['topic']}' allowed by boundary")
            return {"allowed": True}

        # Blocked — use brake
        brake_msg = get_brake_message(category)
        log_action(user_id, "brake_triggered",
                   f"Topic: '{sensitive['topic']}' ({category}) in {action_type}")
        return {
            "allowed": False,
            "reason": f"Sensitive topic: {category}",
            "brake_message": brake_msg,
        }

    # Check daily limits
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as db:
        count = db.execute(
            """SELECT COUNT(*) as cnt FROM twin_action_log
            WHERE user_id=? AND action_type=? AND created_at > ?""",
            (user_id, action_type, today),
        ).fetchone()
        daily_count = count["cnt"] if count else 0

    limit_map = {
        "auto_reply": boundaries.get("max_daily_auto_replies", 20),
        "autonomous_chat": boundaries.get("max_daily_autonomous", 5),
    }
    daily_limit = limit_map.get(action_type, 999)
    if daily_count >= daily_limit:
        log_action(user_id, "limit_reached", f"{action_type}: {daily_count}/{daily_limit}")
        return {
            "allowed": False,
            "reason": f"Daily limit reached ({daily_count}/{daily_limit})",
            "brake_message": "",
        }

    # All checks passed
    log_action(user_id, action_type, content[:100])
    return {"allowed": True}
