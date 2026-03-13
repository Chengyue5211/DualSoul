"""Twin personality model — how a digital twin represents its owner.

Supports two sources:
- 'local': lightweight twin with freeform personality/speech_style strings
- 'nianlun': rich twin imported from 年轮 with 5D personality, memories, entities
"""

import json
from dataclasses import dataclass, field

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
    twin_source: str = "local"  # 'local' or 'nianlun'

    # Nianlun 5D dimensions (populated when twin_source='nianlun')
    dim_judgement: dict = field(default_factory=dict)
    dim_cognition: dict = field(default_factory=dict)
    dim_expression: dict = field(default_factory=dict)
    dim_relation: dict = field(default_factory=dict)
    dim_sovereignty: dict = field(default_factory=dict)

    # Nianlun structured data
    value_order: list = field(default_factory=list)
    behavior_patterns: list = field(default_factory=list)
    boundaries: dict = field(default_factory=dict)

    # Context for prompt (memories + entities)
    recent_memories: list = field(default_factory=list)
    key_entities: list = field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        """Whether the twin has been personalized beyond defaults."""
        return bool(self.personality and self.personality != DEFAULT_PERSONALITY)

    @property
    def is_nianlun(self) -> bool:
        """Whether this twin was imported from Nianlun."""
        return self.twin_source == "nianlun"

    def build_personality_prompt(self) -> str:
        """Build the personality section for AI prompts.

        Local twins get a simple 2-line prompt.
        Nianlun twins get a rich multi-section prompt with 5D data.
        """
        if not self.is_nianlun:
            return (
                f"Personality: {self.personality}\n"
                f"Speech style: {self.speech_style}\n"
            )

        lines = ["[Five-Dimension Personality Profile]"]

        dims = [
            ("Judgement (判断力)", self.dim_judgement),
            ("Cognition (认知方式)", self.dim_cognition),
            ("Expression (表达风格)", self.dim_expression),
            ("Relation (关系模式)", self.dim_relation),
            ("Sovereignty (独立边界)", self.dim_sovereignty),
        ]
        for name, dim in dims:
            if dim:
                desc = dim.get("description", "")
                patterns = dim.get("patterns", [])
                score = dim.get("score", "")
                line = f"- {name}"
                if score:
                    line += f" [{score}]"
                if desc:
                    line += f": {desc}"
                if patterns:
                    line += f" (patterns: {', '.join(patterns[:3])})"
                lines.append(line)

        if self.value_order:
            lines.append(f"\nCore values (ranked): {', '.join(self.value_order[:5])}")

        if self.behavior_patterns:
            lines.append(f"Behavior patterns: {', '.join(self.behavior_patterns[:5])}")

        if self.speech_style:
            lines.append(f"Speech style: {self.speech_style}")

        if self.boundaries:
            b = self.boundaries
            if isinstance(b, dict):
                rules = b.get("rules", [])
                if rules:
                    lines.append(f"Boundaries: {'; '.join(rules[:3])}")

        # Inject recent memories as context
        if self.recent_memories:
            lines.append("\n[Recent Context]")
            for mem in self.recent_memories[:5]:
                tone = f" ({mem['tone']})" if mem.get("tone") else ""
                lines.append(f"- {mem['period']}: {mem['summary']}{tone}")

        # Inject key entities
        if self.key_entities:
            people = [e for e in self.key_entities if e.get("type") == "person"]
            if people:
                names = [f"{e['name']}({e.get('context', '')})" for e in people[:5]]
                lines.append(f"\nKey people: {', '.join(names)}")

        return "\n".join(lines) + "\n"


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


def _parse_json(text: str, default=None):
    """Safely parse JSON text, return default on failure."""
    if not text:
        return default if default is not None else {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def get_twin_profile(user_id: str) -> TwinProfile | None:
    """Fetch a user's twin profile from the database.

    For 'nianlun' twins, also loads 5D dimensions, recent memories, and key entities.
    For 'local' twins, returns the simple personality/speech_style profile.
    """
    with get_db() as db:
        row = db.execute(
            "SELECT user_id, display_name, twin_personality, twin_speech_style, "
            "preferred_lang, twin_source "
            "FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if not row:
        return None

    twin_source = row["twin_source"] or "local"

    profile = TwinProfile(
        user_id=row["user_id"],
        display_name=row["display_name"] or "User",
        personality=row["twin_personality"] or DEFAULT_PERSONALITY,
        speech_style=row["twin_speech_style"] or DEFAULT_SPEECH_STYLE,
        preferred_lang=row["preferred_lang"] or "",
        twin_source=twin_source,
    )

    # For Nianlun twins, load rich data
    if twin_source == "nianlun":
        _load_nianlun_data(profile)

    return profile


def _load_nianlun_data(profile: TwinProfile):
    """Load Nianlun 5D dimensions, recent memories, and key entities."""
    with get_db() as db:
        # Active twin profile
        tp = db.execute(
            "SELECT * FROM twin_profiles WHERE user_id=? AND is_active=1 "
            "ORDER BY version DESC LIMIT 1",
            (profile.user_id,),
        ).fetchone()

        if tp:
            profile.dim_judgement = _parse_json(tp["dim_judgement"])
            profile.dim_cognition = _parse_json(tp["dim_cognition"])
            profile.dim_expression = _parse_json(tp["dim_expression"])
            profile.dim_relation = _parse_json(tp["dim_relation"])
            profile.dim_sovereignty = _parse_json(tp["dim_sovereignty"])
            profile.value_order = _parse_json(tp["value_order"], [])
            profile.behavior_patterns = _parse_json(tp["behavior_patterns"], [])
            profile.boundaries = _parse_json(tp["boundaries"])

            # Use Nianlun speech_style if available, overriding the simple string
            nianlun_style = _parse_json(tp["speech_style"])
            if nianlun_style:
                if isinstance(nianlun_style, dict):
                    profile.speech_style = nianlun_style.get("description", profile.speech_style)
                elif isinstance(nianlun_style, str):
                    profile.speech_style = nianlun_style

        # Recent memories (last 5 weekly or monthly)
        mems = db.execute(
            "SELECT memory_type, period_start, period_end, summary_text, emotional_tone "
            "FROM twin_memories WHERE user_id=? "
            "ORDER BY period_end DESC LIMIT 5",
            (profile.user_id,),
        ).fetchall()
        profile.recent_memories = [
            {
                "period": f"{m['period_start']}~{m['period_end']}",
                "summary": m["summary_text"],
                "tone": m["emotional_tone"] or "",
            }
            for m in mems
        ]

        # Key entities (top 10 by importance)
        ents = db.execute(
            "SELECT entity_name, entity_type, importance_score, context "
            "FROM twin_entities WHERE user_id=? "
            "ORDER BY importance_score DESC LIMIT 10",
            (profile.user_id,),
        ).fetchall()
        profile.key_entities = [
            {
                "name": e["entity_name"],
                "type": e["entity_type"],
                "context": e["context"] or "",
            }
            for e in ents
        ]
