"""Narrative Memory — conversation summarization, memory management, and rollups.

Gives the twin real memory of conversations, not just numbers.
After each conversation ends (10-min gap), AI generates a narrative summary.
These summaries are injected into the twin's prompt for continuity.
"""

import json
import logging
from datetime import datetime, timedelta

import httpx

from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import gen_id, get_db

logger = logging.getLogger(__name__)

# --- Constants ---
CONVERSATION_GAP_MINUTES = 10
MAX_MESSAGES_PER_SUMMARY = 30
MAX_SEGMENTS_PER_CYCLE = 5
CLEANUP_DAYS = 30


def find_unsummarized_conversations(
    user_id: str, gap_minutes: int = CONVERSATION_GAP_MINUTES
) -> list[dict]:
    """Find conversation segments that ended 10+ min ago and haven't been summarized.

    Returns list of {friend_id, messages: [...], period_start, period_end}.
    """
    cutoff = datetime.now() - timedelta(minutes=gap_minutes)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as db:
        # Fetch recent messages (last 24 hours) involving this user
        rows = db.execute(
            """SELECT msg_id, from_user_id, to_user_id, content, sender_mode,
                      created_at, ai_generated
               FROM social_messages
               WHERE (from_user_id=? OR to_user_id=?)
                 AND from_user_id != to_user_id
                 AND msg_type='text' AND content != ''
                 AND created_at > datetime('now','localtime','-24 hours')
                 AND created_at < ?
               ORDER BY created_at ASC""",
            (user_id, user_id, cutoff_str),
        ).fetchall()

    if not rows:
        return []

    # Group messages by friend_id
    friend_groups: dict[str, list[dict]] = {}
    for r in rows:
        fid = r["to_user_id"] if r["from_user_id"] == user_id else r["from_user_id"]
        if fid not in friend_groups:
            friend_groups[fid] = []
        friend_groups[fid].append(dict(r))

    # Split each friend's messages into segments at gap boundaries
    segments = []
    for fid, msgs in friend_groups.items():
        current_segment: list[dict] = [msgs[0]]
        for i in range(1, len(msgs)):
            prev_time = datetime.strptime(msgs[i - 1]["created_at"][:19], "%Y-%m-%d %H:%M:%S")
            curr_time = datetime.strptime(msgs[i]["created_at"][:19], "%Y-%m-%d %H:%M:%S")
            if (curr_time - prev_time).total_seconds() > gap_minutes * 60:
                # Gap detected — close current segment
                segments.append({
                    "friend_id": fid,
                    "messages": current_segment,
                    "period_start": current_segment[0]["created_at"],
                    "period_end": current_segment[-1]["created_at"],
                })
                current_segment = [msgs[i]]
            else:
                current_segment.append(msgs[i])
        # Close last segment
        if current_segment:
            segments.append({
                "friend_id": fid,
                "messages": current_segment,
                "period_start": current_segment[0]["created_at"],
                "period_end": current_segment[-1]["created_at"],
            })

    # Filter out already-summarized segments
    result = []
    with get_db() as db:
        for seg in segments:
            if len(seg["messages"]) < 2:
                continue  # Skip single-message "conversations"
            existing = db.execute(
                """SELECT memory_id FROM twin_memories
                   WHERE user_id=? AND friend_id=? AND memory_type='conversation'
                     AND period_start=?""",
                (user_id, seg["friend_id"], seg["period_start"]),
            ).fetchone()
            if not existing:
                result.append(seg)

    return result


