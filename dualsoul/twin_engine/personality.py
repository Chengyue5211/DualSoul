"""Twin personality model — how a digital twin represents its owner."""

from dataclasses import dataclass

from dualsoul.database import get_db

DEFAULT_PERSONALITY = "friendly and thoughtful"
DEFAULT_SPEECH_STYLE = "natural and warm"


@dataclass
class TwinProfile:
    """A digital twin's personality profile."""

    user_id: str
    display_name: str
    personality: str
    speech_style: str

    @property
    def is_configured(self) -> bool:
        """Whether the twin has been personalized beyond defaults."""
        return bool(self.personality and self.personality != DEFAULT_PERSONALITY)


def get_twin_profile(user_id: str) -> TwinProfile | None:
    """Fetch a user's twin profile from the database."""
    with get_db() as db:
        row = db.execute(
            "SELECT user_id, display_name, twin_personality, twin_speech_style "
            "FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return TwinProfile(
        user_id=row["user_id"],
        display_name=row["display_name"] or "User",
        personality=row["twin_personality"] or DEFAULT_PERSONALITY,
        speech_style=row["twin_speech_style"] or DEFAULT_SPEECH_STYLE,
    )
