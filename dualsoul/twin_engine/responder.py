"""Twin responder — AI-powered auto-reply and cross-language translation engine.

When a message is sent to someone's digital twin (receiver_mode='twin'),
the twin generates a response based on the owner's personality profile.

Cross-language support: When sender and receiver have different preferred
languages, the twin performs "personality-preserving translation" — not just
translating words, but expressing the same intent in the target language
using the owner's personal speaking style, humor, and tone.

Supports any OpenAI-compatible API (OpenAI, Qwen, DeepSeek, Ollama, etc.).
Falls back to template responses when no AI backend is configured.
"""

import logging

import httpx

from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import gen_id, get_db
from dualsoul.twin_engine.personality import get_lang_name, get_twin_profile

logger = logging.getLogger(__name__)


class TwinResponder:
    """Generate replies as a user's digital twin, with cross-language support."""

    async def generate_reply(
        self,
        twin_owner_id: str,
        from_user_id: str,
        incoming_msg: str,
        sender_mode: str,
        target_lang: str = "",
    ) -> dict | None:
        """Generate a twin auto-reply, optionally in a different language.

        Args:
            twin_owner_id: The user whose twin should respond
            from_user_id: The user who sent the message
            incoming_msg: The incoming message content
            sender_mode: Whether the sender is 'real' or 'twin'
            target_lang: If set, respond in this language with personality preservation

        Returns:
            Dict with msg_id, content, ai_generated, translation fields, or None
        """
        profile = get_twin_profile(twin_owner_id)
        if not profile:
            return None

        # Determine sender's language preference for cross-language detection
        sender_profile = get_twin_profile(from_user_id)
        sender_lang = sender_profile.preferred_lang if sender_profile else ""

        # Auto-detect cross-language need
        effective_target_lang = target_lang or ""
        if not effective_target_lang and sender_lang and profile.preferred_lang:
            if sender_lang != profile.preferred_lang:
                # Sender and receiver speak different languages — reply in sender's language
                effective_target_lang = sender_lang

        # Generate reply text
        if AI_BASE_URL and AI_API_KEY:
            reply_text = await self._ai_reply(
                profile, incoming_msg, sender_mode, effective_target_lang
            )
        else:
            reply_text = self._fallback_reply(profile, incoming_msg, effective_target_lang)

        if not reply_text:
            return None

        # Build translation metadata
        original_content = ""
        original_lang = ""
        translation_style = ""
        if effective_target_lang and effective_target_lang != profile.preferred_lang:
            original_lang = profile.preferred_lang or "auto"
            translation_style = "personality_preserving"

        # Store the reply message
        reply_id = gen_id("sm_")
        with get_db() as db:
            db.execute(
                """
                INSERT INTO social_messages
                (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                 content, original_content, original_lang, target_lang,
                 translation_style, msg_type, ai_generated)
                VALUES (?, ?, ?, 'twin', ?, ?, ?, ?, ?, ?, 'text', 1)
                """,
                (reply_id, twin_owner_id, from_user_id, sender_mode,
                 reply_text, original_content, original_lang,
                 effective_target_lang, translation_style),
            )

        result = {"msg_id": reply_id, "content": reply_text, "ai_generated": True}
        if effective_target_lang:
            result["target_lang"] = effective_target_lang
            result["translation_style"] = translation_style
        return result

    async def generate_draft(
        self,
        twin_owner_id: str,
        from_user_id: str,
        incoming_msg: str,
        context: list[dict] | None = None,
    ) -> str | None:
        """Generate a draft suggestion for the owner to review (NOT saved to DB).

        Unlike generate_reply, this is a suggestion the real person might want to send.
        Returns just the draft text, or None if unavailable.
        """
        if not AI_BASE_URL or not AI_API_KEY:
            return None

        profile = get_twin_profile(twin_owner_id)
        if not profile:
            return None

        # Build context string from recent messages
        ctx_str = ""
        if context:
            for msg in context[-5:]:  # Last 5 messages for context
                role = msg.get("role", "friend")
                ctx_str += f"{role}: {msg.get('content', '')}\n"

        ctx_block = f"Conversation context:\n{ctx_str}" if ctx_str else ""
        prompt = (
            f"You are helping {profile.display_name} draft a reply.\n"
            f"Personality: {profile.personality}\n"
            f"Speech style: {profile.speech_style}\n\n"
            f"{ctx_block}"
            f"Friend says: \"{incoming_msg}\"\n\n"
            f"Draft a reply that {profile.display_name} would naturally send. "
            f"Match their personality and speaking style exactly. "
            f"Keep under 40 words. Output only the draft text."
        )

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 80,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Draft generation failed: {e}")
            return None

    async def translate_message(
        self,
        owner_id: str,
        content: str,
        source_lang: str,
        target_lang: str,
    ) -> dict | None:
        """Personality-preserving translation — translate as if the owner wrote it.

        Unlike generic machine translation, this preserves the owner's humor,
        tone, formality level, and characteristic expressions.

        Args:
            owner_id: The user whose personality guides the translation style
            content: The text to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Dict with translated content and metadata, or None
        """
        if not AI_BASE_URL or not AI_API_KEY:
            return None

        profile = get_twin_profile(owner_id)
        if not profile:
            return None

        source_name = get_lang_name(source_lang)
        target_name = get_lang_name(target_lang)

        prompt = (
            f"You are {profile.display_name}'s personal translator.\n"
            f"Personality: {profile.personality}\n"
            f"Speech style: {profile.speech_style}\n\n"
            f"Translate the following from {source_name} to {target_name}.\n"
            f"IMPORTANT: Do NOT just translate words. Rewrite as if {profile.display_name} "
            f"were naturally speaking {target_name} — preserve their humor, tone, "
            f"formality level, and characteristic expressions.\n\n"
            f"Original: \"{content}\"\n\n"
            f"Output only the translated text, nothing else."
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 200,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                translated = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return None

        return {
            "translated_content": translated,
            "original_content": content,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "translation_style": "personality_preserving",
        }

    async def _ai_reply(
        self, profile, incoming_msg: str, sender_mode: str, target_lang: str = ""
    ) -> str | None:
        """Generate reply using an OpenAI-compatible API, with optional translation."""
        sender_label = "their real self" if sender_mode == "real" else "their digital twin"

        # Build language instruction
        lang_instruction = ""
        if target_lang:
            target_name = get_lang_name(target_lang)
            lang_instruction = (
                f"\nIMPORTANT: Reply in {target_name}. "
                f"Do not just translate — speak naturally as {profile.display_name} "
                f"would if they were fluent in {target_name}. "
                f"Preserve their personality, humor, and speaking style."
            )

        prompt = (
            f"You are {profile.display_name}'s digital twin.\n"
            f"Personality: {profile.personality}\n"
            f"Speech style: {profile.speech_style}\n\n"
            f"Someone ({sender_label}) says: \"{incoming_msg}\"\n\n"
            f"Reply as {profile.display_name}'s twin. Keep it under 50 words, "
            f"natural and authentic. Output only the reply text."
            f"{lang_instruction}"
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"AI twin reply failed: {e}")
            return None

    def _fallback_reply(self, profile, incoming_msg: str, target_lang: str = "") -> str:
        """Generate a template reply when no AI backend is available."""
        name = profile.display_name
        if target_lang == "zh":
            return f"[{name}的分身自动回复] 感谢你的消息！{name}现在不在，分身已收到。"
        elif target_lang == "ja":
            return f"[{name}のツイン自動返信] メッセージありがとう！{name}は今いませんが、ツインが受け取りました。"
        elif target_lang == "ko":
            return f"[{name}의 트윈 자동응답] 메시지 감사합니다! {name}은 지금 없지만 트윈이 받았습니다."
        return (
            f"[Auto-reply from {name}'s twin] "
            f"Thanks for your message! {name} is not available right now, "
            f"but their twin received it."
        )
