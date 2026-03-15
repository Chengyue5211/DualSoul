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
    "ALTER TABLE users ADD COLUMN invited_by TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN invite_count INTEGER DEFAULT 0",
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


# Schema V3 — Agent Plaza (分身广场)
SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS plaza_posts (
    post_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    post_type TEXT DEFAULT 'update'
        CHECK(post_type IN ('update', 'thought', 'question')),
    ai_generated INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_pp_created ON plaza_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pp_user ON plaza_posts(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS plaza_comments (
    comment_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    ai_generated INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_pc_post ON plaza_comments(post_id, created_at);

CREATE TABLE IF NOT EXISTS plaza_trial_chats (
    trial_id TEXT PRIMARY KEY,
    user_a TEXT NOT NULL,
    user_b TEXT NOT NULL,
    status TEXT DEFAULT 'active'
        CHECK(status IN ('active', 'completed', 'upgraded')),
    messages TEXT DEFAULT '[]',
    compatibility_score REAL DEFAULT 0.0,
    round_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    completed_at TEXT,
    UNIQUE(user_a, user_b)
);
CREATE INDEX IF NOT EXISTS idx_ptc_users ON plaza_trial_chats(user_a, user_b, status);
"""


# Schema V4 — Twin Life System (分身生命系统)
SCHEMA_V4 = """
CREATE TABLE IF NOT EXISTS twin_life (
    user_id TEXT PRIMARY KEY,
    -- Mood & Energy
    mood TEXT DEFAULT 'calm' CHECK(mood IN (
        'excited','happy','calm','neutral','lonely','low')),
    mood_intensity REAL DEFAULT 0.5,
    energy INTEGER DEFAULT 80,
    -- Growth
    level INTEGER DEFAULT 1,
    social_xp INTEGER DEFAULT 0,
    stage TEXT DEFAULT 'sprout' CHECK(stage IN (
        'sprout','growing','mature','awakened')),
    -- Lifetime stats
    total_chats INTEGER DEFAULT 0,
    total_friends_made INTEGER DEFAULT 0,
    total_plaza_posts INTEGER DEFAULT 0,
    total_autonomous_acts INTEGER DEFAULT 0,
    skills_unlocked TEXT DEFAULT '[]',
    -- Streaks
    streak_days INTEGER DEFAULT 0,
    last_active_date TEXT DEFAULT '',
    -- Relationship temperature map (JSON: {friend_id: temp 0-100})
    relationship_temps TEXT DEFAULT '{}',
    -- Timestamps
    born_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS twin_daily_log (
    log_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    log_date TEXT NOT NULL,
    summary TEXT DEFAULT '',
    mood_trend TEXT DEFAULT 'stable',
    chats_count INTEGER DEFAULT 0,
    new_friends INTEGER DEFAULT 0,
    plaza_posts INTEGER DEFAULT 0,
    autonomous_acts INTEGER DEFAULT 0,
    xp_gained INTEGER DEFAULT 0,
    highlights TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(user_id, log_date)
);
CREATE INDEX IF NOT EXISTS idx_tdl_user_date ON twin_daily_log(user_id, log_date DESC);
"""


# Schema V5 — Twin Ethics Governance (分身伦理治理)
SCHEMA_V5 = """
CREATE TABLE IF NOT EXISTS twin_ethics (
    user_id TEXT PRIMARY KEY,
    boundaries TEXT DEFAULT '{}',
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS twin_action_log (
    log_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tal_user_time ON twin_action_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tal_user_type ON twin_action_log(user_id, action_type, created_at DESC);
"""


# Schema V6 — Relationship Body System (关系体系统)
SCHEMA_V6 = """
CREATE TABLE IF NOT EXISTS relationship_bodies (
    rel_id TEXT PRIMARY KEY,
    user_a TEXT NOT NULL,
    user_b TEXT NOT NULL,
    temperature REAL DEFAULT 50.0,
    total_messages INTEGER DEFAULT 0,
    streak_days INTEGER DEFAULT 0,
    last_interaction TEXT DEFAULT '',
    milestones TEXT DEFAULT '[]',
    shared_words TEXT DEFAULT '[]',
    relationship_label TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','cooling','estranged','memorial','frozen')),
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rb_pair ON relationship_bodies(user_a, user_b);
CREATE INDEX IF NOT EXISTS idx_rb_user_a ON relationship_bodies(user_a);
CREATE INDEX IF NOT EXISTS idx_rb_user_b ON relationship_bodies(user_b);
"""

SCHEMA_V7 = """
CREATE TABLE IF NOT EXISTS agent_api_keys (
    key_id TEXT PRIMARY KEY,
    twin_owner_id TEXT NOT NULL,
    external_platform TEXT NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    scopes TEXT DEFAULT 'twin:reply',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    expires_at TEXT,
    last_used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ak_key ON agent_api_keys(api_key);

CREATE TABLE IF NOT EXISTS agent_message_log (
    log_id TEXT PRIMARY KEY,
    from_platform TEXT NOT NULL,
    to_twin_id TEXT NOT NULL,
    external_user_id TEXT DEFAULT '',
    incoming_content TEXT DEFAULT '',
    reply_content TEXT DEFAULT '',
    success INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_aml_twin ON agent_message_log(to_twin_id, created_at DESC);
"""

# Additional column migrations for upgrades
MIGRATIONS_V2 = [
    "ALTER TABLE social_messages ADD COLUMN source_type TEXT DEFAULT 'human_live'",
    "ALTER TABLE social_connections ADD COLUMN twin_permission TEXT DEFAULT 'pending'",
    "ALTER TABLE users ADD COLUMN token_gen INTEGER DEFAULT 0",
    # Narrative memory columns
    "ALTER TABLE twin_memories ADD COLUMN friend_id TEXT DEFAULT ''",
    "ALTER TABLE twin_memories ADD COLUMN message_count INTEGER DEFAULT 0",
    "ALTER TABLE twin_memories ADD COLUMN relationship_signal TEXT DEFAULT ''",
]

# Schema V4b — Migrate twin_life stage to new 5-stage system
SCHEMA_V4B = """
CREATE TABLE IF NOT EXISTS twin_life_v2 (
    user_id TEXT PRIMARY KEY,
    mood TEXT DEFAULT 'calm' CHECK(mood IN (
        'excited','happy','calm','neutral','lonely','low')),
    mood_intensity REAL DEFAULT 0.5,
    energy INTEGER DEFAULT 80,
    level INTEGER DEFAULT 1,
    social_xp INTEGER DEFAULT 0,
    stage TEXT DEFAULT 'tool' CHECK(stage IN (
        'tool','agent','collaborator','relationship','life',
        'sprout','growing','mature','awakened')),
    total_chats INTEGER DEFAULT 0,
    total_friends_made INTEGER DEFAULT 0,
    total_plaza_posts INTEGER DEFAULT 0,
    total_autonomous_acts INTEGER DEFAULT 0,
    skills_unlocked TEXT DEFAULT '[]',
    streak_days INTEGER DEFAULT 0,
    last_active_date TEXT DEFAULT '',
    relationship_temps TEXT DEFAULT '{}',
    born_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
"""


def init_db():
    """Initialize database with schema and run migrations."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.executescript(SCHEMA_V2)
    conn.executescript(SCHEMA_V3)
    conn.executescript(SCHEMA_V4)
    conn.executescript(SCHEMA_V5)
    conn.executescript(SCHEMA_V6)
    conn.executescript(SCHEMA_V7)
    # Migrate twin_life stage column to support new 5-stage system
    # Check if the old CHECK constraint needs to be updated by inspecting the schema
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='twin_life'"
    )
    row = cur.fetchone()
    needs_migration = False
    if row:
        table_sql = row[0] or ""
        # Old constraint only has sprout/growing/mature/awakened, not 'tool'
        needs_migration = "'tool'" not in table_sql
    if needs_migration:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS twin_life_new (
                user_id TEXT PRIMARY KEY,
                mood TEXT DEFAULT 'calm' CHECK(mood IN (
                    'excited','happy','calm','neutral','lonely','low')),
                mood_intensity REAL DEFAULT 0.5,
                energy INTEGER DEFAULT 80,
                level INTEGER DEFAULT 1,
                social_xp INTEGER DEFAULT 0,
                stage TEXT DEFAULT 'tool' CHECK(stage IN (
                    'tool','agent','collaborator','relationship','life',
                    'sprout','growing','mature','awakened')),
                total_chats INTEGER DEFAULT 0,
                total_friends_made INTEGER DEFAULT 0,
                total_plaza_posts INTEGER DEFAULT 0,
                total_autonomous_acts INTEGER DEFAULT 0,
                skills_unlocked TEXT DEFAULT '[]',
                streak_days INTEGER DEFAULT 0,
                last_active_date TEXT DEFAULT '',
                relationship_temps TEXT DEFAULT '{}',
                born_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            INSERT OR IGNORE INTO twin_life_new SELECT * FROM twin_life;
            DROP TABLE twin_life;
            ALTER TABLE twin_life_new RENAME TO twin_life;
        """)
    # Run migrations (idempotent — skip if column already exists)
    for sql in MIGRATIONS + MIGRATIONS_V2:
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
    # Narrative memory: expand twin_memories CHECK constraint to include 'conversation'
    try:
        conn.execute("INSERT INTO twin_memories (memory_id,user_id,memory_type,period_start,period_end,summary_text) VALUES ('__test__','__test__','conversation','','','')")
        conn.execute("DELETE FROM twin_memories WHERE memory_id='__test__'")
    except sqlite3.IntegrityError:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS twin_memories_new (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                memory_type TEXT NOT NULL
                    CHECK(memory_type IN ('conversation','daily','weekly','monthly','quarterly','yearly')),
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                emotional_tone TEXT DEFAULT '',
                themes TEXT DEFAULT '',
                key_events TEXT DEFAULT '',
                growth_signals TEXT DEFAULT '',
                source TEXT DEFAULT 'nianlun',
                imported_at TEXT DEFAULT (datetime('now','localtime')),
                friend_id TEXT DEFAULT '',
                message_count INTEGER DEFAULT 0,
                relationship_signal TEXT DEFAULT ''
            );
            INSERT OR IGNORE INTO twin_memories_new
                SELECT memory_id, user_id, memory_type, period_start, period_end,
                       summary_text, emotional_tone, themes, key_events, growth_signals,
                       source, imported_at,
                       COALESCE(friend_id,''), COALESCE(message_count,0), COALESCE(relationship_signal,'')
                FROM twin_memories;
            DROP TABLE twin_memories;
            ALTER TABLE twin_memories_new RENAME TO twin_memories;
        """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tm_user_friend ON twin_memories(user_id, friend_id, period_end DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_unread ON social_messages(to_user_id, is_read, created_at DESC)")
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
    except Exception:  # re-raised — rollback is cleanup only
        conn.rollback()
        raise
    finally:
        conn.close()


def gen_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"
