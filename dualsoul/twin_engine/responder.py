"""Twin responder — AI-powered auto-reply engine.

When a message is sent to someone's digital twin (receiver_mode='twin'),
the twin generates a response based on the owner's personality profile.

Supports any OpenAI-compatible API (OpenAI, Qwen, DeepSeek, Ollama, etc.).
Falls back to template responses when no AI backend is configured.
"""

import logging

import httpx

from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import gen_id, get_db
from dualsoul.twin_engine.personality import get_twin_profile

logger = logging.getLogger(__name__)


class TwinResponder:
    """Generate replies as a user's digital twin."""

    async def generate_reply(
        self,
        twin_owner_id: str,
        from_user_id: str,
        incoming_msg: str,
        sender_mode: str,
    ) -> dict | None:
        """Generate a twin auto-reply.

        Args:
            twin_owner_id: The user whose twin should respond
            from_user_id: The user who sent the message
            incoming_msg: The incoming message content
            sender_mode: Whether the sender is 'real' or 'twin'

        Returns:
            Dict with msg_id, content, ai_generated, or None if failed
        """
        profile = get_twin_profile(twin_owner_id)
        if not profile:
            return None

        # Generate reply text
        if AI_BASE_URL and AI_API_KEY:
            reply_text = await self._ai_reply(profile, incoming_msg, sender_mode)
        else:
            reply_text = self._fallback_reply(profile, incoming_msg)

        if not reply_text:
            return None

        # Store the reply message
        reply_id = gen_id("sm_")
        with get_db() as db:
            db.execute(
                """
                INSERT INTO social_messages
                (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                 content, msg_type, ai_generated)
                VALUES (?, ?, ?, 'twin', ?, ?, 'text', 1)
                """,
                (reply_id, twin_owner_id, from_user_id, sender_mode, reply_text),
            )

        return {"msg_id": reply_id, "content": reply_text, "ai_generated": True}

    async def _ai_reply(self, profile, incoming_msg: str, sender_mode: str) -> str | None:
        """Generate reply using an OpenAI-compatible API."""
        sender_label = "their real self" if sender_mode == "real" else "their digital twin"
        prompt = (
            f"You are {profile.display_name}'s digital twin.\n"
            f"Personality: {profile.personality}\n"
            f"Speech style: {profile.speech_style}\n\n"
            f"Someone ({sender_label}) says: \"{incoming_msg}\"\n\n"
            f"Reply as {profile.display_name}'s twin. Keep it under 50 words, "
            f"natural and authentic. Output only the reply text."
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

    def _fallback_reply(self, profile, incoming_msg: str) -> str:
        """Generate a template reply when no AI backend is available."""
        name = profile.display_name
        return (
            f"[Auto-reply from {name}'s twin] "
            f"Thanks for your message! {name} is not available right now, "
            f"but their twin received it."
        )