async def summarize_conversation(
    user_id: str,
    friend_id: str,
    messages: list[dict],
) -> dict | None:
    """Summarize a conversation segment into a narrative memory entry.

    Returns the saved memory dict, or None if AI call fails.
    """
    if not AI_BASE_URL or not AI_API_KEY:
        return None

    # Get display names
    with get_db() as db:
        user_row = db.execute(
            "SELECT display_name, username FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        friend_row = db.execute(
            "SELECT display_name, username FROM users WHERE user_id=?", (friend_id,)
        ).fetchone()

    user_name = (user_row["display_name"] or user_row["username"]) if user_row else "我"
    friend_name = (friend_row["display_name"] or friend_row["username"]) if friend_row else "对方"

    # Build conversation text (limit to last MAX_MESSAGES_PER_SUMMARY)
    recent = messages[-MAX_MESSAGES_PER_SUMMARY:]
    conv_lines = []
    for m in recent:
        sender = user_name if m["from_user_id"] == user_id else friend_name
        mode_tag = "[分身]" if m["sender_mode"] == "twin" or m.get("ai_generated") else ""
        conv_lines.append(f"{sender}{mode_tag}: {m['content']}")
    conv_text = "\n".join(conv_lines)

    period = f"{messages[0]['created_at'][:16]} ~ {messages[-1]['created_at'][:16]}"

    prompt = f"""请根据以下对话记录，写一段简短的叙事摘要。

对话双方: {user_name} 和 {friend_name}
时间: {period}

对话内容:
{conv_text}

请输出JSON（不要输出其他内容）:
{{
  "summary": "2-3句话的叙事摘要，像日记一样自然，用第一人称'我'代表{user_name}",
  "emotional_tone": "warm/playful/serious/supportive/tense/neutral 之一",
  "themes": ["话题关键词", "最多3个"],
  "key_events": ["重要事件，0-3个，没有就空数组"],
  "relationship_signal": "warming/stable/cooling 之一"
}}

要求：用中文，口语化，summary不超过100字。"""

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODEL,
                    "max_tokens": 300,
                    "temperature": 0.7,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Parse JSON from AI response
        # Handle potential markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

    except Exception as e:
        logger.warning(f"[NarrativeMemory] Summarization failed for {user_id}↔{friend_id}: {e}")
        return None

    # Save to twin_memories
    memory_id = gen_id("nm_")
    summary = data.get("summary", "")[:500]
    tone = data.get("emotional_tone", "neutral")
    themes = json.dumps(data.get("themes", []), ensure_ascii=False)
    key_events = json.dumps(data.get("key_events", []), ensure_ascii=False)
    signal = data.get("relationship_signal", "stable")

    with get_db() as db:
        db.execute(
            """INSERT INTO twin_memories
               (memory_id, user_id, memory_type, period_start, period_end,
                summary_text, emotional_tone, themes, key_events,
                source, friend_id, message_count, relationship_signal)
               VALUES (?, ?, 'conversation', ?, ?, ?, ?, ?, ?, 'dualsoul', ?, ?, ?)""",
            (memory_id, user_id,
             messages[0]["created_at"], messages[-1]["created_at"],
             summary, tone, themes, key_events,
             friend_id, len(messages), signal),
        )

    logger.info(
        f"[NarrativeMemory] Saved conversation memory {memory_id}: "
        f"{user_id}↔{friend_id}, {len(messages)} msgs, tone={tone}, signal={signal}"
    )
    return {
        "memory_id": memory_id,
        "summary": summary,
        "emotional_tone": tone,
        "themes": data.get("themes", []),
        "key_events": data.get("key_events", []),
        "relationship_signal": signal,
    }


def get_narrative_context(
    user_id: str, friend_id: str, limit: int = 3
) -> list[dict]:
    """Fetch recent narrative memories for a user-friend pair.

    Returns [{summary, tone, period, themes}] for prompt injection.
    """
    with get_db() as db:
        rows = db.execute(
            """SELECT summary_text, emotional_tone, period_start, period_end, themes
               FROM twin_memories
               WHERE user_id=? AND friend_id=? AND source='dualsoul'
                 AND memory_type IN ('conversation', 'daily')
               ORDER BY period_end DESC LIMIT ?""",
            (user_id, friend_id, limit),
        ).fetchall()

    result = []
    for r in rows:
        period = r["period_start"][:10] if r["period_start"] else ""
        themes = []
        try:
            themes = json.loads(r["themes"] or "[]")
        except Exception:
            pass
        result.append({
            "summary": r["summary_text"],
            "tone": r["emotional_tone"],
            "period": period,
            "themes": themes,
        })
    return result


