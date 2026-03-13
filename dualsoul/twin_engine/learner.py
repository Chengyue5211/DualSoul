"""Style learner — analyze a user's real messages to extract personality and speech patterns.

Reads the user's human-sent messages (ai_generated=0, sender_mode='real'),
sends samples to AI for analysis, and updates the twin's personality/speech_style
to better match how the user actually communicates.
"""

import logging

import httpx

from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import get_db

logger = logging.getLogger(__name__)

# Minimum messages needed before learning is meaningful
MIN_MESSAGES_FOR_LEARNING = 10
# How many recent messages to analyze
SAMPLE_SIZE = 80


def get_user_messages(user_id: str, limit: int = SAMPLE_SIZE) -> list[str]:
    """Fetch a user's real (human-written) messages for style analysis."""
    with get_db() as db:
        rows = db.execute(
            """
            SELECT content FROM social_messages
            WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
                AND msg_type='text' AND content != ''
            ORDER BY created_at DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [r["content"] for r in rows]


def get_message_count(user_id: str) -> int:
    """Count how many real messages a user has sent."""
    with get_db() as db:
        row = db.execute(
            """
            SELECT COUNT(*) as cnt FROM social_messages
            WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
                AND msg_type='text'
            """,
            (user_id,),
        ).fetchone()
    return row["cnt"] if row else 0


async def analyze_style(user_id: str) -> dict | None:
    """Analyze a user's messages and extract personality + speech style.

    Returns:
        Dict with 'personality' and 'speech_style' strings, or None if
        not enough data or AI unavailable.
    """
    if not AI_BASE_URL or not AI_API_KEY:
        return None

    msg_count = get_message_count(user_id)
    if msg_count < MIN_MESSAGES_FOR_LEARNING:
        return {
            "error": "not_enough_messages",
            "current": msg_count,
            "required": MIN_MESSAGES_FOR_LEARNING,
        }

    messages = get_user_messages(user_id)
    if not messages:
        return None

    # Get current profile for context
    with get_db() as db:
        row = db.execute(
            "SELECT display_name, twin_personality, twin_speech_style, preferred_lang "
            "FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if not row:
        return None

    name = row["display_name"] or "用户"
    current_personality = row["twin_personality"] or ""
    current_style = row["twin_speech_style"] or ""
    lang = row["preferred_lang"] or "zh"

    # Build message samples (numbered for clarity)
    samples = []
    for i, msg in enumerate(messages[:SAMPLE_SIZE], 1):
        samples.append(f"{i}. {msg}")
    samples_text = "\n".join(samples)

    # Context about current settings
    current_block = ""
    if current_personality or current_style:
        current_block = (
            f"\n当前分身性格设定: {current_personality}"
            f"\n当前分身说话风格: {current_style}"
            f"\n请在当前设定基础上，根据实际聊天记录进行修正和丰富。\n"
        )

    # Use Chinese prompt if user's language is Chinese
    if lang == "zh":
        prompt = (
            f"你是一个语言风格分析专家。下面是{name}最近发送的{len(messages)}条真实聊天消息。\n"
            f"请仔细分析这些消息，提炼出两个方面：\n\n"
            f"1. **性格特征**（personality）：从消息内容推断此人的性格特点，"
            f"如：乐观/严谨/幽默/直率/温柔/理性等，用自然的短句描述，不超过50字。\n\n"
            f"2. **说话风格**（speech_style）：分析此人的语言习惯，包括：\n"
            f"   - 句子长短偏好（简短还是长句）\n"
            f"   - 是否用emoji/表情\n"
            f"   - 口头禅或常用词\n"
            f"   - 语气特点（正式/随意/调侃等）\n"
            f"   - 标点符号习惯\n"
            f"   用自然的短句描述，不超过80字。\n\n"
            f"{current_block}"
            f"聊天记录：\n{samples_text}\n\n"
            f"请严格按以下JSON格式输出，不要输出其他内容：\n"
            f'{{"personality": "...", "speech_style": "..."}}'
        )
    else:
        prompt = (
            f"You are a linguistic style analyst. Below are {len(messages)} real chat messages "
            f"sent by {name}.\n"
            f"Analyze these messages and extract two aspects:\n\n"
            f"1. **personality**: Infer personality traits from the messages "
            f"(e.g., optimistic, rigorous, humorous, direct, warm, rational). "
            f"Describe in natural short phrases, max 50 words.\n\n"
            f"2. **speech_style**: Analyze language habits including:\n"
            f"   - Sentence length preference\n"
            f"   - Emoji usage\n"
            f"   - Catchphrases or frequent expressions\n"
            f"   - Tone (formal/casual/playful)\n"
            f"   - Punctuation habits\n"
            f"   Describe in natural short phrases, max 80 words.\n\n"
            f"{current_block}"
            f"Chat messages:\n{samples_text}\n\n"
            f"Output STRICTLY in this JSON format, nothing else:\n"
            f'{{"personality": "...", "speech_style": "..."}}'
        )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "max_tokens": 300,
                    "temperature": 0.3,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            raw = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Style analysis failed: {e}")
        return None

    # Parse JSON response
    import json

    # Try to extract JSON from response (AI might wrap in markdown code blocks)
    json_str = raw
    if "```" in raw:
        lines = raw.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                json_lines.append(line)
        json_str = "\n".join(json_lines)

    try:
        result = json.loads(json_str)
        personality = result.get("personality", "").strip()
        speech_style = result.get("speech_style", "").strip()
        if not personality or not speech_style:
            logger.warning(f"Incomplete style analysis result: {raw}")
            return None
        return {
            "personality": personality,
            "speech_style": speech_style,
            "message_count": msg_count,
            "samples_analyzed": len(messages),
        }
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse style analysis JSON: {raw}")
        return None


async def learn_and_update(user_id: str, auto_apply: bool = False) -> dict | None:
    """Analyze style and optionally auto-apply to the user's twin profile.

    Args:
        user_id: The user whose messages to analyze
        auto_apply: If True, directly update the twin profile in DB

    Returns:
        Dict with analysis results + whether it was applied
    """
    result = await analyze_style(user_id)
    if not result:
        return None

    if "error" in result:
        return result

    if auto_apply:
        with get_db() as db:
            db.execute(
                "UPDATE users SET twin_personality=?, twin_speech_style=? WHERE user_id=?",
                (result["personality"], result["speech_style"], user_id),
            )
        result["applied"] = True
    else:
        result["applied"] = False

    return result
