"""DualSoul database — SQLite with WAL mode."""

import sqlite3
import uuid
from contextlib import contextmanager

from dualsoul.config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    current_mode TEXT DEFAULT 'real' CHECK(current_mode IN ('real', 'twin')),
    twin_personality TEXT DEFAULT '',
    twin_speech_style TEXT DEFAULT '',
    avatar TEXT DEFAULT '',
    twin_avatar TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS social_connections (
    conn_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    friend_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending'
        CHECK(status IN ('pending', 'accepted', 'blocked')),
    created_at TEXT DEFAULT (datetime('now','localtime')),
    accepted_at TEXT,
    UNIQUE(user_id, friend_id)
);
CREATE INDEX IF NOT EXISTS idx_sc_user ON social_connections(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sc_friend ON social_connections(friend_id, status);

CREATE TABLE IF NOT EXISTS social_messages (
    msg_id TEXT PRIMARY KEY,
    from_user_id TEXT NOT NULL,
    to_user_id TEXT NOT NULL,
    sender_mode TEXT DEFAULT 'real'
        CHECK(sender_mode IN ('real', 'twin')),
    receiver_mode TEXT DEFAULT 'real'
        CHECK(receiver_mode IN ('real', 'twin')),
    content TEXT NOT NULL,
    msg_type TEXT DEFAULT 'text'
        CHECK(msg_type IN ('text', 'image', 'voice', 'system')),
    is_read INTEGER DEFAULT 0,
    ai_generated INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sm_from ON social_messages(from_user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sm_to ON social_messages(to_user_id, is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_sm_conv ON social_messages(from_user_id, to_user_id, created_at);
"""


def init_db():
    """Initialize database with schema."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """Get a database connection as a context manager."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def gen_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"