def get_user_recent_memories(user_id: str, limit: int = 5) -> list[dict]:
    """Fetch recent memories across all friends (for general twin context).

    Returns daily/weekly rollups for overall context.
    """
    with get_db() as db:
        rows = db.execute(
            """SELECT summary_text, emotional_tone, period_start, friend_id, themes
               FROM twin_memories
               WHERE user_id=? AND source='dualsoul'
                 AND memory_type IN ('conversation', 'daily')
               ORDER BY period_end DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()

    return [
        {
            "summary": r["summary_text"],
            "tone": r["emotional_tone"],
            "period": r["period_start"][:10] if r["period_start"] else "",
            "friend_id": r["friend_id"],
        }
        for r in rows
    ]


async def rollup_daily(user_id: str, date_str: str):
    """Aggregate a day's conversation memories into daily summaries per friend.

    date_str format: '2026-03-15'
    """
    if not AI_BASE_URL or not AI_API_KEY:
        return

    with get_db() as db:
        # Check if daily rollup already exists for this date
        existing = db.execute(
            """SELECT memory_id FROM twin_memories
               WHERE user_id=? AND memory_type='daily'
                 AND period_start LIKE ? AND source='dualsoul'""",
            (user_id, f"{date_str}%"),
        ).fetchone()
        if existing:
            return  # Already rolled up

        # Get all conversation memories for the day, grouped by friend
        convos = db.execute(
            """SELECT friend_id, summary_text, emotional_tone
               FROM twin_memories
               WHERE user_id=? AND memory_type='conversation'
                 AND source='dualsoul' AND period_start LIKE ?
               ORDER BY period_start ASC""",
            (user_id, f"{date_str}%"),
        ).fetchall()

    if not convos:
        return

    # Group by friend
    friend_summaries: dict[str, list[str]] = {}
    for c in convos:
        fid = c["friend_id"]
        if fid not in friend_summaries:
            friend_summaries[fid] = []
        friend_summaries[fid].append(c["summary_text"])

    # Generate daily rollup for each friend
    for fid, summaries in friend_summaries.items():
        if len(summaries) == 1:
            # Only one conversation — just copy it as daily
            daily_summary = summaries[0]
        else:
            # Multiple conversations — AI merge
            merge_prompt = (
                f"以下是今天的几段对话摘要，请合并成一段简短的日记式总结（2-3句话，不超过80字）：\n\n"
                + "\n".join(f"- {s}" for s in summaries)
            )
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        f"{AI_BASE_URL}/chat/completions",
                        headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": AI_MODEL, "max_tokens": 150,
                            "messages": [{"role": "user", "content": merge_prompt}],
                        },
                    )
                    daily_summary = resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"[NarrativeMemory] Daily rollup AI failed: {e}")
                daily_summary = " ".join(summaries)[:200]

        # Save daily memory
        with get_db() as db:
            db.execute(
                """INSERT INTO twin_memories
                   (memory_id, user_id, memory_type, period_start, period_end,
                    summary_text, source, friend_id, message_count)
                   VALUES (?, ?, 'daily', ?, ?, ?, 'dualsoul', ?, ?)""",
                (gen_id("nm_"), user_id,
                 f"{date_str} 00:00:00", f"{date_str} 23:59:59",
                 daily_summary, fid, len(summaries)),
            )

    logger.info(f"[NarrativeMemory] Daily rollup for {user_id} on {date_str}: {len(friend_summaries)} friends")


def cleanup_old_memories(days: int = CLEANUP_DAYS):
    """Delete conversation-level memories older than N days (replaced by daily rollups)."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        result = db.execute(
            """DELETE FROM twin_memories
               WHERE memory_type='conversation' AND source='dualsoul'
                 AND period_end < ?""",
            (cutoff,),
        )
    logger.info(f"[NarrativeMemory] Cleaned up conversation memories older than {days} days")
