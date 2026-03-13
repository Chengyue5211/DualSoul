"""WebSocket connection manager — tracks online users for real-time push."""

import logging
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage active WebSocket connections by user_id."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._last_active: dict[str, datetime] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        # Close existing connection if the same user reconnects
        old = self._connections.get(user_id)
        if old:
            try:
                await old.close(code=4000, reason="Replaced by new connection")
            except Exception:
                pass
        self._connections[user_id] = websocket
        self._last_active[user_id] = datetime.now()
        logger.info(f"WS connected: {user_id} (total: {len(self._connections)})")

    def disconnect(self, user_id: str):
        """Remove a disconnected user."""
        self._connections.pop(user_id, None)
        logger.info(f"WS disconnected: {user_id} (total: {len(self._connections)})")

    def is_online(self, user_id: str) -> bool:
        """Check if a user has an active WebSocket."""
        return user_id in self._connections

    def last_active(self, user_id: str) -> datetime | None:
        """Get the last activity time for a user."""
        return self._last_active.get(user_id)

    def touch(self, user_id: str):
        """Update last-active timestamp."""
        self._last_active[user_id] = datetime.now()

    async def send_to(self, user_id: str, data: dict) -> bool:
        """Send JSON data to a specific user. Returns True if sent."""
        ws = self._connections.get(user_id)
        if not ws:
            return False
        try:
            await ws.send_json(data)
            return True
        except Exception:
            self.disconnect(user_id)
            return False

    async def broadcast(self, user_ids: list[str], data: dict):
        """Send JSON data to multiple users."""
        for uid in user_ids:
            await self.send_to(uid, data)


# Singleton instance — imported by routers
manager = ConnectionManager()
