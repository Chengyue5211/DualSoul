"""Twin Event Bus — fire-and-forget event system for twin reactions.

Instead of waiting for the 30-min polling loop, twins react to events
immediately. emit() launches async handlers via asyncio.ensure_future()
so the caller (e.g., message send, WS connect) never blocks.

Usage at hook points:
    from dualsoul.twin_engine.twin_events import emit
    emit("message_sent", {"from_user_id": uid, "to_user_id": fid})
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Registry: event_type -> list of async handler functions
_handlers: dict[str, list[Callable[..., Coroutine]]] = defaultdict(list)

# Debounce state: (event_type, debounce_key) -> asyncio.Task
_debounce_tasks: dict[tuple[str, str], asyncio.Task] = {}

# Per-event debounce windows (seconds). Events not listed fire immediately.
DEBOUNCE_WINDOWS: dict[str, float] = {
    "message_sent": 10.0,
    "friend_online": 5.0,
    "relationship_temp_changed": 60.0,
}


def on(event_type: str):
    """Decorator to register an async handler for an event type."""
    def decorator(fn):
        _handlers[event_type].append(fn)
        logger.debug(f"[TwinEvent] Registered handler {fn.__name__} for '{event_type}'")
        return fn
    return decorator


def emit(event_type: str, data: dict, debounce_key: str | None = None):
    """Fire-and-forget: schedule all handlers for this event.

    Args:
        event_type: The event name (e.g., "message_sent")
        data: Event payload dict
        debounce_key: Optional key for debouncing. If set and the event_type
            has a debounce window, the handler is delayed and resets on each
            new emit with the same key.
    """
    handlers = _handlers.get(event_type)
    if not handlers:
        return

    window = DEBOUNCE_WINDOWS.get(event_type, 0) if debounce_key else 0

    if window > 0 and debounce_key:
        key = (event_type, debounce_key)
        # Cancel any pending debounced task for this key
        old_task = _debounce_tasks.pop(key, None)
        if old_task and not old_task.done():
            old_task.cancel()
        # Schedule a new delayed fire
        _debounce_tasks[key] = asyncio.ensure_future(
            _debounced_fire(key, window, event_type, data)
        )
    else:
        _fire(event_type, data)


async def _debounced_fire(key: tuple, delay: float, event_type: str, data: dict):
    """Wait `delay` seconds, then fire. Cancelled if a new emit resets the timer."""
    try:
        await asyncio.sleep(delay)
        _fire(event_type, data)
    except asyncio.CancelledError:
        pass  # Normal — debounce reset
    finally:
        _debounce_tasks.pop(key, None)


def _fire(event_type: str, data: dict):
    """Launch all handlers for the event as fire-and-forget tasks."""
    for handler in _handlers.get(event_type, []):
        asyncio.ensure_future(_safe_run(handler, event_type, data))


async def _safe_run(handler, event_type: str, data: dict):
    """Run a handler with exception catching so one failure doesn't break others."""
    try:
        await handler(data)
    except Exception as e:
        logger.error(
            f"[TwinEvent] Handler {handler.__name__} failed for '{event_type}': {e}",
            exc_info=True,
        )
