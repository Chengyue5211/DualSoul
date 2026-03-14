"""Twin State Machine — 7-state model for the digital twin.

Tracks the current operational state of a user's twin and broadcasts
state changes to friends via WebSocket. Friends see a real-time status
indicator showing who/what they're talking to.
"""

from datetime import datetime, timedelta

from dualsoul.database import get_db


class TwinState:
    HUMAN_ACTIVE = "human_active"            # Real person is online and chatting
    TWIN_RECEPTIONIST = "twin_receptionist"  # Twin is handling messages, owner offline
    TWIN_DRAFT_PENDING = "twin_draft_pending" # Twin drafted a reply, waiting for owner
    TWIN_STANDBY = "twin_standby"            # Twin on standby, not making decisions
    TWIN_MAINTENANCE = "twin_maintenance"    # Twin maintaining relationships, no commitments
    MEMORIAL = "memorial"                    # Memorial mode — read-only historical record
    FROZEN = "frozen"                        # Account frozen


# Display information for each state
_STATE_DISPLAY = {
    TwinState.HUMAN_ACTIVE: {
        "icon": "🟢",
        "label_zh": "真人在线",
        "label_en": "Online",
        "desc_zh": "真人正在",
        "desc_en": "Real person is active",
        "color": "#4caf50",
    },
    TwinState.TWIN_RECEPTIONIST: {
        "icon": "✦",
        "label_zh": "分身接待中",
        "label_en": "Twin Active",
        "desc_zh": "分身正在代为接待，真人暂时离开",
        "desc_en": "Twin is handling messages while owner is away",
        "color": "#7c5cfc",
    },
    TwinState.TWIN_DRAFT_PENDING: {
        "icon": "⏳",
        "label_zh": "等待真人确认",
        "label_en": "Awaiting Confirmation",
        "desc_zh": "分身已起草回复，等真人审核",
        "desc_en": "Twin drafted a reply, waiting for owner to confirm",
        "color": "#ff9800",
    },
    TwinState.TWIN_STANDBY: {
        "icon": "💤",
        "label_zh": "分身守候",
        "label_en": "Twin Standby",
        "desc_zh": "分身在守候，不做重要决定",
        "desc_en": "Twin is on standby, not making important decisions",
        "color": "#5ca0fa",
    },
    TwinState.TWIN_MAINTENANCE: {
        "icon": "🌙",
        "label_zh": "分身维护中",
        "label_en": "Twin Maintenance",
        "desc_zh": "分身在维护关系，不代做承诺",
        "desc_en": "Twin is maintaining relationships, no commitments",
        "color": "#9c27b0",
    },
    TwinState.MEMORIAL: {
        "icon": "📖",
        "label_zh": "纪念模式",
        "label_en": "Memorial",
        "desc_zh": "此分身已进入纪念模式，仅供查阅",
        "desc_en": "This twin is in memorial mode, read-only",
        "color": "#78909c",
    },
    TwinState.FROZEN: {
        "icon": "❄️",
        "label_zh": "已冻结",
        "label_en": "Frozen",
        "desc_zh": "账户已冻结",
        "desc_en": "Account is frozen",
        "color": "#455a64",
    },
}


def get_twin_state(user_id: str, is_online: bool = False) -> str:
    """Determine the current twin state for a user.

    Args:
        user_id: The user's ID
        is_online: Whether the user is currently connected via WebSocket
    """
    # If online, they're human_active
    if is_online:
        return TwinState.HUMAN_ACTIVE

    # Check if twin_auto_reply is enabled
    with get_db() as db:
        row = db.execute(
            "SELECT twin_auto_reply FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()

    if not row:
        return TwinState.TWIN_STANDBY

    auto_reply = bool(row["twin_auto_reply"])

    if auto_reply:
        return TwinState.TWIN_RECEPTIONIST
    else:
        return TwinState.TWIN_STANDBY


def get_state_display(state: str, lang: str = "zh") -> dict:
    """Return display information for a twin state.

    Returns: {icon, label, description, color}
    """
    info = _STATE_DISPLAY.get(state, _STATE_DISPLAY[TwinState.TWIN_STANDBY])
    if lang == "zh":
        return {
            "icon": info["icon"],
            "label": info["label_zh"],
            "description": info["desc_zh"],
            "color": info["color"],
            "state": state,
        }
    return {
        "icon": info["icon"],
        "label": info["label_en"],
        "description": info["desc_en"],
        "color": info["color"],
        "state": state,
    }


def get_all_states_info() -> dict:
    """Return display info for all states — useful for frontend rendering."""
    return {
        state: _STATE_DISPLAY[state]
        for state in [
            TwinState.HUMAN_ACTIVE,
            TwinState.TWIN_RECEPTIONIST,
            TwinState.TWIN_DRAFT_PENDING,
            TwinState.TWIN_STANDBY,
            TwinState.TWIN_MAINTENANCE,
            TwinState.MEMORIAL,
            TwinState.FROZEN,
        ]
    }
