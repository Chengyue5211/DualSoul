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
    preferred_lang TEXT DEFAULT ''
        CHECK(preferred_lang IN ('', 'zh', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'ru', 'ar', 'hi', 'th', 'vi', 'id', 'auto')),
    avatar TEXT DEFAULT '',
    twin_avatar TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS social_connections (
    conn_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    friend_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending'
        CHECK(status IN ('pending', 'accepted', 'blocked', 'deleted')),
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
    original_content TEXT DEFAULT '',
    original_lang TEXT DEFAULT '',
    target_lang TEXT DEFAULT '',
    translation_style TEXT DEFAULT ''
        CHECK(translation_style IN ('', 'literal', 'personality_preserving')),
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


MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN twin_auto_reply INTEGER DEFAULT 1",
    "ALTER TABLE social_messages ADD COLUMN auto_reply INTEGER DEFAULT 0",
    "ALTER TABLE social_messages ADD COLUMN metadata TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN voice_sample TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN twin_source TEXT DEFAULT 'local'",
    "ALTER TABLE users ADD COLUMN gender TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN reg_source TEXT DEFAULT 'dualsoul'",
]


# Schema V2 — Twin import from Nianlun (年轮分身导入)
SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS twin_profiles (
    profile_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'nianlun',
    version INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,

    -- Identity
    twin_name TEXT DEFAULT '',
    training_status TEXT DEFAULT '',
    quality_score REAL DEFAULT 0.0,
    self_awareness REAL DEFAULT 0.0,
    interaction_count INTEGER DEFAULT 0,

    -- Five-dimension personality (五维人格骨架)
    dim_judgement TEXT DEFAULT '',
    dim_cognition TEXT DEFAULT '',
    dim_expression TEXT DEFAULT '',
    dim_relation TEXT DEFAULT '',
    dim_sovereignty TEXT DEFAULT '',

    -- Structured personality
    value_order TEXT DEFAULT '',
    behavior_patterns TEXT DEFAULT '',
    speech_style TEXT DEFAULT '',
    boundaries TEXT DEFAULT '',

    -- Certificate (身份证书)
    certificate TEXT DEFAULT '',

    -- Full import payload (cold storage)
    raw_import TEXT DEFAULT '',

    imported_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),

    UNIQUE(user_id, version)
);
CREATE INDEX IF NOT EXISTS idx_tp_user_active ON twin_profiles(user_id, is_active);

CREATE TABLE IF NOT EXISTS twin_memories (
    memory_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    memory_type TEXT NOT NULL
        CHECK(memory_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,

    summary_text TEXT NOT NULL,
    emotional_tone TEXT DEFAULT '',
    themes TEXT DEFAULT '',

    key_events TEXT DEFAULT '',
    growth_signals TEXT DEFAULT '',

    source TEXT DEFAULT 'nianlun',
    imported_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tm_user_type ON twin_memories(user_id, memory_type, period_start);
CREATE INDEX IF NOT EXISTS idx_tm_user_recent ON twin_memories(user_id, period_end DESC);

CREATE TABLE IF NOT EXISTS twin_entities (
    entity_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL
        CHECK(entity_type IN ('person', 'place', 'thing', 'event', 'concept')),
    importance_score REAL DEFAULT 0.0,
    mention_count INTEGER DEFAULT 0,
    context TEXT DEFAULT '',
    relations TEXT DEFAULT '',

    source TEXT DEFAULT 'nianlun',
    imported_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_te_user_type ON twin_entities(user_id, entity_type, importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_te_user_name ON twin_entities(user_id, entity_name);
"""


def init_db():
    """Initialize database with schema and run migrations."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.executescript(SCHEMA_V2)
    # Run migrations (idempotent — skip if column already exists)
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # Column already exists
    # Migrate social_connections: add 'deleted' to status CHECK constraint
    # SQLite can't ALTER CHECK, so recreate table if needed
    try:
        conn.execute("UPDATE social_connections SET status='deleted' WHERE 0", ())
    except sqlite3.IntegrityError:
        # CHECK constraint doesn't include 'deleted' — recreate table
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS social_connections_new (
                conn_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                friend_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending', 'accepted', 'blocked', 'deleted')),
                created_at TEXT DEFAULT (datetime('now','localtime')),
                accepted_at TEXT,
                UNIQUE(user_id, friend_id)
            );
            INSERT OR IGNORE INTO social_connections_new SELECT * FROM social_connections;
            DROP TABLE social_connections;
            ALTER TABLE social_connections_new RENAME TO social_connections;
            CREATE INDEX IF NOT EXISTS idx_sc_user ON social_connections(user_id, status);
            CREATE INDEX IF NOT EXISTS idx_sc_friend ON social_connections(friend_id, status);
        """)
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
