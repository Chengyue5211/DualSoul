"""Tests for twin_events, narrative_memory, and twin_reactions modules."""

import asyncio
import logging

import pytest

# ---------------------------------------------------------------------------
# twin_events tests
# ---------------------------------------------------------------------------


class TestTwinEventBus:
    """Test the fire-and-forget event bus in twin_events."""

    def test_emit_fires_handler(self):
        """emit() should invoke registered async handlers."""
        from dualsoul.twin_engine.twin_events import _handlers, emit, on

        called_with = {}

        # Register a test handler on a unique event name
        @on("test_emit_fires")
        async def _handler(data):
            called_with.update(data)

        # We need a running event loop to process the fire-and-forget task
        loop = asyncio.new_event_loop()
        try:
            # emit schedules via ensure_future; run loop briefly to execute
            loop.run_until_complete(_run_emit_and_wait(
                "test_emit_fires", {"key": "value"}
            ))
        finally:
            loop.close()

        assert called_with.get("key") == "value"
        # Cleanup
        _handlers.pop("test_emit_fires", None)

    def test_debounce_calls_handler_once(self):
        """Rapid emits with debounce_key should only call handler once."""
        from dualsoul.twin_engine.twin_events import (
            DEBOUNCE_WINDOWS,
            _handlers,
            emit,
            on,
        )

        call_count = 0

        @on("test_debounce_event")
        async def _handler(data):
            nonlocal call_count
            call_count += 1

        # Set a short debounce window for testing
        DEBOUNCE_WINDOWS["test_debounce_event"] = 0.1  # 100ms

        loop = asyncio.new_event_loop()
        try:
            async def _rapid_emits():
                for i in range(5):
                    emit("test_debounce_event", {"i": i}, debounce_key="same")
                # Wait for debounce window to expire + processing
                await asyncio.sleep(0.3)

            loop.run_until_complete(_rapid_emits())
        finally:
            loop.close()

        # Handler should have been called exactly once (debounced)
        assert call_count == 1
        # Cleanup
        _handlers.pop("test_debounce_event", None)
        DEBOUNCE_WINDOWS.pop("test_debounce_event", None)

    def test_handler_exception_doesnt_crash(self):
        """A handler that raises should not break the event system."""
        from dualsoul.twin_engine.twin_events import _handlers, emit, on

        @on("test_exception_event")
        async def _bad_handler(data):
            raise ValueError("intentional test error")

        # Should not raise
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run_emit_and_wait(
                "test_exception_event", {"x": 1}
            ))
        finally:
            loop.close()

        # If we reach here, the exception was caught internally
        _handlers.pop("test_exception_event", None)


async def _run_emit_and_wait(event_type: str, data: dict, delay: float = 0.1):
    """Helper: emit an event and wait briefly for async handlers to execute."""
    from dualsoul.twin_engine.twin_events import emit
    emit(event_type, data)
    await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# narrative_memory tests
# ---------------------------------------------------------------------------


class TestNarrativeMemory:
    """Test narrative_memory data-flow functions (no AI calls needed)."""

    def test_find_unsummarized_empty_db(self, client):
        """find_unsummarized_conversations returns [] for a user with no messages."""
        from dualsoul.twin_engine.narrative_memory import find_unsummarized_conversations
        result = find_unsummarized_conversations("nonexistent_user_id_xyz")
        assert result == []

    def test_get_narrative_context_empty(self, client):
        """get_narrative_context returns [] when no memories exist."""
        from dualsoul.twin_engine.narrative_memory import get_narrative_context
        result = get_narrative_context("no_user", "no_friend")
        assert result == []

    def test_cleanup_old_memories_no_crash(self, client):
        """cleanup_old_memories runs without error on empty DB."""
        from dualsoul.twin_engine.narrative_memory import cleanup_old_memories
        # Should not raise
        cleanup_old_memories(days=30)

    def test_conversation_segmentation(self, client, alice_token):
        """Messages with a 10+ minute gap should be segmented into separate conversations."""
        from dualsoul.database import gen_id, get_db
        from dualsoul.twin_engine.narrative_memory import find_unsummarized_conversations

        # Get alice's user_id
        with get_db() as db:
            alice = db.execute(
                "SELECT user_id FROM users WHERE username='alice'"
            ).fetchone()
        if not alice:
            pytest.skip("alice not registered")
        alice_id = alice["user_id"]

        # Create a fake friend
        friend_id = gen_id("u_")
        with get_db() as db:
            db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, password_hash, display_name) "
                "VALUES (?, 'seg_test_friend', 'x', 'SegFriend')",
                (friend_id,),
            )

        # Insert messages with a >10 min gap in the middle
        # Segment 1: two messages close together
        # Segment 2: two messages close together, but 15 min after segment 1
        from datetime import datetime, timedelta
        base = datetime.now() - timedelta(hours=1)
        times = [
            base.strftime("%Y-%m-%d %H:%M:%S"),
            (base + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
            (base + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
            (base + timedelta(minutes=16)).strftime("%Y-%m-%d %H:%M:%S"),
        ]

        with get_db() as db:
            for i, t in enumerate(times):
                sender = alice_id if i % 2 == 0 else friend_id
                receiver = friend_id if i % 2 == 0 else alice_id
                db.execute(
                    """INSERT INTO social_messages
                       (msg_id, from_user_id, to_user_id, content, sender_mode,
                        msg_type, created_at)
                       VALUES (?, ?, ?, ?, 'real', 'text', ?)""",
                    (gen_id("sm_"), sender, receiver, f"test msg {i}", t),
                )

        segments = find_unsummarized_conversations(alice_id, gap_minutes=10)
        # Should find at least 2 segments (the two groups separated by 15 min gap)
        friend_segments = [s for s in segments if s["friend_id"] == friend_id]
        assert len(friend_segments) == 2, (
            f"Expected 2 segments, got {len(friend_segments)}"
        )


# ---------------------------------------------------------------------------
# twin_reactions tests
# ---------------------------------------------------------------------------


class TestTwinReactions:
    """Test that twin_reactions registers handlers correctly."""

    def test_handlers_registered(self):
        """Importing twin_reactions should register handlers in the event bus."""
        # Force import so decorators run
        import dualsoul.twin_engine.twin_reactions  # noqa: F401
        from dualsoul.twin_engine.twin_events import _handlers

        expected_events = [
            "friend_online",
            "friend_offline",
            "user_registered",
            "plaza_post_created",
            "relationship_temp_changed",
            "message_sent",
        ]
        for ev in expected_events:
            assert ev in _handlers, f"No handler registered for '{ev}'"
            assert len(_handlers[ev]) > 0, f"Handler list for '{ev}' is empty"
