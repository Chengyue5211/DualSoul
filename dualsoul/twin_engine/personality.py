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
    preferred_lang: str  # ISO 639-1 code (zh, en, ja, ko, etc.) or empty

    @property
    def is_configured(self) -> bool:
        """Whether the twin has been personalized beyond defaults."""
        return bool(self.personality and self.personality != DEFAULT_PERSONALITY)


# Language display names for prompt construction
LANG_NAMES = {
    "zh": "Chinese (中文)", "en": "English", "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)", "fr": "French (Français)", "de": "German (Deutsch)",
    "es": "Spanish (Español)", "pt": "Portuguese (Português)",
    "ru": "Russian (Русский)", "ar": "Arabic (العربية)",
    "hi": "Hindi (हिन्दी)", "th": "Thai (ไทย)", "vi": "Vietnamese (Tiếng Việt)",
    "id": "Indonesian (Bahasa Indonesia)",
}


def get_lang_name(code: str) -> str:
    """Get human-readable language name from ISO 639-1 code."""
    return LANG_NAMES.get(code, code)


def get_twin_profile(user_id: str) -> TwinProfile | None:
    """Fetch a user's twin profile from the database."""
    with get_db() as db:
        row = db.execute(
            "SELECT user_id, display_name, twin_personality, twin_speech_style, preferred_lang "
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
        preferred_lang=row["preferred_lang"] or "",
    )
