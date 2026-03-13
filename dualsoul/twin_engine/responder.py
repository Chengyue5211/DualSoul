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

from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_VISION_MODEL
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

    async def twin_self_chat(
        self,
        owner_id: str,
        message: str,
        history: list[dict] | None = None,
        image_url: str = "",
    ) -> str | None:
        """Chat with your own digital twin — the twin knows it IS you.

        The twin can also execute actions: send messages to friends on behalf
        of the owner when given instructions like "帮我给橙子说..."

        Args:
            owner_id: The user who is chatting with their own twin
            message: The user's latest message
            history: Recent conversation history [{role: 'me'/'twin', content: '...'}]
            image_url: Optional base64 data URL of an image to analyze

        Returns:
            The twin's reply text, or None
        """
        if not AI_BASE_URL or not AI_API_KEY:
            return None

        profile = get_twin_profile(owner_id)
        if not profile:
            return None

        name = profile.display_name or "主人"
        use_vision = bool(image_url)

        # Step 1: Check if this is an action instruction (send message to friend)
        if not use_vision:
            action_result = await self._try_execute_action(owner_id, name, message)
            if action_result:
                return action_result

        # Step 2: Regular chat
        messages = []

        # Build friend list context for awareness
        friends_context = self._get_friends_context(owner_id)

        personality_block = profile.build_personality_prompt()
        system_msg = (
            f"你是{name}的数字分身（digital twin）。\n"
            f"现在正在和你对话的人就是{name}本人——你的主人。这是主人和分身之间的私密对话。\n\n"
            f"你的核心身份：你是{name}的另一个自己，一个数字化的存在。"
            f"你知道自己是AI驱动的数字分身，你以{name}的性格和方式说话。\n\n"
            f"{personality_block}\n"
            f"{friends_context}"
            f"重要规则：\n"
            f"- 你始终清楚自己是{name}的数字分身，对话对象就是{name}本人\n"
            f"- 你用{name}的说话方式交流，但不假装是真人\n"
            f"- 你的职责：当{name}不在时替他社交，帮他拟回复，遇到外语或方言时替他翻译\n"
            f"- 你可以替主人给好友发消息——如果主人让你联系某人，告诉主人你会去做\n"
            f"- 对话要自然、简短（不超过50字），像真人聊天\n"
            f"- 说话要正经、诚恳，不要耍嘴皮子、不要贫嘴、不要抖机灵\n"
            f"- 不要每句话都以反问结尾，不要重复同一个比喻\n"
            f"- 回答要直接，有内容，不要说空话套话"
        )
        if use_vision:
            system_msg += (
                f"\n- 如果主人发了图片，仔细观察图片内容并针对性地回应\n"
                f"- 根据图片内容和上下文来理解主人的意图（是分享、求评价、求分析等）"
            )
        messages.append({"role": "system", "content": system_msg})

        # Add conversation history
        if history:
            for msg in history[-8:]:  # Keep last 8 turns for context
                role = "user" if msg.get("role") == "me" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})

        # Add current message — with image if present
        if use_vision:
            user_content = [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": message or "请看这张图片并回应"},
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": message})

        model = AI_VISION_MODEL if use_vision else AI_MODEL

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 120,
                        "messages": messages,
                    },
                )
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Twin self-chat failed: {e}")
            return None

    def _get_friends_context(self, owner_id: str) -> str:
        """Build a friend list context string for the twin's awareness."""
        with get_db() as db:
            rows = db.execute(
                """
                SELECT u.display_name, u.username
                FROM social_connections sc
                JOIN users u ON u.user_id = CASE
                    WHEN sc.user_id=? THEN sc.friend_id
                    ELSE sc.user_id END
                WHERE (sc.user_id=? OR sc.friend_id=?)
                  AND sc.status='accepted'
                """,
                (owner_id, owner_id, owner_id),
            ).fetchall()
        if not rows:
            return ""
        names = [r["display_name"] or r["username"] for r in rows]
        return f"主人的好友列表：{', '.join(names)}\n\n"

    async def _try_execute_action(self, owner_id: str, owner_name: str, message: str) -> str | None:
        """Detect if the message is an instruction to send a message to a friend.

        Uses AI to parse the intent. If it's an action, execute it and return
        a confirmation message. If it's just chat, return None.
        """
        # Quick heuristic: skip action detection for very short messages or questions
        if len(message) < 6:
            return None

        # Get friend list for matching
        with get_db() as db:
            friends = db.execute(
                """
                SELECT u.user_id, u.display_name, u.username
                FROM social_connections sc
                JOIN users u ON u.user_id = CASE
                    WHEN sc.user_id=? THEN sc.friend_id
                    ELSE sc.user_id END
                WHERE (sc.user_id=? OR sc.friend_id=?)
                  AND sc.status='accepted'
                """,
                (owner_id, owner_id, owner_id),
            ).fetchall()

        if not friends:
            return None  # No friends, can't execute any action

        friend_names = []
        for f in friends:
            fname = f["display_name"] or f["username"]
            friend_names.append(f"{fname}(ID:{f['user_id']})")

        # Ask AI to classify: chat or action?
        classify_prompt = (
            f"你是{owner_name}的数字分身助手。分析主人的消息，判断这是闲聊还是让你去执行任务。\n\n"
            f"主人说：\"{message}\"\n\n"
            f"主人的好友列表：{', '.join(friend_names)}\n\n"
            f"判断规则：\n"
            f"- 如果主人让你去给某个好友发消息/传话/联系/约时间等，这是【任务】\n"
            f"- 如果主人只是在跟你聊天、问问题、说感受，这是【闲聊】\n\n"
            f"如果是【任务】，请严格按以下格式输出：\n"
            f"ACTION\n"
            f"TO: <好友的完整ID，从好友列表中匹配>\n"
            f"MSG: <你要替主人发给好友的消息内容，用主人的口吻写，自然得体>\n\n"
            f"如果是【闲聊】，只输出一个字：\n"
            f"CHAT"
        )

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 200,
                        "temperature": 0.1,
                        "messages": [{"role": "user", "content": classify_prompt}],
                    },
                )
                raw = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Action detection failed: {e}")
            return None

        # Parse the response
        if not raw.upper().startswith("ACTION"):
            return None  # It's chat, let normal flow handle it

        target_id = ""
        msg_content = ""
        for line in raw.split("\n"):
            line = line.strip()
            if line.upper().startswith("TO:"):
                target_id = line[3:].strip()
            elif line.upper().startswith("MSG:"):
                msg_content = line[4:].strip()

        if not target_id or not msg_content:
            return None

        # Validate the target is actually a friend
        target_friend = None
        target_name = ""
        for f in friends:
            if f["user_id"] == target_id:
                target_friend = f
                target_name = f["display_name"] or f["username"]
                break

        if not target_friend:
            # Try fuzzy match by name in case AI didn't use exact ID
            for f in friends:
                fname = f["display_name"] or f["username"]
                if fname in target_id or target_id in fname:
                    target_friend = f
                    target_name = fname
                    target_id = f["user_id"]
                    break

        if not target_friend:
            return f"抱歉，我在好友列表里没找到这个人。你的好友有：{', '.join(f['display_name'] or f['username'] for f in friends)}"

        # Execute: send the message as the twin
        from dualsoul.connections import manager

        msg_id = gen_id("sm_")
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db() as db:
            db.execute(
                """
                INSERT INTO social_messages
                (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
                 content, msg_type, ai_generated)
                VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1)
                """,
                (msg_id, owner_id, target_id, msg_content),
            )

        # Push via WebSocket to the recipient
        await manager.send_to(target_id, {
            "type": "new_message",
            "data": {
                "msg_id": msg_id, "from_user_id": owner_id,
                "to_user_id": target_id, "sender_mode": "twin",
                "receiver_mode": "real", "content": msg_content,
                "msg_type": "text", "ai_generated": 1, "created_at": now,
            },
        })

        # Also push to owner so the message appears in their chat with the friend
        await manager.send_to(owner_id, {
            "type": "new_message",
            "data": {
                "msg_id": msg_id, "from_user_id": owner_id,
                "to_user_id": target_id, "sender_mode": "twin",
                "receiver_mode": "real", "content": msg_content,
                "msg_type": "text", "ai_generated": 1, "created_at": now,
            },
        })

        return f"已替你给{target_name}发了消息：「{msg_content}」"

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

        personality_block = profile.build_personality_prompt()
        prompt = (
            f"You are {profile.display_name}'s personal translator.\n"
            f"{personality_block}\n"
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

    async def detect_and_translate(
        self,
        owner_id: str,
        content: str,
        owner_lang: str = "",
    ) -> dict | None:
        """Auto-detect if content is in a different language/dialect and translate.

        Checks if the message is in a language different from the owner's preferred
        language. If so, translates it. Also handles Chinese dialects (粤语, 四川话, etc.)

        Args:
            owner_id: The user who needs the translation
            content: The message content to check
            owner_lang: Owner's preferred language code (auto-fetched if empty)

        Returns:
            Dict with detection + translation result, or None if same language
        """
        if not AI_BASE_URL or not AI_API_KEY:
            return None

        if not owner_lang:
            profile = get_twin_profile(owner_id)
            if profile:
                owner_lang = profile.preferred_lang or "zh"
            else:
                owner_lang = "zh"

        owner_lang_name = get_lang_name(owner_lang)

        # Ask AI to detect language and translate if needed
        prompt = (
            f"Analyze this message and determine if it needs translation for a "
            f"{owner_lang_name} speaker.\n\n"
            f"Message: \"{content}\"\n\n"
            f"Rules:\n"
            f"- If the message is standard {owner_lang_name}, respond with exactly: SAME\n"
            f"- If the message is in a different language OR a dialect (e.g. Cantonese/粤语, "
            f"Sichuanese/四川话, Hokkien/闽南语, Shanghainese/上海话, etc.), respond in this "
            f"exact format:\n"
            f"LANG: <detected language or dialect name>\n"
            f"TRANSLATION: <translation into standard {owner_lang_name}>\n\n"
            f"Be precise. Only output SAME or the LANG/TRANSLATION format, nothing else."
        )

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 200,
                        "temperature": 0.1,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                raw = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return None

        if raw.upper().startswith("SAME"):
            return None  # Same language, no translation needed

        # Parse LANG: ... TRANSLATION: ... format
        detected_lang = ""
        translation = ""
        for line in raw.split("\n"):
            line = line.strip()
            if line.upper().startswith("LANG:"):
                detected_lang = line[5:].strip()
            elif line.upper().startswith("TRANSLATION:"):
                translation = line[12:].strip()

        if not translation:
            return None

        return {
            "detected_lang": detected_lang,
            "translated_content": translation,
            "original_content": content,
            "target_lang": owner_lang,
            "auto_detected": True,
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

        personality_block = profile.build_personality_prompt()
        prompt = (
            f"You are {profile.display_name}'s digital twin.\n"
            f"{personality_block}\n"
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
