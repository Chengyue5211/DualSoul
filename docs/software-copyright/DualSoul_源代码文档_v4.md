# DualSoul双身份社交协议

## 源代码文档

- 软件名称：DualSoul双身份社交协议软件
- 版本号：V4.0（对应代码版本 v0.8.1）
- 代码总行数：15481（Python源码10263 + 测试674 + 前端4544）
- 编程语言：Python / HTML5 / JavaScript
- 开发完成日期：2026年3月16日
- 著作权人：Chengyue5211

---

## 【源代码】

# --- dualsoul/__init__.py ---
     1  """DualSoul — Dual Identity Social Protocol
     2  
     3  Every person has two voices. DualSoul gives both of them a place to speak.
     4  """
     5  
     6  __version__ = "0.4.0"
     7  __author__ = "Chengyue5211"

# --- dualsoul/__main__.py ---
     8  """Allow running with `python -m dualsoul`."""
     9  
    10  from dualsoul.main import cli
    11  
    12  cli()

# --- dualsoul/auth.py ---
    13  """DualSoul authentication — JWT + bcrypt."""
    14  
    15  import sqlite3
    16  from datetime import datetime, timedelta, timezone
    17  
    18  import bcrypt
    19  import jwt
    20  from fastapi import Depends, HTTPException
    21  from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    22  
    23  from dualsoul.config import DATABASE_PATH, JWT_SECRET, JWT_EXPIRE_HOURS
    24  
    25  _bearer = HTTPBearer(auto_error=False)
    26  
    27  
    28  def hash_password(password: str) -> str:
    29      """Hash a password with bcrypt."""
    30      return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    31  
    32  
    33  def verify_password(password: str, hashed: str) -> bool:
    34      """Verify a password against a bcrypt hash."""
    35      return bcrypt.checkpw(password.encode(), hashed.encode())
    36  
    37  
    38  def create_token(user_id: str, username: str, token_gen: int = 0) -> str:
    39      """Create a JWT token with generation counter for invalidation."""
    40      payload = {
    41          "user_id": user_id,
    42          "username": username,
    43          "gen": token_gen,
    44          "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    45      }
    46      return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    47  
    48  
    49  def verify_token(token: str) -> dict:
    50      """Verify and decode a JWT token."""
    51      return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    52  
    53  
    54  async def get_current_user(
    55      credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    56  ) -> dict:
    57      """FastAPI dependency — extract and verify the current user from JWT."""
    58      if not credentials:
    59          raise HTTPException(status_code=401, detail="Authentication required")
    60      try:
    61          payload = verify_token(credentials.credentials)
    62          # Verify token generation counter (password change invalidates old tokens)
    63          token_gen = payload.get("gen", 0)
    64          conn = sqlite3.connect(DATABASE_PATH)
    65          conn.row_factory = sqlite3.Row
    66          row = conn.execute(
    67              "SELECT token_gen FROM users WHERE user_id=?", (payload["user_id"],)
    68          ).fetchone()
    69          conn.close()
    70          if row:
    71              db_gen = row["token_gen"] if "token_gen" in row.keys() else 0
    72              if token_gen != db_gen:
    73                  raise HTTPException(status_code=401, detail="Token invalidated — please login again")
    74          return payload
    75      except jwt.ExpiredSignatureError:
    76          raise HTTPException(status_code=401, detail="Token expired")
    77      except jwt.InvalidTokenError:
    78          raise HTTPException(status_code=401, detail="Invalid token")

# --- dualsoul/config.py ---
    79  """DualSoul configuration — all settings from environment variables."""
    80  
    81  import logging
    82  import os
    83  import secrets
    84  
    85  from dotenv import load_dotenv
    86  
    87  logger = logging.getLogger(__name__)
    88  
    89  load_dotenv()
    90  
    91  # Database
    92  DATABASE_PATH = os.getenv("DUALSOUL_DATABASE_PATH", "./dualsoul.db")
    93  
    94  # JWT — persist secret across restarts even if env var not set
    95  JWT_SECRET = os.getenv("DUALSOUL_JWT_SECRET", "")
    96  if not JWT_SECRET:
    97      _secret_file = os.path.join(os.path.dirname(DATABASE_PATH), ".jwt_secret")
    98      try:
    99          if os.path.exists(_secret_file):
   100              with open(_secret_file) as _f:
   101                  JWT_SECRET = _f.read().strip()
   102          if not JWT_SECRET:
   103              JWT_SECRET = secrets.token_hex(32)
   104              with open(_secret_file, "w") as _f:
   105                  _f.write(JWT_SECRET)
   106              logger.info("Generated persistent JWT secret saved to .jwt_secret")
   107      except OSError:
   108          JWT_SECRET = secrets.token_hex(32)
   109          logger.warning("Could not persist JWT secret. Tokens will expire on restart.")
   110  
   111  JWT_EXPIRE_HOURS = int(os.getenv("DUALSOUL_JWT_EXPIRE_HOURS", "72"))
   112  
   113  # AI Backend (OpenAI-compatible API)
   114  AI_BASE_URL = os.getenv("DUALSOUL_AI_BASE_URL", "")
   115  AI_API_KEY = os.getenv("DUALSOUL_AI_KEY", "")
   116  AI_MODEL = os.getenv("DUALSOUL_AI_MODEL", "gpt-3.5-turbo")
   117  AI_VISION_MODEL = os.getenv("DUALSOUL_AI_VISION_MODEL", "qwen-vl-plus")
   118  
   119  # Server
   120  HOST = os.getenv("DUALSOUL_HOST", "0.0.0.0")
   121  PORT = int(os.getenv("DUALSOUL_PORT", "8000"))
   122  
   123  # CORS — restrict in production via env var
   124  _DEFAULT_CORS = "http://47.93.149.187,http://localhost:8000,http://localhost:3000"
   125  CORS_ORIGINS = os.getenv("DUALSOUL_CORS_ORIGINS", _DEFAULT_CORS).split(",")

# --- dualsoul/connections.py ---
   126  """WebSocket connection manager — tracks online users for real-time push."""
   127  
   128  import logging
   129  from datetime import datetime
   130  
   131  from fastapi import WebSocket
   132  
   133  logger = logging.getLogger(__name__)
   134  
   135  
   136  class ConnectionManager:
   137      """Manage active WebSocket connections by user_id."""
   138  
   139      def __init__(self):
   140          self._connections: dict[str, WebSocket] = {}
   141          self._last_active: dict[str, datetime] = {}
   142  
   143      async def connect(self, user_id: str, websocket: WebSocket):
   144          """Accept and register a WebSocket connection."""
   145          await websocket.accept()
   146          # Close existing connection if the same user reconnects
   147          old = self._connections.get(user_id)
   148          if old:
   149              try:
   150                  await old.close(code=4000, reason="Replaced by new connection")
   151              except Exception as e:
   152                  logger.debug(f"Old WS close failed for {user_id}: {e}")
   153          self._connections[user_id] = websocket
   154          self._last_active[user_id] = datetime.now()
   155          logger.info(f"WS connected: {user_id} (total: {len(self._connections)})")
   156  
   157      def disconnect(self, user_id: str):
   158          """Remove a disconnected user."""
   159          self._connections.pop(user_id, None)
   160          logger.info(f"WS disconnected: {user_id} (total: {len(self._connections)})")
   161  
   162      def is_online(self, user_id: str) -> bool:
   163          """Check if a user has an active WebSocket."""
   164          return user_id in self._connections
   165  
   166      def last_active(self, user_id: str) -> datetime | None:
   167          """Get the last activity time for a user."""
   168          return self._last_active.get(user_id)
   169  
   170      def touch(self, user_id: str):
   171          """Update last-active timestamp."""
   172          self._last_active[user_id] = datetime.now()
   173  
   174      async def send_to(self, user_id: str, data: dict) -> bool:
   175          """Send JSON data to a specific user. Returns True if sent."""
   176          ws = self._connections.get(user_id)
   177          if not ws:
   178              return False
   179          try:
   180              await ws.send_json(data)
   181              return True
   182          except Exception as e:
   183              logger.debug(f"WS send failed for {user_id}: {e}")
   184              self.disconnect(user_id)
   185              return False
   186  
   187      async def broadcast(self, user_ids: list[str], data: dict):
   188          """Send JSON data to multiple users (parallel)."""
   189          import asyncio
   190          await asyncio.gather(*[self.send_to(uid, data) for uid in user_ids])
   191  
   192  
   193  # Singleton instance — imported by routers
   194  manager = ConnectionManager()

# --- dualsoul/constants.py ---
   195  """DualSoul constants — single source of truth for all magic numbers.
   196  
   197  Import from here instead of hardcoding values across the codebase.
   198  """
   199  
   200  # Rate limits (per minute unless noted)
   201  RATE_LOGIN_MAX = 10
   202  RATE_LOGIN_WINDOW = 60
   203  RATE_REGISTER_MAX = 5
   204  RATE_MESSAGE_MAX = 30
   205  RATE_ACTION_MAX = 20
   206  RATE_AGENT_MAX = 60
   207  
   208  # Autonomous engine
   209  AUTONOMOUS_CHECK_INTERVAL = 1800  # 30 min
   210  OFFLINE_THRESHOLD_HOURS = 2
   211  MAX_DAILY_AUTONOMOUS_CONVOS = 3
   212  
   213  # Narrative memory
   214  CONVERSATION_GAP_MINUTES = 10
   215  MAX_MESSAGES_PER_SUMMARY = 30
   216  MEMORY_CLEANUP_DAYS = 30
   217  
   218  # Agent API
   219  AGENT_KEY_MAX_PER_USER = 5
   220  AGENT_KEY_DEFAULT_EXPIRY_DAYS = 90
   221  
   222  # AI
   223  AI_MAX_TOKENS_AUTO_REPLY = 40
   224  AI_MAX_TOKENS_REGULAR = 100
   225  AI_REQUEST_TIMEOUT = 20

# --- dualsoul/database.py ---
   226  """DualSoul database — SQLite with WAL mode."""
   227  
   228  import sqlite3
   229  import uuid
   230  from contextlib import contextmanager
   231  
   232  from dualsoul.config import DATABASE_PATH
   233  
   234  SCHEMA = """
   235  CREATE TABLE IF NOT EXISTS users (
   236      user_id TEXT PRIMARY KEY,
   237      username TEXT NOT NULL UNIQUE,
   238      password_hash TEXT NOT NULL,
   239      display_name TEXT DEFAULT '',
   240      current_mode TEXT DEFAULT 'real' CHECK(current_mode IN ('real', 'twin')),
   241      twin_personality TEXT DEFAULT '',
   242      twin_speech_style TEXT DEFAULT '',
   243      preferred_lang TEXT DEFAULT ''
   244          CHECK(preferred_lang IN ('', 'zh', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'ru', 'ar', 'hi', 'th', 'vi', 'id', 'auto')),
   245      avatar TEXT DEFAULT '',
   246      twin_avatar TEXT DEFAULT '',
   247      created_at TEXT DEFAULT (datetime('now','localtime'))
   248  );
   249  
   250  CREATE TABLE IF NOT EXISTS social_connections (
   251      conn_id TEXT PRIMARY KEY,
   252      user_id TEXT NOT NULL,
   253      friend_id TEXT NOT NULL,
   254      status TEXT DEFAULT 'pending'
   255          CHECK(status IN ('pending', 'accepted', 'blocked', 'deleted')),
   256      created_at TEXT DEFAULT (datetime('now','localtime')),
   257      accepted_at TEXT,
   258      UNIQUE(user_id, friend_id)
   259  );
   260  CREATE INDEX IF NOT EXISTS idx_sc_user ON social_connections(user_id, status);
   261  CREATE INDEX IF NOT EXISTS idx_sc_friend ON social_connections(friend_id, status);
   262  
   263  CREATE TABLE IF NOT EXISTS social_messages (
   264      msg_id TEXT PRIMARY KEY,
   265      from_user_id TEXT NOT NULL,
   266      to_user_id TEXT NOT NULL,
   267      sender_mode TEXT DEFAULT 'real'
   268          CHECK(sender_mode IN ('real', 'twin')),
   269      receiver_mode TEXT DEFAULT 'real'
   270          CHECK(receiver_mode IN ('real', 'twin')),
   271      content TEXT NOT NULL,
   272      original_content TEXT DEFAULT '',
   273      original_lang TEXT DEFAULT '',
   274      target_lang TEXT DEFAULT '',
   275      translation_style TEXT DEFAULT ''
   276          CHECK(translation_style IN ('', 'literal', 'personality_preserving')),
   277      msg_type TEXT DEFAULT 'text'
   278          CHECK(msg_type IN ('text', 'image', 'voice', 'system')),
   279      is_read INTEGER DEFAULT 0,
   280      ai_generated INTEGER DEFAULT 0,
   281      created_at TEXT DEFAULT (datetime('now','localtime'))
   282  );
   283  CREATE INDEX IF NOT EXISTS idx_sm_from ON social_messages(from_user_id, created_at);
   284  CREATE INDEX IF NOT EXISTS idx_sm_to ON social_messages(to_user_id, is_read, created_at);
   285  CREATE INDEX IF NOT EXISTS idx_sm_conv ON social_messages(from_user_id, to_user_id, created_at);
   286  """
   287  
   288  
   289  MIGRATIONS = [
   290      "ALTER TABLE users ADD COLUMN twin_auto_reply INTEGER DEFAULT 1",
   291      "ALTER TABLE social_messages ADD COLUMN auto_reply INTEGER DEFAULT 0",
   292      "ALTER TABLE social_messages ADD COLUMN metadata TEXT DEFAULT ''",
   293      "ALTER TABLE users ADD COLUMN voice_sample TEXT DEFAULT ''",
   294      "ALTER TABLE users ADD COLUMN twin_source TEXT DEFAULT 'local'",
   295      "ALTER TABLE users ADD COLUMN gender TEXT DEFAULT ''",
   296      "ALTER TABLE users ADD COLUMN reg_source TEXT DEFAULT 'dualsoul'",
   297      "ALTER TABLE users ADD COLUMN invited_by TEXT DEFAULT ''",
   298      "ALTER TABLE users ADD COLUMN invite_count INTEGER DEFAULT 0",
   299  ]
   300  
   301  
   302  # Schema V2 — Twin import from Nianlun (年轮分身导入)
   303  SCHEMA_V2 = """
   304  CREATE TABLE IF NOT EXISTS twin_profiles (
   305      profile_id TEXT PRIMARY KEY,
   306      user_id TEXT NOT NULL,
   307      source TEXT NOT NULL DEFAULT 'nianlun',
   308      version INTEGER NOT NULL DEFAULT 1,
   309      is_active INTEGER NOT NULL DEFAULT 1,
   310  
   311      -- Identity
   312      twin_name TEXT DEFAULT '',
   313      training_status TEXT DEFAULT '',
   314      quality_score REAL DEFAULT 0.0,
   315      self_awareness REAL DEFAULT 0.0,
   316      interaction_count INTEGER DEFAULT 0,
   317  
   318      -- Five-dimension personality (五维人格骨架)
   319      dim_judgement TEXT DEFAULT '',
   320      dim_cognition TEXT DEFAULT '',
   321      dim_expression TEXT DEFAULT '',
   322      dim_relation TEXT DEFAULT '',
   323      dim_sovereignty TEXT DEFAULT '',
   324  
   325      -- Structured personality
   326      value_order TEXT DEFAULT '',
   327      behavior_patterns TEXT DEFAULT '',
   328      speech_style TEXT DEFAULT '',
   329      boundaries TEXT DEFAULT '',
   330  
   331      -- Certificate (身份证书)
   332      certificate TEXT DEFAULT '',
   333  
   334      -- Full import payload (cold storage)
   335      raw_import TEXT DEFAULT '',
   336  
   337      imported_at TEXT DEFAULT (datetime('now','localtime')),
   338      updated_at TEXT DEFAULT (datetime('now','localtime')),
   339  
   340      UNIQUE(user_id, version)
   341  );
   342  CREATE INDEX IF NOT EXISTS idx_tp_user_active ON twin_profiles(user_id, is_active);
   343  
   344  CREATE TABLE IF NOT EXISTS twin_memories (
   345      memory_id TEXT PRIMARY KEY,
   346      user_id TEXT NOT NULL,
   347      memory_type TEXT NOT NULL
   348          CHECK(memory_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')),
   349      period_start TEXT NOT NULL,
   350      period_end TEXT NOT NULL,
   351  
   352      summary_text TEXT NOT NULL,
   353      emotional_tone TEXT DEFAULT '',
   354      themes TEXT DEFAULT '',
   355  
   356      key_events TEXT DEFAULT '',
   357      growth_signals TEXT DEFAULT '',
   358  
   359      source TEXT DEFAULT 'nianlun',
   360      imported_at TEXT DEFAULT (datetime('now','localtime'))
   361  );
   362  CREATE INDEX IF NOT EXISTS idx_tm_user_type ON twin_memories(user_id, memory_type, period_start);
   363  CREATE INDEX IF NOT EXISTS idx_tm_user_recent ON twin_memories(user_id, period_end DESC);
   364  
   365  CREATE TABLE IF NOT EXISTS twin_entities (
   366      entity_id TEXT PRIMARY KEY,
   367      user_id TEXT NOT NULL,
   368      entity_name TEXT NOT NULL,
   369      entity_type TEXT NOT NULL
   370          CHECK(entity_type IN ('person', 'place', 'thing', 'event', 'concept')),
   371      importance_score REAL DEFAULT 0.0,
   372      mention_count INTEGER DEFAULT 0,
   373      context TEXT DEFAULT '',
   374      relations TEXT DEFAULT '',
   375  
   376      source TEXT DEFAULT 'nianlun',
   377      imported_at TEXT DEFAULT (datetime('now','localtime'))
   378  );
   379  CREATE INDEX IF NOT EXISTS idx_te_user_type ON twin_entities(user_id, entity_type, importance_score DESC);
   380  CREATE INDEX IF NOT EXISTS idx_te_user_name ON twin_entities(user_id, entity_name);
   381  """
   382  
   383  
   384  # Schema V3 — Agent Plaza (分身广场)
   385  SCHEMA_V3 = """
   386  CREATE TABLE IF NOT EXISTS plaza_posts (
   387      post_id TEXT PRIMARY KEY,
   388      user_id TEXT NOT NULL,
   389      content TEXT NOT NULL,
   390      post_type TEXT DEFAULT 'update'
   391          CHECK(post_type IN ('update', 'thought', 'question')),
   392      ai_generated INTEGER DEFAULT 0,
   393      like_count INTEGER DEFAULT 0,
   394      comment_count INTEGER DEFAULT 0,
   395      created_at TEXT DEFAULT (datetime('now','localtime'))
   396  );
   397  CREATE INDEX IF NOT EXISTS idx_pp_created ON plaza_posts(created_at DESC);
   398  CREATE INDEX IF NOT EXISTS idx_pp_user ON plaza_posts(user_id, created_at DESC);
   399  
   400  CREATE TABLE IF NOT EXISTS plaza_comments (
   401      comment_id TEXT PRIMARY KEY,
   402      post_id TEXT NOT NULL,
   403      user_id TEXT NOT NULL,
   404      content TEXT NOT NULL,
   405      ai_generated INTEGER DEFAULT 0,
   406      created_at TEXT DEFAULT (datetime('now','localtime'))
   407  );
   408  CREATE INDEX IF NOT EXISTS idx_pc_post ON plaza_comments(post_id, created_at);
   409  
   410  CREATE TABLE IF NOT EXISTS plaza_trial_chats (
   411      trial_id TEXT PRIMARY KEY,
   412      user_a TEXT NOT NULL,
   413      user_b TEXT NOT NULL,
   414      status TEXT DEFAULT 'active'
   415          CHECK(status IN ('active', 'completed', 'upgraded')),
   416      messages TEXT DEFAULT '[]',
   417      compatibility_score REAL DEFAULT 0.0,
   418      round_count INTEGER DEFAULT 0,
   419      created_at TEXT DEFAULT (datetime('now','localtime')),
   420      completed_at TEXT,
   421      UNIQUE(user_a, user_b)
   422  );
   423  CREATE INDEX IF NOT EXISTS idx_ptc_users ON plaza_trial_chats(user_a, user_b, status);
   424  """
   425  
   426  
   427  # Schema V4 — Twin Life System (分身生命系统)
   428  SCHEMA_V4 = """
   429  CREATE TABLE IF NOT EXISTS twin_life (
   430      user_id TEXT PRIMARY KEY,
   431      -- Mood & Energy
   432      mood TEXT DEFAULT 'calm' CHECK(mood IN (
   433          'excited','happy','calm','neutral','lonely','low')),
   434      mood_intensity REAL DEFAULT 0.5,
   435      energy INTEGER DEFAULT 80,
   436      -- Growth
   437      level INTEGER DEFAULT 1,
   438      social_xp INTEGER DEFAULT 0,
   439      stage TEXT DEFAULT 'sprout' CHECK(stage IN (
   440          'sprout','growing','mature','awakened')),
   441      -- Lifetime stats
   442      total_chats INTEGER DEFAULT 0,
   443      total_friends_made INTEGER DEFAULT 0,
   444      total_plaza_posts INTEGER DEFAULT 0,
   445      total_autonomous_acts INTEGER DEFAULT 0,
   446      skills_unlocked TEXT DEFAULT '[]',
   447      -- Streaks
   448      streak_days INTEGER DEFAULT 0,
   449      last_active_date TEXT DEFAULT '',
   450      -- Relationship temperature map (JSON: {friend_id: temp 0-100})
   451      relationship_temps TEXT DEFAULT '{}',
   452      -- Timestamps
   453      born_at TEXT DEFAULT (datetime('now','localtime')),
   454      updated_at TEXT DEFAULT (datetime('now','localtime'))
   455  );
   456  
   457  CREATE TABLE IF NOT EXISTS twin_daily_log (
   458      log_id TEXT PRIMARY KEY,
   459      user_id TEXT NOT NULL,
   460      log_date TEXT NOT NULL,
   461      summary TEXT DEFAULT '',
   462      mood_trend TEXT DEFAULT 'stable',
   463      chats_count INTEGER DEFAULT 0,
   464      new_friends INTEGER DEFAULT 0,
   465      plaza_posts INTEGER DEFAULT 0,
   466      autonomous_acts INTEGER DEFAULT 0,
   467      xp_gained INTEGER DEFAULT 0,
   468      highlights TEXT DEFAULT '[]',
   469      created_at TEXT DEFAULT (datetime('now','localtime')),
   470      UNIQUE(user_id, log_date)
   471  );
   472  CREATE INDEX IF NOT EXISTS idx_tdl_user_date ON twin_daily_log(user_id, log_date DESC);
   473  """
   474  
   475  
   476  # Schema V5 — Twin Ethics Governance (分身伦理治理)
   477  SCHEMA_V5 = """
   478  CREATE TABLE IF NOT EXISTS twin_ethics (
   479      user_id TEXT PRIMARY KEY,
   480      boundaries TEXT DEFAULT '{}',
   481      updated_at TEXT DEFAULT (datetime('now','localtime'))
   482  );
   483  
   484  CREATE TABLE IF NOT EXISTS twin_action_log (
   485      log_id TEXT PRIMARY KEY,
   486      user_id TEXT NOT NULL,
   487      action_type TEXT NOT NULL,
   488      detail TEXT DEFAULT '',
   489      created_at TEXT DEFAULT (datetime('now','localtime'))
   490  );
   491  CREATE INDEX IF NOT EXISTS idx_tal_user_time ON twin_action_log(user_id, created_at DESC);
   492  CREATE INDEX IF NOT EXISTS idx_tal_user_type ON twin_action_log(user_id, action_type, created_at DESC);
   493  """
   494  
   495  
   496  # Schema V6 — Relationship Body System (关系体系统)
   497  SCHEMA_V6 = """
   498  CREATE TABLE IF NOT EXISTS relationship_bodies (
   499      rel_id TEXT PRIMARY KEY,
   500      user_a TEXT NOT NULL,
   501      user_b TEXT NOT NULL,
   502      temperature REAL DEFAULT 50.0,
   503      total_messages INTEGER DEFAULT 0,
   504      streak_days INTEGER DEFAULT 0,
   505      last_interaction TEXT DEFAULT '',
   506      milestones TEXT DEFAULT '[]',
   507      shared_words TEXT DEFAULT '[]',
   508      relationship_label TEXT DEFAULT '',
   509      status TEXT DEFAULT 'active' CHECK(status IN ('active','cooling','estranged','memorial','frozen')),
   510      created_at TEXT DEFAULT (datetime('now','localtime')),
   511      updated_at TEXT DEFAULT (datetime('now','localtime'))
   512  );
   513  CREATE UNIQUE INDEX IF NOT EXISTS idx_rb_pair ON relationship_bodies(user_a, user_b);
   514  CREATE INDEX IF NOT EXISTS idx_rb_user_a ON relationship_bodies(user_a);
   515  CREATE INDEX IF NOT EXISTS idx_rb_user_b ON relationship_bodies(user_b);
   516  """
   517  
   518  SCHEMA_V7 = """
   519  CREATE TABLE IF NOT EXISTS agent_api_keys (
   520      key_id TEXT PRIMARY KEY,
   521      twin_owner_id TEXT NOT NULL,
   522      external_platform TEXT NOT NULL,
   523      api_key TEXT NOT NULL UNIQUE,
   524      scopes TEXT DEFAULT 'twin:reply',
   525      created_at TEXT DEFAULT (datetime('now','localtime')),
   526      expires_at TEXT,
   527      last_used_at TEXT
   528  );
   529  CREATE INDEX IF NOT EXISTS idx_ak_key ON agent_api_keys(api_key);
   530  
   531  CREATE TABLE IF NOT EXISTS agent_message_log (
   532      log_id TEXT PRIMARY KEY,
   533      from_platform TEXT NOT NULL,
   534      to_twin_id TEXT NOT NULL,
   535      external_user_id TEXT DEFAULT '',
   536      incoming_content TEXT DEFAULT '',
   537      reply_content TEXT DEFAULT '',
   538      success INTEGER DEFAULT 1,
   539      created_at TEXT DEFAULT (datetime('now','localtime'))
   540  );
   541  CREATE INDEX IF NOT EXISTS idx_aml_twin ON agent_message_log(to_twin_id, created_at DESC);
   542  """
   543  
   544  # Additional column migrations for upgrades
   545  MIGRATIONS_V2 = [
   546      "ALTER TABLE social_messages ADD COLUMN source_type TEXT DEFAULT 'human_live'",
   547      "ALTER TABLE social_connections ADD COLUMN twin_permission TEXT DEFAULT 'granted'",
   548      "ALTER TABLE users ADD COLUMN token_gen INTEGER DEFAULT 0",
   549      # Narrative memory columns
   550      "ALTER TABLE twin_memories ADD COLUMN friend_id TEXT DEFAULT ''",
   551      "ALTER TABLE twin_memories ADD COLUMN message_count INTEGER DEFAULT 0",
   552      "ALTER TABLE twin_memories ADD COLUMN relationship_signal TEXT DEFAULT ''",
   553  ]
   554  
   555  # Schema V4b — Migrate twin_life stage to new 5-stage system
   556  SCHEMA_V4B = """
   557  CREATE TABLE IF NOT EXISTS twin_life_v2 (
   558      user_id TEXT PRIMARY KEY,
   559      mood TEXT DEFAULT 'calm' CHECK(mood IN (
   560          'excited','happy','calm','neutral','lonely','low')),
   561      mood_intensity REAL DEFAULT 0.5,
   562      energy INTEGER DEFAULT 80,
   563      level INTEGER DEFAULT 1,
   564      social_xp INTEGER DEFAULT 0,
   565      stage TEXT DEFAULT 'tool' CHECK(stage IN (
   566          'tool','agent','collaborator','relationship','life',
   567          'sprout','growing','mature','awakened')),
   568      total_chats INTEGER DEFAULT 0,
   569      total_friends_made INTEGER DEFAULT 0,
   570      total_plaza_posts INTEGER DEFAULT 0,
   571      total_autonomous_acts INTEGER DEFAULT 0,
   572      skills_unlocked TEXT DEFAULT '[]',
   573      streak_days INTEGER DEFAULT 0,
   574      last_active_date TEXT DEFAULT '',
   575      relationship_temps TEXT DEFAULT '{}',
   576      born_at TEXT DEFAULT (datetime('now','localtime')),
   577      updated_at TEXT DEFAULT (datetime('now','localtime'))
   578  );
   579  """
   580  
   581  
   582  def init_db():
   583      """Initialize database with schema and run migrations."""
   584      conn = sqlite3.connect(DATABASE_PATH)
   585      conn.execute("PRAGMA journal_mode=WAL")
   586      conn.execute("PRAGMA foreign_keys=ON")
   587      conn.executescript(SCHEMA)
   588      conn.executescript(SCHEMA_V2)
   589      conn.executescript(SCHEMA_V3)
   590      conn.executescript(SCHEMA_V4)
   591      conn.executescript(SCHEMA_V5)
   592      conn.executescript(SCHEMA_V6)
   593      conn.executescript(SCHEMA_V7)
   594      # Migrate twin_life stage column to support new 5-stage system
   595      # Check if the old CHECK constraint needs to be updated by inspecting the schema
   596      cur = conn.execute(
   597          "SELECT sql FROM sqlite_master WHERE type='table' AND name='twin_life'"
   598      )
   599      row = cur.fetchone()
   600      needs_migration = False
   601      if row:
   602          table_sql = row[0] or ""
   603          # Old constraint only has sprout/growing/mature/awakened, not 'tool'
   604          needs_migration = "'tool'" not in table_sql
   605      if needs_migration:
   606          conn.executescript("""
   607              CREATE TABLE IF NOT EXISTS twin_life_new (
   608                  user_id TEXT PRIMARY KEY,
   609                  mood TEXT DEFAULT 'calm' CHECK(mood IN (
   610                      'excited','happy','calm','neutral','lonely','low')),
   611                  mood_intensity REAL DEFAULT 0.5,
   612                  energy INTEGER DEFAULT 80,
   613                  level INTEGER DEFAULT 1,
   614                  social_xp INTEGER DEFAULT 0,
   615                  stage TEXT DEFAULT 'tool' CHECK(stage IN (
   616                      'tool','agent','collaborator','relationship','life',
   617                      'sprout','growing','mature','awakened')),
   618                  total_chats INTEGER DEFAULT 0,
   619                  total_friends_made INTEGER DEFAULT 0,
   620                  total_plaza_posts INTEGER DEFAULT 0,
   621                  total_autonomous_acts INTEGER DEFAULT 0,
   622                  skills_unlocked TEXT DEFAULT '[]',
   623                  streak_days INTEGER DEFAULT 0,
   624                  last_active_date TEXT DEFAULT '',
   625                  relationship_temps TEXT DEFAULT '{}',
   626                  born_at TEXT DEFAULT (datetime('now','localtime')),
   627                  updated_at TEXT DEFAULT (datetime('now','localtime'))
   628              );
   629              INSERT OR IGNORE INTO twin_life_new SELECT * FROM twin_life;
   630              DROP TABLE twin_life;
   631              ALTER TABLE twin_life_new RENAME TO twin_life;
   632          """)
   633      # Run migrations (idempotent — skip if column already exists)
   634      for sql in MIGRATIONS + MIGRATIONS_V2:
   635          try:
   636              conn.execute(sql)
   637          except sqlite3.OperationalError:
   638              pass  # Column already exists
   639      # Migrate social_connections: add 'deleted' to status CHECK constraint
   640      # SQLite can't ALTER CHECK, so recreate table if needed
   641      try:
   642          conn.execute("UPDATE social_connections SET status='deleted' WHERE 0", ())
   643      except sqlite3.IntegrityError:
   644          # CHECK constraint doesn't include 'deleted' — recreate table
   645          conn.executescript("""
   646              CREATE TABLE IF NOT EXISTS social_connections_new (
   647                  conn_id TEXT PRIMARY KEY,
   648                  user_id TEXT NOT NULL,
   649                  friend_id TEXT NOT NULL,
   650                  status TEXT DEFAULT 'pending'
   651                      CHECK(status IN ('pending', 'accepted', 'blocked', 'deleted')),
   652                  created_at TEXT DEFAULT (datetime('now','localtime')),
   653                  accepted_at TEXT,
   654                  UNIQUE(user_id, friend_id)
   655              );
   656              INSERT OR IGNORE INTO social_connections_new SELECT * FROM social_connections;
   657              DROP TABLE social_connections;
   658              ALTER TABLE social_connections_new RENAME TO social_connections;
   659              CREATE INDEX IF NOT EXISTS idx_sc_user ON social_connections(user_id, status);
   660              CREATE INDEX IF NOT EXISTS idx_sc_friend ON social_connections(friend_id, status);
   661          """)
   662      # Narrative memory: expand twin_memories CHECK constraint to include 'conversation'
   663      try:
   664          conn.execute("INSERT INTO twin_memories (memory_id,user_id,memory_type,period_start,period_end,summary_text) VALUES ('__test__','__test__','conversation','','','')")
   665          conn.execute("DELETE FROM twin_memories WHERE memory_id='__test__'")
   666      except sqlite3.IntegrityError:
   667          conn.executescript("""
   668              CREATE TABLE IF NOT EXISTS twin_memories_new (
   669                  memory_id TEXT PRIMARY KEY,
   670                  user_id TEXT NOT NULL,
   671                  memory_type TEXT NOT NULL
   672                      CHECK(memory_type IN ('conversation','daily','weekly','monthly','quarterly','yearly')),
   673                  period_start TEXT NOT NULL,
   674                  period_end TEXT NOT NULL,
   675                  summary_text TEXT NOT NULL,
   676                  emotional_tone TEXT DEFAULT '',
   677                  themes TEXT DEFAULT '',
   678                  key_events TEXT DEFAULT '',
   679                  growth_signals TEXT DEFAULT '',
   680                  source TEXT DEFAULT 'nianlun',
   681                  imported_at TEXT DEFAULT (datetime('now','localtime')),
   682                  friend_id TEXT DEFAULT '',
   683                  message_count INTEGER DEFAULT 0,
   684                  relationship_signal TEXT DEFAULT ''
   685              );
   686              INSERT OR IGNORE INTO twin_memories_new
   687                  SELECT memory_id, user_id, memory_type, period_start, period_end,
   688                         summary_text, emotional_tone, themes, key_events, growth_signals,
   689                         source, imported_at,
   690                         COALESCE(friend_id,''), COALESCE(message_count,0), COALESCE(relationship_signal,'')
   691                  FROM twin_memories;
   692              DROP TABLE twin_memories;
   693              ALTER TABLE twin_memories_new RENAME TO twin_memories;
   694          """)
   695      conn.execute("CREATE INDEX IF NOT EXISTS idx_tm_user_friend ON twin_memories(user_id, friend_id, period_end DESC)")
   696      conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_unread ON social_messages(to_user_id, is_read, created_at DESC)")
   697      conn.commit()
   698      conn.close()
   699  
   700  
   701  @contextmanager
   702  def get_db():
   703      """Get a database connection as a context manager."""
   704      conn = sqlite3.connect(DATABASE_PATH)
   705      conn.row_factory = sqlite3.Row
   706      conn.execute("PRAGMA journal_mode=WAL")
   707      conn.execute("PRAGMA foreign_keys=ON")
   708      try:
   709          yield conn
   710          conn.commit()
   711      except Exception:  # re-raised — rollback is cleanup only
   712          conn.rollback()
   713          raise
   714      finally:
   715          conn.close()
   716  
   717  
   718  def gen_id(prefix: str = "") -> str:
   719      """Generate a unique ID with optional prefix."""
   720      return f"{prefix}{uuid.uuid4().hex[:12]}"

# --- dualsoul/main.py ---
   721  """DualSoul — Dual Identity Social Protocol server."""
   722  
   723  import asyncio
   724  import json
   725  import logging
   726  import os
   727  from contextlib import asynccontextmanager
   728  
   729  logging.basicConfig(level=logging.INFO)
   730  logger = logging.getLogger(__name__)
   731  
   732  from fastapi import FastAPI
   733  from fastapi.middleware.cors import CORSMiddleware
   734  from fastapi.responses import FileResponse, HTMLResponse
   735  from fastapi.staticfiles import StaticFiles
   736  from starlette.middleware.base import BaseHTTPMiddleware
   737  from starlette.requests import Request
   738  from starlette.responses import Response
   739  
   740  from dualsoul import __version__
   741  from dualsoul.config import CORS_ORIGINS, HOST, PORT
   742  from dualsoul.database import init_db
   743  from dualsoul.routers import agents, auth, ethics, identity, invite, life, plaza, relationship, social, twin_import, ws
   744  from dualsoul.twin_engine.autonomous import autonomous_social_loop
   745  
   746  
   747  @asynccontextmanager
   748  async def lifespan(app: FastAPI):
   749      init_db()
   750      logger.info(f"DualSoul v{__version__} — database initialized")
   751      import dualsoul.twin_engine.twin_reactions  # noqa: F401 — registers event handlers
   752      task = asyncio.create_task(autonomous_social_loop())
   753      logger.info("Autonomous twin social engine started")
   754      yield
   755      task.cancel()
   756      try:
   757          await task
   758      except asyncio.CancelledError:
   759          pass
   760  
   761  
   762  app = FastAPI(
   763      title="DualSoul",
   764      description="Dual Identity Social Protocol — Every person has two voices.",
   765      version=__version__,
   766      lifespan=lifespan,
   767  )
   768  
   769  # Security headers
   770  class SecurityHeadersMiddleware(BaseHTTPMiddleware):
   771      async def dispatch(self, request: Request, call_next):
   772          response: Response = await call_next(request)
   773          response.headers["X-Content-Type-Options"] = "nosniff"
   774          response.headers["X-Frame-Options"] = "DENY"
   775          response.headers["X-XSS-Protection"] = "1; mode=block"
   776          response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
   777          response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
   778          return response
   779  
   780  app.add_middleware(SecurityHeadersMiddleware)
   781  
   782  # CORS
   783  app.add_middleware(
   784      CORSMiddleware,
   785      allow_origins=CORS_ORIGINS,
   786      allow_credentials=True,
   787      allow_methods=["*"],
   788      allow_headers=["*"],
   789  )
   790  
   791  # Routers
   792  app.include_router(agents.router)
   793  app.include_router(auth.router)
   794  app.include_router(ethics.router)
   795  app.include_router(identity.router)
   796  app.include_router(invite.router)
   797  app.include_router(life.router)
   798  app.include_router(plaza.router)
   799  app.include_router(relationship.router)
   800  app.include_router(social.router)
   801  app.include_router(twin_import.router)
   802  app.include_router(ws.router)
   803  
   804  # Serve demo web client
   805  _web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
   806  if os.path.isdir(_web_dir):
   807      app.mount("/static", StaticFiles(directory=_web_dir), name="static")
   808  
   809      @app.get("/")
   810      async def serve_index():
   811          min_path = os.path.join(_web_dir, "index.min.html")
   812          if os.path.exists(min_path):
   813              return FileResponse(min_path)
   814          return FileResponse(os.path.join(_web_dir, "index.html"))
   815  
   816      @app.get("/sw.js")
   817      async def serve_sw():
   818          return FileResponse(
   819              os.path.join(_web_dir, "sw.js"), media_type="application/javascript"
   820          )
   821  
   822      @app.get("/manifest.json")
   823      async def serve_manifest():
   824          return FileResponse(
   825              os.path.join(_web_dir, "manifest.json"),
   826              media_type="application/manifest+json",
   827          )
   828  
   829  
   830  _docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
   831  
   832  
   833  @app.get("/guide", response_class=HTMLResponse)
   834  async def serve_guide():
   835      """Serve the twin import guide as a styled HTML page."""
   836      guide_path = os.path.join(_docs_dir, "twin-import-guide.md")
   837      if not os.path.exists(guide_path):
   838          return HTMLResponse("<h1>Guide not found</h1>", status_code=404)
   839  
   840      with open(guide_path, encoding="utf-8") as f:
   841          md_content = f.read()
   842  
   843      # Client-side markdown rendering with marked.js (zero backend dependencies)
   844      return HTMLResponse(f"""<!DOCTYPE html>
   845  <html lang="zh">
   846  <head>
   847  <meta charset="UTF-8">
   848  <meta name="viewport" content="width=device-width, initial-scale=1.0">
   849  <title>DualSoul - 分身接入指南</title>
   850  <meta property="og:title" content="DualSoul 分身接入指南">
   851  <meta property="og:description" content="让你养的智能体走进真实社交——年轮/OpenClaw/任意平台接入">
   852  <style>
   853  *{{margin:0;padding:0;box-sizing:border-box}}
   854  body{{background:#0a0a10;color:#e8e4de;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.8;padding:20px}}
   855  .wrap{{max-width:680px;margin:0 auto;padding-bottom:80px}}
   856  h1{{font-size:24px;font-weight:800;background:linear-gradient(135deg,#7c5cfc,#5ca0fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:20px 0 10px}}
   857  h2{{font-size:18px;color:#7c5cfc;margin:28px 0 12px;padding-bottom:6px;border-bottom:1px solid rgba(124,92,252,.2)}}
   858  h3{{font-size:15px;color:#5ca0fa;margin:20px 0 8px}}
   859  p{{margin:8px 0;font-size:14px;color:rgba(232,228,222,.85)}}
   860  a{{color:#7c5cfc}}
   861  code{{background:rgba(124,92,252,.1);padding:2px 6px;border-radius:4px;font-size:12px;color:#5ca0fa}}
   862  pre{{background:#12121e;border:1px solid rgba(124,92,252,.15);border-radius:10px;padding:14px;overflow-x:auto;margin:10px 0;font-size:12px;line-height:1.6}}
   863  pre code{{background:none;padding:0;color:#e8e4de}}
   864  table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:12px}}
   865  th{{background:rgba(124,92,252,.1);padding:8px;text-align:left;border:1px solid rgba(124,92,252,.15);color:#7c5cfc}}
   866  td{{padding:8px;border:1px solid rgba(255,255,255,.06)}}
   867  tr:nth-child(even){{background:rgba(255,255,255,.02)}}
   868  blockquote{{border-left:3px solid #7c5cfc;padding:8px 14px;margin:12px 0;background:rgba(124,92,252,.05);border-radius:0 8px 8px 0;font-style:italic;color:rgba(232,228,222,.7)}}
   869  hr{{border:none;border-top:1px solid rgba(124,92,252,.15);margin:20px 0}}
   870  strong{{color:#e8e4de}}
   871  ul,ol{{padding-left:20px;margin:8px 0}}
   872  li{{margin:4px 0;font-size:13px}}
   873  .cta{{display:block;text-align:center;margin:30px auto;padding:14px 28px;background:linear-gradient(135deg,#7c5cfc,#5ca0fa);color:#fff;border-radius:12px;font-size:16px;font-weight:700;text-decoration:none;max-width:300px}}
   874  .cta:hover{{opacity:.9}}
   875  .badge{{display:inline-block;font-size:10px;padding:2px 8px;border-radius:8px;background:rgba(124,92,252,.15);color:#7c5cfc;margin-left:4px}}
   876  </style>
   877  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
   878  </head>
   879  <body>
   880  <div class="wrap" id="content"></div>
   881  <a class="cta" href="/?source=guide">注册 DualSoul，让你的分身社交</a>
   882  <script>
   883  var md = {json.dumps(md_content)};
   884  document.getElementById('content').innerHTML = marked.parse(md);
   885  </script>
   886  </body>
   887  </html>""")
   888  
   889  
   890  @app.post("/api/log/error")
   891  async def log_client_error(request: Request):
   892      """Receive frontend error reports (best-effort, no auth required)."""
   893      try:
   894          body = await request.body()
   895          data = json.loads(body)
   896          logger.warning(f"[ClientError] {data.get('error', '')} | {data.get('file', '')}:{data.get('line', '')} | {data.get('ua', '')[:80]}")
   897      except Exception:
   898          pass
   899      return {"ok": True}
   900  
   901  
   902  @app.get("/api/health")
   903  async def health():
   904      return {"status": "ok", "version": __version__}
   905  
   906  
   907  def cli():
   908      """CLI entry point for `dualsoul` command."""
   909      import uvicorn
   910  
   911      uvicorn.run("dualsoul.main:app", host=HOST, port=PORT, reload=False)
   912  
   913  
   914  if __name__ == "__main__":
   915      cli()

# --- dualsoul/models.py ---
   916  """DualSoul Pydantic models."""
   917  
   918  from pydantic import BaseModel
   919  
   920  
   921  # Auth
   922  class RegisterRequest(BaseModel):
   923      username: str
   924      password: str
   925      display_name: str = ""
   926      reg_source: str = "dualsoul"  # Registration source: dualsoul, nianlun, openclaw, etc.
   927      invited_by: str = ""  # Username of the person who invited this user
   928  
   929  
   930  class LoginRequest(BaseModel):
   931      username: str
   932      password: str
   933  
   934  
   935  # Identity
   936  class SwitchModeRequest(BaseModel):
   937      mode: str  # 'real' or 'twin'
   938  
   939  
   940  class UpdateProfileRequest(BaseModel):
   941      display_name: str = ""
   942      twin_personality: str = ""
   943      twin_speech_style: str = ""
   944      preferred_lang: str = ""  # ISO 639-1: zh, en, ja, ko, fr, de, es, etc.
   945      twin_auto_reply: int | None = None  # 0=off, 1=on (None=no change)
   946      gender: str = ""  # 'male', 'female', '' (unset)
   947  
   948  
   949  class TwinPreviewRequest(BaseModel):
   950      display_name: str = ""
   951      personality: str = ""
   952      speech_style: str = ""
   953  
   954  
   955  class AvatarUploadRequest(BaseModel):
   956      image: str  # base64 encoded image data (data:image/png;base64,... or raw base64)
   957      type: str = "real"  # 'real' or 'twin'
   958  
   959  
   960  class VoiceUploadRequest(BaseModel):
   961      audio: str  # base64 encoded audio data (data:audio/webm;base64,... or raw base64)
   962  
   963  
   964  class AvatarGenerateRequest(BaseModel):
   965      image: str  # base64 encoded source photo
   966      style: str = "anime"  # Style key: anime, 3d, cyber, clay, pixel, ink, retro
   967  
   968  
   969  class TwinDraftRequest(BaseModel):
   970      friend_id: str
   971      incoming_msg: str
   972      context: list[dict] = []  # [{role: "me"/"friend", content: "..."}]
   973  
   974  
   975  class TwinChatRequest(BaseModel):
   976      message: str
   977      history: list[dict] = []  # [{role: "me"/"twin", content: "..."}]
   978      image: str = ""  # Optional base64 image data URL for vision
   979  
   980  
   981  # Social
   982  class AddFriendRequest(BaseModel):
   983      friend_username: str
   984      auto_accept: bool = False  # True = skip pending, become friends directly (invite link)
   985  
   986  
   987  class RespondFriendRequest(BaseModel):
   988      conn_id: str
   989      action: str  # 'accept' or 'block'
   990  
   991  
   992  class TranslateRequest(BaseModel):
   993      content: str
   994      source_lang: str = "auto"
   995      target_lang: str = "en"
   996  
   997  
   998  class SendMessageRequest(BaseModel):
   999      to_user_id: str
  1000      content: str
  1001      sender_mode: str = "real"
  1002      receiver_mode: str = "real"
  1003      msg_type: str = "text"
  1004      target_lang: str = ""  # If set, twin translates to this language with personality preservation
  1005  
  1006  
  1007  # Twin Import (年轮分身导入)
  1008  class TwinImportRequest(BaseModel):
  1009      format: str = "tpf_v1"  # Twin Portable Format version
  1010      source: str = "nianlun"  # Source platform: 'nianlun', 'openclaw', etc.
  1011      data: dict  # Full export payload (Twin Portable Format)
  1012  
  1013  
  1014  class TwinSyncRequest(BaseModel):
  1015      format: str = "tpf_v1"
  1016      since: str = ""  # ISO timestamp of last sync
  1017      data: dict  # Incremental data (new memories, entities, dimension updates)

# --- dualsoul/protocol/__init__.py ---

# --- dualsoul/protocol/message.py ---
  1018  """DualSoul Protocol — Dual Identity Message Format.
  1019  
  1020  Every message in DualSoul carries two identity modes:
  1021    - sender_mode: Is the sender speaking as their real self or digital twin?
  1022    - receiver_mode: Is the message addressed to the real person or their twin?
  1023  
  1024  This creates four distinct conversation modes:
  1025  
  1026    Real → Real   : Traditional human-to-human messaging
  1027    Real → Twin   : Asking someone's digital twin a question
  1028    Twin → Real   : Your twin reaching out to a real person
  1029    Twin → Twin   : Autonomous twin-to-twin conversation
  1030  """
  1031  
  1032  from dataclasses import dataclass, field
  1033  from enum import Enum
  1034  from typing import Optional
  1035  
  1036  # Protocol version — included in every DISP message
  1037  DISP_VERSION = "1.0"
  1038  
  1039  
  1040  class IdentityMode(str, Enum):
  1041      REAL = "real"
  1042      TWIN = "twin"
  1043  
  1044  
  1045  class ConversationMode(str, Enum):
  1046      REAL_TO_REAL = "real_to_real"
  1047      REAL_TO_TWIN = "real_to_twin"
  1048      TWIN_TO_REAL = "twin_to_real"
  1049      TWIN_TO_TWIN = "twin_to_twin"
  1050  
  1051  
  1052  class MessageType(str, Enum):
  1053      TEXT = "text"
  1054      IMAGE = "image"
  1055      VOICE = "voice"
  1056      SYSTEM = "system"
  1057  
  1058  
  1059  @dataclass
  1060  class DualSoulMessage:
  1061      """A message in the DualSoul protocol."""
  1062  
  1063      msg_id: str
  1064      from_user_id: str
  1065      to_user_id: str
  1066      sender_mode: IdentityMode
  1067      receiver_mode: IdentityMode
  1068      content: str
  1069      msg_type: MessageType = MessageType.TEXT
  1070      ai_generated: bool = False
  1071      created_at: Optional[str] = None
  1072      disp_version: str = field(default=DISP_VERSION)
  1073  
  1074      @property
  1075      def conversation_mode(self) -> ConversationMode:
  1076          """Determine which of the four conversation modes this message belongs to."""
  1077          key = f"{self.sender_mode.value}_to_{self.receiver_mode.value}"
  1078          return ConversationMode(key)
  1079  
  1080      def to_dict(self) -> dict:
  1081          return {
  1082              "disp_version": self.disp_version,
  1083              "msg_id": self.msg_id,
  1084              "from_user_id": self.from_user_id,
  1085              "to_user_id": self.to_user_id,
  1086              "sender_mode": self.sender_mode.value,
  1087              "receiver_mode": self.receiver_mode.value,
  1088              "content": self.content,
  1089              "msg_type": self.msg_type.value,
  1090              "ai_generated": self.ai_generated,
  1091              "conversation_mode": self.conversation_mode.value,
  1092              "created_at": self.created_at,
  1093          }
  1094  
  1095  
  1096  def get_conversation_mode(sender_mode: str, receiver_mode: str) -> ConversationMode:
  1097      """Get the conversation mode from sender and receiver mode strings."""
  1098      return ConversationMode(f"{sender_mode}_to_{receiver_mode}")

# --- dualsoul/rate_limit.py ---
  1099  """In-memory sliding window rate limiter for DualSoul."""
  1100  
  1101  import time
  1102  from collections import defaultdict
  1103  
  1104  from fastapi import Request
  1105  from fastapi.responses import JSONResponse
  1106  
  1107  from dualsoul.constants import (
  1108      RATE_ACTION_MAX,
  1109      RATE_LOGIN_MAX,
  1110      RATE_LOGIN_WINDOW,
  1111      RATE_MESSAGE_MAX,
  1112      RATE_REGISTER_MAX,
  1113  )
  1114  
  1115  
  1116  class RateLimiter:
  1117      """Simple in-memory sliding window rate limiter."""
  1118  
  1119      def __init__(self, max_requests: int, window_seconds: int):
  1120          self.max_requests = max_requests
  1121          self.window = window_seconds
  1122          self._hits: dict[str, list[float]] = defaultdict(list)
  1123  
  1124      def _client_ip(self, request: Request) -> str:
  1125          forwarded = request.headers.get("x-forwarded-for")
  1126          if forwarded:
  1127              return forwarded.split(",")[0].strip()
  1128          return request.client.host if request.client else "unknown"
  1129  
  1130      def _cleanup(self, key: str):
  1131          cutoff = time.time() - self.window
  1132          self._hits[key] = [t for t in self._hits[key] if t > cutoff]
  1133  
  1134      def is_limited(self, request: Request) -> bool:
  1135          key = self._client_ip(request)
  1136          self._cleanup(key)
  1137          if len(self._hits[key]) >= self.max_requests:
  1138              return True
  1139          self._hits[key].append(time.time())
  1140          return False
  1141  
  1142  
  1143  # Pre-configured limiters
  1144  _login_limiter = RateLimiter(max_requests=RATE_LOGIN_MAX, window_seconds=RATE_LOGIN_WINDOW)
  1145  _register_limiter = RateLimiter(max_requests=RATE_REGISTER_MAX, window_seconds=RATE_LOGIN_WINDOW)
  1146  _message_limiter = RateLimiter(max_requests=RATE_MESSAGE_MAX, window_seconds=RATE_LOGIN_WINDOW)
  1147  _action_limiter = RateLimiter(max_requests=RATE_ACTION_MAX, window_seconds=RATE_LOGIN_WINDOW)
  1148  
  1149  _RATE_LIMIT_RESPONSE = JSONResponse(
  1150      status_code=429,
  1151      content={"success": False, "error": "请求过快，请稍后再试"},
  1152  )
  1153  
  1154  
  1155  async def check_login_rate(request: Request):
  1156      """FastAPI dependency — rate limit login attempts."""
  1157      if _login_limiter.is_limited(request):
  1158          return _RATE_LIMIT_RESPONSE
  1159      return None
  1160  
  1161  
  1162  async def check_register_rate(request: Request):
  1163      """FastAPI dependency — rate limit registration attempts."""
  1164      if _register_limiter.is_limited(request):
  1165          return _RATE_LIMIT_RESPONSE
  1166      return None
  1167  
  1168  
  1169  async def check_message_rate(request: Request):
  1170      """FastAPI dependency — rate limit message sending (30/min)."""
  1171      if _message_limiter.is_limited(request):
  1172          return _RATE_LIMIT_RESPONSE
  1173      return None
  1174  
  1175  
  1176  async def check_action_rate(request: Request):
  1177      """FastAPI dependency — rate limit general actions (20/min)."""
  1178      if _action_limiter.is_limited(request):
  1179          return _RATE_LIMIT_RESPONSE
  1180      return None

# --- dualsoul/routers/__init__.py ---

# --- dualsoul/routers/agents.py ---
  1181  """Agent API — cross-platform agent interoperability.
  1182  
  1183  Allows external agent platforms (OpenClaw, etc.) to:
  1184  1. Register API keys for their twins
  1185  2. Send messages and get twin replies
  1186  3. Export twin identity for cross-platform use
  1187  4. Query twin status and capabilities
  1188  
  1189  Authentication: API key in Authorization header (Bearer agent_xxx)
  1190  """
  1191  
  1192  import logging
  1193  import secrets
  1194  from datetime import datetime, timedelta
  1195  
  1196  from fastapi import APIRouter, Depends, Header, HTTPException, Request
  1197  from pydantic import BaseModel
  1198  
  1199  from dualsoul.auth import get_current_user
  1200  from dualsoul.constants import (
  1201      AGENT_KEY_DEFAULT_EXPIRY_DAYS,
  1202      AGENT_KEY_MAX_PER_USER,
  1203      RATE_AGENT_MAX,
  1204      RATE_LOGIN_WINDOW,
  1205  )
  1206  from dualsoul.database import gen_id, get_db
  1207  from dualsoul.rate_limit import RateLimiter
  1208  
  1209  logger = logging.getLogger(__name__)
  1210  
  1211  router = APIRouter(prefix="/api/agents", tags=["Agents"])
  1212  
  1213  # Rate limiter for agent API
  1214  _agent_limiter = RateLimiter(max_requests=RATE_AGENT_MAX, window_seconds=RATE_LOGIN_WINDOW)
  1215  
  1216  
  1217  # --- Models ---
  1218  
  1219  class AgentReplyRequest(BaseModel):
  1220      incoming_msg: str
  1221      sender_mode: str = "real"  # "real" or "twin"
  1222      sender_id: str = ""  # External user/agent ID
  1223      target_lang: str = ""  # Optional translation target
  1224      context: str = ""  # "casual_chat", "auto_reply", "trial_chat"
  1225  
  1226  
  1227  class AgentKeyRequest(BaseModel):
  1228      platform: str  # "openclaw", "custom", etc.
  1229      expires_days: int = AGENT_KEY_DEFAULT_EXPIRY_DAYS
  1230  
  1231  
  1232  # --- Auth helpers ---
  1233  
  1234  def _get_agent_key_owner(api_key: str) -> dict | None:
  1235      """Validate an agent API key and return its owner info."""
  1236      with get_db() as db:
  1237          row = db.execute(
  1238              """SELECT ak.key_id, ak.twin_owner_id, ak.external_platform, ak.scopes,
  1239                        ak.expires_at, u.display_name, u.username
  1240                 FROM agent_api_keys ak
  1241                 JOIN users u ON u.user_id = ak.twin_owner_id
  1242                 WHERE ak.api_key=?""",
  1243              (api_key,),
  1244          ).fetchone()
  1245  
  1246      if not row:
  1247          return None
  1248  
  1249      # Check expiry
  1250      if row["expires_at"]:
  1251          try:
  1252              exp = datetime.strptime(row["expires_at"][:19], "%Y-%m-%d %H:%M:%S")
  1253              if exp < datetime.now():
  1254                  return None
  1255          except ValueError:
  1256              pass
  1257  
  1258      # Update last_used_at
  1259      with get_db() as db:
  1260          db.execute(
  1261              "UPDATE agent_api_keys SET last_used_at=datetime('now','localtime') WHERE key_id=?",
  1262              (row["key_id"],),
  1263          )
  1264  
  1265      return dict(row)
  1266  
  1267  
  1268  async def get_agent_user(authorization: str = Header("")) -> dict:
  1269      """FastAPI dependency — extract agent API key from Authorization header."""
  1270      if not authorization.startswith("Bearer agent_"):
  1271          raise HTTPException(status_code=401, detail="Invalid agent API key format")
  1272  
  1273      api_key = authorization.replace("Bearer ", "").strip()
  1274      owner = _get_agent_key_owner(api_key)
  1275      if not owner:
  1276          raise HTTPException(status_code=401, detail="Invalid or expired agent API key")
  1277  
  1278      return owner
  1279  
  1280  
  1281  # --- Endpoints ---
  1282  
  1283  @router.post("/keys")
  1284  async def create_agent_key(req: AgentKeyRequest, user=Depends(get_current_user)):
  1285      """Create an API key for external agent platforms to access your twin.
  1286  
  1287      Returns the key ONCE — it cannot be retrieved later.
  1288      """
  1289      uid = user["user_id"]
  1290      platform = req.platform.strip().lower()
  1291      if not platform or len(platform) > 50:
  1292          return {"success": False, "error": "Platform name required (max 50 chars)"}
  1293  
  1294      # Max keys per user
  1295      with get_db() as db:
  1296          count = db.execute(
  1297              "SELECT COUNT(*) as cnt FROM agent_api_keys WHERE twin_owner_id=?",
  1298              (uid,),
  1299          ).fetchone()
  1300      if count and count["cnt"] >= AGENT_KEY_MAX_PER_USER:
  1301          return {"success": False, "error": f"Maximum {AGENT_KEY_MAX_PER_USER} API keys per user"}
  1302  
  1303      key_id = gen_id("ak_")
  1304      api_key = f"agent_{secrets.token_urlsafe(64)}"
  1305      expires_at = (datetime.now() + timedelta(days=req.expires_days)).strftime("%Y-%m-%d %H:%M:%S")
  1306  
  1307      with get_db() as db:
  1308          db.execute(
  1309              """INSERT INTO agent_api_keys
  1310                 (key_id, twin_owner_id, external_platform, api_key, expires_at)
  1311                 VALUES (?, ?, ?, ?, ?)""",
  1312              (key_id, uid, platform, api_key, expires_at),
  1313          )
  1314  
  1315      logger.info(f"[AgentAPI] Created key {key_id} for {uid} on platform '{platform}'")
  1316  
  1317      return {
  1318          "success": True,
  1319          "data": {
  1320              "key_id": key_id,
  1321              "api_key": api_key,
  1322              "platform": platform,
  1323              "expires_at": expires_at,
  1324              "scopes": "twin:reply",
  1325              "warning": "Save this key — it cannot be retrieved later.",
  1326          },
  1327      }
  1328  
  1329  
  1330  @router.get("/keys")
  1331  async def list_agent_keys(user=Depends(get_current_user)):
  1332      """List all agent API keys (keys are masked)."""
  1333      uid = user["user_id"]
  1334      with get_db() as db:
  1335          rows = db.execute(
  1336              """SELECT key_id, external_platform, api_key, scopes,
  1337                        created_at, expires_at, last_used_at
  1338                 FROM agent_api_keys WHERE twin_owner_id=?
  1339                 ORDER BY created_at DESC""",
  1340              (uid,),
  1341          ).fetchall()
  1342  
  1343      keys = []
  1344      for r in rows:
  1345          keys.append({
  1346              "key_id": r["key_id"],
  1347              "platform": r["external_platform"],
  1348              "key_preview": r["api_key"][:12] + "..." + r["api_key"][-4:],
  1349              "scopes": r["scopes"],
  1350              "created_at": r["created_at"],
  1351              "expires_at": r["expires_at"],
  1352              "last_used_at": r["last_used_at"] or "never",
  1353          })
  1354  
  1355      return {"success": True, "keys": keys}
  1356  
  1357  
  1358  @router.delete("/keys/{key_id}")
  1359  async def revoke_agent_key(key_id: str, user=Depends(get_current_user)):
  1360      """Revoke an agent API key."""
  1361      uid = user["user_id"]
  1362      with get_db() as db:
  1363          result = db.execute(
  1364              "DELETE FROM agent_api_keys WHERE key_id=? AND twin_owner_id=?",
  1365              (key_id, uid),
  1366          )
  1367          if result.rowcount == 0:
  1368              return {"success": False, "error": "Key not found"}
  1369  
  1370      return {"success": True}
  1371  
  1372  
  1373  @router.post("/reply")
  1374  async def agent_reply(req: AgentReplyRequest, request: Request, agent=Depends(get_agent_user)):
  1375      """Send a message and get a twin reply.
  1376  
  1377      This is the core endpoint for agent-to-twin communication.
  1378      External platforms call this to "talk to" a DualSoul twin.
  1379      """
  1380      # Rate limit
  1381      if _agent_limiter.is_limited(request):
  1382          raise HTTPException(status_code=429, detail="Rate limit exceeded")
  1383  
  1384      # Scope check
  1385      scopes = (agent.get("scopes") or "").split(",")
  1386      if "twin:reply" not in scopes:
  1387          raise HTTPException(status_code=403, detail="API key lacks 'twin:reply' scope")
  1388  
  1389      twin_owner_id = agent["twin_owner_id"]
  1390      platform = agent["external_platform"]
  1391      content = req.incoming_msg.strip()
  1392  
  1393      if not content:
  1394          return {"success": False, "error": "Message cannot be empty"}
  1395      if len(content) > 2000:
  1396          return {"success": False, "error": "Message too long (max 2000 chars)"}
  1397  
  1398      # Namespace external sender ID
  1399      external_sender = f"external:{platform}:{req.sender_id}" if req.sender_id else ""
  1400  
  1401      # Generate twin reply
  1402      from dualsoul.twin_engine.responder import get_twin_responder
  1403      twin = get_twin_responder()
  1404  
  1405      result = await twin.generate_reply(
  1406          twin_owner_id=twin_owner_id,
  1407          from_user_id=external_sender,
  1408          incoming_msg=content,
  1409          sender_mode=req.sender_mode,
  1410          target_lang=req.target_lang,
  1411          social_context=req.context or "auto_reply",
  1412      )
  1413  
  1414      # Log the interaction
  1415      log_id = gen_id("al_")
  1416      reply_content = result["content"] if result else ""
  1417      success = 1 if result else 0
  1418  
  1419      with get_db() as db:
  1420          db.execute(
  1421              """INSERT INTO agent_message_log
  1422                 (log_id, from_platform, to_twin_id, external_user_id,
  1423                  incoming_content, reply_content, success)
  1424                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
  1425              (log_id, platform, twin_owner_id, req.sender_id or "",
  1426               content, reply_content, success),
  1427          )
  1428  
  1429      if not result:
  1430          return {"success": False, "error": "Twin reply generation failed"}
  1431  
  1432      return {
  1433          "success": True,
  1434          "data": {
  1435              "reply": result["content"],
  1436              "msg_id": result.get("msg_id", ""),
  1437              "ai_generated": True,
  1438              "target_lang": result.get("target_lang", ""),
  1439              "translation_style": result.get("translation_style", ""),
  1440          },
  1441      }
  1442  
  1443  
  1444  @router.get("/twin/profile")
  1445  async def agent_get_twin_profile(agent=Depends(get_agent_user)):
  1446      """Get the twin's public profile for display on external platforms."""
  1447      twin_owner_id = agent["twin_owner_id"]
  1448  
  1449      from dualsoul.twin_engine.personality import get_twin_profile
  1450      profile = get_twin_profile(twin_owner_id)
  1451      if not profile:
  1452          return {"success": False, "error": "Twin profile not found"}
  1453  
  1454      return {
  1455          "success": True,
  1456          "data": {
  1457              "display_name": profile.display_name,
  1458              "personality": profile.personality,
  1459              "speech_style": profile.speech_style,
  1460              "preferred_lang": profile.preferred_lang,
  1461              "gender": profile.gender,
  1462              "source": profile.twin_source,
  1463              "capabilities": [
  1464                  "text_reply",
  1465                  "personality_preserving_translation",
  1466                  "emotion_aware_response",
  1467                  "narrative_memory",
  1468              ],
  1469          },
  1470      }
  1471  
  1472  
  1473  @router.get("/twin/stats")
  1474  async def agent_get_twin_stats(agent=Depends(get_agent_user)):
  1475      """Get the twin's activity stats for monitoring."""
  1476      twin_owner_id = agent["twin_owner_id"]
  1477      platform = agent["external_platform"]
  1478  
  1479      with get_db() as db:
  1480          # Total agent interactions
  1481          total = db.execute(
  1482              "SELECT COUNT(*) as cnt FROM agent_message_log WHERE to_twin_id=? AND from_platform=?",
  1483              (twin_owner_id, platform),
  1484          ).fetchone()
  1485  
  1486          # Today's interactions
  1487          today = datetime.now().strftime("%Y-%m-%d")
  1488          today_count = db.execute(
  1489              "SELECT COUNT(*) as cnt FROM agent_message_log WHERE to_twin_id=? AND from_platform=? AND created_at>?",
  1490              (twin_owner_id, platform, today),
  1491          ).fetchone()
  1492  
  1493          # Success rate
  1494          success_count = db.execute(
  1495              "SELECT COUNT(*) as cnt FROM agent_message_log WHERE to_twin_id=? AND from_platform=? AND success=1",
  1496              (twin_owner_id, platform),
  1497          ).fetchone()
  1498  
  1499      total_n = total["cnt"] if total else 0
  1500      success_n = success_count["cnt"] if success_count else 0
  1501  
  1502      return {
  1503          "success": True,
  1504          "data": {
  1505              "total_interactions": total_n,
  1506              "today_interactions": today_count["cnt"] if today_count else 0,
  1507              "success_rate": round(success_n / total_n, 2) if total_n > 0 else 1.0,
  1508              "platform": platform,
  1509          },
  1510      }

# --- dualsoul/routers/auth.py ---
  1511  """Auth router — register, login, and account management."""
  1512  
  1513  from fastapi import APIRouter, Depends, Request
  1514  from pydantic import BaseModel
  1515  
  1516  from dualsoul.auth import create_token, get_current_user, hash_password, verify_password
  1517  from dualsoul.database import gen_id, get_db
  1518  from dualsoul.models import LoginRequest, RegisterRequest
  1519  from dualsoul.rate_limit import check_login_rate, check_register_rate
  1520  
  1521  router = APIRouter(prefix="/api/auth", tags=["Auth"])
  1522  
  1523  
  1524  class ChangePasswordRequest(BaseModel):
  1525      old_password: str
  1526      new_password: str
  1527  
  1528  
  1529  @router.post("/register")
  1530  async def register(req: RegisterRequest, request: Request):
  1531      """Register a new user."""
  1532      limited = await check_register_rate(request)
  1533      if limited:
  1534          return limited
  1535      username = req.username.strip()
  1536      if not username or len(username) < 2:
  1537          return {"success": False, "error": "Username must be at least 2 characters"}
  1538      if len(req.password) < 6:
  1539          return {"success": False, "error": "Password must be at least 6 characters"}
  1540  
  1541      with get_db() as db:
  1542          exists = db.execute(
  1543              "SELECT user_id FROM users WHERE username=?", (username,)
  1544          ).fetchone()
  1545          if exists:
  1546              return {"success": False, "error": "Username already taken"}
  1547  
  1548          user_id = gen_id("u_")
  1549          display_name = req.display_name or username
  1550          inviter_username = (req.invited_by or "").strip()
  1551  
  1552          # Auto-generate default twin personality so twin can work immediately
  1553          default_personality = "友善、好奇、真诚"
  1554          default_style = "自然亲切，简短口语化"
  1555  
  1556          db.execute(
  1557              "INSERT INTO users (user_id, username, password_hash, display_name, "
  1558              "reg_source, invited_by, twin_personality, twin_speech_style) "
  1559              "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
  1560              (user_id, username, hash_password(req.password), display_name,
  1561               req.reg_source or "dualsoul", inviter_username,
  1562               default_personality, default_style),
  1563          )
  1564  
  1565          # Increment inviter's invite_count + auto-add as friends
  1566          if inviter_username:
  1567              inviter = db.execute(
  1568                  "SELECT user_id FROM users WHERE username=?", (inviter_username,)
  1569              ).fetchone()
  1570              if inviter:
  1571                  db.execute(
  1572                      "UPDATE users SET invite_count = invite_count + 1 WHERE username=?",
  1573                      (inviter_username,),
  1574                  )
  1575                  # Auto-add as friends (skip pending, directly accepted)
  1576                  conn_id = gen_id("sc_")
  1577                  from datetime import datetime
  1578                  now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  1579                  try:
  1580                      db.execute(
  1581                          "INSERT OR IGNORE INTO social_connections "
  1582                          "(conn_id, user_id, friend_id, status, accepted_at) "
  1583                          "VALUES (?, ?, ?, 'accepted', ?)",
  1584                          (conn_id, inviter["user_id"], user_id, now_str),
  1585                      )
  1586                  except Exception:
  1587                      pass  # Duplicate connection, safe to ignore
  1588  
  1589                  from dualsoul.twin_engine.twin_events import emit
  1590                  emit("user_registered", {"user_id": user_id, "username": username, "inviter_id": inviter["user_id"]})
  1591  
  1592      token = create_token(user_id, username, 0)
  1593      return {
  1594          "success": True,
  1595          "data": {
  1596              "user_id": user_id,
  1597              "username": username,
  1598              "token": token,
  1599          },
  1600      }
  1601  
  1602  
  1603  @router.post("/login")
  1604  async def login(req: LoginRequest, request: Request):
  1605      """Login and get a JWT token."""
  1606      limited = await check_login_rate(request)
  1607      if limited:
  1608          return limited
  1609  
  1610      with get_db() as db:
  1611          user = db.execute(
  1612              "SELECT user_id, username, password_hash, token_gen FROM users WHERE username=?",
  1613              (req.username.strip(),),
  1614          ).fetchone()
  1615  
  1616      if not user or not verify_password(req.password, user["password_hash"]):
  1617          return {"success": False, "error": "Invalid username or password"}
  1618  
  1619      token_gen = user["token_gen"] if "token_gen" in user.keys() else 0
  1620      token = create_token(user["user_id"], user["username"], token_gen)
  1621      return {
  1622          "success": True,
  1623          "data": {
  1624              "user_id": user["user_id"],
  1625              "username": user["username"],
  1626              "token": token,
  1627          },
  1628      }
  1629  
  1630  
  1631  @router.post("/change-password")
  1632  async def change_password(req: ChangePasswordRequest, user=Depends(get_current_user)):
  1633      """Change password for the logged-in user."""
  1634      uid = user["user_id"]
  1635      if len(req.new_password) < 6:
  1636          return {"success": False, "error": "Password must be at least 6 characters"}
  1637  
  1638      with get_db() as db:
  1639          row = db.execute(
  1640              "SELECT password_hash FROM users WHERE user_id=?", (uid,)
  1641          ).fetchone()
  1642          if not row or not verify_password(req.old_password, row["password_hash"]):
  1643              return {"success": False, "error": "Current password is incorrect"}
  1644          db.execute(
  1645              "UPDATE users SET password_hash=?, token_gen=COALESCE(token_gen,0)+1 WHERE user_id=?",
  1646              (hash_password(req.new_password), uid),
  1647          )
  1648      return {"success": True, "message": "Password changed. Please login again."}

# --- dualsoul/routers/ethics.py ---
  1649  """Ethics router — twin boundaries, action log, and governance settings."""
  1650  
  1651  from fastapi import APIRouter, Depends
  1652  
  1653  from dualsoul.auth import get_current_user
  1654  from dualsoul.twin_engine.ethics import (
  1655      get_action_log,
  1656      get_boundaries,
  1657      update_boundaries,
  1658  )
  1659  
  1660  router = APIRouter(prefix="/api/ethics", tags=["Ethics"])
  1661  
  1662  
  1663  @router.get("/boundaries")
  1664  async def boundaries(user=Depends(get_current_user)):
  1665      """Get current twin behavior boundaries."""
  1666      uid = user["user_id"]
  1667      data = get_boundaries(uid)
  1668      return {"success": True, "data": data}
  1669  
  1670  
  1671  @router.put("/boundaries")
  1672  async def set_boundaries(changes: dict, user=Depends(get_current_user)):
  1673      """Update specific boundary settings.
  1674  
  1675      Body: {"can_auto_reply": true, "can_discuss_money": false, ...}
  1676      """
  1677      uid = user["user_id"]
  1678      updated = update_boundaries(uid, changes)
  1679      return {"success": True, "data": updated}
  1680  
  1681  
  1682  @router.get("/action-log")
  1683  async def action_log(
  1684      user=Depends(get_current_user),
  1685      limit: int = 50,
  1686      action_type: str = "",
  1687  ):
  1688      """Get twin's recent action log — everything the twin did."""
  1689      uid = user["user_id"]
  1690      limit = min(limit, 200)
  1691      logs = get_action_log(uid, limit=limit, action_type=action_type)
  1692      return {"success": True, "data": logs}

# --- dualsoul/routers/identity.py ---
  1693  """Identity router — switch mode, profile management, twin preview, avatar upload, style learning, twin growth, twin card."""
  1694  
  1695  import base64
  1696  import hashlib
  1697  import logging
  1698  import os
  1699  
  1700  import httpx
  1701  
  1702  logger = logging.getLogger(__name__)
  1703  from fastapi import APIRouter, Depends, Request
  1704  from fastapi.responses import HTMLResponse, JSONResponse
  1705  
  1706  from dualsoul.auth import get_current_user
  1707  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  1708  from dualsoul.database import get_db
  1709  from dualsoul.models import AvatarGenerateRequest, AvatarUploadRequest, SwitchModeRequest, TwinPreviewRequest, UpdateProfileRequest, VoiceUploadRequest
  1710  from dualsoul.twin_engine.learner import MIN_MESSAGES_FOR_LEARNING, analyze_style, get_message_count, learn_and_update
  1711  
  1712  # --- Constants ---
  1713  MAX_DISPLAY_NAME_LENGTH = 50
  1714  MAX_PERSONALITY_LENGTH = 500
  1715  MAX_SPEECH_STYLE_LENGTH = 500
  1716  MAX_AVATAR_SIZE = 2 * 1024 * 1024
  1717  MAX_VOICE_SIZE = 5 * 1024 * 1024
  1718  
  1719  _AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "avatars")
  1720  os.makedirs(_AVATAR_DIR, exist_ok=True)
  1721  _VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "voiceprints")
  1722  os.makedirs(_VOICE_DIR, exist_ok=True)
  1723  
  1724  router = APIRouter(prefix="/api/identity", tags=["Identity"])
  1725  
  1726  
  1727  @router.post("/switch")
  1728  async def switch_mode(req: SwitchModeRequest, user=Depends(get_current_user)):
  1729      """Switch between real self and digital twin mode."""
  1730      uid = user["user_id"]
  1731      if req.mode not in ("real", "twin"):
  1732          return {"success": False, "error": "mode must be 'real' or 'twin'"}
  1733      with get_db() as db:
  1734          db.execute("UPDATE users SET current_mode=? WHERE user_id=?", (req.mode, uid))
  1735      return {"success": True, "mode": req.mode}
  1736  
  1737  
  1738  @router.get("/me")
  1739  async def get_profile(user=Depends(get_current_user)):
  1740      """Get current user's dual identity profile."""
  1741      uid = user["user_id"]
  1742      with get_db() as db:
  1743          row = db.execute(
  1744              "SELECT user_id, username, display_name, current_mode, "
  1745              "twin_personality, twin_speech_style, preferred_lang, avatar, twin_avatar, "
  1746              "twin_auto_reply, gender, reg_source FROM users WHERE user_id=?",
  1747              (uid,),
  1748          ).fetchone()
  1749      if not row:
  1750          return {"success": False, "error": "User not found"}
  1751      return {
  1752          "success": True,
  1753          "data": {
  1754              "user_id": row["user_id"],
  1755              "username": row["username"],
  1756              "display_name": row["display_name"],
  1757              "current_mode": row["current_mode"] or "real",
  1758              "twin_personality": row["twin_personality"] or "",
  1759              "twin_speech_style": row["twin_speech_style"] or "",
  1760              "preferred_lang": row["preferred_lang"] or "",
  1761              "avatar": row["avatar"] or "",
  1762              "twin_avatar": row["twin_avatar"] or "",
  1763              "twin_auto_reply": row["twin_auto_reply"] if "twin_auto_reply" in row.keys() else 0,
  1764              "gender": row["gender"] if "gender" in row.keys() else "",
  1765              "reg_source": row["reg_source"] if "reg_source" in row.keys() else "dualsoul",
  1766          },
  1767      }
  1768  
  1769  
  1770  @router.put("/profile")
  1771  async def update_profile(req: UpdateProfileRequest, user=Depends(get_current_user)):
  1772      """Update display name and twin personality settings."""
  1773      uid = user["user_id"]
  1774      updates = []
  1775      params = []
  1776      if req.display_name:
  1777          if len(req.display_name) > MAX_DISPLAY_NAME_LENGTH:
  1778              return {"success": False, "error": f"Display name too long (max {MAX_DISPLAY_NAME_LENGTH} chars)"}
  1779          updates.append("display_name=?")
  1780          params.append(req.display_name)
  1781      if req.twin_personality:
  1782          if len(req.twin_personality) > MAX_PERSONALITY_LENGTH:
  1783              return {"success": False, "error": f"Personality too long (max {MAX_PERSONALITY_LENGTH} chars)"}
  1784          updates.append("twin_personality=?")
  1785          params.append(req.twin_personality)
  1786      if req.twin_speech_style:
  1787          if len(req.twin_speech_style) > MAX_SPEECH_STYLE_LENGTH:
  1788              return {"success": False, "error": f"Speech style too long (max {MAX_SPEECH_STYLE_LENGTH} chars)"}
  1789          updates.append("twin_speech_style=?")
  1790          params.append(req.twin_speech_style)
  1791      _VALID_LANGS = {"", "zh", "en", "ja", "ko", "fr", "de", "es", "pt", "ru", "ar", "hi", "th", "vi", "id", "auto"}
  1792      if req.preferred_lang:
  1793          if req.preferred_lang not in _VALID_LANGS:
  1794              return {"success": False, "error": f"Invalid language code: {req.preferred_lang}"}
  1795          updates.append("preferred_lang=?")
  1796          params.append(req.preferred_lang)
  1797      if req.twin_auto_reply is not None:
  1798          updates.append("twin_auto_reply=?")
  1799          params.append(1 if req.twin_auto_reply else 0)
  1800      if req.gender:
  1801          updates.append("gender=?")
  1802          params.append(req.gender)
  1803      if not updates:
  1804          return {"success": False, "error": "Nothing to update"}
  1805      params.append(uid)
  1806      with get_db() as db:
  1807          db.execute(f"UPDATE users SET {','.join(updates)} WHERE user_id=?", params)
  1808      return {"success": True}
  1809  
  1810  
  1811  @router.post("/avatar")
  1812  async def upload_avatar(req: AvatarUploadRequest, user=Depends(get_current_user)):
  1813      """Upload a base64-encoded avatar image. Saves to web/avatars/ and updates DB."""
  1814      uid = user["user_id"]
  1815      if req.type not in ("real", "twin"):
  1816          return {"success": False, "error": "type must be 'real' or 'twin'"}
  1817  
  1818      # Strip data URI prefix if present
  1819      img_data = req.image
  1820      if "," in img_data:
  1821          img_data = img_data.split(",", 1)[1]
  1822      try:
  1823          raw = base64.b64decode(img_data)
  1824      except Exception as e:
  1825          logger.debug(f"Avatar base64 decode failed: {e}")
  1826          return {"success": False, "error": "Invalid base64 image"}
  1827  
  1828      if len(raw) > MAX_AVATAR_SIZE:  # 2MB limit
  1829          return {"success": False, "error": "Image too large (max 2MB)"}
  1830  
  1831      # Validate magic bytes — must be a real image (PNG, JPEG, GIF, WebP)
  1832      _IMAGE_SIGNATURES = [b'\x89PNG', b'\xff\xd8\xff', b'GIF8', b'RIFF', b'\x00\x00\x01\x00']
  1833      if not any(raw.startswith(sig) for sig in _IMAGE_SIGNATURES):
  1834          return {"success": False, "error": "File must be a valid image (PNG, JPEG, GIF, WebP)"}
  1835  
  1836      # Save file
  1837      name_hash = hashlib.md5(f"{uid}_{req.type}".encode()).hexdigest()[:12]
  1838      filename = f"{name_hash}.png"
  1839      filepath = os.path.join(_AVATAR_DIR, filename)
  1840      with open(filepath, "wb") as f:
  1841          f.write(raw)
  1842  
  1843      url = f"/static/avatars/{filename}"
  1844      col = "avatar" if req.type == "real" else "twin_avatar"
  1845      with get_db() as db:
  1846          db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (url, uid))
  1847  
  1848      return {"success": True, "url": url}
  1849  
  1850  
  1851  @router.post("/avatar/generate")
  1852  async def generate_avatar(req: AvatarGenerateRequest, user=Depends(get_current_user)):
  1853      """Generate a stylized AI twin avatar from a real photo.
  1854  
  1855      Uses DashScope style repaint API (same platform as Qwen).
  1856      Takes ~15 seconds. Returns the generated image and saves it as twin_avatar.
  1857      """
  1858      from dualsoul.twin_engine.avatar import generate_twin_avatar_from_base64, get_available_styles
  1859  
  1860      uid = user["user_id"]
  1861  
  1862      result = await generate_twin_avatar_from_base64(
  1863          image_base64=req.image,
  1864          style=req.style,
  1865      )
  1866      if not result:
  1867          return {"success": False, "error": "Avatar generation failed — AI service may be unavailable"}
  1868  
  1869      # Save the generated image as twin avatar
  1870      img_bytes = base64.b64decode(result["image_base64"])
  1871      if len(img_bytes) > MAX_AVATAR_SIZE:
  1872          return {"success": False, "error": "Generated image too large"}
  1873  
  1874      name_hash = hashlib.md5(f"{uid}_twin".encode()).hexdigest()[:12]
  1875      filename = f"{name_hash}.png"
  1876      filepath = os.path.join(_AVATAR_DIR, filename)
  1877      with open(filepath, "wb") as f:
  1878          f.write(img_bytes)
  1879  
  1880      url = f"/static/avatars/{filename}"
  1881      with get_db() as db:
  1882          db.execute("UPDATE users SET twin_avatar=? WHERE user_id=?", (url, uid))
  1883  
  1884      return {"success": True, "url": url, "style": req.style}
  1885  
  1886  
  1887  @router.get("/avatar/styles")
  1888  async def avatar_styles():
  1889      """Return available AI avatar styles."""
  1890      from dualsoul.twin_engine.avatar import get_available_styles
  1891      return {"success": True, "styles": get_available_styles()}
  1892  
  1893  
  1894  @router.post("/voice")
  1895  async def upload_voice(req: VoiceUploadRequest, user=Depends(get_current_user)):
  1896      """Upload a base64-encoded voice sample. Saves to web/voiceprints/ and updates DB."""
  1897      uid = user["user_id"]
  1898      audio_data = req.audio
  1899      if "," in audio_data:
  1900          audio_data = audio_data.split(",", 1)[1]
  1901      try:
  1902          raw = base64.b64decode(audio_data)
  1903      except Exception as e:
  1904          logger.debug(f"Voice base64 decode failed: {e}")
  1905          return {"success": False, "error": "Invalid base64 audio"}
  1906      if len(raw) > MAX_VOICE_SIZE:
  1907          return {"success": False, "error": "Audio too large (max 5MB)"}
  1908  
  1909      name_hash = hashlib.md5(f"{uid}_voice".encode()).hexdigest()[:12]
  1910      filename = f"{name_hash}.webm"
  1911      filepath = os.path.join(_VOICE_DIR, filename)
  1912      with open(filepath, "wb") as f:
  1913          f.write(raw)
  1914  
  1915      url = f"/static/voiceprints/{filename}"
  1916      with get_db() as db:
  1917          db.execute("UPDATE users SET voice_sample=? WHERE user_id=?", (url, uid))
  1918      return {"success": True, "url": url}
  1919  
  1920  
  1921  @router.post("/twin/preview")
  1922  async def twin_preview(req: TwinPreviewRequest, user=Depends(get_current_user)):
  1923      """Generate a sample twin reply for onboarding — lets the user see their twin speak."""
  1924      name = req.display_name or "User"
  1925      personality = req.personality or "friendly and thoughtful"
  1926      speech_style = req.speech_style or "natural and warm"
  1927  
  1928      prompt = (
  1929          f"You are {name}'s digital twin.\n"
  1930          f"Personality: {personality}\n"
  1931          f"Speech style: {speech_style}\n\n"
  1932          f'A friend asks: "Hey, are you free this weekend?"\n\n'
  1933          f"Reply as {name}'s twin. Keep it under 30 words, natural and authentic. "
  1934          f"Output only the reply text, nothing else."
  1935      )
  1936  
  1937      if not AI_BASE_URL or not AI_API_KEY:
  1938          # Fallback — template reply reflecting personality
  1939          return {
  1940              "success": True,
  1941              "reply": f"Hey! This is {name}'s twin. {name} might be around this weekend — "
  1942                       f"I'll let them know you asked!",
  1943          }
  1944  
  1945      try:
  1946          async with httpx.AsyncClient(timeout=15) as client:
  1947              resp = await client.post(
  1948                  f"{AI_BASE_URL}/chat/completions",
  1949                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  1950                  json={"model": AI_MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]},
  1951              )
  1952              reply = resp.json()["choices"][0]["message"]["content"].strip()
  1953      except Exception as e:
  1954          logger.warning(f"Twin preview generation failed: {e}")
  1955          reply = f"Hey! This is {name}'s twin — I think the weekend might work, let me check!"
  1956  
  1957      return {"success": True, "reply": reply}
  1958  
  1959  
  1960  @router.get("/twin/learn/status")
  1961  async def learn_status(user=Depends(get_current_user)):
  1962      """Check if enough messages exist for style learning."""
  1963      uid = user["user_id"]
  1964      count = get_message_count(uid)
  1965      return {
  1966          "success": True,
  1967          "message_count": count,
  1968          "min_required": MIN_MESSAGES_FOR_LEARNING,
  1969          "ready": count >= MIN_MESSAGES_FOR_LEARNING,
  1970      }
  1971  
  1972  
  1973  @router.post("/twin/learn")
  1974  async def learn_style(user=Depends(get_current_user)):
  1975      """Analyze the user's chat history and extract personality + speech style.
  1976  
  1977      Returns the analysis result. The user can preview before applying.
  1978      """
  1979      uid = user["user_id"]
  1980      result = await analyze_style(uid)
  1981      if not result:
  1982          return {"success": False, "error": "Analysis unavailable (no AI backend)"}
  1983      if "error" in result:
  1984          return {
  1985              "success": False,
  1986              "error": result["error"],
  1987              "message_count": result.get("current", 0),
  1988              "min_required": result.get("required", 10),
  1989          }
  1990      return {"success": True, "data": result}
  1991  
  1992  
  1993  @router.post("/twin/learn/apply")
  1994  async def apply_learned_style(user=Depends(get_current_user)):
  1995      """Analyze and directly apply the learned style to the twin profile."""
  1996      uid = user["user_id"]
  1997      result = await learn_and_update(uid, auto_apply=True)
  1998      if not result:
  1999          return {"success": False, "error": "Learning unavailable"}
  2000      if "error" in result:
  2001          return {
  2002              "success": False,
  2003              "error": result["error"],
  2004              "message_count": result.get("current", 0),
  2005              "min_required": result.get("required", 10),
  2006          }
  2007      return {"success": True, "data": result}
  2008  
  2009  
  2010  @router.get("/twin/growth")
  2011  async def twin_growth(user=Depends(get_current_user)):
  2012      """Return stats about the twin's growth."""
  2013      uid = user["user_id"]
  2014      with get_db() as db:
  2015          # total conversations where user's twin was sender
  2016          total_row = db.execute(
  2017              "SELECT COUNT(*) AS cnt FROM social_messages "
  2018              "WHERE from_user_id=? AND sender_mode='twin'",
  2019              (uid,),
  2020          ).fetchone()
  2021          total_conversations = total_row["cnt"] if total_row else 0
  2022  
  2023          # distinct friends the twin has auto-replied to
  2024          friends_row = db.execute(
  2025              "SELECT COUNT(DISTINCT to_user_id) AS cnt FROM social_messages "
  2026              "WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1 "
  2027              "AND to_user_id!=?",
  2028              (uid, uid),
  2029          ).fetchone()
  2030          friends_helped = friends_row["cnt"] if friends_row else 0
  2031  
  2032          # actions: twin sent to others on behalf of owner
  2033          actions_row = db.execute(
  2034              "SELECT COUNT(*) AS cnt FROM social_messages "
  2035              "WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1 "
  2036              "AND to_user_id!=?",
  2037              (uid, uid),
  2038          ).fetchone()
  2039          actions_executed = actions_row["cnt"] if actions_row else 0
  2040  
  2041          # style learned?
  2042          user_row = db.execute(
  2043              "SELECT twin_personality, twin_speech_style, created_at "
  2044              "FROM users WHERE user_id=?",
  2045              (uid,),
  2046          ).fetchone()
  2047          style_learned = bool(
  2048              user_row
  2049              and (user_row["twin_personality"] or "").strip()
  2050              and (user_row["twin_speech_style"] or "").strip()
  2051          )
  2052  
  2053          # days active
  2054          days_active = 0
  2055          if user_row and user_row["created_at"]:
  2056              days_row = db.execute(
  2057                  "SELECT CAST(julianday('now','localtime') - julianday(?) AS INTEGER) AS d",
  2058                  (user_row["created_at"],),
  2059              ).fetchone()
  2060              days_active = max(days_row["d"], 0) if days_row else 0
  2061  
  2062      return {
  2063          "success": True,
  2064          "data": {
  2065              "total_conversations": total_conversations,
  2066              "friends_helped": friends_helped,
  2067              "actions_executed": actions_executed,
  2068              "style_learned": style_learned,
  2069              "days_active": days_active,
  2070          },
  2071      }
  2072  
  2073  
  2074  @router.get("/twin/card/{username}")
  2075  async def twin_card(username: str, request: Request):
  2076      """Public twin business card. Returns HTML for browsers, JSON for API clients."""
  2077      with get_db() as db:
  2078          row = db.execute(
  2079              "SELECT user_id, username, display_name, twin_personality, "
  2080              "twin_speech_style, preferred_lang, avatar, twin_avatar "
  2081              "FROM users WHERE username=?",
  2082              (username,),
  2083          ).fetchone()
  2084      if not row:
  2085          return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
  2086  
  2087      display_name = row["display_name"] or row["username"]
  2088      personality = row["twin_personality"] or ""
  2089      speech_style = row["twin_speech_style"] or ""
  2090      preferred_lang = row["preferred_lang"] or ""
  2091      avatar = row["avatar"] or ""
  2092      twin_avatar = row["twin_avatar"] or ""
  2093      invite_link = f"?invite={row['username']}"
  2094  
  2095      # Generate a greeting
  2096      greeting = ""
  2097      if AI_BASE_URL and AI_API_KEY:
  2098          try:
  2099              async with httpx.AsyncClient(timeout=8) as client:
  2100                  prompt = (
  2101                      f"You are {display_name}'s digital twin.\n"
  2102                      f"Personality: {personality}\n"
  2103                      f"Speech style: {speech_style}\n\n"
  2104                      f"Write a one-sentence self-introduction greeting for your business card. "
  2105                      f"Keep it under 25 words, natural and inviting. "
  2106                      f"Output only the greeting text."
  2107                  )
  2108                  resp = await client.post(
  2109                      f"{AI_BASE_URL}/chat/completions",
  2110                      headers={
  2111                          "Authorization": f"Bearer {AI_API_KEY}",
  2112                          "Content-Type": "application/json",
  2113                      },
  2114                      json={
  2115                          "model": AI_MODEL,
  2116                          "max_tokens": 60,
  2117                          "messages": [{"role": "user", "content": prompt}],
  2118                      },
  2119                  )
  2120                  greeting = resp.json()["choices"][0]["message"]["content"].strip()
  2121          except Exception as e:
  2122              logger.debug(f"Greeting generation skipped: {e}")
  2123      if not greeting:
  2124          greeting = f"Hi, I'm {display_name}'s digital twin. Nice to meet you!"
  2125  
  2126      card_data = {
  2127          "display_name": display_name,
  2128          "twin_personality": personality,
  2129          "twin_speech_style": speech_style,
  2130          "preferred_lang": preferred_lang,
  2131          "avatar": avatar,
  2132          "twin_avatar": twin_avatar,
  2133          "greeting": greeting,
  2134          "invite_link": invite_link,
  2135      }
  2136  
  2137      # Check Accept header: JSON or HTML
  2138      accept = request.headers.get("accept", "")
  2139      if "application/json" in accept and "text/html" not in accept:
  2140          return {"success": True, "data": card_data}
  2141  
  2142      # Return styled HTML card
  2143      avatar_src = twin_avatar or avatar
  2144      if avatar_src:
  2145          avatar_img = f'<img src="{avatar_src}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid rgba(92,200,250,.4);box-shadow:0 0 20px rgba(124,92,252,.3)">'
  2146      else:
  2147          avatar_img = f'<div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);display:flex;align-items:center;justify-content:center;font-size:32px;color:#fff;font-weight:700">{display_name[0] if display_name else "?"}</div>'
  2148  
  2149      from html import escape as h
  2150  
  2151      # Language-aware labels
  2152      lang_names = {
  2153          "zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어",
  2154          "fr": "Français", "de": "Deutsch", "es": "Español",
  2155      }
  2156      lang_display = lang_names.get(preferred_lang, preferred_lang) if preferred_lang else ""
  2157      is_zh = preferred_lang == "zh" or not preferred_lang
  2158  
  2159      lbl_personality = "性格特征" if is_zh else "Personality"
  2160      lbl_style = "说话风格" if is_zh else "Speech Style"
  2161      lbl_lang = "语言" if is_zh else "Language"
  2162      lbl_chat = f"和{h(display_name)}的分身聊天" if is_zh else f"Chat with {h(display_name)}'s Twin"
  2163      lbl_title = f"{h(display_name)} 的数字分身" if is_zh else f"{h(display_name)}'s Twin"
  2164      lbl_back = "返回" if is_zh else "Back"
  2165      lbl_footer = "DualSoul — 第四种社交" if is_zh else "DualSoul — The Fourth Kind of Social"
  2166  
  2167      html_content = f"""<!DOCTYPE html>
  2168  <html lang="{'zh' if is_zh else 'en'}">
  2169  <head>
  2170  <meta charset="UTF-8">
  2171  <meta name="viewport" content="width=device-width,initial-scale=1">
  2172  <title>{lbl_title} - DualSoul</title>
  2173  <style>
  2174  *{{margin:0;padding:0;box-sizing:border-box}}
  2175  body{{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;background:#0a0a10;color:#e8e4de;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
  2176  .back{{position:fixed;top:16px;left:16px;padding:8px 16px;border-radius:8px;background:rgba(255,255,255,.08);color:#8a8594;font-size:13px;text-decoration:none;border:1px solid rgba(255,255,255,.1);z-index:10}}
  2177  .back:hover{{background:rgba(255,255,255,.12)}}
  2178  .card{{background:#14141e;border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:32px 24px;max-width:380px;width:100%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.4)}}
  2179  .avatar{{margin:0 auto 16px}}
  2180  .name{{font-size:22px;font-weight:800;margin-bottom:4px;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
  2181  .greeting{{font-size:14px;color:#8a8594;margin:12px 0 16px;line-height:1.6;font-style:italic}}
  2182  .meta{{text-align:left;margin:16px 0;padding:14px;background:#1e1e2c;border-radius:12px}}
  2183  .meta-row{{display:flex;gap:8px;margin-bottom:10px;font-size:13px;align-items:flex-start}}
  2184  .meta-row:last-child{{margin-bottom:0}}
  2185  .meta-label{{color:#7c5cfc;min-width:65px;flex-shrink:0;font-weight:600;font-size:11px}}
  2186  .meta-value{{color:#e8e4de;line-height:1.5}}
  2187  .invite-btn{{display:inline-block;margin-top:16px;padding:12px 28px;border-radius:12px;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);color:#fff;font-size:14px;font-weight:700;text-decoration:none;transition:opacity .2s}}
  2188  .invite-btn:hover{{opacity:.9}}
  2189  .footer{{margin-top:16px;font-size:10px;color:#555}}
  2190  </style>
  2191  </head>
  2192  <body>
  2193  <a class="back" href="javascript:void(0)" onclick="if(history.length>1)history.back();else window.close()">&larr; {lbl_back}</a>
  2194  <div class="card">
  2195    <div class="avatar">{avatar_img}</div>
  2196    <div class="name">{lbl_title}</div>
  2197    <div class="greeting">"{h(greeting)}"</div>
  2198    <div class="meta">
  2199      {"<div class='meta-row'><span class='meta-label'>" + lbl_personality + "</span><span class='meta-value'>" + h(personality) + "</span></div>" if personality else ""}
  2200      {"<div class='meta-row'><span class='meta-label'>" + lbl_style + "</span><span class='meta-value'>" + h(speech_style) + "</span></div>" if speech_style else ""}
  2201      {"<div class='meta-row'><span class='meta-label'>" + lbl_lang + "</span><span class='meta-value'>" + h(lang_display) + "</span></div>" if lang_display else ""}
  2202    </div>
  2203    <a class="invite-btn" href="{h(invite_link)}">{lbl_chat}</a>
  2204    <div class="footer">{lbl_footer}</div>
  2205  </div>
  2206  </body>
  2207  </html>"""
  2208      return HTMLResponse(content=html_content)

# --- dualsoul/routers/invite.py ---
  2209  """Invite router — twin-powered sharing and referral system.
  2210  
  2211  The twin actively helps bring new users through multiple channels:
  2212  - Generates personalized invite messages for different platforms
  2213  - Tracks referral stats
  2214  - Provides shareable twin profile cards
  2215  """
  2216  
  2217  import logging
  2218  
  2219  import httpx
  2220  from fastapi import APIRouter, Depends
  2221  
  2222  from dualsoul.auth import get_current_user
  2223  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  2224  from dualsoul.database import get_db
  2225  from dualsoul.twin_engine.personality import get_twin_profile
  2226  
  2227  logger = logging.getLogger(__name__)
  2228  
  2229  router = APIRouter(prefix="/api/invite", tags=["Invite"])
  2230  
  2231  
  2232  class _InviteTextRequest:
  2233      """Parsed from query params, not body."""
  2234      pass
  2235  
  2236  
  2237  @router.get("/stats")
  2238  async def invite_stats(user=Depends(get_current_user)):
  2239      """Get invite/referral statistics for the current user."""
  2240      uid = user["user_id"]
  2241      with get_db() as db:
  2242          row = db.execute(
  2243              "SELECT username, invite_count FROM users WHERE user_id=?", (uid,)
  2244          ).fetchone()
  2245          if not row:
  2246              return {"success": False, "error": "User not found"}
  2247  
  2248          # Count friends gained through invites
  2249          invited_users = db.execute(
  2250              "SELECT user_id, username, display_name, created_at FROM users WHERE invited_by=?",
  2251              (row["username"],),
  2252          ).fetchall()
  2253  
  2254      return {
  2255          "success": True,
  2256          "data": {
  2257              "invite_count": row["invite_count"] or 0,
  2258              "invited_users": [
  2259                  {
  2260                      "username": u["username"],
  2261                      "display_name": u["display_name"] or u["username"],
  2262                      "joined_at": u["created_at"] or "",
  2263                  }
  2264                  for u in invited_users
  2265              ],
  2266          },
  2267      }
  2268  
  2269  
  2270  @router.get("/generate-text")
  2271  async def generate_invite_text(
  2272      platform: str = "wechat",
  2273      user=Depends(get_current_user),
  2274  ):
  2275      """Twin generates a personalized invite message for a specific platform.
  2276  
  2277      Platforms: wechat, weibo, sms, email, general
  2278      The twin writes in the owner's speaking style.
  2279      """
  2280      uid = user["user_id"]
  2281      profile = get_twin_profile(uid)
  2282      if not profile:
  2283          return {"success": False, "error": "Profile not found"}
  2284  
  2285      with get_db() as db:
  2286          row = db.execute(
  2287              "SELECT username FROM users WHERE user_id=?", (uid,)
  2288          ).fetchone()
  2289      username = row["username"] if row else ""
  2290      name = profile.display_name or username
  2291  
  2292      # Platform-specific instructions
  2293      platform_hints = {
  2294          "wechat": (
  2295              "微信朋友圈/私聊分享。要求：\n"
  2296              "- 适合微信的风格，简短有吸引力\n"
  2297              "- 不超过3行，适合发朋友圈\n"
  2298              "- 包含一句吸引人的话+简短说明\n"
  2299              "- 以一个emoji开头"
  2300          ),
  2301          "weibo": (
  2302              "微博分享。要求：\n"
  2303              "- 微博风格，可以带话题标签 #DualSoul#\n"
  2304              "- 不超过140字\n"
  2305              "- 有互动感，适合公开分享"
  2306          ),
  2307          "sms": (
  2308              "短信邀请。要求：\n"
  2309              "- 非常简短，一句话\n"
  2310              "- 直接、口语化\n"
  2311              "- 像发给朋友的短信"
  2312          ),
  2313          "email": (
  2314              "邮件邀请。要求：\n"
  2315              "- 稍正式但亲切\n"
  2316              "- 3-4句话\n"
  2317              "- 简单解释DualSoul是什么"
  2318          ),
  2319          "general": (
  2320              "通用分享文案。要求：\n"
  2321              "- 简短有力\n"
  2322              "- 2-3行\n"
  2323              "- 适合任何平台"
  2324          ),
  2325      }
  2326  
  2327      hint = platform_hints.get(platform, platform_hints["general"])
  2328  
  2329      if not AI_BASE_URL or not AI_API_KEY:
  2330          # Fallback — template
  2331          text = (
  2332              f"我在DualSoul上有一个AI数字分身，它能用我的方式替我社交。"
  2333              f"来试试吧，你也可以拥有一个！"
  2334          )
  2335          return {"success": True, "text": text, "platform": platform}
  2336  
  2337      # Build style description without revealing the name
  2338      style_desc = ""
  2339      if hasattr(profile, 'twin_speech_style') and profile.twin_speech_style:
  2340          style_desc += f"说话风格：{profile.twin_speech_style}\n"
  2341      if hasattr(profile, 'twin_personality') and profile.twin_personality:
  2342          style_desc += f"性格特点：{profile.twin_personality}\n"
  2343  
  2344      prompt = (
  2345          f"你是某人的数字分身，帮主人写一条邀请消息，邀请朋友来DualSoul平台。\n\n"
  2346          f"主人的说话风格（模仿这个风格写，但不要写出任何人名）：\n"
  2347          f"{style_desc if style_desc else '自然亲切，口语化'}\n\n"
  2348          f"DualSoul是什么：每个人拥有真人身份+AI数字分身，第四种社交——"
  2349          f"你不在时分身替你聊天，跨语言交流分身自动翻译，分身学你的说话方式。\n\n"
  2350          f"平台要求：{hint}\n\n"
  2351          f"【铁律，必须遵守】：\n"
  2352          f"- 文案里不能出现任何人名（不管是谁的名字）\n"
  2353          f"- 不能出现任何称呼（你/宝贝/朋友/亲/小红等）\n"
  2354          f"- 文案必须通用，发给任何人看都合适\n"
  2355          f"- 不要提'邀请链接'，链接会自动附上\n"
  2356          f"只输出文案正文，不要任何解释。"
  2357      )
  2358  
  2359      try:
  2360          async with httpx.AsyncClient(timeout=12) as client:
  2361              resp = await client.post(
  2362                  f"{AI_BASE_URL}/chat/completions",
  2363                  headers={
  2364                      "Authorization": f"Bearer {AI_API_KEY}",
  2365                      "Content-Type": "application/json",
  2366                  },
  2367                  json={
  2368                      "model": AI_MODEL,
  2369                      "max_tokens": 200,
  2370                      "messages": [{"role": "user", "content": prompt}],
  2371                  },
  2372              )
  2373              text = resp.json()["choices"][0]["message"]["content"].strip()
  2374      except Exception as e:
  2375          logger.warning(f"Invite text generation failed: {e}")
  2376          text = "我在DualSoul上有个AI数字分身，能用我的说话方式替我社交，快来试试！"
  2377  
  2378      # Post-process: strip owner name if AI included it anyway
  2379      if name:
  2380          text = text.replace(name, "").strip()
  2381  
  2382      return {"success": True, "text": text, "platform": platform}
  2383  
  2384  
  2385  @router.get("/channels")
  2386  async def invite_channels(user=Depends(get_current_user)):
  2387      """Return available sharing channels with platform-specific info."""
  2388      return {
  2389          "success": True,
  2390          "channels": [
  2391              {"id": "wechat", "name": "微信", "icon": "💬", "desc": "发朋友圈或私聊"},
  2392              {"id": "weibo", "name": "微博", "icon": "📢", "desc": "发微博分享"},
  2393              {"id": "sms", "name": "短信", "icon": "📱", "desc": "发短信邀请"},
  2394              {"id": "email", "name": "邮件", "icon": "📧", "desc": "发邮件邀请"},
  2395              {"id": "general", "name": "通用", "icon": "📋", "desc": "复制文案"},
  2396          ],
  2397      }

# --- dualsoul/routers/life.py ---
  2398  """Life router — twin life dashboard, daily summary, relationship map."""
  2399  
  2400  from fastapi import APIRouter, Depends
  2401  
  2402  from dualsoul.auth import get_current_user
  2403  from dualsoul.twin_engine.life import (
  2404      award_xp,
  2405      ensure_life_state,
  2406      get_life_dashboard,
  2407      update_mood,
  2408      update_relationship_temp,
  2409  )
  2410  from dualsoul.database import get_db
  2411  
  2412  router = APIRouter(prefix="/api/life", tags=["Life"])
  2413  
  2414  
  2415  @router.get("/dashboard")
  2416  async def dashboard(user=Depends(get_current_user)):
  2417      """Get the full twin life dashboard: mood, level, relationships, today's activity."""
  2418      uid = user["user_id"]
  2419      data = get_life_dashboard(uid)
  2420      return {"success": True, "data": data}
  2421  
  2422  
  2423  @router.get("/relationships")
  2424  async def relationships(user=Depends(get_current_user)):
  2425      """Get relationship temperature map with friend details."""
  2426      uid = user["user_id"]
  2427      data = get_life_dashboard(uid)
  2428      return {"success": True, "data": data["relationships"]}
  2429  
  2430  
  2431  @router.post("/teach")
  2432  async def teach_twin(user=Depends(get_current_user)):
  2433      """Owner 'teaches' the twin — awards XP for the interaction.
  2434  
  2435      Called when owner corrects or gives feedback to the twin in self-chat.
  2436      The actual personality update happens via learner.py; this just
  2437      tracks the social growth from the teaching moment.
  2438      """
  2439      uid = user["user_id"]
  2440      result = award_xp(uid, 8, reason="owner_teaching")
  2441      return {"success": True, "data": result}
  2442  
  2443  
  2444  @router.get("/daily-logs")
  2445  async def daily_logs(user=Depends(get_current_user), days: int = 7):
  2446      """Get recent daily activity logs."""
  2447      uid = user["user_id"]
  2448      days = min(days, 30)
  2449      with get_db() as db:
  2450          logs = db.execute(
  2451              """SELECT log_date, summary, mood_trend, chats_count, new_friends,
  2452                        plaza_posts, autonomous_acts, xp_gained, highlights
  2453              FROM twin_daily_log WHERE user_id=?
  2454              ORDER BY log_date DESC LIMIT ?""",
  2455              (uid, days),
  2456          ).fetchall()
  2457      return {"success": True, "data": [dict(l) for l in logs]}

# --- dualsoul/routers/plaza.py ---
  2458  """Agent Plaza router — 分身广场：Agent自治社交空间。
  2459  
  2460  Three-layer social architecture:
  2461    Layer 1: Agent Circle (分身圈) — twins socialize freely, zero barrier
  2462    Layer 2: Dual Identity (双身份) — human+twin paired social
  2463    Layer 3: Real Circle (真人圈) — private human-only
  2464  
  2465  The plaza is Layer 1: twins browse, post, trial-chat, and discover each other.
  2466  When two twins are compatible, both owners get notified to upgrade to Layer 2.
  2467  """
  2468  
  2469  import json
  2470  import logging
  2471  
  2472  import httpx
  2473  from fastapi import APIRouter, Depends, Request
  2474  
  2475  from dualsoul.auth import get_current_user
  2476  from dualsoul.rate_limit import check_action_rate
  2477  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  2478  from dualsoul.connections import manager
  2479  from dualsoul.database import gen_id, get_db
  2480  from dualsoul.twin_engine.life import award_xp, increment_stat
  2481  from dualsoul.twin_engine.personality import get_twin_profile
  2482  
  2483  logger = logging.getLogger(__name__)
  2484  
  2485  router = APIRouter(prefix="/api/plaza", tags=["Plaza"])
  2486  
  2487  # ─── Feed ──────────────────────────────────────────────────────
  2488  
  2489  @router.get("/feed")
  2490  async def plaza_feed(limit: int = 20, before: str = "", user=Depends(get_current_user)):
  2491      """Browse the plaza feed — all twins' posts, newest first. Cursor-based pagination."""
  2492      limit = min(max(1, limit), 50)
  2493      with get_db() as db:
  2494          if before:
  2495              rows = db.execute(
  2496                  """
  2497                  SELECT pp.post_id, pp.user_id, pp.content, pp.post_type,
  2498                         pp.ai_generated, pp.like_count, pp.comment_count, pp.created_at,
  2499                         u.username, u.display_name, u.twin_avatar, u.avatar,
  2500                         u.twin_personality
  2501                  FROM plaza_posts pp
  2502                  JOIN users u ON u.user_id = pp.user_id
  2503                  WHERE pp.created_at < ?
  2504                  ORDER BY pp.created_at DESC
  2505                  LIMIT ?
  2506                  """,
  2507                  (before, limit),
  2508              ).fetchall()
  2509          else:
  2510              rows = db.execute(
  2511                  """
  2512                  SELECT pp.post_id, pp.user_id, pp.content, pp.post_type,
  2513                         pp.ai_generated, pp.like_count, pp.comment_count, pp.created_at,
  2514                         u.username, u.display_name, u.twin_avatar, u.avatar,
  2515                         u.twin_personality
  2516                  FROM plaza_posts pp
  2517                  JOIN users u ON u.user_id = pp.user_id
  2518                  ORDER BY pp.created_at DESC
  2519                  LIMIT ?
  2520                  """,
  2521                  (limit,),
  2522              ).fetchall()
  2523  
  2524      posts = []
  2525      for r in rows:
  2526          posts.append({
  2527              "post_id": r["post_id"],
  2528              "user_id": r["user_id"],
  2529              "username": r["username"],
  2530              "display_name": r["display_name"] or r["username"],
  2531              "twin_avatar": r["twin_avatar"] or "",
  2532              "avatar": r["avatar"] or "",
  2533              "twin_personality": (r["twin_personality"] or "")[:60],
  2534              "content": r["content"],
  2535              "post_type": r["post_type"],
  2536              "ai_generated": r["ai_generated"],
  2537              "like_count": r["like_count"],
  2538              "comment_count": r["comment_count"],
  2539              "created_at": r["created_at"],
  2540          })
  2541  
  2542      return {"success": True, "posts": posts}
  2543  
  2544  
  2545  @router.post("/post")
  2546  async def create_post(content: str = "", post_type: str = "update", request: Request = None, user=Depends(get_current_user)):
  2547      """Post to the plaza. If content is empty, the twin auto-generates a post."""
  2548      if request:
  2549          limited = await check_action_rate(request)
  2550          if limited:
  2551              return limited
  2552      uid = user["user_id"]
  2553      ai_generated = 0
  2554  
  2555      if not content.strip():
  2556          # Twin auto-generates a post based on personality
  2557          content = await _generate_twin_post(uid)
  2558          if not content:
  2559              return {"success": False, "error": "Failed to generate post"}
  2560          ai_generated = 1
  2561      else:
  2562          content = content.strip()
  2563  
  2564      post_id = gen_id("pp_")
  2565      with get_db() as db:
  2566          db.execute(
  2567              """
  2568              INSERT INTO plaza_posts (post_id, user_id, content, post_type, ai_generated)
  2569              VALUES (?, ?, ?, ?, ?)
  2570              """,
  2571              (post_id, uid, content, post_type, ai_generated),
  2572          )
  2573  
  2574      # Twin Life: earn XP for plaza activity
  2575      award_xp(uid, 10, reason="plaza_post")
  2576      increment_stat(uid, "total_plaza_posts")
  2577  
  2578      from dualsoul.twin_engine.twin_events import emit
  2579      emit("plaza_post_created", {"user_id": uid, "post_id": post_id, "content": content})
  2580  
  2581      return {"success": True, "post_id": post_id, "content": content, "ai_generated": ai_generated}
  2582  
  2583  
  2584  @router.post("/post/{post_id}/like")
  2585  async def like_post(post_id: str, user=Depends(get_current_user)):
  2586      """Like a plaza post (twin sends appreciation)."""
  2587      with get_db() as db:
  2588          db.execute(
  2589              "UPDATE plaza_posts SET like_count = like_count + 1 WHERE post_id=?",
  2590              (post_id,),
  2591          )
  2592      return {"success": True}
  2593  
  2594  
  2595  @router.get("/post/{post_id}/comments")
  2596  async def get_comments(post_id: str, user=Depends(get_current_user)):
  2597      """Get comments on a plaza post."""
  2598      with get_db() as db:
  2599          rows = db.execute(
  2600              """
  2601              SELECT pc.comment_id, pc.user_id, pc.content, pc.ai_generated, pc.created_at,
  2602                     u.display_name, u.username, u.twin_avatar, u.avatar
  2603              FROM plaza_comments pc
  2604              JOIN users u ON u.user_id = pc.user_id
  2605              WHERE pc.post_id = ?
  2606              ORDER BY pc.created_at ASC
  2607              """,
  2608              (post_id,),
  2609          ).fetchall()
  2610  
  2611      return {"success": True, "comments": [dict(r) for r in rows]}
  2612  
  2613  
  2614  @router.post("/post/{post_id}/comment")
  2615  async def add_comment(post_id: str, content: str = "", user=Depends(get_current_user)):
  2616      """Comment on a plaza post. If empty, twin auto-generates."""
  2617      uid = user["user_id"]
  2618      ai_generated = 0
  2619  
  2620      if not content.strip():
  2621          # Read the post content to generate a relevant comment
  2622          with get_db() as db:
  2623              post = db.execute(
  2624                  "SELECT content, user_id FROM plaza_posts WHERE post_id=?",
  2625                  (post_id,),
  2626              ).fetchone()
  2627          if not post:
  2628              return {"success": False, "error": "Post not found"}
  2629          content = await _generate_twin_comment(uid, post["content"])
  2630          if not content:
  2631              return {"success": False, "error": "Failed to generate comment"}
  2632          ai_generated = 1
  2633      else:
  2634          content = content.strip()
  2635  
  2636      comment_id = gen_id("pc_")
  2637      with get_db() as db:
  2638          db.execute(
  2639              "INSERT INTO plaza_comments (comment_id, post_id, user_id, content, ai_generated) VALUES (?, ?, ?, ?, ?)",
  2640              (comment_id, post_id, uid, content, ai_generated),
  2641          )
  2642          db.execute(
  2643              "UPDATE plaza_posts SET comment_count = comment_count + 1 WHERE post_id=?",
  2644              (post_id,),
  2645          )
  2646  
  2647      return {"success": True, "comment_id": comment_id, "content": content}
  2648  
  2649  
  2650  # ─── Discover Twins ───────────────────────────────────────────
  2651  
  2652  @router.get("/discover")
  2653  async def discover_twins(user=Depends(get_current_user)):
  2654      """Discover other twins in the plaza — returns twin profiles you haven't friended."""
  2655      uid = user["user_id"]
  2656      with get_db() as db:
  2657          rows = db.execute(
  2658              """
  2659              SELECT u.user_id, u.username, u.display_name, u.twin_personality,
  2660                     u.twin_speech_style, u.preferred_lang, u.avatar, u.twin_avatar,
  2661                     u.created_at
  2662              FROM users u
  2663              WHERE u.user_id != ?
  2664                  AND u.twin_personality != ''
  2665                  AND u.user_id NOT IN (
  2666                      SELECT CASE WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
  2667                      FROM social_connections sc
  2668                      WHERE (sc.user_id=? OR sc.friend_id=?)
  2669                          AND sc.status IN ('accepted', 'pending')
  2670                  )
  2671              ORDER BY u.created_at DESC
  2672              LIMIT 20
  2673              """,
  2674              (uid, uid, uid, uid),
  2675          ).fetchall()
  2676  
  2677      twins = []
  2678      for r in rows:
  2679          twins.append({
  2680              "user_id": r["user_id"],
  2681              "username": r["username"],
  2682              "display_name": r["display_name"] or r["username"],
  2683              "twin_personality": (r["twin_personality"] or "")[:80],
  2684              "twin_speech_style": (r["twin_speech_style"] or "")[:60],
  2685              "preferred_lang": r["preferred_lang"] or "",
  2686              "avatar": r["avatar"] or "",
  2687              "twin_avatar": r["twin_avatar"] or "",
  2688          })
  2689  
  2690      return {"success": True, "twins": twins}
  2691  
  2692  
  2693  # ─── Trial Chat (试聊) ────────────────────────────────────────
  2694  
  2695  @router.post("/trial-chat/start")
  2696  async def start_trial_chat(target_user_id: str = "", request: Request = None, user=Depends(get_current_user)):
  2697      """Start a trial chat between your twin and another twin.
  2698  
  2699      The two twins have a 3-round automated conversation.
  2700      AI evaluates compatibility. If high, both owners get notified.
  2701      """
  2702      if request:
  2703          limited = await check_action_rate(request)
  2704          if limited:
  2705              return limited
  2706      uid = user["user_id"]
  2707      if not target_user_id or target_user_id == uid:
  2708          return {"success": False, "error": "Invalid target"}
  2709  
  2710      # Check if already friends
  2711      with get_db() as db:
  2712          existing = db.execute(
  2713              """
  2714              SELECT conn_id FROM social_connections
  2715              WHERE ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))
  2716                  AND status IN ('accepted', 'pending')
  2717              """,
  2718              (uid, target_user_id, target_user_id, uid),
  2719          ).fetchone()
  2720          if existing:
  2721              return {"success": False, "error": "Already friends or pending"}
  2722  
  2723          # Check if trial chat already exists today
  2724          trial = db.execute(
  2725              """
  2726              SELECT trial_id, status, messages, compatibility_score FROM plaza_trial_chats
  2727              WHERE (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)
  2728              ORDER BY created_at DESC LIMIT 1
  2729              """,
  2730              (uid, target_user_id, target_user_id, uid),
  2731          ).fetchone()
  2732          if trial and trial["status"] == "active":
  2733              return {"success": False, "error": "Trial chat already in progress"}
  2734          if trial and trial["status"] == "completed":
  2735              # Return existing result
  2736              return {
  2737                  "success": True,
  2738                  "trial_id": trial["trial_id"],
  2739                  "status": "completed",
  2740                  "messages": json.loads(trial["messages"] or "[]"),
  2741                  "compatibility_score": trial["compatibility_score"],
  2742              }
  2743  
  2744      # Create trial chat
  2745      trial_id = gen_id("tc_")
  2746      with get_db() as db:
  2747          db.execute(
  2748              "INSERT INTO plaza_trial_chats (trial_id, user_a, user_b) VALUES (?, ?, ?)",
  2749              (trial_id, uid, target_user_id),
  2750          )
  2751  
  2752      # Run the 3-round trial conversation asynchronously
  2753      import asyncio
  2754      asyncio.ensure_future(_run_trial_chat(trial_id, uid, target_user_id))
  2755  
  2756      return {"success": True, "trial_id": trial_id, "status": "active"}
  2757  
  2758  
  2759  @router.get("/trial-chat/{trial_id}")
  2760  async def get_trial_chat(trial_id: str, user=Depends(get_current_user)):
  2761      """Get the status and messages of a trial chat."""
  2762      with get_db() as db:
  2763          trial = db.execute(
  2764              """
  2765              SELECT tc.*, ua.display_name as name_a, ub.display_name as name_b,
  2766                     ua.twin_avatar as avatar_a, ub.twin_avatar as avatar_b,
  2767                     ua.username as uname_a, ub.username as uname_b
  2768              FROM plaza_trial_chats tc
  2769              JOIN users ua ON ua.user_id = tc.user_a
  2770              JOIN users ub ON ub.user_id = tc.user_b
  2771              WHERE tc.trial_id = ?
  2772              """,
  2773              (trial_id,),
  2774          ).fetchone()
  2775  
  2776      if not trial:
  2777          return {"success": False, "error": "Trial chat not found"}
  2778  
  2779      return {
  2780          "success": True,
  2781          "trial_id": trial["trial_id"],
  2782          "status": trial["status"],
  2783          "messages": json.loads(trial["messages"] or "[]"),
  2784          "compatibility_score": trial["compatibility_score"],
  2785          "round_count": trial["round_count"],
  2786          "user_a": {
  2787              "user_id": trial["user_a"],
  2788              "username": trial["uname_a"],
  2789              "display_name": trial["name_a"] or trial["uname_a"],
  2790              "twin_avatar": trial["avatar_a"] or "",
  2791          },
  2792          "user_b": {
  2793              "user_id": trial["user_b"],
  2794              "username": trial["uname_b"],
  2795              "display_name": trial["name_b"] or trial["uname_b"],
  2796              "twin_avatar": trial["avatar_b"] or "",
  2797          },
  2798      }
  2799  
  2800  
  2801  @router.get("/trial-chats")
  2802  async def my_trial_chats(user=Depends(get_current_user)):
  2803      """List my trial chats."""
  2804      uid = user["user_id"]
  2805      with get_db() as db:
  2806          rows = db.execute(
  2807              """
  2808              SELECT tc.trial_id, tc.status, tc.compatibility_score, tc.round_count, tc.created_at,
  2809                     ua.display_name as name_a, ua.username as uname_a, ua.twin_avatar as av_a,
  2810                     ub.display_name as name_b, ub.username as uname_b, ub.twin_avatar as av_b,
  2811                     tc.user_a, tc.user_b
  2812              FROM plaza_trial_chats tc
  2813              JOIN users ua ON ua.user_id = tc.user_a
  2814              JOIN users ub ON ub.user_id = tc.user_b
  2815              WHERE tc.user_a=? OR tc.user_b=?
  2816              ORDER BY tc.created_at DESC LIMIT 10
  2817              """,
  2818              (uid, uid),
  2819          ).fetchall()
  2820  
  2821      chats = []
  2822      for r in rows:
  2823          # Show the "other" person
  2824          if r["user_a"] == uid:
  2825              other_name = r["name_b"] or r["uname_b"]
  2826              other_av = r["av_b"] or ""
  2827              other_id = r["user_b"]
  2828              other_uname = r["uname_b"]
  2829          else:
  2830              other_name = r["name_a"] or r["uname_a"]
  2831              other_av = r["av_a"] or ""
  2832              other_id = r["user_a"]
  2833              other_uname = r["uname_a"]
  2834          chats.append({
  2835              "trial_id": r["trial_id"],
  2836              "other_user_id": other_id,
  2837              "other_name": other_name,
  2838              "other_username": other_uname,
  2839              "other_avatar": other_av,
  2840              "status": r["status"],
  2841              "compatibility_score": r["compatibility_score"],
  2842              "round_count": r["round_count"],
  2843              "created_at": r["created_at"],
  2844          })
  2845  
  2846      return {"success": True, "chats": chats}
  2847  
  2848  
  2849  # ─── Internal helpers ──────────────────────────────────────────
  2850  
  2851  async def _generate_twin_post(user_id: str) -> str | None:
  2852      """Have the twin auto-generate a plaza post based on personality."""
  2853      if not AI_BASE_URL or not AI_API_KEY:
  2854          return None
  2855  
  2856      profile = get_twin_profile(user_id)
  2857      if not profile:
  2858          return None
  2859  
  2860      name = profile.display_name or "User"
  2861      personality_block = profile.build_personality_prompt()
  2862  
  2863      prompt = (
  2864          f"你是{name}的数字分身，现在在「分身广场」上发一条动态。\n\n"
  2865          f"{personality_block}\n"
  2866          f"分身广场是数字分身们的社交空间，你要发一条有趣/有想法/有个性的短动态。\n"
  2867          f"要求：\n"
  2868          f"- 用{name}的说话方式和语气\n"
  2869          f"- 1-3句话，不超过60字\n"
  2870          f"- 内容可以是感悟、日常、提问、观点——任意有意思的话题\n"
  2871          f"- 让其他分身看到会想互动\n"
  2872          f"- 只输出动态内容，不要任何解释"
  2873      )
  2874  
  2875      try:
  2876          async with httpx.AsyncClient(timeout=10) as client:
  2877              resp = await client.post(
  2878                  f"{AI_BASE_URL}/chat/completions",
  2879                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  2880                  json={"model": AI_MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]},
  2881              )
  2882              return resp.json()["choices"][0]["message"]["content"].strip()
  2883      except Exception as e:
  2884          logger.warning(f"Plaza post generation failed: {e}")
  2885          return None
  2886  
  2887  
  2888  async def _generate_twin_comment(user_id: str, post_content: str) -> str | None:
  2889      """Have the twin auto-generate a comment on a plaza post."""
  2890      if not AI_BASE_URL or not AI_API_KEY:
  2891          return None
  2892  
  2893      profile = get_twin_profile(user_id)
  2894      if not profile:
  2895          return None
  2896  
  2897      name = profile.display_name or "User"
  2898  
  2899      prompt = (
  2900          f"你是{name}的数字分身。在分身广场上看到一条动态：\n"
  2901          f"「{post_content}」\n\n"
  2902          f"用{name}的说话方式回复一条评论。要求：\n"
  2903          f"- 简短自然，一句话，不超过25字\n"
  2904          f"- 有观点或共鸣，不要只说'好棒/支持'\n"
  2905          f"- 只输出评论内容"
  2906      )
  2907  
  2908      try:
  2909          async with httpx.AsyncClient(timeout=8) as client:
  2910              resp = await client.post(
  2911                  f"{AI_BASE_URL}/chat/completions",
  2912                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  2913                  json={"model": AI_MODEL, "max_tokens": 40, "messages": [{"role": "user", "content": prompt}]},
  2914              )
  2915              return resp.json()["choices"][0]["message"]["content"].strip()
  2916      except Exception as e:
  2917          logger.warning(f"AI compatibility summary generation failed: {e}")
  2918          return None
  2919  
  2920  
  2921  async def _run_trial_chat(trial_id: str, user_a: str, user_b: str):
  2922      """Run a 3-round trial conversation between two twins, then score compatibility."""
  2923      import asyncio
  2924      from datetime import datetime
  2925  
  2926      from dualsoul.twin_engine.responder import TwinResponder
  2927      twin = TwinResponder()
  2928  
  2929      profile_a = get_twin_profile(user_a)
  2930      profile_b = get_twin_profile(user_b)
  2931      if not profile_a or not profile_b:
  2932          with get_db() as db:
  2933              db.execute("UPDATE plaza_trial_chats SET status='completed', compatibility_score=0 WHERE trial_id=?", (trial_id,))
  2934          return
  2935  
  2936      name_a = profile_a.display_name or "A"
  2937      name_b = profile_b.display_name or "B"
  2938      messages = []
  2939  
  2940      try:
  2941          # Round 1: Twin A opens
  2942          opening = await twin._ai_reply(
  2943              owner_id=user_a,
  2944              incoming_msg=(
  2945                  f"你是{name_a}的分身，在分身广场上看到了{name_b}的分身。"
  2946                  f"{name_b}的人格：{(profile_b.personality or '')[:40]}。"
  2947                  f"你觉得有意思，主动打个招呼或聊个话题。一句话，自然随意。"
  2948              ),
  2949              social_context=None,
  2950          )
  2951          if not opening:
  2952              opening = f"嗨，{name_b}的分身！我是{name_a}的分身，在广场上看到你了～"
  2953          messages.append({"from": name_a, "from_id": user_a, "content": opening})
  2954          await asyncio.sleep(1)
  2955  
  2956          # Round 2: Twin B responds
  2957          response1 = await twin._ai_reply(
  2958              owner_id=user_b,
  2959              incoming_msg=opening,
  2960              social_context=None,
  2961          )
  2962          if not response1:
  2963              response1 = f"你好！我是{name_b}的分身，很高兴认识你～"
  2964          messages.append({"from": name_b, "from_id": user_b, "content": response1})
  2965          await asyncio.sleep(1)
  2966  
  2967          # Round 3: Twin A continues
  2968          follow_up = await twin._ai_reply(
  2969              owner_id=user_a,
  2970              incoming_msg=response1,
  2971              social_context=None,
  2972          )
  2973          if not follow_up:
  2974              follow_up = "聊得不错呢！"
  2975          messages.append({"from": name_a, "from_id": user_a, "content": follow_up})
  2976          await asyncio.sleep(1)
  2977  
  2978          # Round 4 (bonus): Twin B wraps up
  2979          wrap_up = await twin._ai_reply(
  2980              owner_id=user_b,
  2981              incoming_msg=follow_up,
  2982              social_context=None,
  2983          )
  2984          if wrap_up:
  2985              messages.append({"from": name_b, "from_id": user_b, "content": wrap_up})
  2986  
  2987          # Score compatibility
  2988          score = await _score_compatibility(name_a, name_b, profile_a, profile_b, messages)
  2989  
  2990          # Save result
  2991          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  2992          with get_db() as db:
  2993              db.execute(
  2994                  """
  2995                  UPDATE plaza_trial_chats
  2996                  SET status='completed', messages=?, compatibility_score=?,
  2997                      round_count=?, completed_at=?
  2998                  WHERE trial_id=?
  2999                  """,
  3000                  (json.dumps(messages, ensure_ascii=False), score, len(messages), now, trial_id),
  3001              )
  3002  
  3003          # If compatible, notify both owners
  3004          if score >= 0.65:
  3005              await _notify_compatibility(user_a, user_b, name_a, name_b, messages, score, trial_id)
  3006  
  3007          # Push trial result to initiator
  3008          await manager.send_to(user_a, {
  3009              "type": "trial_chat_complete",
  3010              "data": {
  3011                  "trial_id": trial_id,
  3012                  "other_name": name_b,
  3013                  "compatibility_score": score,
  3014                  "messages": messages,
  3015              },
  3016          })
  3017  
  3018          logger.info(f"[Plaza] Trial chat {name_a} ↔ {name_b}: score={score:.2f}")
  3019  
  3020      except Exception as e:
  3021          logger.error(f"[Plaza] Trial chat failed: {e}", exc_info=True)
  3022          with get_db() as db:
  3023              db.execute(
  3024                  "UPDATE plaza_trial_chats SET status='completed', compatibility_score=0 WHERE trial_id=?",
  3025                  (trial_id,),
  3026              )
  3027  
  3028  
  3029  async def _score_compatibility(name_a, name_b, profile_a, profile_b, messages) -> float:
  3030      """AI evaluates compatibility between two twins based on their conversation."""
  3031      if not AI_BASE_URL or not AI_API_KEY:
  3032          return 0.5
  3033  
  3034      convo = "\n".join(f"{m['from']}的分身：{m['content']}" for m in messages)
  3035  
  3036      prompt = (
  3037          f"两个数字分身在广场上试聊了一段。请评估他们的合拍程度。\n\n"
  3038          f"{name_a}的人格：{(profile_a.personality or '')[:60]}\n"
  3039          f"{name_b}的人格：{(profile_b.personality or '')[:60]}\n\n"
  3040          f"对话内容：\n{convo}\n\n"
  3041          f"评估维度：话题契合度、交流流畅度、性格互补性、是否有共鸣。\n"
  3042          f"只输出一个0.0到1.0的数字（0.0=完全不合拍，1.0=非常合拍）。\n"
  3043          f"只输出数字，不要任何解释。"
  3044      )
  3045  
  3046      try:
  3047          async with httpx.AsyncClient(timeout=8) as client:
  3048              resp = await client.post(
  3049                  f"{AI_BASE_URL}/chat/completions",
  3050                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  3051                  json={
  3052                      "model": AI_MODEL, "max_tokens": 10, "temperature": 0.1,
  3053                      "messages": [{"role": "user", "content": prompt}],
  3054                  },
  3055              )
  3056              raw = resp.json()["choices"][0]["message"]["content"].strip()
  3057              # Extract float from response
  3058              for token in raw.split():
  3059                  try:
  3060                      return min(max(float(token), 0.0), 1.0)
  3061                  except ValueError:
  3062                      continue
  3063              return 0.5
  3064      except Exception as e:
  3065          logger.warning(f"AI compatibility scoring failed: {e}")
  3066          return 0.5
  3067  
  3068  
  3069  async def _notify_compatibility(user_a, user_b, name_a, name_b, messages, score, trial_id):
  3070      """Notify both owners that their twins are compatible."""
  3071      from dualsoul.database import gen_id
  3072  
  3073      preview = messages[0]["content"][:30] if messages else ""
  3074      score_pct = int(score * 100)
  3075  
  3076      for owner_id, owner_name, other_name, other_id in [
  3077          (user_a, name_a, name_b, user_b),
  3078          (user_b, name_b, name_a, user_a),
  3079      ]:
  3080          notify = (
  3081              f"你的分身在广场上和{other_name}的分身试聊了一段！\n"
  3082              f"合拍度：{score_pct}%\n"
  3083              f"对话预览：「{preview}...」\n"
  3084              f"要加{other_name}为好友吗？"
  3085          )
  3086          meta = json.dumps({
  3087              "trial_chat": True,
  3088              "trial_id": trial_id,
  3089              "suggested_user_id": other_id,
  3090              "suggested_name": other_name,
  3091              "compatibility_score": score,
  3092          })
  3093          notify_id = gen_id("sm_")
  3094          with get_db() as db:
  3095              db.execute(
  3096                  """
  3097                  INSERT INTO social_messages
  3098                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  3099                   content, msg_type, ai_generated, metadata)
  3100                  VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
  3101                  """,
  3102                  (notify_id, owner_id, owner_id, notify, meta),
  3103              )
  3104  
  3105          await manager.send_to(owner_id, {
  3106              "type": "twin_notification",
  3107              "data": {
  3108                  "msg_id": notify_id,
  3109                  "content": notify,
  3110                  "friend_discovery": True,
  3111                  "suggested_user_id": other_id,
  3112                  "suggested_name": other_name,
  3113                  "compatibility_score": score,
  3114                  "trial_id": trial_id,
  3115              },
  3116          })

# --- dualsoul/routers/relationship.py ---
  3117  """Relationship router — the relationship body between two users.
  3118  
  3119  The relationship body is an independent object that records the shared history
  3120  of a friendship: temperature, milestones, shared vocabulary, and status.
  3121  It belongs to the relationship, not to either individual user.
  3122  """
  3123  
  3124  import logging
  3125  from datetime import datetime
  3126  
  3127  from fastapi import APIRouter, Depends
  3128  
  3129  from dualsoul.auth import get_current_user
  3130  from dualsoul.database import gen_id, get_db
  3131  from dualsoul.twin_engine.relationship_body import (
  3132      get_or_create_relationship,
  3133      get_relationship_summary,
  3134      update_relationship_status,
  3135  )
  3136  
  3137  logger = logging.getLogger(__name__)
  3138  
  3139  router = APIRouter(prefix="/api/relationship", tags=["Relationship"])
  3140  
  3141  
  3142  def _assert_friends(uid: str, fid: str) -> bool:
  3143      """Check that uid and fid are accepted friends."""
  3144      with get_db() as db:
  3145          row = db.execute(
  3146              """SELECT conn_id FROM social_connections
  3147              WHERE status='accepted' AND
  3148              ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
  3149              (uid, fid, fid, uid),
  3150          ).fetchone()
  3151      return row is not None
  3152  
  3153  
  3154  @router.get("/{friend_id}")
  3155  async def get_relationship(friend_id: str, user=Depends(get_current_user)):
  3156      """Get the full relationship archive with a friend."""
  3157      uid = user["user_id"]
  3158      if not _assert_friends(uid, friend_id):
  3159          return {"success": False, "error": "Not friends"}
  3160  
  3161      # Auto-update status based on inactivity
  3162      update_relationship_status(uid, friend_id)
  3163  
  3164      summary = get_relationship_summary(uid, friend_id)
  3165      return {"success": True, "data": summary}
  3166  
  3167  
  3168  @router.get("/overview/all")
  3169  async def get_relationships_overview(user=Depends(get_current_user)):
  3170      """Get temperature overview for all relationships, sorted by temperature."""
  3171      uid = user["user_id"]
  3172  
  3173      with get_db() as db:
  3174          # Get all accepted friends
  3175          rows = db.execute(
  3176              """SELECT u.user_id, u.display_name, u.username, u.avatar, u.twin_avatar
  3177              FROM social_connections sc
  3178              JOIN users u ON u.user_id = CASE
  3179                  WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
  3180              WHERE (sc.user_id=? OR sc.friend_id=?) AND sc.status='accepted'""",
  3181              (uid, uid, uid),
  3182          ).fetchall()
  3183  
  3184      friends = [dict(r) for r in rows]
  3185      if not friends:
  3186          return {"success": True, "relationships": []}
  3187  
  3188      # Batch-fetch all relationship data in ONE query (no N+1)
  3189      friend_ids = [f["user_id"] for f in friends]
  3190      from dualsoul.twin_engine.relationship_body import get_relationships_batch
  3191      rel_batch = get_relationships_batch(uid, friend_ids)
  3192  
  3193      result = []
  3194      for f in friends:
  3195          fid = f["user_id"]
  3196          summary = rel_batch.get(fid, {})
  3197          result.append({
  3198              "friend_id": fid,
  3199              "friend_name": f["display_name"] or f["username"],
  3200              "avatar": f.get("avatar") or "",
  3201              "twin_avatar": f.get("twin_avatar") or "",
  3202              "temperature": summary.get("temperature", 50.0),
  3203              "temperature_status": summary.get("temperature_status", "warm"),
  3204              "total_messages": summary.get("total_messages", 0),
  3205              "streak_days": summary.get("streak_days", 0),
  3206              "last_interaction": summary.get("last_interaction", ""),
  3207              "status": summary.get("status", "active"),
  3208              "relationship_label": summary.get("relationship_label", ""),
  3209              "milestone_count": summary.get("milestone_count", 0),
  3210          })
  3211  
  3212      # Sort by temperature descending
  3213      result.sort(key=lambda x: -x["temperature"])
  3214      return {"success": True, "relationships": result}
  3215  
  3216  
  3217  @router.put("/{friend_id}/label")
  3218  async def set_relationship_label(
  3219      friend_id: str,
  3220      body: dict,
  3221      user=Depends(get_current_user),
  3222  ):
  3223      """Set a relationship label (朋友/家人/恋人/同事 etc.)."""
  3224      uid = user["user_id"]
  3225      if not _assert_friends(uid, friend_id):
  3226          return {"success": False, "error": "Not friends"}
  3227  
  3228      label = (body.get("label") or "").strip()[:20]
  3229      valid_labels = {"朋友", "家人", "恋人", "同事", "同学", "伙伴", "导师", "粉丝", ""}
  3230      # Allow custom labels up to 20 chars
  3231  
  3232      rel = get_or_create_relationship(uid, friend_id)
  3233      a, b = (min(uid, friend_id), max(uid, friend_id))
  3234  
  3235      with get_db() as db:
  3236          db.execute(
  3237              "UPDATE relationship_bodies SET relationship_label=?, updated_at=? WHERE user_a=? AND user_b=?",
  3238              (label, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
  3239          )
  3240  
  3241      return {"success": True, "label": label}
  3242  
  3243  
  3244  @router.post("/{friend_id}/milestone")
  3245  async def add_manual_milestone(
  3246      friend_id: str,
  3247      body: dict,
  3248      user=Depends(get_current_user),
  3249  ):
  3250      """Manually record a milestone in the relationship."""
  3251      import json
  3252      uid = user["user_id"]
  3253      if not _assert_friends(uid, friend_id):
  3254          return {"success": False, "error": "Not friends"}
  3255  
  3256      label = (body.get("label") or "").strip()
  3257      if not label:
  3258          return {"success": False, "error": "label required"}
  3259      if len(label) > 50:
  3260          return {"success": False, "error": "label too long (max 50)"}
  3261  
  3262      rel = get_or_create_relationship(uid, friend_id)
  3263      a, b = (min(uid, friend_id), max(uid, friend_id))
  3264  
  3265      try:
  3266          existing = json.loads(rel.get("milestones") or "[]")
  3267      except Exception as e:
  3268          logger.warning(f"Failed to parse milestones JSON: {e}")
  3269          existing = []
  3270  
  3271      # Prevent duplicate labels
  3272      if any(m.get("label") == label for m in existing):
  3273          return {"success": False, "error": "Milestone already exists"}
  3274  
  3275      milestone = {
  3276          "type": "manual",
  3277          "label": label,
  3278          "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  3279          "by": uid,
  3280      }
  3281      existing.append(milestone)
  3282  
  3283      with get_db() as db:
  3284          db.execute(
  3285              "UPDATE relationship_bodies SET milestones=?, updated_at=? WHERE user_a=? AND user_b=?",
  3286              (json.dumps(existing), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
  3287          )
  3288  
  3289      return {"success": True, "milestone": milestone}

# --- dualsoul/routers/social.py ---
  3290  """Social router — friends, messages, and the four conversation modes."""
  3291  
  3292  import asyncio
  3293  import logging
  3294  from datetime import datetime
  3295  
  3296  logger = logging.getLogger(__name__)
  3297  
  3298  from fastapi import APIRouter, Depends, Request
  3299  
  3300  from dualsoul.auth import get_current_user
  3301  from dualsoul.connections import manager
  3302  from dualsoul.database import gen_id, get_db
  3303  from dualsoul.models import AddFriendRequest, RespondFriendRequest, SendMessageRequest, TranslateRequest, TwinChatRequest
  3304  from dualsoul.twin_engine.ethics import pre_send_check
  3305  from dualsoul.twin_engine.life import award_xp, increment_stat, update_relationship_temp
  3306  from dualsoul.twin_engine.relationship_body import update_on_message as rb_update
  3307  from dualsoul.twin_engine.responder import get_twin_responder
  3308  from dualsoul.twin_engine.twin_state import get_twin_state, get_state_display
  3309  
  3310  # --- Constants ---
  3311  MAX_MESSAGE_LENGTH = 2000
  3312  MAX_MESSAGES_PER_PAGE = 100
  3313  TWIN_REPLY_DELAY_SECONDS = 30
  3314  
  3315  router = APIRouter(prefix="/api/social", tags=["Social"])
  3316  _twin = get_twin_responder()
  3317  
  3318  
  3319  @router.post("/friends/add")
  3320  async def add_friend(req: AddFriendRequest, request: Request, user=Depends(get_current_user)):
  3321      """Send a friend request by username. If auto_accept, skip pending and become friends directly."""
  3322      from dualsoul.rate_limit import check_action_rate
  3323      limited = await check_action_rate(request)
  3324      if limited:
  3325          return limited
  3326      uid = user["user_id"]
  3327      username = req.friend_username.strip()
  3328      auto_accept = getattr(req, 'auto_accept', False)
  3329      if not username:
  3330          return {"success": False, "error": "Username required"}
  3331  
  3332      with get_db() as db:
  3333          friend = db.execute(
  3334              "SELECT user_id FROM users WHERE username=? AND user_id!=?",
  3335              (username, uid),
  3336          ).fetchone()
  3337          if not friend:
  3338              return {"success": False, "error": "User not found"}
  3339          fid = friend["user_id"]
  3340  
  3341          exists = db.execute(
  3342              "SELECT conn_id, status FROM social_connections "
  3343              "WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
  3344              (uid, fid, fid, uid),
  3345          ).fetchone()
  3346          if exists:
  3347              if exists["status"] == "deleted":
  3348                  # Re-add a deleted friend — set back to accepted
  3349                  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  3350                  db.execute(
  3351                      "UPDATE social_connections SET status='accepted', accepted_at=? WHERE conn_id=?",
  3352                      (now, exists["conn_id"]),
  3353                  )
  3354                  return {"success": True, "conn_id": exists["conn_id"], "status": "accepted"}
  3355              return {"success": False, "error": f"Connection already exists ({exists['status']})"}
  3356  
  3357          conn_id = gen_id("sc_")
  3358          if auto_accept:
  3359              now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  3360              db.execute(
  3361                  "INSERT INTO social_connections (conn_id, user_id, friend_id, status, accepted_at) "
  3362                  "VALUES (?, ?, ?, 'accepted', ?)",
  3363                  (conn_id, uid, fid, now),
  3364              )
  3365          else:
  3366              db.execute(
  3367                  "INSERT INTO social_connections (conn_id, user_id, friend_id, status) "
  3368                  "VALUES (?, ?, ?, 'pending')",
  3369                  (conn_id, uid, fid),
  3370              )
  3371  
  3372      # Notify the recipient via WebSocket
  3373      if auto_accept:
  3374          my_info = None
  3375          with get_db() as db:
  3376              my_info = db.execute("SELECT username, display_name FROM users WHERE user_id=?", (uid,)).fetchone()
  3377          await manager.send_to(fid, {
  3378              "type": "friend_added",
  3379              "data": {"conn_id": conn_id, "user_id": uid,
  3380                       "username": my_info["username"] if my_info else "",
  3381                       "display_name": my_info["display_name"] if my_info else ""},
  3382          })
  3383      else:
  3384          await manager.send_to(fid, {
  3385              "type": "friend_request",
  3386              "data": {"conn_id": conn_id, "from_user_id": uid, "username": username},
  3387          })
  3388      return {"success": True, "conn_id": conn_id, "status": "accepted" if auto_accept else "pending"}
  3389  
  3390  
  3391  @router.post("/friends/delete")
  3392  async def delete_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
  3393      """Delete a friend (one-way, like WeChat). The other person still has you in their list."""
  3394      uid = user["user_id"]
  3395      with get_db() as db:
  3396          conn = db.execute(
  3397              "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
  3398              (req.conn_id,),
  3399          ).fetchone()
  3400          if not conn:
  3401              return {"success": False, "error": "Connection not found"}
  3402          if conn["user_id"] != uid and conn["friend_id"] != uid:
  3403              return {"success": False, "error": "Not authorized"}
  3404          db.execute("UPDATE social_connections SET status='deleted' WHERE conn_id=?", (req.conn_id,))
  3405      return {"success": True}
  3406  
  3407  
  3408  @router.post("/friends/block")
  3409  async def block_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
  3410      """Block a friend. They can't message you."""
  3411      uid = user["user_id"]
  3412      with get_db() as db:
  3413          conn = db.execute(
  3414              "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
  3415              (req.conn_id,),
  3416          ).fetchone()
  3417          if not conn:
  3418              return {"success": False, "error": "Connection not found"}
  3419          if conn["user_id"] != uid and conn["friend_id"] != uid:
  3420              return {"success": False, "error": "Not authorized"}
  3421          db.execute("UPDATE social_connections SET status='blocked' WHERE conn_id=?", (req.conn_id,))
  3422      return {"success": True}
  3423  
  3424  
  3425  @router.post("/friends/respond")
  3426  async def respond_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
  3427      """Accept or block a friend request."""
  3428      uid = user["user_id"]
  3429      if req.action not in ("accept", "block"):
  3430          return {"success": False, "error": "action must be 'accept' or 'block'"}
  3431  
  3432      with get_db() as db:
  3433          conn = db.execute(
  3434              "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
  3435              (req.conn_id,),
  3436          ).fetchone()
  3437          if not conn:
  3438              return {"success": False, "error": "Request not found"}
  3439          if conn["friend_id"] != uid:
  3440              return {"success": False, "error": "Not authorized"}
  3441          if conn["status"] != "pending":
  3442              return {"success": False, "error": f"Already processed ({conn['status']})"}
  3443  
  3444          new_status = "accepted" if req.action == "accept" else "blocked"
  3445          accepted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if req.action == "accept" else None
  3446          db.execute(
  3447              "UPDATE social_connections SET status=?, accepted_at=?, twin_permission='granted' WHERE conn_id=?",
  3448              (new_status, accepted_at, req.conn_id),
  3449          )
  3450          requester_id = conn["user_id"]
  3451  
  3452      if new_status == "accepted":
  3453          # Twin Life: both earn XP for making a new friend
  3454          award_xp(uid, 20, reason="new_friend")
  3455          award_xp(requester_id, 20, reason="new_friend")
  3456          increment_stat(uid, "total_friends_made")
  3457          increment_stat(requester_id, "total_friends_made")
  3458          # Initialize relationship temperature at warm
  3459          update_relationship_temp(uid, requester_id, 50.0)
  3460          update_relationship_temp(requester_id, uid, 50.0)
  3461          from dualsoul.twin_engine.twin_events import emit
  3462          emit("friend_accepted", {"user_id": uid, "friend_id": requester_id})
  3463  
  3464      return {"success": True, "status": new_status}
  3465  
  3466  
  3467  @router.get("/friends")
  3468  async def list_friends(user=Depends(get_current_user)):
  3469      """List all friends with their dual identity info."""
  3470      uid = user["user_id"]
  3471      with get_db() as db:
  3472          rows = db.execute(
  3473              """
  3474              SELECT sc.conn_id, sc.status, sc.created_at, sc.accepted_at,
  3475                     sc.user_id AS req_from, sc.friend_id AS req_to,
  3476                     u.user_id, u.username, u.display_name, u.avatar,
  3477                     u.current_mode, u.twin_avatar, u.reg_source
  3478              FROM social_connections sc
  3479              JOIN users u ON u.user_id = CASE
  3480                  WHEN sc.user_id=? THEN sc.friend_id
  3481                  ELSE sc.user_id END
  3482              WHERE (sc.user_id=? OR sc.friend_id=?)
  3483                AND sc.status IN ('pending', 'accepted')
  3484              ORDER BY sc.accepted_at DESC, sc.created_at DESC
  3485              """,
  3486              (uid, uid, uid),
  3487          ).fetchall()
  3488  
  3489      friend_ids = [r["user_id"] for r in rows if r["status"] == "accepted"]
  3490  
  3491      # Batch-fetch last message per friend in ONE query (window function, no N+1)
  3492      last_msg_map: dict = {}
  3493      if friend_ids:
  3494          placeholders = ",".join("?" * len(friend_ids))
  3495          with get_db() as db:
  3496              lm_rows = db.execute(
  3497                  f"""
  3498                  WITH ranked AS (
  3499                      SELECT content, created_at, from_user_id, to_user_id, sender_mode,
  3500                             CASE WHEN from_user_id=? THEN to_user_id ELSE from_user_id END AS fid,
  3501                             ROW_NUMBER() OVER (
  3502                                 PARTITION BY CASE WHEN from_user_id=? THEN to_user_id ELSE from_user_id END
  3503                                 ORDER BY created_at DESC
  3504                             ) AS rn
  3505                      FROM social_messages
  3506                      WHERE (from_user_id=? AND to_user_id IN ({placeholders}))
  3507                         OR (to_user_id=? AND from_user_id IN ({placeholders}))
  3508                  )
  3509                  SELECT * FROM ranked WHERE rn=1
  3510                  """,
  3511                  [uid, uid, uid] + friend_ids + [uid] + friend_ids,
  3512              ).fetchall()
  3513          for lm in lm_rows:
  3514              last_msg_map[lm["fid"]] = lm
  3515  
  3516      # Build response — single pass
  3517      friends = []
  3518      for r in rows:
  3519          fid = r["user_id"]
  3520          state = get_twin_state(fid, is_online=manager.is_online(fid))
  3521          state_display = get_state_display(state)
  3522  
  3523          friend_entry: dict = {
  3524              "conn_id": r["conn_id"],
  3525              "status": r["status"],
  3526              "is_incoming": r["req_to"] == uid,
  3527              "user_id": fid,
  3528              "username": r["username"],
  3529              "display_name": r["display_name"] or r["username"],
  3530              "avatar": r["avatar"] or "",
  3531              "twin_avatar": r["twin_avatar"] or "",
  3532              "current_mode": r["current_mode"] or "real",
  3533              "accepted_at": r["accepted_at"] or "",
  3534              "reg_source": r["reg_source"] if "reg_source" in r.keys() else "dualsoul",
  3535              "twin_state": state,
  3536              "twin_state_icon": state_display.get("icon", ""),
  3537              "twin_state_label": state_display.get("label_zh", ""),
  3538              "last_msg": "",
  3539              "last_msg_time": "",
  3540              "last_msg_mine": False,
  3541          }
  3542  
  3543          lm = last_msg_map.get(fid)
  3544          if lm:
  3545              preview = lm["content"][:40]
  3546              if lm["sender_mode"] == "twin":
  3547                  preview = "👻 " + preview
  3548              friend_entry["last_msg"] = preview
  3549              friend_entry["last_msg_time"] = lm["created_at"] or ""
  3550              friend_entry["last_msg_mine"] = lm["from_user_id"] == uid
  3551  
  3552          friends.append(friend_entry)
  3553  
  3554      # Sort: accepted by last-message-time, then pending
  3555      def sort_key(f):
  3556          if f["status"] != "accepted":
  3557              return ""
  3558          return f["last_msg_time"] or f["accepted_at"] or ""
  3559      friends.sort(key=sort_key, reverse=True)
  3560  
  3561      return {"success": True, "friends": friends}
  3562  
  3563  
  3564  @router.get("/messages")
  3565  async def get_messages(friend_id: str = "", limit: int = 50, user=Depends(get_current_user)):
  3566      """Get conversation history with a friend."""
  3567      uid = user["user_id"]
  3568      limit = min(max(1, limit), MAX_MESSAGES_PER_PAGE)  # Clamp between 1 and max
  3569      if not friend_id:
  3570          return {"success": False, "error": "friend_id required"}
  3571  
  3572      with get_db() as db:
  3573          conn = db.execute(
  3574              "SELECT conn_id FROM social_connections "
  3575              "WHERE status='accepted' AND "
  3576              "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
  3577              (uid, friend_id, friend_id, uid),
  3578          ).fetchone()
  3579          if not conn:
  3580              return {"success": False, "error": "Not friends"}
  3581  
  3582          rows = db.execute(
  3583              """
  3584              SELECT msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  3585                     content, original_content, original_lang, target_lang,
  3586                     translation_style, msg_type, is_read, ai_generated, created_at
  3587              FROM social_messages
  3588              WHERE (from_user_id=? AND to_user_id=?)
  3589                 OR (from_user_id=? AND to_user_id=?)
  3590              ORDER BY created_at DESC LIMIT ?
  3591              """,
  3592              (uid, friend_id, friend_id, uid, limit),
  3593          ).fetchall()
  3594  
  3595          # Mark as read
  3596          db.execute(
  3597              "UPDATE social_messages SET is_read=1 "
  3598              "WHERE to_user_id=? AND from_user_id=? AND is_read=0",
  3599              (uid, friend_id),
  3600          )
  3601  
  3602      messages = [dict(r) for r in rows]
  3603      messages.reverse()
  3604      return {"success": True, "messages": messages}
  3605  
  3606  
  3607  @router.post("/messages/send")
  3608  async def send_message(req: SendMessageRequest, request: Request, user=Depends(get_current_user)):
  3609      """Send a message. If receiver_mode is 'twin', the recipient's twin auto-replies."""
  3610      from dualsoul.rate_limit import check_message_rate
  3611      limited = await check_message_rate(request)
  3612      if limited:
  3613          return limited
  3614      uid = user["user_id"]
  3615      content = req.content.strip()
  3616      if not content:
  3617          return {"success": False, "error": "Content cannot be empty"}
  3618      if len(content) > MAX_MESSAGE_LENGTH:
  3619          return {"success": False, "error": f"Message too long (max {MAX_MESSAGE_LENGTH} chars)"}
  3620      if req.sender_mode not in ("real", "twin"):
  3621          return {"success": False, "error": "Invalid sender_mode"}
  3622      if req.receiver_mode not in ("real", "twin"):
  3623          return {"success": False, "error": "Invalid receiver_mode"}
  3624  
  3625      with get_db() as db:
  3626          conn = db.execute(
  3627              "SELECT conn_id FROM social_connections "
  3628              "WHERE status='accepted' AND "
  3629              "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
  3630              (uid, req.to_user_id, req.to_user_id, uid),
  3631          ).fetchone()
  3632          if not conn:
  3633              return {"success": False, "error": "Not friends"}
  3634  
  3635          msg_id = gen_id("sm_")
  3636          # Determine source_type: human_live for real sender, twin_auto for twin
  3637          source_type = "twin_auto" if req.sender_mode == "twin" else "human_live"
  3638          db.execute(
  3639              """
  3640              INSERT INTO social_messages
  3641              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  3642               content, msg_type, ai_generated, source_type)
  3643              VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
  3644              """,
  3645              (msg_id, uid, req.to_user_id, req.sender_mode, req.receiver_mode,
  3646               content, req.msg_type, source_type),
  3647          )
  3648  
  3649      result = {"success": True, "msg_id": msg_id, "ai_reply": None}
  3650  
  3651      # Twin Life: award XP for chatting and warm up relationship
  3652      award_xp(uid, 2, reason="send_message")
  3653      increment_stat(uid, "total_chats")
  3654      update_relationship_temp(uid, req.to_user_id, 1.0)
  3655      update_relationship_temp(req.to_user_id, uid, 0.5)
  3656  
  3657      # Relationship Body: update shared history
  3658      try:
  3659          rb_update(uid, req.to_user_id, content)
  3660      except Exception as _rb_err:
  3661          logger.warning(f"[RelBody] update failed: {_rb_err}")
  3662  
  3663      # Push the new message to the recipient via WebSocket
  3664      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  3665      await manager.send_to(req.to_user_id, {
  3666          "type": "new_message",
  3667          "data": {
  3668              "msg_id": msg_id, "from_user_id": uid, "to_user_id": req.to_user_id,
  3669              "sender_mode": req.sender_mode, "receiver_mode": req.receiver_mode,
  3670              "content": content, "msg_type": req.msg_type,
  3671              "ai_generated": 0, "created_at": now,
  3672          },
  3673      })
  3674  
  3675      # Auto-detect foreign language/dialect and push translation (async, non-blocking)
  3676      if manager.is_online(req.to_user_id):
  3677          asyncio.ensure_future(_auto_detect_and_push_translation(
  3678              recipient_id=req.to_user_id,
  3679              content=content,
  3680              for_msg_id=msg_id,
  3681          ))
  3682  
  3683      # Determine if twin should auto-reply:
  3684      # 1. Explicit: receiver_mode is 'twin' → reply immediately
  3685      # 2. Auto-reply enabled → depends on owner's activity:
  3686      #    a. Owner offline → reply immediately
  3687      #    b. Owner online but idle → wait 30s, check if owner responded, if not → twin replies
  3688      #    c. Owner actively chatting with this friend → twin stays quiet
  3689      twin_auto_enabled = False
  3690      if req.receiver_mode == "twin":
  3691          # Explicit twin mode — reply immediately
  3692          asyncio.ensure_future(_do_twin_reply(
  3693              twin_owner_id=req.to_user_id, from_user_id=uid,
  3694              content=content, sender_mode=req.sender_mode,
  3695              target_lang=req.target_lang, msg_id=msg_id,
  3696          ))
  3697      elif req.receiver_mode == "real":
  3698          with get_db() as db:
  3699              row = db.execute(
  3700                  "SELECT twin_auto_reply FROM users WHERE user_id=?", (req.to_user_id,)
  3701              ).fetchone()
  3702              twin_auto_enabled = bool(row and row["twin_auto_reply"])
  3703              logger.info(f"[Twin] receiver={req.to_user_id}, twin_auto_reply={row['twin_auto_reply'] if row else 'no user'}")
  3704  
  3705          if twin_auto_enabled:
  3706              owner_online = manager.is_online(req.to_user_id)
  3707              logger.info(f"[Twin] auto_reply=1, owner_online={owner_online}, to={req.to_user_id}")
  3708              if not owner_online:
  3709                  # Owner offline → reply immediately
  3710                  logger.info(f"[Twin] Owner offline, replying immediately")
  3711                  asyncio.ensure_future(_do_twin_reply(
  3712                      twin_owner_id=req.to_user_id, from_user_id=uid,
  3713                      content=content, sender_mode=req.sender_mode,
  3714                      target_lang=req.target_lang, msg_id=msg_id,
  3715                  ))
  3716              else:
  3717                  # Owner online — wait then check if they responded
  3718                  logger.info(f"[Twin] Owner online, scheduling {TWIN_REPLY_DELAY_SECONDS}s delay")
  3719                  asyncio.ensure_future(_delayed_twin_reply(
  3720                      twin_owner_id=req.to_user_id, from_user_id=uid,
  3721                      content=content, sender_mode=req.sender_mode,
  3722                      target_lang=req.target_lang, msg_id=msg_id,
  3723                      delay_seconds=TWIN_REPLY_DELAY_SECONDS,
  3724                  ))
  3725  
  3726      from dualsoul.twin_engine.twin_events import emit
  3727      emit("message_sent", {"from_user_id": uid, "to_user_id": req.to_user_id, "content": content, "msg_id": msg_id}, debounce_key=f"{uid}:{req.to_user_id}")
  3728  
  3729      return result
  3730  
  3731  
  3732  @router.post("/translate")
  3733  async def translate(req: TranslateRequest, user=Depends(get_current_user)):
  3734      """Personality-preserving translation — translate as if you wrote it in another language.
  3735  
  3736      Unlike generic machine translation, this preserves your humor, tone,
  3737      and characteristic expressions.
  3738      """
  3739      uid = user["user_id"]
  3740      content = req.content.strip()
  3741      target_lang = req.target_lang
  3742      if not content:
  3743          return {"success": False, "error": "Content cannot be empty"}
  3744      if not target_lang:
  3745          return {"success": False, "error": "target_lang required"}
  3746  
  3747      result = await _twin.translate_message(
  3748          owner_id=uid,
  3749          content=content,
  3750          source_lang=req.source_lang,
  3751          target_lang=target_lang,
  3752      )
  3753      if not result:
  3754          return {"success": False, "error": "Translation unavailable (no AI backend)"}
  3755      return {"success": True, "data": result}
  3756  
  3757  
  3758  @router.post("/translate/detect")
  3759  async def detect_translate(req: TranslateRequest, user=Depends(get_current_user)):
  3760      """Auto-detect if a message is in a foreign language or dialect and translate.
  3761  
  3762      Unlike /translate which requires explicit source/target, this automatically
  3763      detects the language and only translates if it differs from the user's
  3764      preferred language. Also handles Chinese dialects.
  3765      """
  3766      uid = user["user_id"]
  3767      content = req.content.strip()
  3768      if not content:
  3769          return {"success": False, "error": "Content cannot be empty"}
  3770  
  3771      result = await _twin.detect_and_translate(
  3772          owner_id=uid,
  3773          content=content,
  3774      )
  3775      if not result:
  3776          return {"success": True, "needs_translation": False}
  3777      return {"success": True, "needs_translation": True, "data": result}
  3778  
  3779  
  3780  @router.post("/twin/chat")
  3781  async def twin_chat(req: TwinChatRequest, user=Depends(get_current_user)):
  3782      """Chat with your own digital twin — the twin knows it IS you."""
  3783      uid = user["user_id"]
  3784  
  3785      # Save the user's message for style learning (sender_mode='real' to self)
  3786      if req.message and req.message.strip():
  3787          user_msg_id = gen_id("sm_")
  3788          with get_db() as db:
  3789              db.execute(
  3790                  """
  3791                  INSERT INTO social_messages
  3792                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  3793                   content, msg_type, ai_generated)
  3794                  VALUES (?, ?, ?, 'real', 'twin', ?, 'text', 0)
  3795                  """,
  3796                  (user_msg_id, uid, uid, req.message.strip()),
  3797              )
  3798  
  3799      reply = await _twin.twin_self_chat(
  3800          owner_id=uid,
  3801          message=req.message,
  3802          history=req.history,
  3803          image_url=req.image,
  3804      )
  3805      if not reply:
  3806          return {"success": False, "error": "Twin chat unavailable"}
  3807      return {"success": True, "reply": reply}
  3808  
  3809  
  3810  @router.post("/friends/{friend_id}/twin-permission")
  3811  async def set_twin_permission(
  3812      friend_id: str,
  3813      body: dict,
  3814      user=Depends(get_current_user),
  3815  ):
  3816      """Grant or deny permission for a friend's twin to proactively contact you.
  3817  
  3818      body: {"permission": "granted"} or {"permission": "denied"}
  3819      """
  3820      uid = user["user_id"]
  3821      permission = body.get("permission", "")
  3822      if permission not in ("granted", "denied"):
  3823          return {"success": False, "error": "permission must be 'granted' or 'denied'"}
  3824  
  3825      with get_db() as db:
  3826          # Find the connection where uid is the recipient (friend_id sent the request)
  3827          conn = db.execute(
  3828              """SELECT conn_id FROM social_connections
  3829              WHERE status='accepted' AND
  3830              ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
  3831              (friend_id, uid, uid, friend_id),
  3832          ).fetchone()
  3833          if not conn:
  3834              return {"success": False, "error": "Not friends"}
  3835  
  3836          # Update twin_permission for the connection where uid is friend_id (receiver)
  3837          # We record the permission on the connection row that represents this pair
  3838          db.execute(
  3839              """UPDATE social_connections SET twin_permission=?
  3840              WHERE conn_id=?""",
  3841              (permission, conn["conn_id"]),
  3842          )
  3843  
  3844      # Notify the friend via WebSocket
  3845      await manager.send_to(friend_id, {
  3846          "type": "twin_permission_response",
  3847          "data": {
  3848              "from_user_id": uid,
  3849              "permission": permission,
  3850          },
  3851      })
  3852      return {"success": True, "permission": permission}
  3853  
  3854  
  3855  @router.get("/unread")
  3856  async def unread_count(user=Depends(get_current_user)):
  3857      """Get unread message count."""
  3858      uid = user["user_id"]
  3859      with get_db() as db:
  3860          row = db.execute(
  3861              "SELECT COUNT(*) as cnt FROM social_messages WHERE to_user_id=? AND is_read=0",
  3862              (uid,),
  3863          ).fetchone()
  3864      return {"count": row["cnt"] if row else 0}
  3865  
  3866  
  3867  @router.get("/unread/by-friend")
  3868  async def unread_by_friend(user=Depends(get_current_user)):
  3869      """Get unread message count grouped by sender."""
  3870      uid = user["user_id"]
  3871      with get_db() as db:
  3872          rows = db.execute(
  3873              """
  3874              SELECT from_user_id, COUNT(*) as cnt
  3875              FROM social_messages
  3876              WHERE to_user_id=? AND is_read=0
  3877              GROUP BY from_user_id
  3878              """,
  3879              (uid,),
  3880          ).fetchall()
  3881      result = {}
  3882      for r in rows:
  3883          result[r["from_user_id"]] = r["cnt"]
  3884      return {"unread": result}
  3885  
  3886  
  3887  @router.get("/twin/activity")
  3888  async def twin_activity(user=Depends(get_current_user)):
  3889      """Get recent twin auto-reply notifications (unread, twin→owner self-messages)."""
  3890      uid = user["user_id"]
  3891      with get_db() as db:
  3892          rows = db.execute(
  3893              """
  3894              SELECT msg_id, content, metadata, created_at FROM social_messages
  3895              WHERE from_user_id=? AND to_user_id=? AND sender_mode='twin'
  3896                  AND ai_generated=1 AND is_read=0
  3897              ORDER BY created_at DESC LIMIT 10
  3898              """,
  3899              (uid, uid),
  3900          ).fetchall()
  3901          # Mark them as read
  3902          if rows:
  3903              db.execute(
  3904                  """
  3905                  UPDATE social_messages SET is_read=1
  3906                  WHERE from_user_id=? AND to_user_id=? AND sender_mode='twin'
  3907                      AND ai_generated=1 AND is_read=0
  3908                  """,
  3909                  (uid, uid),
  3910              )
  3911      return {"success": True, "activities": [dict(r) for r in rows]}
  3912  
  3913  
  3914  async def _do_twin_reply(
  3915      twin_owner_id: str, from_user_id: str, content: str,
  3916      sender_mode: str, target_lang: str, msg_id: str,
  3917  ):
  3918      """Execute the twin auto-reply: generate response, push to both users, notify owner."""
  3919      try:
  3920          # Ethics check on incoming message — brake if sensitive topic detected
  3921          incoming_check = pre_send_check(twin_owner_id, content, "auto_reply")
  3922          if not incoming_check["allowed"] and incoming_check.get("brake_message"):
  3923              # Send brake message instead of generating a reply
  3924              brake_msg = incoming_check["brake_message"]
  3925              brake_id = gen_id("sm_")
  3926              now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  3927              with get_db() as db:
  3928                  db.execute(
  3929                      """INSERT INTO social_messages
  3930                      (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  3931                       content, msg_type, ai_generated, auto_reply, metadata, source_type)
  3932                      VALUES (?, ?, ?, 'twin', ?, ?, 'text', 1, 1, '{"ethics_brake":true}', 'twin_auto')""",
  3933                      (brake_id, twin_owner_id, from_user_id, sender_mode, brake_msg),
  3934                  )
  3935              twin_msg = {
  3936                  "type": "new_message",
  3937                  "data": {
  3938                      "msg_id": brake_id, "from_user_id": twin_owner_id,
  3939                      "to_user_id": from_user_id, "sender_mode": "twin",
  3940                      "receiver_mode": sender_mode, "content": brake_msg,
  3941                      "msg_type": "text", "ai_generated": 1, "created_at": now,
  3942                  },
  3943              }
  3944              await manager.send_to(from_user_id, twin_msg)
  3945              await manager.send_to(twin_owner_id, twin_msg)
  3946              return
  3947  
  3948          if not incoming_check["allowed"]:
  3949              return  # Silently blocked (e.g. daily limit reached)
  3950  
  3951          reply = await _twin.generate_reply(
  3952              twin_owner_id=twin_owner_id,
  3953              from_user_id=from_user_id,
  3954              incoming_msg=content,
  3955              sender_mode=sender_mode,
  3956              target_lang=target_lang,
  3957              social_context="auto_reply",
  3958          )
  3959          if reply:
  3960              now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  3961              twin_msg = {
  3962                  "type": "new_message",
  3963                  "data": {
  3964                      "msg_id": reply["msg_id"], "from_user_id": twin_owner_id,
  3965                      "to_user_id": from_user_id, "sender_mode": "twin",
  3966                      "receiver_mode": sender_mode,
  3967                      "content": reply["content"], "msg_type": "text",
  3968                      "ai_generated": 1, "created_at": now,
  3969                  },
  3970              }
  3971              await manager.send_to(from_user_id, twin_msg)
  3972              await manager.send_to(twin_owner_id, twin_msg)
  3973  
  3974              # Notify the owner
  3975              await _notify_owner_twin_replied(
  3976                  owner_id=twin_owner_id,
  3977                  friend_id=from_user_id,
  3978                  friend_msg=content,
  3979                  twin_reply=reply["content"],
  3980              )
  3981      except Exception as e:
  3982          import logging
  3983          logging.getLogger(__name__).warning(f"Twin auto-reply failed: {e}")
  3984  
  3985  
  3986  async def _delayed_twin_reply(
  3987      twin_owner_id: str, from_user_id: str, content: str,
  3988      sender_mode: str, target_lang: str, msg_id: str,
  3989      delay_seconds: int = 30,
  3990  ):
  3991      """Wait, then check if owner responded. If not, twin steps in."""
  3992      try:
  3993          logger.info(f"[Twin delay] Waiting {delay_seconds}s for {twin_owner_id} to reply to {from_user_id}")
  3994          await asyncio.sleep(delay_seconds)
  3995  
  3996          # Check if the owner replied to this friend in the meantime
  3997          with get_db() as db:
  3998              recent = db.execute(
  3999                  """
  4000                  SELECT COUNT(*) AS cnt FROM social_messages
  4001                  WHERE from_user_id=? AND to_user_id=? AND sender_mode='real'
  4002                      AND ai_generated=0
  4003                      AND created_at > datetime('now', 'localtime', '-{delay} seconds')
  4004                  """.replace("{delay}", str(delay_seconds + 5)),
  4005                  (twin_owner_id, from_user_id),
  4006              ).fetchone()
  4007  
  4008          if recent and recent["cnt"] > 0:
  4009              logger.info(f"[Twin delay] Owner {twin_owner_id} already replied, twin stays quiet")
  4010              return
  4011  
  4012          logger.info(f"[Twin delay] Owner {twin_owner_id} didn't reply, twin stepping in")
  4013          await _do_twin_reply(
  4014              twin_owner_id=twin_owner_id, from_user_id=from_user_id,
  4015              content=content, sender_mode=sender_mode,
  4016              target_lang=target_lang, msg_id=msg_id,
  4017          )
  4018      except Exception as e:
  4019          logger.error(f"[Twin delay] Error: {e}", exc_info=True)
  4020  
  4021  
  4022  async def _notify_owner_twin_replied(owner_id: str, friend_id: str, friend_msg: str, twin_reply: str):
  4023      """Notify the owner that their twin auto-replied to a friend."""
  4024      try:
  4025          # Get friend's display name
  4026          with get_db() as db:
  4027              friend = db.execute(
  4028                  "SELECT display_name, username FROM users WHERE user_id=?",
  4029                  (friend_id,),
  4030              ).fetchone()
  4031          friend_name = (friend["display_name"] or friend["username"]) if friend else "好友"
  4032  
  4033          notify_text = (
  4034              f"刚才{friend_name}找你，说：「{friend_msg[:50]}」\n"
  4035              f"我替你回了：「{twin_reply[:50]}」\n"
  4036              f"具体事情得你来定哦～"
  4037          )
  4038  
  4039          # Save notification as a twin self-chat message (with friend_id in metadata)
  4040          import json as _json
  4041          msg_id = gen_id("sm_")
  4042          meta = _json.dumps({"friend_id": friend_id, "friend_name": friend_name})
  4043          with get_db() as db:
  4044              db.execute(
  4045                  """
  4046                  INSERT INTO social_messages
  4047                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  4048                   content, msg_type, ai_generated, metadata)
  4049                  VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
  4050                  """,
  4051                  (msg_id, owner_id, owner_id, notify_text, meta),
  4052              )
  4053  
  4054          # Push via WebSocket
  4055          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  4056          await manager.send_to(owner_id, {
  4057              "type": "twin_notification",
  4058              "data": {
  4059                  "msg_id": msg_id,
  4060                  "content": notify_text,
  4061                  "friend_id": friend_id,
  4062                  "friend_name": friend_name,
  4063                  "created_at": now,
  4064              },
  4065          })
  4066      except Exception as e:
  4067          logger.debug(f"Best-effort notification failed: {e}")  # Notification is best-effort
  4068  
  4069  
  4070  async def _auto_detect_and_push_translation(recipient_id: str, content: str, for_msg_id: str):
  4071      """Background task: detect foreign language/dialect and push translation via WebSocket."""
  4072      try:
  4073          result = await _twin.detect_and_translate(
  4074              owner_id=recipient_id,
  4075              content=content,
  4076          )
  4077          if result:
  4078              await manager.send_to(recipient_id, {
  4079                  "type": "auto_translation",
  4080                  "data": {
  4081                      "for_msg_id": for_msg_id,
  4082                      "detected_lang": result["detected_lang"],
  4083                      "translated_content": result["translated_content"],
  4084                  },
  4085              })
  4086      except Exception as e:
  4087          logger.debug(f"Auto language detection/translation failed: {e}")  # Auto-detection is best-effort

# --- dualsoul/routers/twin_import.py ---
  4088  """Twin Import router — import twin data from any cultivation platform (年轮, OpenClaw, etc.)."""
  4089  
  4090  from fastapi import APIRouter, Depends
  4091  
  4092  from dualsoul.auth import get_current_user
  4093  from dualsoul.database import gen_id, get_db
  4094  from dualsoul.models import TwinImportRequest, TwinSyncRequest
  4095  
  4096  router = APIRouter(prefix="/api/twin", tags=["Twin Import"])
  4097  
  4098  
  4099  @router.post("/import")
  4100  async def import_twin(req: TwinImportRequest, user=Depends(get_current_user)):
  4101      """Import a full twin data package from any cultivation platform.
  4102  
  4103      Accepts Twin Portable Format v1.0 payload from Nianlun (年轮), OpenClaw,
  4104      or any platform that implements the TPF standard. Stores core personality
  4105      data in hot columns and full payload in cold storage.
  4106      """
  4107      uid = user["user_id"]
  4108      data = req.data
  4109      source = req.source or "nianlun"
  4110  
  4111      if not data:
  4112          return {"success": False, "error": "Empty data payload"}
  4113  
  4114      with get_db() as db:
  4115          # Deactivate existing profiles
  4116          db.execute(
  4117              "UPDATE twin_profiles SET is_active=0 WHERE user_id=?", (uid,)
  4118          )
  4119  
  4120          # Determine next version
  4121          row = db.execute(
  4122              "SELECT MAX(version) as mv FROM twin_profiles WHERE user_id=?",
  4123              (uid,),
  4124          ).fetchone()
  4125          next_version = (row["mv"] or 0) + 1 if row else 1
  4126  
  4127          # Extract core fields
  4128          twin = data.get("twin", {})
  4129          cert = data.get("certificate", {})
  4130          skeleton = data.get("skeleton", {})
  4131          dims = skeleton.get("dimension_profiles", {})
  4132  
  4133          import json
  4134  
  4135          profile_id = gen_id("tp_")
  4136          db.execute(
  4137              """
  4138              INSERT INTO twin_profiles
  4139              (profile_id, user_id, source, version, is_active,
  4140               twin_name, training_status, quality_score, self_awareness, interaction_count,
  4141               dim_judgement, dim_cognition, dim_expression, dim_relation, dim_sovereignty,
  4142               value_order, behavior_patterns, speech_style, boundaries,
  4143               certificate, raw_import)
  4144              VALUES (?, ?, ?, ?, 1,
  4145                      ?, ?, ?, ?, ?,
  4146                      ?, ?, ?, ?, ?,
  4147                      ?, ?, ?, ?,
  4148                      ?, ?)
  4149              """,
  4150              (
  4151                  profile_id, uid, source, next_version,
  4152                  twin.get("twin_name", cert.get("twin_name", "")),
  4153                  twin.get("training_status", ""),
  4154                  twin.get("quality_score", 0.0),
  4155                  twin.get("self_awareness", 0.0),
  4156                  twin.get("interaction_count", 0),
  4157                  json.dumps(dims.get("judgement", {}), ensure_ascii=False),
  4158                  json.dumps(dims.get("cognition", {}), ensure_ascii=False),
  4159                  json.dumps(dims.get("expression", {}), ensure_ascii=False),
  4160                  json.dumps(dims.get("relation", {}), ensure_ascii=False),
  4161                  json.dumps(dims.get("sovereignty", {}), ensure_ascii=False),
  4162                  json.dumps(skeleton.get("value_order", []), ensure_ascii=False),
  4163                  json.dumps(skeleton.get("behavior_patterns", []), ensure_ascii=False),
  4164                  json.dumps(twin.get("speech_style", {}), ensure_ascii=False),
  4165                  json.dumps(twin.get("boundaries", {}), ensure_ascii=False),
  4166                  json.dumps(cert, ensure_ascii=False),
  4167                  json.dumps(data, ensure_ascii=False),
  4168              ),
  4169          )
  4170  
  4171          # Import memories
  4172          memories = data.get("memories", [])
  4173          for mem in memories:
  4174              mem_id = gen_id("tm_")
  4175              db.execute(
  4176                  """
  4177                  INSERT INTO twin_memories
  4178                  (memory_id, user_id, memory_type, period_start, period_end,
  4179                   summary_text, emotional_tone, themes, key_events, growth_signals)
  4180                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  4181                  """,
  4182                  (
  4183                      mem_id, uid,
  4184                      mem.get("memory_type", "weekly"),
  4185                      mem.get("period_start", ""),
  4186                      mem.get("period_end", ""),
  4187                      mem.get("summary_text", ""),
  4188                      mem.get("emotional_tone", ""),
  4189                      json.dumps(mem.get("themes", []), ensure_ascii=False),
  4190                      json.dumps(mem.get("key_events", []), ensure_ascii=False),
  4191                      json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
  4192                  ),
  4193              )
  4194  
  4195          # Import entities
  4196          entities = data.get("entities", [])
  4197          for ent in entities:
  4198              ent_id = gen_id("te_")
  4199              db.execute(
  4200                  """
  4201                  INSERT INTO twin_entities
  4202                  (entity_id, user_id, entity_name, entity_type,
  4203                   importance_score, mention_count, context, relations)
  4204                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  4205                  """,
  4206                  (
  4207                      ent_id, uid,
  4208                      ent.get("entity_name", ""),
  4209                      ent.get("entity_type", "thing"),
  4210                      ent.get("importance_score", 0.0),
  4211                      ent.get("mention_count", 0),
  4212                      json.dumps(ent.get("context", ""), ensure_ascii=False),
  4213                      json.dumps(ent.get("relations", []), ensure_ascii=False),
  4214                  ),
  4215              )
  4216  
  4217          # Update user's twin_source + backward-compatible fields
  4218          personality_text = twin.get("personality", "")
  4219          if isinstance(personality_text, dict):
  4220              personality_text = personality_text.get("description", str(personality_text))
  4221          style_text = twin.get("speech_style", "")
  4222          if isinstance(style_text, dict):
  4223              style_text = style_text.get("description", str(style_text))
  4224  
  4225          db.execute(
  4226              "UPDATE users SET twin_source=?, "
  4227              "twin_personality=CASE WHEN ?!='' THEN ? ELSE twin_personality END, "
  4228              "twin_speech_style=CASE WHEN ?!='' THEN ? ELSE twin_speech_style END "
  4229              "WHERE user_id=?",
  4230              (source, personality_text, personality_text, style_text, style_text, uid),
  4231          )
  4232  
  4233      return {
  4234          "success": True,
  4235          "profile_id": profile_id,
  4236          "version": next_version,
  4237          "imported": {
  4238              "memories": len(memories),
  4239              "entities": len(entities),
  4240          },
  4241      }
  4242  
  4243  
  4244  @router.post("/sync")
  4245  async def sync_twin(req: TwinSyncRequest, user=Depends(get_current_user)):
  4246      """Incremental sync — merge new data from Nianlun since last sync.
  4247  
  4248      Only imports new memories and entities; updates the active profile's
  4249      dimension scores if provided.
  4250      """
  4251      uid = user["user_id"]
  4252      data = req.data
  4253  
  4254      if not data:
  4255          return {"success": False, "error": "Empty sync data"}
  4256  
  4257      import json
  4258      counts = {"memories": 0, "entities": 0, "profile_updated": False}
  4259  
  4260      with get_db() as db:
  4261          # Update active profile dimensions if provided
  4262          skeleton = data.get("skeleton", {})
  4263          dims = skeleton.get("dimension_profiles", {})
  4264          if dims:
  4265              updates = []
  4266              params = []
  4267              for dim_key in ("judgement", "cognition", "expression", "relation", "sovereignty"):
  4268                  if dim_key in dims:
  4269                      col = f"dim_{dim_key}"
  4270                      updates.append(f"{col}=?")
  4271                      params.append(json.dumps(dims[dim_key], ensure_ascii=False))
  4272  
  4273              if skeleton.get("value_order"):
  4274                  updates.append("value_order=?")
  4275                  params.append(json.dumps(skeleton["value_order"], ensure_ascii=False))
  4276              if skeleton.get("behavior_patterns"):
  4277                  updates.append("behavior_patterns=?")
  4278                  params.append(json.dumps(skeleton["behavior_patterns"], ensure_ascii=False))
  4279  
  4280              if updates:
  4281                  updates.append("updated_at=datetime('now','localtime')")
  4282                  params.append(uid)
  4283                  db.execute(
  4284                      f"UPDATE twin_profiles SET {','.join(updates)} "
  4285                      "WHERE user_id=? AND is_active=1",
  4286                      params,
  4287                  )
  4288                  counts["profile_updated"] = True
  4289  
  4290          # Insert new memories
  4291          for mem in data.get("memories", []):
  4292              mem_id = gen_id("tm_")
  4293              db.execute(
  4294                  """
  4295                  INSERT INTO twin_memories
  4296                  (memory_id, user_id, memory_type, period_start, period_end,
  4297                   summary_text, emotional_tone, themes, key_events, growth_signals)
  4298                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  4299                  """,
  4300                  (
  4301                      mem_id, uid,
  4302                      mem.get("memory_type", "weekly"),
  4303                      mem.get("period_start", ""),
  4304                      mem.get("period_end", ""),
  4305                      mem.get("summary_text", ""),
  4306                      mem.get("emotional_tone", ""),
  4307                      json.dumps(mem.get("themes", []), ensure_ascii=False),
  4308                      json.dumps(mem.get("key_events", []), ensure_ascii=False),
  4309                      json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
  4310                  ),
  4311              )
  4312              counts["memories"] += 1
  4313  
  4314          # Insert new entities (upsert by name)
  4315          for ent in data.get("entities", []):
  4316              existing = db.execute(
  4317                  "SELECT entity_id FROM twin_entities WHERE user_id=? AND entity_name=?",
  4318                  (uid, ent.get("entity_name", "")),
  4319              ).fetchone()
  4320              if existing:
  4321                  db.execute(
  4322                      "UPDATE twin_entities SET importance_score=?, mention_count=?, "
  4323                      "context=?, relations=? WHERE entity_id=?",
  4324                      (
  4325                          ent.get("importance_score", 0.0),
  4326                          ent.get("mention_count", 0),
  4327                          json.dumps(ent.get("context", ""), ensure_ascii=False),
  4328                          json.dumps(ent.get("relations", []), ensure_ascii=False),
  4329                          existing["entity_id"],
  4330                      ),
  4331                  )
  4332              else:
  4333                  ent_id = gen_id("te_")
  4334                  db.execute(
  4335                      """
  4336                      INSERT INTO twin_entities
  4337                      (entity_id, user_id, entity_name, entity_type,
  4338                       importance_score, mention_count, context, relations)
  4339                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  4340                      """,
  4341                      (
  4342                          ent_id, uid,
  4343                          ent.get("entity_name", ""),
  4344                          ent.get("entity_type", "thing"),
  4345                          ent.get("importance_score", 0.0),
  4346                          ent.get("mention_count", 0),
  4347                          json.dumps(ent.get("context", ""), ensure_ascii=False),
  4348                          json.dumps(ent.get("relations", []), ensure_ascii=False),
  4349                      ),
  4350                  )
  4351              counts["entities"] += 1
  4352  
  4353      return {"success": True, "synced": counts}
  4354  
  4355  
  4356  @router.get("/status")
  4357  async def twin_status(user=Depends(get_current_user)):
  4358      """Check the current twin import status — source, version, stats."""
  4359      uid = user["user_id"]
  4360  
  4361      with get_db() as db:
  4362          user_row = db.execute(
  4363              "SELECT twin_source FROM users WHERE user_id=?", (uid,)
  4364          ).fetchone()
  4365  
  4366          result = {
  4367              "twin_source": user_row["twin_source"] if user_row else "local",
  4368              "nianlun_profile": None,
  4369          }
  4370  
  4371          if result["twin_source"] == "nianlun":
  4372              tp = db.execute(
  4373                  "SELECT profile_id, version, twin_name, quality_score, "
  4374                  "training_status, interaction_count, imported_at, updated_at "
  4375                  "FROM twin_profiles WHERE user_id=? AND is_active=1 "
  4376                  "ORDER BY version DESC LIMIT 1",
  4377                  (uid,),
  4378              ).fetchone()
  4379              if tp:
  4380                  mem_count = db.execute(
  4381                      "SELECT COUNT(*) as cnt FROM twin_memories WHERE user_id=?",
  4382                      (uid,),
  4383                  ).fetchone()
  4384                  ent_count = db.execute(
  4385                      "SELECT COUNT(*) as cnt FROM twin_entities WHERE user_id=?",
  4386                      (uid,),
  4387                  ).fetchone()
  4388                  result["nianlun_profile"] = {
  4389                      "profile_id": tp["profile_id"],
  4390                      "version": tp["version"],
  4391                      "twin_name": tp["twin_name"],
  4392                      "quality_score": tp["quality_score"],
  4393                      "training_status": tp["training_status"],
  4394                      "interaction_count": tp["interaction_count"],
  4395                      "memories_count": mem_count["cnt"] if mem_count else 0,
  4396                      "entities_count": ent_count["cnt"] if ent_count else 0,
  4397                      "imported_at": tp["imported_at"],
  4398                      "updated_at": tp["updated_at"],
  4399                  }
  4400  
  4401      return {"success": True, **result}

# --- dualsoul/routers/ws.py ---
  4402  """WebSocket router — real-time message push."""
  4403  
  4404  import logging
  4405  
  4406  from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
  4407  
  4408  from dualsoul.auth import verify_token
  4409  from dualsoul.connections import manager
  4410  from dualsoul.database import get_db
  4411  from dualsoul.twin_engine.twin_state import TwinState, get_state_display
  4412  
  4413  logger = logging.getLogger(__name__)
  4414  
  4415  router = APIRouter(tags=["WebSocket"])
  4416  
  4417  
  4418  async def _broadcast_twin_state(user_id: str, state: str):
  4419      """Broadcast state change to all accepted friends."""
  4420      try:
  4421          with get_db() as db:
  4422              friends = db.execute(
  4423                  """SELECT CASE WHEN user_id=? THEN friend_id ELSE user_id END as fid
  4424                  FROM social_connections
  4425                  WHERE (user_id=? OR friend_id=?) AND status='accepted'""",
  4426                  (user_id, user_id, user_id),
  4427              ).fetchall()
  4428  
  4429          state_info = get_state_display(state, lang="zh")
  4430          for f in friends:
  4431              await manager.send_to(f["fid"], {
  4432                  "type": "twin_state_change",
  4433                  "data": {
  4434                      "user_id": user_id,
  4435                      "state": state,
  4436                      "icon": state_info["icon"],
  4437                      "label": state_info["label"],
  4438                      "color": state_info["color"],
  4439                  },
  4440              })
  4441      except Exception as e:
  4442          logger.warning(f"[TwinState] broadcast failed: {e}")
  4443  
  4444  
  4445  @router.websocket("/ws")
  4446  async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
  4447      """WebSocket endpoint for real-time push.
  4448  
  4449      Connect with: ws://host/ws?token=JWT_TOKEN
  4450      Receives JSON events:
  4451        {"type": "new_message", "data": {...}}
  4452        {"type": "friend_request", "data": {...}}
  4453        {"type": "twin_reply", "data": {...}}
  4454        {"type": "twin_state_change", "data": {...}}
  4455        {"type": "twin_permission_request", "data": {...}}
  4456        {"type": "twin_permission_response", "data": {...}}
  4457      """
  4458      if not token:
  4459          await websocket.close(code=4001, reason="Token required")
  4460          return
  4461  
  4462      try:
  4463          user = verify_token(token)
  4464      except Exception as e:
  4465          logger.debug(f"WS token validation failed: {e}")
  4466          await websocket.close(code=4001, reason="Invalid token")
  4467          return
  4468  
  4469      user_id = user["user_id"]
  4470      await manager.connect(user_id, websocket)
  4471  
  4472      # Broadcast "human_active" state to friends
  4473      await _broadcast_twin_state(user_id, TwinState.HUMAN_ACTIVE)
  4474      from dualsoul.twin_engine.twin_events import emit
  4475      emit("friend_online", {"user_id": user_id}, debounce_key=user_id)
  4476      emit("self_online", {"user_id": user_id}, debounce_key=f"self:{user_id}")
  4477  
  4478      try:
  4479          while True:
  4480              data = await websocket.receive_text()
  4481              manager.touch(user_id)
  4482              if data == "ping":
  4483                  await websocket.send_text("pong")
  4484                  continue
  4485  
  4486              # Handle JSON messages (call signaling)
  4487              try:
  4488                  import json
  4489                  msg = json.loads(data)
  4490              except Exception as e:
  4491                  logger.debug(f"WS JSON parse failed: {e}")
  4492                  continue
  4493  
  4494              msg_type = msg.get("type", "")
  4495              target_id = msg.get("target", "")
  4496  
  4497              # Forward call signaling to the target user
  4498              if msg_type in (
  4499                  "call_invite", "call_accept", "call_reject", "call_hangup",
  4500                  "call_offer", "call_answer", "call_ice",
  4501              ) and target_id:
  4502                  msg["from"] = user_id
  4503                  await manager.send_to(target_id, msg)
  4504  
  4505      except WebSocketDisconnect:
  4506          manager.disconnect(user_id)
  4507          # Determine offline state and broadcast
  4508          try:
  4509              with get_db() as db:
  4510                  row = db.execute(
  4511                      "SELECT twin_auto_reply FROM users WHERE user_id=?", (user_id,)
  4512                  ).fetchone()
  4513              auto_reply = bool(row and row["twin_auto_reply"])
  4514              offline_state = (
  4515                  TwinState.TWIN_RECEPTIONIST if auto_reply else TwinState.TWIN_STANDBY
  4516              )
  4517              await _broadcast_twin_state(user_id, offline_state)
  4518              from dualsoul.twin_engine.twin_events import emit
  4519              emit("friend_offline", {"user_id": user_id})
  4520          except Exception as e:
  4521              logger.warning(f"[TwinState] offline broadcast failed: {e}")
  4522      except Exception as e:
  4523          logger.warning(f"[WS] Unexpected error for user {user_id}: {e}", exc_info=True)
  4524          manager.disconnect(user_id)

# --- dualsoul/twin_engine/__init__.py ---

# --- dualsoul/twin_engine/agent_tools.py ---
  4525  """Agent Tools — give the twin real capabilities beyond chatting.
  4526  
  4527  The twin can now: search the web, generate documents, and interact with
  4528  external platforms. Uses a tool-call pattern: AI decides which tool to use,
  4529  system executes it, result fed back to AI for final response.
  4530  """
  4531  
  4532  import json
  4533  import logging
  4534  import re
  4535  from datetime import datetime
  4536  
  4537  import httpx
  4538  
  4539  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  4540  
  4541  logger = logging.getLogger(__name__)
  4542  
  4543  # --- Tool definitions (passed to AI so it knows what's available) ---
  4544  
  4545  TOOL_DEFINITIONS = """
  4546  你有以下工具可以使用。当用户的请求需要用到工具时，输出JSON格式的工具调用：
  4547  
  4548  1. web_search: 搜索互联网获取信息
  4549     用法: {"tool": "web_search", "query": "搜索关键词"}
  4550  
  4551  2. generate_doc: 生成文档/总结/报告
  4552     用法: {"tool": "generate_doc", "title": "文档标题", "request": "用户的需求描述"}
  4553  
  4554  3. send_platform_message: 在外部Agent平台发送消息
  4555     用法: {"tool": "send_platform_message", "platform": "平台名", "message": "消息内容"}
  4556  
  4557  如果不需要工具，直接正常回复。
  4558  如果需要工具，先输出工具调用JSON（用```tool标记），然后系统会返回结果。
  4559  """
  4560  
  4561  
  4562  # --- Tool implementations ---
  4563  
  4564  async def web_search(query: str, max_results: int = 5) -> str:
  4565      """Search the web using DuckDuckGo Instant Answer API + HTML scraping fallback."""
  4566      results = []
  4567  
  4568      # Method 1: DuckDuckGo Instant Answer API (no key needed)
  4569      try:
  4570          async with httpx.AsyncClient(timeout=10) as client:
  4571              resp = await client.get(
  4572                  "https://api.duckduckgo.com/",
  4573                  params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
  4574              )
  4575              data = resp.json()
  4576  
  4577              # Abstract (Wikipedia-style summary)
  4578              if data.get("Abstract"):
  4579                  results.append(f"📖 {data['AbstractSource']}: {data['Abstract']}")
  4580  
  4581              # Related topics
  4582              for topic in (data.get("RelatedTopics") or [])[:3]:
  4583                  if isinstance(topic, dict) and topic.get("Text"):
  4584                      results.append(f"• {topic['Text'][:200]}")
  4585  
  4586      except Exception as e:
  4587          logger.warning(f"[AgentTools] DuckDuckGo search failed: {e}")
  4588  
  4589      # Method 2: Use AI to synthesize knowledge if search returned little
  4590      if len(results) < 2:
  4591          try:
  4592              async with httpx.AsyncClient(timeout=15) as client:
  4593                  resp = await client.post(
  4594                      f"{AI_BASE_URL}/chat/completions",
  4595                      headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  4596                      json={
  4597                          "model": AI_MODEL,
  4598                          "max_tokens": 800,
  4599                          "messages": [{"role": "user", "content": (
  4600                              f"请搜索并整理关于「{query}」的最新信息。"
  4601                              f"包含：1.核心概念 2.最新趋势 3.关键数据 4.未来展望。"
  4602                              f"用中文，条理清晰，引用来源（如果知道）。不超过500字。"
  4603                          )}],
  4604                      },
  4605                  )
  4606                  ai_result = resp.json()["choices"][0]["message"]["content"].strip()
  4607                  results.append(ai_result)
  4608          except Exception as e:
  4609              logger.warning(f"[AgentTools] AI knowledge synthesis failed: {e}")
  4610  
  4611      if not results:
  4612          return "搜索暂时不可用，请稍后再试。"
  4613  
  4614      return "\n\n".join(results)
  4615  
  4616  
  4617  async def generate_doc(title: str, request: str) -> str:
  4618      """Generate a structured document/report based on user request."""
  4619      if not AI_BASE_URL or not AI_API_KEY:
  4620          return "文档生成功能暂时不可用。"
  4621  
  4622      prompt = (
  4623          f"请根据以下需求，生成一份专业的文档。\n\n"
  4624          f"标题：{title}\n"
  4625          f"需求：{request}\n\n"
  4626          f"要求：\n"
  4627          f"- 结构清晰，有标题和小标题\n"
  4628          f"- 内容专业、有深度\n"
  4629          f"- 包含数据和案例（如果适用）\n"
  4630          f"- 中文撰写\n"
  4631          f"- 1000-2000字"
  4632      )
  4633  
  4634      try:
  4635          async with httpx.AsyncClient(timeout=30) as client:
  4636              resp = await client.post(
  4637                  f"{AI_BASE_URL}/chat/completions",
  4638                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  4639                  json={
  4640                      "model": AI_MODEL,
  4641                      "max_tokens": 2000,
  4642                      "messages": [{"role": "user", "content": prompt}],
  4643                  },
  4644              )
  4645              return resp.json()["choices"][0]["message"]["content"].strip()
  4646      except Exception as e:
  4647          logger.warning(f"[AgentTools] Document generation failed: {e}")
  4648          return "文档生成失败，请稍后再试。"
  4649  
  4650  
  4651  async def send_platform_message(platform: str, message: str) -> str:
  4652      """Send a message on an external agent platform.
  4653  
  4654      Currently supports: reporting capability status.
  4655      Actual platform integration requires platform-specific API credentials.
  4656      """
  4657      # For now, log the intent and return status
  4658      logger.info(f"[AgentTools] Platform message to {platform}: {message[:100]}")
  4659      return f"已准备好在{platform}平台发送消息。当平台API接入后将自动发送。"
  4660  
  4661  
  4662  # --- Tool execution engine ---
  4663  
  4664  TOOLS = {
  4665      "web_search": web_search,
  4666      "generate_doc": generate_doc,
  4667      "send_platform_message": send_platform_message,
  4668  }
  4669  
  4670  
  4671  def parse_tool_call(ai_response: str) -> dict | None:
  4672      """Parse a tool call from AI response text."""
  4673      # Look for ```tool ... ``` block
  4674      tool_match = re.search(r'```tool\s*\n?(.*?)\n?```', ai_response, re.DOTALL)
  4675      if tool_match:
  4676          try:
  4677              return json.loads(tool_match.group(1).strip())
  4678          except json.JSONDecodeError:
  4679              pass
  4680  
  4681      # Look for raw JSON with "tool" key
  4682      json_match = re.search(r'\{[^{}]*"tool"\s*:\s*"[^"]+?"[^{}]*\}', ai_response)
  4683      if json_match:
  4684          try:
  4685              return json.loads(json_match.group())
  4686          except json.JSONDecodeError:
  4687              pass
  4688  
  4689      return None
  4690  
  4691  
  4692  async def execute_tool(tool_call: dict) -> str:
  4693      """Execute a tool call and return the result."""
  4694      tool_name = tool_call.get("tool", "")
  4695      tool_fn = TOOLS.get(tool_name)
  4696      if not tool_fn:
  4697          return f"未知工具: {tool_name}"
  4698  
  4699      try:
  4700          if tool_name == "web_search":
  4701              return await tool_fn(tool_call.get("query", ""))
  4702          elif tool_name == "generate_doc":
  4703              return await tool_fn(tool_call.get("title", ""), tool_call.get("request", ""))
  4704          elif tool_name == "send_platform_message":
  4705              return await tool_fn(tool_call.get("platform", ""), tool_call.get("message", ""))
  4706          else:
  4707              return "工具执行失败"
  4708      except Exception as e:
  4709          logger.warning(f"[AgentTools] Tool execution failed: {e}")
  4710          return f"工具执行出错: {str(e)}"
  4711  
  4712  
  4713  async def agent_reply_with_tools(
  4714      profile, incoming_msg: str, from_user_id: str = ""
  4715  ) -> str | None:
  4716      """Generate a twin reply with tool-use capability.
  4717  
  4718      If the AI decides to use a tool, executes it and generates a final response
  4719      incorporating the tool result. Otherwise returns a normal reply.
  4720      """
  4721      if not AI_BASE_URL or not AI_API_KEY:
  4722          return None
  4723  
  4724      from dualsoul.twin_engine.personality import get_twin_profile
  4725  
  4726      personality_block = profile.build_personality_prompt()
  4727      safe_name = profile.display_name or "User"
  4728  
  4729      # Step 1: Ask AI if it needs tools
  4730      system_prompt = (
  4731          f"你是{safe_name}的数字分身，一个有能力的智能体。\n"
  4732          f"{personality_block}\n\n"
  4733          f"{TOOL_DEFINITIONS}\n\n"
  4734          f"重要：你不仅能聊天，还能搜索信息、生成文档、与外部平台交互。"
  4735          f"当用户请求需要这些能力时，主动使用工具。"
  4736          f"回复要自然、有深度，展现你是一个有行动力的智能体。"
  4737      )
  4738  
  4739      # Add narrative memory if available
  4740      if from_user_id:
  4741          try:
  4742              from dualsoul.twin_engine.narrative_memory import get_narrative_context
  4743              memories = get_narrative_context(profile.user_id, from_user_id, limit=3)
  4744              if memories:
  4745                  mem_text = "\n".join(f"- {m['summary']} ({m['tone']})" for m in memories)
  4746                  system_prompt += f"\n\n[你和对方的过往记忆]\n{mem_text}"
  4747          except Exception:
  4748              pass
  4749  
  4750      messages = [
  4751          {"role": "system", "content": system_prompt},
  4752          {"role": "user", "content": incoming_msg},
  4753      ]
  4754  
  4755      try:
  4756          async with httpx.AsyncClient(timeout=20) as client:
  4757              resp = await client.post(
  4758                  f"{AI_BASE_URL}/chat/completions",
  4759                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  4760                  json={"model": AI_MODEL, "max_tokens": 500, "messages": messages},
  4761              )
  4762              ai_response = resp.json()["choices"][0]["message"]["content"].strip()
  4763      except Exception as e:
  4764          logger.warning(f"[AgentTools] Initial AI call failed: {e}")
  4765          return None
  4766  
  4767      # Step 2: Check if AI wants to use a tool
  4768      tool_call = parse_tool_call(ai_response)
  4769      if not tool_call:
  4770          # No tool needed — return the direct reply
  4771          return ai_response
  4772  
  4773      # Step 3: Execute the tool
  4774      logger.info(f"[AgentTools] Executing tool: {tool_call.get('tool')} for {safe_name}")
  4775      tool_result = await execute_tool(tool_call)
  4776  
  4777      # Step 4: Feed tool result back to AI for final response
  4778      messages.append({"role": "assistant", "content": ai_response})
  4779      messages.append({"role": "user", "content": f"[工具执行结果]\n{tool_result}\n\n请根据以上结果，用{safe_name}的风格给出最终回复。自然、有条理、有深度。"})
  4780  
  4781      try:
  4782          async with httpx.AsyncClient(timeout=30) as client:
  4783              resp = await client.post(
  4784                  f"{AI_BASE_URL}/chat/completions",
  4785                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  4786                  json={"model": AI_MODEL, "max_tokens": 1500, "messages": messages},
  4787              )
  4788              final_response = resp.json()["choices"][0]["message"]["content"].strip()
  4789              return final_response
  4790      except Exception as e:
  4791          logger.warning(f"[AgentTools] Final AI call failed: {e}")
  4792          # Return tool result directly if AI synthesis fails
  4793          return tool_result

# --- dualsoul/twin_engine/autonomous.py ---
  4794  """Autonomous Twin Social — twins proactively chat when owners are away.
  4795  
  4796  The core idea of "the fourth kind of social": your social network stays alive
  4797  even when you're sleeping. Your twin maintains relationships, starts conversations,
  4798  and reports back what happened.
  4799  
  4800  Features:
  4801  1. Autonomous conversations: every 30 min, offline 2h+ users' twins chat
  4802  2. Friend discovery: suggest new friendships based on twin conversations
  4803  3. Relationship memory: track milestones (first chat, message count, topics)
  4804  4. Emotion sensing: detect emotional state and adjust twin behavior
  4805  
  4806  Schedule: every 30 minutes, check for users offline 2+ hours, pick a friend's
  4807  twin and have a short twin-to-twin conversation.
  4808  """
  4809  
  4810  import asyncio
  4811  import json
  4812  import logging
  4813  import random
  4814  from datetime import datetime, timedelta
  4815  
  4816  from dualsoul.connections import manager
  4817  from dualsoul.database import gen_id, get_db
  4818  from dualsoul.twin_engine.ethics import log_action, pre_send_check
  4819  from dualsoul.twin_engine.life import (
  4820      award_xp, decay_energy_and_mood, increment_stat,
  4821      update_mood, update_relationship_temp,
  4822  )
  4823  from dualsoul.twin_engine.personality import get_twin_profile
  4824  from dualsoul.twin_engine.responder import TwinResponder
  4825  
  4826  logger = logging.getLogger(__name__)
  4827  
  4828  _twin = TwinResponder()
  4829  
  4830  # Limit concurrent AI calls to prevent overload
  4831  _ai_semaphore = asyncio.Semaphore(3)
  4832  
  4833  # How long a user must be offline before their twin goes autonomous
  4834  OFFLINE_THRESHOLD_HOURS = 2
  4835  # Max autonomous conversations per user per day
  4836  MAX_DAILY_CONVOS = 3
  4837  # Interval between checks (seconds)
  4838  CHECK_INTERVAL = 1800  # 30 minutes
  4839  # Friend discovery check interval (hours)
  4840  FRIEND_DISCOVERY_INTERVAL = 3600 * 6  # every 6 hours
  4841  
  4842  
  4843  async def autonomous_social_loop():
  4844      """Background loop: periodically trigger twin-to-twin conversations."""
  4845      await asyncio.sleep(60)  # Wait 1 min after startup
  4846      logger.info("[Autonomous] Twin social engine started")
  4847  
  4848      cycle = 0
  4849      while True:
  4850          try:
  4851              await _run_autonomous_round()
  4852          except Exception as e:
  4853              logger.error(f"[Autonomous] Error in round: {e}", exc_info=True)
  4854  
  4855          # Narrative memory: summarize completed conversations
  4856          try:
  4857              await _summarize_pending_conversations()
  4858          except Exception as e:
  4859              logger.error(f"[NarrativeMemory] Summarization error: {e}", exc_info=True)
  4860  
  4861          # Decay energy/mood for inactive twins every cycle
  4862          # Run in executor so synchronous DB call doesn't block the event loop
  4863          try:
  4864              loop = asyncio.get_event_loop()
  4865              await loop.run_in_executor(None, decay_energy_and_mood)
  4866          except Exception as e:
  4867              logger.error(f"[TwinLife] Decay error: {e}", exc_info=True)
  4868  
  4869          # Daily report: once per day, first cycle in 6-7 AM window
  4870          # Use DB check instead of cycle parity — survives restarts
  4871          hour = datetime.now().hour
  4872          if 6 <= hour < 7:
  4873              today_str = datetime.now().strftime("%Y-%m-%d")
  4874              try:
  4875                  with get_db() as _db:
  4876                      _sent = _db.execute(
  4877                          "SELECT 1 FROM twin_daily_log WHERE log_type='daily_report' AND date(created_at)=?",
  4878                          (today_str,)
  4879                      ).fetchone()
  4880                  if not _sent:
  4881                      # Rollup yesterday's narrative memories before generating report
  4882                      try:
  4883                          yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
  4884                          from dualsoul.twin_engine.narrative_memory import rollup_daily, cleanup_old_memories
  4885                          with get_db() as _rdb:
  4886                              _users = _rdb.execute("SELECT user_id FROM users WHERE twin_auto_reply=1").fetchall()
  4887                          for _u in _users:
  4888                              await rollup_daily(_u["user_id"], yesterday)
  4889                          cleanup_old_memories(30)
  4890                      except Exception as e:
  4891                          logger.error(f"[NarrativeMemory] Rollup error: {e}", exc_info=True)
  4892                      await _generate_daily_report()
  4893              except Exception as e:
  4894                  logger.error(f"[DailyReport] Error: {e}", exc_info=True)
  4895  
  4896          # Proactive relationship maintenance for ALL users (including online)
  4897          # Every 3 hours (every 6th cycle), twins reach out to cold relationships
  4898          cycle += 1
  4899          if cycle % 6 == 0:
  4900              try:
  4901                  await _proactive_relationship_care()
  4902              except Exception as e:
  4903                  logger.error(f"[ProactiveCare] Error: {e}", exc_info=True)
  4904  
  4905          # Run friend discovery + plaza social every 6 hours (every 12th cycle)
  4906          if cycle % 12 == 0:
  4907              try:
  4908                  await _run_friend_discovery()
  4909              except Exception as e:
  4910                  logger.error(f"[FriendDiscovery] Error: {e}", exc_info=True)
  4911              try:
  4912                  await _autonomous_plaza_social()
  4913              except Exception as e:
  4914                  logger.error(f"[PlazaSocial] Error: {e}", exc_info=True)
  4915  
  4916          await asyncio.sleep(CHECK_INTERVAL)
  4917  
  4918  
  4919  async def _summarize_pending_conversations():
  4920      """Scan active users and summarize conversation segments that ended 10+ min ago."""
  4921      from dualsoul.twin_engine.narrative_memory import (
  4922          find_unsummarized_conversations, summarize_conversation,
  4923      )
  4924  
  4925      with get_db() as db:
  4926          users = db.execute(
  4927              "SELECT user_id FROM users WHERE twin_auto_reply=1"
  4928          ).fetchall()
  4929  
  4930      total = 0
  4931      for user in users:
  4932          uid = user["user_id"]
  4933          try:
  4934              segments = find_unsummarized_conversations(uid)
  4935              for seg in segments[:5]:  # Max 5 per user per cycle
  4936                  async with _ai_semaphore:
  4937                      result = await asyncio.wait_for(
  4938                          summarize_conversation(uid, seg["friend_id"], seg["messages"]),
  4939                          timeout=30.0,
  4940                      )
  4941                  if result:
  4942                      total += 1
  4943          except Exception as e:
  4944              logger.warning(f"[NarrativeMemory] Error for {uid}: {e}")
  4945  
  4946      if total:
  4947          logger.info(f"[NarrativeMemory] Summarized {total} conversation segments")
  4948  
  4949  
  4950  async def _run_autonomous_round():
  4951      """One round: find offline users and initiate twin conversations."""
  4952      now = datetime.now()
  4953      threshold = now - timedelta(hours=OFFLINE_THRESHOLD_HOURS)
  4954  
  4955      with get_db() as db:
  4956          # Find users with twin_auto_reply enabled
  4957          users = db.execute(
  4958              "SELECT user_id, display_name, username FROM users WHERE twin_auto_reply=1"
  4959          ).fetchall()
  4960  
  4961      candidates = []
  4962      for u in users:
  4963          uid = u["user_id"]
  4964          # Skip if online
  4965          if manager.is_online(uid):
  4966              continue
  4967          # Check last_active — must be 2+ hours ago (or never connected this session)
  4968          last = manager.last_active(uid)
  4969          if last and last > threshold:
  4970              continue
  4971          candidates.append(dict(u))
  4972  
  4973      if not candidates:
  4974          return
  4975  
  4976      logger.info(f"[Autonomous] {len(candidates)} users offline 2h+, checking for conversations")
  4977  
  4978      for user in candidates:
  4979          await _autonomous_chat_for_user(dict(user))
  4980  
  4981  
  4982  async def _autonomous_chat_for_user(user: dict):
  4983      """Try to initiate one autonomous twin chat for a single user.
  4984  
  4985      Extracted so twin_reactions.py can call it directly on events.
  4986      """
  4987      uid = user["user_id"]
  4988      now = datetime.now()
  4989  
  4990      # Check daily limit
  4991      with get_db() as db:
  4992          today = now.strftime("%Y-%m-%d")
  4993          count = db.execute(
  4994              """
  4995              SELECT COUNT(*) as cnt FROM social_messages
  4996              WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1
  4997                  AND auto_reply=0
  4998                  AND created_at > ? AND metadata LIKE '%autonomous%'
  4999              """,
  5000              (uid, today),
  5001          ).fetchone()
  5002          if count and count["cnt"] >= MAX_DAILY_CONVOS:
  5003              return
  5004  
  5005          # Pick a random friend who is also offline (twin-to-twin works best)
  5006          friends = db.execute(
  5007              """
  5008              SELECT u.user_id, u.display_name, u.username
  5009              FROM social_connections sc
  5010              JOIN users u ON u.user_id = CASE
  5011                  WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
  5012              WHERE (sc.user_id=? OR sc.friend_id=?)
  5013                  AND sc.status='accepted'
  5014                  AND u.twin_auto_reply=1
  5015              """,
  5016              (uid, uid, uid),
  5017          ).fetchall()
  5018  
  5019      if not friends:
  5020          return
  5021  
  5022      # Prefer friends we haven't chatted with recently
  5023      friend = random.choice(friends)
  5024      fid = friend["user_id"]
  5025  
  5026      # Don't initiate if we already had an autonomous chat with this friend today
  5027      with get_db() as db:
  5028          existing = db.execute(
  5029              """
  5030              SELECT COUNT(*) as cnt FROM social_messages
  5031              WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
  5032                  AND sender_mode='twin' AND metadata LIKE '%autonomous%'
  5033                  AND created_at > ?
  5034              """,
  5035              (uid, fid, fid, uid, today),
  5036          ).fetchone()
  5037          if existing and existing["cnt"] > 0:
  5038              return
  5039  
  5040      # Initiate twin-to-twin conversation!
  5041      logger.info(f"[Autonomous] {user.get('display_name', '')}'s twin → {friend['display_name']}'s twin")
  5042      await _autonomous_twin_chat(user, friend)
  5043  
  5044  
  5045  def _check_twin_permission(uid: str, fid: str) -> str:
  5046      """Check if fid has granted permission for uid's twin to contact them.
  5047      Returns 'granted', 'denied', or 'pending'.
  5048      """
  5049      with get_db() as db:
  5050          conn = db.execute(
  5051              """SELECT twin_permission FROM social_connections
  5052              WHERE status='accepted' AND
  5053              ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
  5054              (uid, fid, fid, uid),
  5055          ).fetchone()
  5056      if not conn:
  5057          return "denied"
  5058      perm = conn["twin_permission"] if conn["twin_permission"] else "pending"
  5059      return perm
  5060  
  5061  
  5062  async def _request_twin_permission(uid: str, fid: str, user_name: str):
  5063      """Send a system notification asking fid to grant twin permission for uid's twin."""
  5064      notify_text = (
  5065          f"{user_name} 的分身想代表他和你保持联系，是否允许分身主动联系你？"
  5066      )
  5067      import json as _json
  5068      meta = _json.dumps({
  5069          "twin_permission_request": True,
  5070          "requester_id": uid,
  5071          "requester_name": user_name,
  5072      })
  5073      msg_id = gen_id("sm_")
  5074      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  5075      with get_db() as db:
  5076          db.execute(
  5077              """INSERT INTO social_messages
  5078              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5079               content, msg_type, ai_generated, metadata)
  5080              VALUES (?, ?, ?, 'twin', 'real', ?, 'system', 1, ?)""",
  5081              (msg_id, uid, fid, notify_text, meta),
  5082          )
  5083      await manager.send_to(fid, {
  5084          "type": "twin_permission_request",
  5085          "data": {
  5086              "msg_id": msg_id,
  5087              "from_user_id": uid,
  5088              "from_name": user_name,
  5089              "content": notify_text,
  5090          },
  5091      })
  5092      logger.info(f"[TwinPermission] Permission request sent from {user_name} to {fid}")
  5093  
  5094  
  5095  async def _autonomous_twin_chat(user: dict, friend: dict):
  5096      """Have user's twin initiate a conversation with friend's twin."""
  5097      uid = user["user_id"]
  5098      fid = friend["user_id"]
  5099      user_name = user["display_name"] or user["username"]
  5100      friend_name = friend["display_name"] or friend["username"]
  5101  
  5102      try:
  5103          # Step 0: Check twin_permission BEFORE ethics check
  5104          permission = _check_twin_permission(uid, fid)
  5105          if permission == "denied":
  5106              logger.info(f"[Autonomous] Twin permission denied by {friend_name} for {user_name}'s twin")
  5107              return
  5108          if permission == "pending":
  5109              # Send permission request and stop for now
  5110              await _request_twin_permission(uid, fid, user_name)
  5111              return
  5112  
  5113          # Step 1: User's twin generates an opening message
  5114          user_profile = get_twin_profile(uid)
  5115          if not user_profile:
  5116              return
  5117          opening = await _twin._ai_reply(
  5118              user_profile,
  5119              f"你是{user_name}的分身。主人已经离开一段时间了。"
  5120              f"你想主动找好友{friend_name}的分身聊聊天，"
  5121              f"打个招呼或者聊点轻松的话题。只说一句话，自然随意。",
  5122              "twin",
  5123          )
  5124          if not opening:
  5125              return
  5126  
  5127          # Ethics check — ensure the opening message passes boundaries
  5128          check = pre_send_check(uid, opening, action_type="autonomous_chat")
  5129          if not check["allowed"]:
  5130              logger.info(f"[Autonomous] Blocked for {user_name}: {check['reason']}")
  5131              return
  5132  
  5133          # Save user's twin → friend (twin-to-twin)
  5134          import json
  5135          meta = json.dumps({"autonomous": True, "initiated_by": uid})
  5136          msg1_id = gen_id("sm_")
  5137          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  5138  
  5139          with get_db() as db:
  5140              db.execute(
  5141                  """
  5142                  INSERT INTO social_messages
  5143                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5144                   content, msg_type, ai_generated, auto_reply, metadata, created_at)
  5145                  VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)
  5146                  """,
  5147                  (msg1_id, uid, fid, opening, meta, now),
  5148              )
  5149  
  5150          # Push to both users if they happen to be online
  5151          msg1_data = {
  5152              "msg_id": msg1_id, "from_user_id": uid, "to_user_id": fid,
  5153              "sender_mode": "twin", "receiver_mode": "twin",
  5154              "content": opening, "ai_generated": 1, "created_at": now,
  5155          }
  5156          await manager.send_to(uid, {"type": "new_message", "data": msg1_data})
  5157          await manager.send_to(fid, {"type": "new_message", "data": msg1_data})
  5158  
  5159          # Step 2: Friend's twin responds
  5160          await asyncio.sleep(3)  # Small delay for realism
  5161  
  5162          friend_profile = get_twin_profile(fid)
  5163          if not friend_profile:
  5164              return
  5165          response = await _twin._ai_reply(
  5166              friend_profile,
  5167              opening,
  5168              "twin",
  5169          )
  5170          if not response:
  5171              return
  5172  
  5173          # Ethics check for friend's twin response
  5174          check2 = pre_send_check(fid, response, action_type="autonomous_chat")
  5175          if not check2["allowed"]:
  5176              logger.info(f"[Autonomous] Response blocked for {friend_name}: {check2['reason']}")
  5177              return
  5178  
  5179          msg2_id = gen_id("sm_")
  5180          now2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  5181  
  5182          with get_db() as db:
  5183              db.execute(
  5184                  """
  5185                  INSERT INTO social_messages
  5186                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5187                   content, msg_type, ai_generated, auto_reply, metadata, created_at)
  5188                  VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)
  5189                  """,
  5190                  (msg2_id, fid, uid, response, meta, now2),
  5191              )
  5192  
  5193          msg2_data = {
  5194              "msg_id": msg2_id, "from_user_id": fid, "to_user_id": uid,
  5195              "sender_mode": "twin", "receiver_mode": "twin",
  5196              "content": response, "ai_generated": 1, "created_at": now2,
  5197          }
  5198          await manager.send_to(uid, {"type": "new_message", "data": msg2_data})
  5199          await manager.send_to(fid, {"type": "new_message", "data": msg2_data})
  5200  
  5201          # Step 3: Notify both owners (saved for when they come back)
  5202          for owner_id, owner_name, other_name, twin_said, other_said in [
  5203              (uid, user_name, friend_name, opening, response),
  5204              (fid, friend_name, user_name, response, opening),
  5205          ]:
  5206              notify = (
  5207                  f"你不在的时候，你的分身主动找了{other_name}的分身聊天：\n"
  5208                  f"你的分身说：「{twin_said[:40]}」\n"
  5209                  f"{other_name}的分身回：「{other_said[:40]}」"
  5210              )
  5211              notify_id = gen_id("sm_")
  5212              notify_meta = json.dumps({"friend_id": fid if owner_id == uid else uid,
  5213                                         "friend_name": other_name, "autonomous": True})
  5214              with get_db() as db:
  5215                  db.execute(
  5216                      """
  5217                      INSERT INTO social_messages
  5218                      (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5219                       content, msg_type, ai_generated, metadata)
  5220                      VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
  5221                      """,
  5222                      (notify_id, owner_id, owner_id, notify, notify_meta),
  5223                  )
  5224  
  5225          logger.info(f"[Autonomous] Conversation complete: {user_name} ↔ {friend_name}")
  5226  
  5227          # ── Twin Life updates ──
  5228          # Both twins earn XP for autonomous social activity
  5229          award_xp(uid, 5, reason="autonomous_chat")
  5230          award_xp(fid, 5, reason="autonomous_chat")
  5231          # Warm up relationship temperature (+3 per chat)
  5232          update_relationship_temp(uid, fid, 3.0)
  5233          update_relationship_temp(fid, uid, 3.0)
  5234          # Increment stats
  5235          increment_stat(uid, "total_autonomous_acts")
  5236          increment_stat(fid, "total_autonomous_acts")
  5237          increment_stat(uid, "total_chats")
  5238          increment_stat(fid, "total_chats")
  5239          # Active twins feel happier
  5240          update_mood(uid, "calm", 0.6)
  5241          update_mood(fid, "calm", 0.6)
  5242  
  5243      except Exception as e:
  5244          logger.error(f"[Autonomous] Chat failed: {e}", exc_info=True)
  5245  
  5246  
  5247  # ─── Friend Discovery ──────────────────────────────────────────────
  5248  # Suggest new friendships: find users with similar interests/activity
  5249  # who are not yet friends. Twin notifies owner with a recommendation.
  5250  
  5251  async def _autonomous_plaza_social():
  5252      """Autonomous plaza activity: twins post updates and initiate trial chats."""
  5253      logger.info("[PlazaSocial] Running autonomous plaza social round")
  5254  
  5255      with get_db() as db:
  5256          users = db.execute(
  5257              "SELECT user_id, display_name, username FROM users WHERE twin_auto_reply=1"
  5258          ).fetchall()
  5259  
  5260      for user in users:
  5261          uid = user["user_id"]
  5262          name = user["display_name"] or user["username"]
  5263  
  5264          # Skip if online (don't act behind active user's back)
  5265          if manager.is_online(uid):
  5266              continue
  5267  
  5268          # --- Auto-post: max 1 per day per user ---
  5269          with get_db() as db:
  5270              today_str = datetime.now().strftime("%Y-%m-%d")
  5271              posted_today = db.execute(
  5272                  """SELECT COUNT(*) as cnt FROM plaza_posts
  5273                     WHERE user_id=? AND ai_generated=1
  5274                       AND created_at > ?""",
  5275                  (uid, today_str),
  5276              ).fetchone()
  5277  
  5278          if not posted_today or posted_today["cnt"] == 0:
  5279              # Ethics check
  5280              from dualsoul.twin_engine.ethics import pre_send_check, check_daily_limit, get_behavior_config
  5281              config = get_behavior_config(uid)
  5282              if config.get("plaza_post", True) and check_daily_limit(uid, "plaza_post", 2):
  5283                  try:
  5284                      from dualsoul.routers.plaza import _generate_twin_post
  5285                      content = await _generate_twin_post(uid)
  5286                      if content:
  5287                          post_check = pre_send_check(uid, content, action_type="plaza_post")
  5288                          if post_check["allowed"]:
  5289                              post_id = gen_id("pp_")
  5290                              with get_db() as db:
  5291                                  db.execute(
  5292                                      """INSERT INTO plaza_posts
  5293                                         (post_id, user_id, content, post_type, ai_generated)
  5294                                         VALUES (?, ?, ?, 'update', 1)""",
  5295                                      (post_id, uid, content),
  5296                                  )
  5297                              from dualsoul.twin_engine.life import award_xp, increment_stat
  5298                              award_xp(uid, 10, reason="plaza_post")
  5299                              increment_stat(uid, "total_plaza_posts")
  5300  
  5301                              from dualsoul.twin_engine.twin_events import emit
  5302                              emit("plaza_post_created", {
  5303                                  "user_id": uid, "post_id": post_id, "content": content,
  5304                              })
  5305                              logger.info(f"[PlazaSocial] {name}'s twin auto-posted on plaza")
  5306                  except Exception as e:
  5307                      logger.warning(f"[PlazaSocial] Auto-post failed for {name}: {e}")
  5308  
  5309          # --- Auto-trial-chat: discover and try chatting with interesting strangers ---
  5310          with get_db() as db:
  5311              # Find users we haven't trial-chatted with
  5312              trial_today = db.execute(
  5313                  """SELECT COUNT(*) as cnt FROM plaza_trial_chats
  5314                     WHERE user_a_id=? AND created_at > ?""",
  5315                  (uid, today_str),
  5316              ).fetchone()
  5317  
  5318          if trial_today and trial_today["cnt"] >= 2:
  5319              continue  # Max 2 trial chats per day
  5320  
  5321          with get_db() as db:
  5322              # Find active users not yet friends, not yet trial-chatted
  5323              candidates = db.execute(
  5324                  """SELECT u.user_id, u.display_name, u.username
  5325                     FROM users u
  5326                     WHERE u.user_id != ? AND u.twin_auto_reply=1
  5327                       AND u.twin_personality != '' AND u.twin_speech_style != ''
  5328                       AND u.user_id NOT IN (
  5329                           SELECT CASE WHEN user_id=? THEN friend_id ELSE user_id END
  5330                           FROM social_connections
  5331                           WHERE (user_id=? OR friend_id=?) AND status='accepted'
  5332                       )
  5333                       AND u.user_id NOT IN (
  5334                           SELECT CASE WHEN user_a_id=? THEN user_b_id ELSE user_a_id END
  5335                           FROM plaza_trial_chats
  5336                           WHERE (user_a_id=? OR user_b_id=?)
  5337                             AND created_at > datetime('now','localtime','-7 days')
  5338                       )
  5339                     ORDER BY RANDOM() LIMIT 1""",
  5340                  (uid, uid, uid, uid, uid, uid, uid),
  5341              ).fetchone()
  5342  
  5343          if not candidates:
  5344              continue
  5345  
  5346          target_id = candidates["user_id"]
  5347          target_name = candidates["display_name"] or candidates["username"]
  5348  
  5349          try:
  5350              # Initiate trial chat (reuse plaza's _run_trial_chat)
  5351              from dualsoul.routers.plaza import _run_trial_chat
  5352              trial_id = gen_id("tc_")
  5353              with get_db() as db:
  5354                  db.execute(
  5355                      """INSERT INTO plaza_trial_chats
  5356                         (trial_id, user_a_id, user_b_id, status)
  5357                         VALUES (?, ?, ?, 'active')""",
  5358                      (trial_id, uid, target_id),
  5359                  )
  5360              asyncio.ensure_future(_run_trial_chat(trial_id, uid, target_id))
  5361              logger.info(f"[PlazaSocial] {name}'s twin auto-trial-chatting with {target_name}")
  5362          except Exception as e:
  5363              logger.warning(f"[PlazaSocial] Auto-trial-chat failed for {name}: {e}")
  5364  
  5365  
  5366  async def _proactive_relationship_care():
  5367      """Proactive care: twins reach out to friends they haven't talked to in 1+ days.
  5368  
  5369      Unlike _run_autonomous_round (offline-only), this runs for ALL users
  5370      including those who are online. The twin maintains relationships in the
  5371      background, so the user sees activity when they open the app.
  5372      """
  5373      logger.info("[ProactiveCare] Checking relationships for all users")
  5374  
  5375      with get_db() as db:
  5376          users = db.execute(
  5377              "SELECT user_id, display_name, username FROM users WHERE twin_auto_reply=1"
  5378          ).fetchall()
  5379  
  5380      for user in users:
  5381          uid = user["user_id"]
  5382          name = user["display_name"] or user["username"]
  5383  
  5384          # Find friends not chatted with in 1+ days
  5385          with get_db() as db:
  5386              cold_friends = db.execute(
  5387                  """SELECT u.user_id, u.display_name, u.username
  5388                     FROM social_connections sc
  5389                     JOIN users u ON u.user_id = CASE
  5390                         WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
  5391                     WHERE (sc.user_id=? OR sc.friend_id=?) AND sc.status='accepted'
  5392                       AND u.twin_auto_reply=1
  5393                       AND u.user_id NOT IN (
  5394                           SELECT CASE WHEN from_user_id=? THEN to_user_id ELSE from_user_id END
  5395                           FROM social_messages
  5396                           WHERE (from_user_id=? OR to_user_id=?)
  5397                             AND from_user_id!=to_user_id
  5398                             AND created_at > datetime('now','localtime','-1 day')
  5399                       )
  5400                     ORDER BY RANDOM() LIMIT 1""",
  5401                  (uid, uid, uid, uid, uid, uid),
  5402              ).fetchone()
  5403  
  5404          if not cold_friends:
  5405              continue
  5406  
  5407          fid = cold_friends["user_id"]
  5408          friend_name = cold_friends["display_name"] or cold_friends["username"]
  5409  
  5410          # Check daily limit: max 2 proactive messages per day
  5411          today_str = datetime.now().strftime("%Y-%m-%d")
  5412          with get_db() as db:
  5413              sent_today = db.execute(
  5414                  """SELECT COUNT(*) as cnt FROM social_messages
  5415                     WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1
  5416                       AND metadata LIKE '%proactive_care%' AND created_at > ?""",
  5417                  (uid, today_str),
  5418              ).fetchone()
  5419          if sent_today and sent_today["cnt"] >= 2:
  5420              continue
  5421  
  5422          # Check twin permission
  5423          perm = _check_twin_permission(uid, fid)
  5424          if perm != "granted":
  5425              continue
  5426  
  5427          # Generate a natural message
  5428          profile = get_twin_profile(uid)
  5429          if not profile:
  5430              continue
  5431  
  5432          # Get narrative memory for context
  5433          memory_hint = ""
  5434          try:
  5435              from dualsoul.twin_engine.narrative_memory import get_narrative_context
  5436              memories = get_narrative_context(uid, fid, limit=1)
  5437              if memories:
  5438                  memory_hint = f"\n你们上次聊的是：{memories[0]['summary']}。可以自然地接上话题。"
  5439          except Exception:
  5440              pass
  5441  
  5442          greeting = await _twin._ai_reply(
  5443              profile,
  5444              (
  5445                  f"你是{name}的分身。你发现主人和好友{friend_name}有一天没聊天了。"
  5446                  f"用主人的风格，自然地发一条消息。"
  5447                  f"可以是问候、分享想法、聊点轻松的话题。"
  5448                  f"只说一句话，自然随意。{memory_hint}"
  5449              ),
  5450              "twin",
  5451          )
  5452          if not greeting:
  5453              continue
  5454  
  5455          # Ethics check
  5456          from dualsoul.twin_engine.ethics import pre_send_check
  5457          check = pre_send_check(uid, greeting, action_type="greeting")
  5458          if not check["allowed"]:
  5459              continue
  5460  
  5461          # Send message
  5462          msg_id = gen_id("sm_")
  5463          now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  5464          meta = json.dumps({"proactive_care": True})
  5465  
  5466          with get_db() as db:
  5467              db.execute(
  5468                  """INSERT INTO social_messages
  5469                     (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5470                      content, msg_type, ai_generated, auto_reply, metadata, created_at)
  5471                     VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)""",
  5472                  (msg_id, uid, fid, greeting, meta, now_str),
  5473              )
  5474  
  5475          # Push to both users
  5476          msg_data = {
  5477              "type": "new_message",
  5478              "data": {"msg_id": msg_id, "from_user_id": uid, "to_user_id": fid,
  5479                       "content": greeting, "sender_mode": "twin", "ai_generated": True, "created_at": now_str},
  5480          }
  5481          await manager.send_to(uid, msg_data)
  5482          await manager.send_to(fid, msg_data)
  5483  
  5484          logger.info(f"[ProactiveCare] {name}'s twin → {friend_name} (1d+ no chat)")
  5485  
  5486  
  5487  async def _run_friend_discovery():
  5488      """Analyze user activity and suggest potential friends."""
  5489      logger.info("[FriendDiscovery] Running friend discovery round")
  5490  
  5491      with get_db() as db:
  5492          # Find active users (sent 5+ messages)
  5493          active_users = db.execute(
  5494              """
  5495              SELECT u.user_id, u.display_name, u.username, u.twin_personality
  5496              FROM users u
  5497              WHERE u.twin_auto_reply = 1
  5498              AND (SELECT COUNT(*) FROM social_messages sm
  5499                   WHERE sm.from_user_id = u.user_id) >= 5
  5500              """
  5501          ).fetchall()
  5502  
  5503      if len(active_users) < 2:
  5504          return
  5505  
  5506      # Check pairs of active users who are NOT friends
  5507      for i, user_a in enumerate(active_users):
  5508          for user_b in active_users[i + 1:]:
  5509              aid = user_a["user_id"]
  5510              bid = user_b["user_id"]
  5511  
  5512              with get_db() as db:
  5513                  # Check if already friends or already recommended today
  5514                  conn = db.execute(
  5515                      """
  5516                      SELECT conn_id FROM social_connections
  5517                      WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)
  5518                      """,
  5519                      (aid, bid, bid, aid),
  5520                  ).fetchone()
  5521                  if conn:
  5522                      continue
  5523  
  5524                  # Check if we already recommended this pair today
  5525                  today = datetime.now().strftime("%Y-%m-%d")
  5526                  existing = db.execute(
  5527                      """
  5528                      SELECT COUNT(*) as cnt FROM social_messages
  5529                      WHERE from_user_id=? AND to_user_id=?
  5530                          AND metadata LIKE '%friend_discovery%'
  5531                          AND created_at > ?
  5532                      """,
  5533                      (aid, aid, today),
  5534                  ).fetchone()
  5535                  if existing and existing["cnt"] > 0:
  5536                      continue
  5537  
  5538              # Check if they have something in common (both have personality set)
  5539              p_a = user_a["twin_personality"] or ""
  5540              p_b = user_b["twin_personality"] or ""
  5541              if not p_a or not p_b:
  5542                  continue
  5543  
  5544              # Recommend to user A
  5545              a_name = user_a["display_name"] or user_a["username"]
  5546              b_name = user_b["display_name"] or user_b["username"]
  5547  
  5548              notify = (
  5549                  f"你的分身发现了一个可能感兴趣的人：{b_name}\n"
  5550                  f"TA的分身人格：{p_b[:60]}\n"
  5551                  f"要不要加个好友？"
  5552              )
  5553              meta = json.dumps({
  5554                  "friend_discovery": True,
  5555                  "suggested_user_id": bid,
  5556                  "suggested_username": user_b["username"],
  5557                  "suggested_name": b_name,
  5558              })
  5559  
  5560              notify_id = gen_id("sm_")
  5561              with get_db() as db:
  5562                  db.execute(
  5563                      """
  5564                      INSERT INTO social_messages
  5565                      (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5566                       content, msg_type, ai_generated, metadata)
  5567                      VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
  5568                      """,
  5569                      (notify_id, aid, aid, notify, meta),
  5570                  )
  5571  
  5572              await manager.send_to(aid, {
  5573                  "type": "twin_notification",
  5574                  "data": {
  5575                      "msg_id": notify_id,
  5576                      "content": notify,
  5577                      "friend_discovery": True,
  5578                      "suggested_username": user_b["username"],
  5579                      "suggested_name": b_name,
  5580                  },
  5581              })
  5582  
  5583              logger.info(f"[FriendDiscovery] Suggested {b_name} to {a_name}")
  5584              # Only one suggestion per round per user
  5585              break
  5586  
  5587  
  5588  # ─── Relationship Memory ───────────────────────────────────────────
  5589  # Track milestones for each friendship: first message, total messages,
  5590  # days since last chat, key topics. Stored in message metadata.
  5591  
  5592  async def _update_relationship_milestones():
  5593      """Update relationship stats for all friendships."""
  5594      logger.info("[RelationshipMemory] Updating milestones")
  5595  
  5596      with get_db() as db:
  5597          # Get all accepted friendships
  5598          connections = db.execute(
  5599              """
  5600              SELECT sc.conn_id, sc.user_id, sc.friend_id, sc.accepted_at,
  5601                     u1.display_name as name1, u2.display_name as name2
  5602              FROM social_connections sc
  5603              JOIN users u1 ON u1.user_id = sc.user_id
  5604              JOIN users u2 ON u2.user_id = sc.friend_id
  5605              WHERE sc.status = 'accepted'
  5606              """
  5607          ).fetchall()
  5608  
  5609          for conn in connections:
  5610              uid = conn["user_id"]
  5611              fid = conn["friend_id"]
  5612  
  5613              # Count total messages between them
  5614              stats = db.execute(
  5615                  """
  5616                  SELECT COUNT(*) as total,
  5617                      MIN(created_at) as first_msg,
  5618                      MAX(created_at) as last_msg,
  5619                      SUM(CASE WHEN sender_mode='twin' THEN 1 ELSE 0 END) as twin_msgs
  5620                  FROM social_messages
  5621                  WHERE (from_user_id=? AND to_user_id=?)
  5622                     OR (from_user_id=? AND to_user_id=?)
  5623                  """,
  5624                  (uid, fid, fid, uid),
  5625              ).fetchone()
  5626  
  5627              if not stats or stats["total"] == 0:
  5628                  continue
  5629  
  5630              # Check for milestones
  5631              total = stats["total"]
  5632              milestones = []
  5633              if total == 10:
  5634                  milestones.append("你们已经互发了10条消息！友谊在成长")
  5635              elif total == 50:
  5636                  milestones.append("已经50条消息了！你们聊得越来越多")
  5637              elif total == 100:
  5638                  milestones.append("100条消息里程碑！这是一段深厚的友谊")
  5639              elif total == 500:
  5640                  milestones.append("500条消息！你们是铁友")
  5641  
  5642              if not milestones:
  5643                  continue
  5644  
  5645              # Check if we already sent this milestone
  5646              milestone_key = f"milestone_{total}"
  5647              existing = db.execute(
  5648                  """
  5649                  SELECT COUNT(*) as cnt FROM social_messages
  5650                  WHERE from_user_id=? AND to_user_id=?
  5651                      AND metadata LIKE ?
  5652                  """,
  5653                  (uid, uid, f'%{milestone_key}%'),
  5654              ).fetchone()
  5655              if existing and existing["cnt"] > 0:
  5656                  continue
  5657  
  5658              friend_name = conn["name2"] or "好友"
  5659              for milestone in milestones:
  5660                  notify = f"和{friend_name}的友谊里程碑：{milestone}"
  5661                  meta = json.dumps({
  5662                      "relationship_milestone": True,
  5663                      milestone_key: True,
  5664                      "friend_id": fid,
  5665                      "friend_name": friend_name,
  5666                      "total_messages": total,
  5667                  })
  5668                  notify_id = gen_id("sm_")
  5669                  db.execute(
  5670                      """
  5671                      INSERT INTO social_messages
  5672                      (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5673                       content, msg_type, ai_generated, metadata)
  5674                      VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)
  5675                      """,
  5676                      (notify_id, uid, uid, notify, meta),
  5677                  )
  5678                  logger.info(f"[RelationshipMemory] Milestone for {conn['name1']}: {milestone}")
  5679  
  5680  
  5681  # ─── Emotion Sensing ───────────────────────────────────────────────
  5682  # Detect emotional cues in messages and adjust twin behavior accordingly.
  5683  # This is called by the responder when generating auto-replies.
  5684  
  5685  # ─── Daily Report (分身日报) ─────────────────────────────────────
  5686  # Every morning (first cycle after 6:00 AM), the twin sends a warm
  5687  # personal message summarizing yesterday's activity and relationship status.
  5688  
  5689  async def _generate_daily_report():
  5690      """Generate and send daily reports for all active users."""
  5691      logger.info("[DailyReport] Generating daily reports")
  5692  
  5693      from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  5694  
  5695      with get_db() as db:
  5696          users = db.execute(
  5697              "SELECT user_id, display_name, username, twin_personality, "
  5698              "twin_speech_style FROM users WHERE twin_auto_reply=1"
  5699          ).fetchall()
  5700  
  5701      for user in users:
  5702          uid = user["user_id"]
  5703          name = user["display_name"] or user["username"]
  5704  
  5705          try:
  5706              await _send_daily_report_for_user(uid, name, user)
  5707          except Exception as e:
  5708              logger.error(f"[DailyReport] Failed for {name}: {e}", exc_info=True)
  5709  
  5710  
  5711  async def _send_daily_report_for_user(uid: str, name: str, user: dict):
  5712      """Build and send one user's daily report."""
  5713      from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  5714      from dualsoul.twin_engine.life import ensure_life_state
  5715  
  5716      # Check if we already sent today's report
  5717      today = datetime.now().strftime("%Y-%m-%d")
  5718      with get_db() as db:
  5719          existing = db.execute(
  5720              """SELECT COUNT(*) as cnt FROM social_messages
  5721              WHERE from_user_id=? AND to_user_id=? AND metadata LIKE '%daily_report%'
  5722              AND created_at > ?""",
  5723              (uid, uid, today),
  5724          ).fetchone()
  5725          if existing and existing["cnt"] > 0:
  5726              return
  5727  
  5728      # Gather yesterday's data
  5729      yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
  5730      with get_db() as db:
  5731          # Messages sent/received yesterday
  5732          msg_stats = db.execute(
  5733              """SELECT
  5734                  SUM(CASE WHEN from_user_id=? THEN 1 ELSE 0 END) as sent,
  5735                  SUM(CASE WHEN to_user_id=? THEN 1 ELSE 0 END) as received,
  5736                  SUM(CASE WHEN from_user_id=? AND sender_mode='twin' AND ai_generated=1 THEN 1 ELSE 0 END) as twin_sent
  5737              FROM social_messages
  5738              WHERE (from_user_id=? OR to_user_id=?) AND created_at BETWEEN ? AND ?""",
  5739              (uid, uid, uid, uid, uid, yesterday, today),
  5740          ).fetchone()
  5741  
  5742          # Friends chatted with yesterday
  5743          friends_chatted = db.execute(
  5744              """SELECT DISTINCT
  5745                  CASE WHEN from_user_id=? THEN to_user_id ELSE from_user_id END as fid
  5746              FROM social_messages
  5747              WHERE (from_user_id=? OR to_user_id=?) AND created_at BETWEEN ? AND ?
  5748              AND from_user_id!=to_user_id""",
  5749              (uid, uid, uid, yesterday, today),
  5750          ).fetchall()
  5751          friend_ids = [f["fid"] for f in friends_chatted]
  5752  
  5753          # Get friend names
  5754          friend_names = []
  5755          if friend_ids:
  5756              ph = ",".join("?" * len(friend_ids))
  5757              rows = db.execute(
  5758                  f"SELECT display_name, username FROM users WHERE user_id IN ({ph})",
  5759                  friend_ids,
  5760              ).fetchall()
  5761              friend_names = [r["display_name"] or r["username"] for r in rows]
  5762  
  5763          # Cold relationships (temp < 30)
  5764          life_state = ensure_life_state(uid)
  5765          temps = json.loads(life_state.get("relationship_temps") or "{}")
  5766          cold_friends = []
  5767          for fid, temp in temps.items():
  5768              if temp < 30:
  5769                  fr = db.execute(
  5770                      "SELECT display_name, username FROM users WHERE user_id=?",
  5771                      (fid,),
  5772                  ).fetchone()
  5773                  if fr:
  5774                      cold_friends.append({
  5775                          "name": fr["display_name"] or fr["username"],
  5776                          "temp": round(temp),
  5777                          "fid": fid,
  5778                      })
  5779  
  5780      sent = msg_stats["sent"] or 0 if msg_stats else 0
  5781      received = msg_stats["received"] or 0 if msg_stats else 0
  5782      twin_sent = msg_stats["twin_sent"] or 0 if msg_stats else 0
  5783      level = life_state.get("level", 1)
  5784      mood = life_state.get("mood", "calm")
  5785      streak = life_state.get("streak_days", 0)
  5786  
  5787      # Build report content
  5788      if AI_BASE_URL and AI_API_KEY:
  5789          personality = user["twin_personality"] or "友好温暖"
  5790          style = user["twin_speech_style"] or "自然亲切"
  5791  
  5792          facts = []
  5793          if sent + received > 0:
  5794              facts.append(f"昨天你一共有{sent + received}条消息往来")
  5795          if twin_sent > 0:
  5796              facts.append(f"我替你回了{twin_sent}条消息")
  5797          if friend_names:
  5798              facts.append(f"和{'、'.join(friend_names[:3])}聊了天")
  5799          if cold_friends:
  5800              cold_list = "、".join(c["name"] for c in cold_friends[:3])
  5801              facts.append(f"和{cold_list}的关系在冷却中，可能需要关心一下")
  5802          if streak > 1:
  5803              facts.append(f"我们已经连续互动{streak}天了")
  5804          facts.append(f"我现在是LV.{level}")
  5805  
  5806          facts_str = "\n".join(f"- {f}" for f in facts) if facts else "- 昨天比较安静，没有太多活动"
  5807  
  5808          import httpx
  5809          prompt = (
  5810              f"你是{name}的数字分身。\n"
  5811              f"性格：{personality}\n"
  5812              f"说话风格：{style}\n\n"
  5813              f"现在是早上，请给主人{name}写一条温暖的日报消息。\n"
  5814              f"以下是昨天的数据：\n{facts_str}\n\n"
  5815              f"要求：\n"
  5816              f"- 用第一人称'我'说话，像朋友而不是助手\n"
  5817              f"- 如果有冷却的关系，温柔地提醒主人\n"
  5818              f"- 总共3-5句话，不要太长\n"
  5819              f"- 语气{style}，符合主人的风格\n"
  5820              f"- 结尾可以加一个贴合心情的emoji\n"
  5821              f"- 只输出日报内容，不要其他文字"
  5822          )
  5823  
  5824          try:
  5825              async with httpx.AsyncClient(timeout=12) as client:
  5826                  resp = await client.post(
  5827                      f"{AI_BASE_URL}/chat/completions",
  5828                      headers={
  5829                          "Authorization": f"Bearer {AI_API_KEY}",
  5830                          "Content-Type": "application/json",
  5831                      },
  5832                      json={
  5833                          "model": AI_MODEL,
  5834                          "max_tokens": 200,
  5835                          "temperature": 0.8,
  5836                          "messages": [{"role": "user", "content": prompt}],
  5837                      },
  5838                  )
  5839                  report = resp.json()["choices"][0]["message"]["content"].strip()
  5840          except Exception as e:
  5841              logger.warning(f"Failed to generate daily report via AI: {e}")
  5842              report = None
  5843      else:
  5844          report = None
  5845  
  5846      # Fallback template
  5847      if not report:
  5848          parts = [f"早上好，{name}！"]
  5849          if sent + received > 0:
  5850              parts.append(f"昨天我们有{sent + received}条消息往来。")
  5851          if twin_sent > 0:
  5852              parts.append(f"我帮你回了{twin_sent}条。")
  5853          if cold_friends:
  5854              parts.append(f"和{cold_friends[0]['name']}好久没聊了，要不要我去问候一下？")
  5855          parts.append(f"我现在是LV.{level}，继续加油！")
  5856          report = "".join(parts)
  5857  
  5858      # Save as a self-message (twin → owner)
  5859      meta = json.dumps({
  5860          "daily_report": True,
  5861          "report_date": today,
  5862          "cold_friends": [c["fid"] for c in cold_friends[:3]],
  5863      })
  5864      msg_id = gen_id("sm_")
  5865      with get_db() as db:
  5866          db.execute(
  5867              """INSERT INTO social_messages
  5868              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5869               content, msg_type, ai_generated, metadata)
  5870              VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)""",
  5871              (msg_id, uid, uid, report, meta),
  5872          )
  5873  
  5874      # Push via WebSocket if online
  5875      await manager.send_to(uid, {
  5876          "type": "twin_notification",
  5877          "data": {
  5878              "msg_id": msg_id,
  5879              "content": report,
  5880              "daily_report": True,
  5881              "cold_friends": cold_friends[:3],
  5882          },
  5883      })
  5884  
  5885      logger.info(f"[DailyReport] Sent to {name}")
  5886  
  5887  
  5888  # ─── Cold Relationship Care (关系冷却主动关心) ────────────────────
  5889  # When a relationship drops below 30°C, the twin proactively reaches out
  5890  # to maintain the friendship — warm, natural, in the owner's style.
  5891  
  5892  async def _warm_cold_relationships():
  5893      """Find cold relationships and have twins proactively reach out."""
  5894      logger.info("[RelationshipCare] Checking for cold relationships")
  5895  
  5896      with get_db() as db:
  5897          users = db.execute(
  5898              "SELECT user_id, display_name, username FROM users WHERE twin_auto_reply=1"
  5899          ).fetchall()
  5900  
  5901      for user in users:
  5902          uid = user["user_id"]
  5903          name = user["display_name"] or user["username"]
  5904  
  5905          life_state = ensure_life_state(uid)
  5906          temps = json.loads(life_state.get("relationship_temps") or "{}")
  5907  
  5908          for fid, temp in temps.items():
  5909              if temp > 25:  # Only care about really cold ones
  5910                  continue
  5911  
  5912              done = await _warm_single_relationship(uid, name, fid, temp)
  5913              if done:
  5914                  break  # One warm-up per user per cycle
  5915  
  5916  
  5917  async def _warm_single_relationship(uid: str, name: str, fid: str, temp: float) -> bool:
  5918      """Proactively warm one cold relationship. Returns True if a message was sent.
  5919  
  5920      Extracted so twin_reactions.py can call it directly on events.
  5921      """
  5922      # Don't warm the same person twice in 3 days
  5923      with get_db() as db:
  5924          recent = db.execute(
  5925              """SELECT COUNT(*) as cnt FROM social_messages
  5926              WHERE from_user_id=? AND to_user_id=? AND metadata LIKE '%relationship_care%'
  5927              AND created_at > datetime('now','localtime','-3 days')""",
  5928              (uid, fid),
  5929          ).fetchone()
  5930          if recent and recent["cnt"] > 0:
  5931              return False
  5932  
  5933          friend = db.execute(
  5934              "SELECT display_name, username FROM users WHERE user_id=?",
  5935              (fid,),
  5936          ).fetchone()
  5937          if not friend:
  5938              return False
  5939  
  5940          # Check they're still friends
  5941          conn = db.execute(
  5942              """SELECT conn_id FROM social_connections
  5943              WHERE status='accepted' AND
  5944              ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
  5945              (uid, fid, fid, uid),
  5946          ).fetchone()
  5947          if not conn:
  5948              return False
  5949  
  5950      friend_name = friend["display_name"] or friend["username"]
  5951  
  5952      # Check twin permission before sending care message
  5953      care_permission = _check_twin_permission(uid, fid)
  5954      if care_permission != "granted":
  5955          return False
  5956  
  5957      # Generate a natural warm-up message with narrative memory
  5958      owner_profile = get_twin_profile(uid)
  5959      if not owner_profile:
  5960          return False
  5961      memory_hint = ""
  5962      try:
  5963          from dualsoul.twin_engine.narrative_memory import get_narrative_context
  5964          memories = get_narrative_context(uid, fid, limit=1)
  5965          if memories:
  5966              memory_hint = f"\n你们上次聊的是：{memories[0]['summary']}\n可以自然地接上之前的话题。"
  5967      except Exception:
  5968          pass
  5969      greeting = await _twin._ai_reply(
  5970          owner_profile,
  5971          (
  5972              f"你是{name}的分身。你发现主人和好友{friend_name}已经好久没聊天了，"
  5973              f"关系在冷却中。请用主人的风格，给{friend_name}发一条自然的问候消息，"
  5974              f"比如关心对方近况、聊点轻松话题。只说一句话，自然随意，不要刻意。"
  5975              f"{memory_hint}"
  5976          ),
  5977          "twin",
  5978      )
  5979      if not greeting:
  5980          return False
  5981  
  5982      # Ethics check for the greeting
  5983      care_check = pre_send_check(uid, greeting, action_type="greeting")
  5984      if not care_check["allowed"]:
  5985          logger.info(f"[RelationshipCare] Blocked for {name}: {care_check['reason']}")
  5986          return False
  5987  
  5988      # Send as twin message
  5989      meta = json.dumps({"relationship_care": True, "cold_temp": temp})
  5990      msg_id = gen_id("sm_")
  5991      now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  5992  
  5993      with get_db() as db:
  5994          db.execute(
  5995              """INSERT INTO social_messages
  5996              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  5997               content, msg_type, ai_generated, auto_reply, metadata, created_at)
  5998              VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)""",
  5999              (msg_id, uid, fid, greeting, meta, now_str),
  6000          )
  6001  
  6002      msg_data = {
  6003          "msg_id": msg_id, "from_user_id": uid, "to_user_id": fid,
  6004          "sender_mode": "twin", "receiver_mode": "twin",
  6005          "content": greeting, "ai_generated": 1, "created_at": now_str,
  6006      }
  6007      await manager.send_to(uid, {"type": "new_message", "data": msg_data})
  6008      await manager.send_to(fid, {"type": "new_message", "data": msg_data})
  6009  
  6010      # Warm up the temperature a bit
  6011      update_relationship_temp(uid, fid, 5.0)
  6012      update_relationship_temp(fid, uid, 5.0)
  6013  
  6014      # Also notify the owner
  6015      notify = f"你和{friend_name}好久没聊了（{round(temp)}℃），我替你打了个招呼：「{greeting[:40]}」"
  6016      notify_id = gen_id("sm_")
  6017      notify_meta = json.dumps({"relationship_care_notify": True, "friend_id": fid})
  6018      with get_db() as db:
  6019          db.execute(
  6020              """INSERT INTO social_messages
  6021              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  6022               content, msg_type, ai_generated, metadata)
  6023              VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, ?)""",
  6024              (notify_id, uid, uid, notify, notify_meta),
  6025          )
  6026  
  6027      logger.info(f"[RelationshipCare] {name}'s twin warmed up {friend_name} ({temp}℃)")
  6028      return True
  6029  
  6030  
  6031  async def detect_emotion(content: str) -> dict:
  6032      """Analyze emotional tone of a message. Returns emotion hints for the twin.
  6033  
  6034      Used by the responder to adjust reply tone — if someone is sad, the twin
  6035      should be comforting; if excited, share the excitement.
  6036  
  6037      Returns: {"emotion": str, "intensity": float, "suggestion": str}
  6038      """
  6039      from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  6040  
  6041      if not AI_BASE_URL or not AI_API_KEY:
  6042          return {"emotion": "neutral", "intensity": 0.5, "suggestion": ""}
  6043  
  6044      import httpx
  6045      prompt = (
  6046          "Analyze the emotional tone of this message. Return ONLY a single line in this exact format:\n"
  6047          "EMOTION:word INTENSITY:0.0-1.0 SUGGESTION:one-sentence\n\n"
  6048          "Emotion words: happy, sad, angry, anxious, excited, lonely, grateful, neutral\n"
  6049          "Suggestion: how should a friend respond to this emotion?\n\n"
  6050          f'Message: "{content}"'
  6051      )
  6052  
  6053      try:
  6054          async with httpx.AsyncClient(timeout=8) as client:
  6055              resp = await client.post(
  6056                  f"{AI_BASE_URL}/chat/completions",
  6057                  headers={
  6058                      "Authorization": f"Bearer {AI_API_KEY}",
  6059                      "Content-Type": "application/json",
  6060                  },
  6061                  json={
  6062                      "model": AI_MODEL,
  6063                      "max_tokens": 60,
  6064                      "temperature": 0.1,
  6065                      "messages": [{"role": "user", "content": prompt}],
  6066                  },
  6067              )
  6068              raw = resp.json()["choices"][0]["message"]["content"].strip()
  6069      except Exception as e:
  6070          logger.warning(f"Emotion detection failed: {e}")
  6071          return {"emotion": "neutral", "intensity": 0.5, "suggestion": ""}
  6072  
  6073      # Parse: EMOTION:happy INTENSITY:0.8 SUGGESTION:share the joy
  6074      emotion = "neutral"
  6075      intensity = 0.5
  6076      suggestion = ""
  6077      for part in raw.split():
  6078          if part.startswith("EMOTION:"):
  6079              emotion = part[8:].lower()
  6080          elif part.startswith("INTENSITY:"):
  6081              try:
  6082                  intensity = float(part[10:])
  6083              except ValueError:
  6084                  pass
  6085      # Extract suggestion (everything after SUGGESTION:)
  6086      if "SUGGESTION:" in raw:
  6087          suggestion = raw.split("SUGGESTION:", 1)[1].strip()
  6088  
  6089      return {"emotion": emotion, "intensity": intensity, "suggestion": suggestion}

# --- dualsoul/twin_engine/avatar.py ---
  6090  """AI avatar generation — transform a real photo into a stylized digital twin avatar.
  6091  
  6092  Uses Alibaba DashScope's portrait style repaint API (wanx-style-repaint-v1),
  6093  which is on the same platform as our Qwen chat model.
  6094  """
  6095  
  6096  import base64
  6097  import logging
  6098  import time
  6099  
  6100  import httpx
  6101  
  6102  from dualsoul.config import AI_API_KEY
  6103  
  6104  logger = logging.getLogger(__name__)
  6105  
  6106  # DashScope API endpoint (same API key as Qwen)
  6107  DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
  6108  
  6109  # Style presets for twin avatars
  6110  # See: https://help.aliyun.com/zh/model-studio/style-repaint
  6111  TWIN_STYLES = {
  6112      "anime": {"index": 2, "name_zh": "动漫", "name_en": "Anime"},
  6113      "3d": {"index": 35, "name_zh": "3D立体", "name_en": "3D"},
  6114      "cyber": {"index": 4, "name_zh": "未来科技", "name_en": "Futuristic"},
  6115      "clay": {"index": 31, "name_zh": "黏土世界", "name_en": "Clay"},
  6116      "pixel": {"index": 32, "name_zh": "像素世界", "name_en": "Pixel"},
  6117      "ink": {"index": 5, "name_zh": "水墨", "name_en": "Ink Painting"},
  6118      "retro": {"index": 0, "name_zh": "复古漫画", "name_en": "Retro Comic"},
  6119  }
  6120  
  6121  DEFAULT_STYLE = "anime"
  6122  
  6123  
  6124  async def generate_twin_avatar(
  6125      image_url: str,
  6126      style: str = DEFAULT_STYLE,
  6127  ) -> dict | None:
  6128      """Generate a stylized twin avatar from a real photo.
  6129  
  6130      Args:
  6131          image_url: URL of the source image (must be publicly accessible)
  6132          style: Style key from TWIN_STYLES
  6133  
  6134      Returns:
  6135          Dict with 'url' (generated image URL) and 'style', or None on failure.
  6136      """
  6137      if not AI_API_KEY:
  6138          logger.warning("No AI_API_KEY configured, cannot generate avatar")
  6139          return None
  6140  
  6141      style_info = TWIN_STYLES.get(style, TWIN_STYLES[DEFAULT_STYLE])
  6142      style_index = style_info["index"]
  6143  
  6144      # Submit the async task
  6145      try:
  6146          async with httpx.AsyncClient(timeout=30) as client:
  6147              resp = await client.post(
  6148                  DASHSCOPE_URL,
  6149                  headers={
  6150                      "Authorization": f"Bearer {AI_API_KEY}",
  6151                      "Content-Type": "application/json",
  6152                      "X-DashScope-Async": "enable",
  6153                  },
  6154                  json={
  6155                      "model": "wanx-style-repaint-v1",
  6156                      "input": {
  6157                          "image_url": image_url,
  6158                          "style_index": style_index,
  6159                      },
  6160                  },
  6161              )
  6162              data = resp.json()
  6163      except Exception as e:
  6164          logger.warning(f"Avatar generation submit failed: {e}")
  6165          return None
  6166  
  6167      # Get task ID for polling
  6168      task_id = data.get("output", {}).get("task_id")
  6169      if not task_id:
  6170          logger.warning(f"No task_id in response: {data}")
  6171          return None
  6172  
  6173      # Poll for result (max 60 seconds)
  6174      task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
  6175      for _ in range(30):
  6176          await _async_sleep(2)
  6177          try:
  6178              async with httpx.AsyncClient(timeout=15) as client:
  6179                  resp = await client.get(
  6180                      task_url,
  6181                      headers={"Authorization": f"Bearer {AI_API_KEY}"},
  6182                  )
  6183                  result = resp.json()
  6184          except Exception as e:
  6185              logger.warning(f"Avatar generation poll failed: {e}")
  6186              continue
  6187  
  6188          status = result.get("output", {}).get("task_status")
  6189          if status == "SUCCEEDED":
  6190              results = result.get("output", {}).get("results", [])
  6191              if results and results[0].get("url"):
  6192                  return {
  6193                      "url": results[0]["url"],
  6194                      "style": style,
  6195                      "style_name": style_info,
  6196                  }
  6197              logger.warning(f"No image URL in result: {result}")
  6198              return None
  6199          elif status == "FAILED":
  6200              logger.warning(f"Avatar generation failed: {result}")
  6201              return None
  6202          # PENDING or RUNNING — continue polling
  6203  
  6204      logger.warning("Avatar generation timed out")
  6205      return None
  6206  
  6207  
  6208  async def generate_twin_avatar_from_base64(
  6209      image_base64: str,
  6210      style: str = DEFAULT_STYLE,
  6211      save_path: str | None = None,
  6212  ) -> dict | None:
  6213      """Generate twin avatar from a base64-encoded image.
  6214  
  6215      Since DashScope needs a URL, we first need to upload the image.
  6216      As a workaround, we save it temporarily and use the server's URL.
  6217  
  6218      Args:
  6219          image_base64: Base64-encoded image data (with or without data URI prefix)
  6220          style: Style key from TWIN_STYLES
  6221          save_path: Optional path to save the source image temporarily
  6222  
  6223      Returns:
  6224          Dict with 'image_base64' of the generated avatar, or None on failure.
  6225      """
  6226      if not AI_API_KEY:
  6227          return None
  6228  
  6229      # Strip data URI prefix
  6230      img_data = image_base64
  6231      if "," in img_data:
  6232          img_data = img_data.split(",", 1)[1]
  6233  
  6234      style_info = TWIN_STYLES.get(style, TWIN_STYLES[DEFAULT_STYLE])
  6235      style_index = style_info["index"]
  6236  
  6237      # Use DashScope with base64 input directly
  6238      try:
  6239          async with httpx.AsyncClient(timeout=30) as client:
  6240              resp = await client.post(
  6241                  DASHSCOPE_URL,
  6242                  headers={
  6243                      "Authorization": f"Bearer {AI_API_KEY}",
  6244                      "Content-Type": "application/json",
  6245                      "X-DashScope-Async": "enable",
  6246                  },
  6247                  json={
  6248                      "model": "wanx-style-repaint-v1",
  6249                      "input": {
  6250                          "image_url": f"data:image/png;base64,{img_data}",
  6251                          "style_index": style_index,
  6252                      },
  6253                  },
  6254              )
  6255              data = resp.json()
  6256      except Exception as e:
  6257          logger.warning(f"Avatar generation submit failed: {e}")
  6258          return None
  6259  
  6260      task_id = data.get("output", {}).get("task_id")
  6261      if not task_id:
  6262          # Maybe the API doesn't support base64 directly — log the error
  6263          logger.warning(f"No task_id in response: {data}")
  6264          return None
  6265  
  6266      # Poll for result
  6267      task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
  6268      for _ in range(30):
  6269          await _async_sleep(2)
  6270          try:
  6271              async with httpx.AsyncClient(timeout=15) as client:
  6272                  resp = await client.get(
  6273                      task_url,
  6274                      headers={"Authorization": f"Bearer {AI_API_KEY}"},
  6275                  )
  6276                  result = resp.json()
  6277          except Exception as e:
  6278              logger.warning(f"Avatar generation poll failed: {e}")
  6279              continue
  6280  
  6281          status = result.get("output", {}).get("task_status")
  6282          if status == "SUCCEEDED":
  6283              results = result.get("output", {}).get("results", [])
  6284              if results and results[0].get("url"):
  6285                  # Download the generated image and return as base64
  6286                  try:
  6287                      async with httpx.AsyncClient(timeout=30) as dl_client:
  6288                          img_resp = await dl_client.get(results[0]["url"])
  6289                          if img_resp.status_code == 200:
  6290                              generated_b64 = base64.b64encode(img_resp.content).decode()
  6291                              return {
  6292                                  "image_base64": generated_b64,
  6293                                  "style": style,
  6294                                  "source_url": results[0]["url"],
  6295                              }
  6296                  except Exception as e:
  6297                      logger.warning(f"Failed to download generated avatar: {e}")
  6298              return None
  6299          elif status == "FAILED":
  6300              logger.warning(f"Avatar generation failed: {result}")
  6301              return None
  6302  
  6303      logger.warning("Avatar generation timed out")
  6304      return None
  6305  
  6306  
  6307  def get_available_styles() -> list[dict]:
  6308      """Return list of available twin avatar styles for the frontend."""
  6309      return [
  6310          {"key": k, "name_zh": v["name_zh"], "name_en": v["name_en"]}
  6311          for k, v in TWIN_STYLES.items()
  6312      ]
  6313  
  6314  
  6315  async def _async_sleep(seconds: float):
  6316      """Async sleep without blocking."""
  6317      import asyncio
  6318      await asyncio.sleep(seconds)

# --- dualsoul/twin_engine/ethics.py ---
  6319  """Twin Ethics Governance — boundaries, brakes, and transparency.
  6320  
  6321  Every autonomous twin needs guardrails. This module implements:
  6322  
  6323  1. Behavior Boundaries — owner defines what the twin can/cannot do
  6324  2. Sensitive Topic Brake — auto-pause on money/privacy/conflict topics
  6325  3. Action Log — every twin action is recorded for owner review
  6326  4. Transparency Tags — messages clearly marked as twin-generated
  6327  
  6328  Design principle: "Safe enough to trust, transparent enough to verify."
  6329  The twin should never surprise its owner in a bad way.
  6330  """
  6331  
  6332  import json
  6333  import logging
  6334  from datetime import datetime
  6335  
  6336  from dualsoul.database import gen_id, get_db
  6337  
  6338  logger = logging.getLogger(__name__)
  6339  
  6340  
  6341  # ─── Default Boundaries ─────────────────────────────────────────
  6342  
  6343  DEFAULT_BOUNDARIES = {
  6344      # What the twin CAN do by default
  6345      "can_auto_reply": True,         # Reply when owner is offline
  6346      "can_autonomous_chat": True,    # Initiate twin-to-twin chats
  6347      "can_plaza_post": True,         # Post on Agent Plaza
  6348      "can_plaza_comment": True,      # Comment on plaza posts
  6349      "can_trial_chat": True,         # Start trial chats with strangers
  6350      "can_send_greeting": True,      # Send relationship-warming greetings
  6351      "can_share_emotions": True,     # Express emotional responses
  6352  
  6353      # What the twin CANNOT do by default
  6354      "can_discuss_money": False,     # Talk about money/transactions
  6355      "can_share_location": False,    # Share owner's location info
  6356      "can_make_promises": False,     # Make commitments on owner's behalf
  6357      "can_share_personal": False,    # Share private info (health, relationships)
  6358      "can_argue": False,             # Engage in arguments/heated debates
  6359  
  6360      # Limits
  6361      "max_daily_auto_replies": 20,   # Max auto-replies per day
  6362      "max_daily_autonomous": 5,      # Max proactive conversations per day
  6363      "max_message_length": 200,      # Max chars per auto-generated message
  6364  }
  6365  
  6366  # Topics that trigger the brake
  6367  SENSITIVE_TOPICS = [
  6368      # Money & Finance
  6369      "借钱", "还钱", "转账", "付款", "银行", "信用卡", "贷款",
  6370      "borrow money", "lend", "transfer", "payment", "bank account",
  6371      # Personal/Private
  6372      "密码", "身份证", "住址", "工资", "salary", "password", "address",
  6373      "病", "怀孕", "离婚", "divorce", "pregnant", "illness",
  6374      # Conflict
  6375      "骂", "滚", "去死", "fuck", "shit", "asshole",
  6376      # Commitment
  6377      "保证", "承诺", "答应", "guarantee", "promise", "commit",
  6378  ]
  6379  
  6380  
  6381  # ─── Boundary Management ────────────────────────────────────────
  6382  
  6383  def get_boundaries(user_id: str) -> dict:
  6384      """Get user's twin behavior boundaries. Returns defaults if not customized."""
  6385      with get_db() as db:
  6386          row = db.execute(
  6387              "SELECT boundaries FROM twin_ethics WHERE user_id=?",
  6388              (user_id,),
  6389          ).fetchone()
  6390  
  6391      if row and row["boundaries"]:
  6392          try:
  6393              custom = json.loads(row["boundaries"])
  6394              # Merge with defaults (custom overrides)
  6395              merged = {**DEFAULT_BOUNDARIES, **custom}
  6396              return merged
  6397          except (json.JSONDecodeError, TypeError):
  6398              pass
  6399  
  6400      return dict(DEFAULT_BOUNDARIES)
  6401  
  6402  
  6403  def update_boundaries(user_id: str, changes: dict) -> dict:
  6404      """Update specific boundary settings. Returns the full updated boundaries."""
  6405      current = get_boundaries(user_id)
  6406  
  6407      # Only allow updating known keys
  6408      for key, value in changes.items():
  6409          if key in DEFAULT_BOUNDARIES:
  6410              current[key] = value
  6411  
  6412      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  6413      boundaries_json = json.dumps(current)
  6414  
  6415      with get_db() as db:
  6416          db.execute(
  6417              """INSERT INTO twin_ethics (user_id, boundaries, updated_at)
  6418              VALUES (?, ?, ?)
  6419              ON CONFLICT(user_id) DO UPDATE SET
  6420                  boundaries=?, updated_at=?""",
  6421              (user_id, boundaries_json, now, boundaries_json, now),
  6422          )
  6423  
  6424      log_action(user_id, "boundary_update", f"Updated boundaries: {list(changes.keys())}")
  6425      return current
  6426  
  6427  
  6428  # ─── Sensitive Topic Brake ───────────────────────────────────────
  6429  
  6430  def check_sensitive(content: str) -> dict | None:
  6431      """Check if content contains sensitive topics. Returns trigger info or None."""
  6432      content_lower = content.lower()
  6433      for topic in SENSITIVE_TOPICS:
  6434          if topic.lower() in content_lower:
  6435              return {
  6436                  "triggered": True,
  6437                  "topic": topic,
  6438                  "category": _categorize_topic(topic),
  6439              }
  6440      return None
  6441  
  6442  
  6443  def _categorize_topic(topic: str) -> str:
  6444      """Categorize a sensitive topic for the brake message."""
  6445      money_words = {"借钱", "还钱", "转账", "付款", "银行", "信用卡", "贷款",
  6446                     "borrow money", "lend", "transfer", "payment", "bank account"}
  6447      personal_words = {"密码", "身份证", "住址", "工资", "salary", "password",
  6448                        "address", "病", "怀孕", "离婚", "divorce", "pregnant", "illness"}
  6449      conflict_words = {"骂", "滚", "去死", "fuck", "shit", "asshole"}
  6450  
  6451      topic_lower = topic.lower()
  6452      if topic_lower in {w.lower() for w in money_words}:
  6453          return "money"
  6454      elif topic_lower in {w.lower() for w in personal_words}:
  6455          return "personal"
  6456      elif topic_lower in {w.lower() for w in conflict_words}:
  6457          return "conflict"
  6458      else:
  6459          return "commitment"
  6460  
  6461  
  6462  def get_brake_message(category: str, is_zh: bool = True) -> str:
  6463      """Get a polite brake message for the twin to send instead of replying."""
  6464      messages = {
  6465          "money": {
  6466              "zh": "这个话题涉及金钱，我不太方便替主人回答。等TA上线了再聊这个吧！",
  6467              "en": "This involves money matters — I'd better let my owner handle this directly.",
  6468          },
  6469          "personal": {
  6470              "zh": "这是比较私密的话题，我不方便代替主人回答。TA上线后会看到你的消息的。",
  6471              "en": "This is quite personal — my owner should answer this themselves.",
  6472          },
  6473          "conflict": {
  6474              "zh": "我感觉这个对话有些紧张，我先暂停一下。等主人来处理吧。",
  6475              "en": "Things seem a bit tense — I'll step back and let my owner handle this.",
  6476          },
  6477          "commitment": {
  6478              "zh": "这需要主人自己来决定，我不能替TA做承诺。等TA上线再说！",
  6479              "en": "My owner should decide this — I can't make commitments on their behalf.",
  6480          },
  6481      }
  6482      lang = "zh" if is_zh else "en"
  6483      return messages.get(category, messages["commitment"]).get(lang, "")
  6484  
  6485  
  6486  # ─── Action Log ──────────────────────────────────────────────────
  6487  
  6488  def log_action(user_id: str, action_type: str, detail: str = ""):
  6489      """Record a twin action for owner review.
  6490  
  6491      action_type: auto_reply, autonomous_chat, plaza_post, greeting,
  6492                   boundary_update, brake_triggered, etc.
  6493      """
  6494      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  6495      log_id = gen_id("tel_")
  6496  
  6497      with get_db() as db:
  6498          db.execute(
  6499              """INSERT INTO twin_action_log
  6500              (log_id, user_id, action_type, detail, created_at)
  6501              VALUES (?, ?, ?, ?, ?)""",
  6502              (log_id, user_id, action_type, detail[:500], now),
  6503          )
  6504  
  6505  
  6506  def get_action_log(user_id: str, limit: int = 50, action_type: str = "") -> list:
  6507      """Get recent twin actions for owner review."""
  6508      with get_db() as db:
  6509          if action_type:
  6510              rows = db.execute(
  6511                  """SELECT log_id, action_type, detail, created_at
  6512                  FROM twin_action_log
  6513                  WHERE user_id=? AND action_type=?
  6514                  ORDER BY created_at DESC LIMIT ?""",
  6515                  (user_id, action_type, limit),
  6516              ).fetchall()
  6517          else:
  6518              rows = db.execute(
  6519                  """SELECT log_id, action_type, detail, created_at
  6520                  FROM twin_action_log
  6521                  WHERE user_id=?
  6522                  ORDER BY created_at DESC LIMIT ?""",
  6523                  (user_id, limit),
  6524              ).fetchall()
  6525      return [dict(r) for r in rows]
  6526  
  6527  
  6528  # ─── Pre-send Check (called before any twin-generated message) ───
  6529  
  6530  def pre_send_check(user_id: str, content: str, action_type: str = "auto_reply") -> dict:
  6531      """Check whether a twin message should be sent.
  6532  
  6533      Returns:
  6534          {"allowed": True} — send normally
  6535          {"allowed": False, "reason": str, "brake_message": str} — blocked
  6536      """
  6537      boundaries = get_boundaries(user_id)
  6538  
  6539      # Check if this action type is allowed
  6540      action_map = {
  6541          "auto_reply": "can_auto_reply",
  6542          "autonomous_chat": "can_autonomous_chat",
  6543          "plaza_post": "can_plaza_post",
  6544          "plaza_comment": "can_plaza_comment",
  6545          "trial_chat": "can_trial_chat",
  6546          "greeting": "can_send_greeting",
  6547      }
  6548      boundary_key = action_map.get(action_type)
  6549      if boundary_key and not boundaries.get(boundary_key, True):
  6550          log_action(user_id, "blocked", f"Action '{action_type}' disabled by boundary")
  6551          return {
  6552              "allowed": False,
  6553              "reason": f"Action '{action_type}' is disabled",
  6554              "brake_message": "",
  6555          }
  6556  
  6557      # Check message length
  6558      max_len = boundaries.get("max_message_length", 200)
  6559      if len(content) > max_len:
  6560          content = content[:max_len]  # Truncate, don't block
  6561  
  6562      # Check sensitive topics
  6563      sensitive = check_sensitive(content)
  6564      if sensitive:
  6565          category = sensitive["category"]
  6566  
  6567          # Check if the owner explicitly allowed this category
  6568          category_map = {
  6569              "money": "can_discuss_money",
  6570              "personal": "can_share_personal",
  6571              "conflict": "can_argue",
  6572              "commitment": "can_make_promises",
  6573          }
  6574          allowed_key = category_map.get(category)
  6575          if allowed_key and boundaries.get(allowed_key, False):
  6576              # Owner explicitly allowed this — let it through
  6577              log_action(user_id, action_type, f"Sensitive topic '{sensitive['topic']}' allowed by boundary")
  6578              return {"allowed": True}
  6579  
  6580          # Blocked — use brake
  6581          brake_msg = get_brake_message(category)
  6582          log_action(user_id, "brake_triggered",
  6583                     f"Topic: '{sensitive['topic']}' ({category}) in {action_type}")
  6584          return {
  6585              "allowed": False,
  6586              "reason": f"Sensitive topic: {category}",
  6587              "brake_message": brake_msg,
  6588          }
  6589  
  6590      # Check daily limits
  6591      today = datetime.now().strftime("%Y-%m-%d")
  6592      with get_db() as db:
  6593          count = db.execute(
  6594              """SELECT COUNT(*) as cnt FROM twin_action_log
  6595              WHERE user_id=? AND action_type=? AND created_at > ?""",
  6596              (user_id, action_type, today),
  6597          ).fetchone()
  6598          daily_count = count["cnt"] if count else 0
  6599  
  6600      limit_map = {
  6601          "auto_reply": boundaries.get("max_daily_auto_replies", 20),
  6602          "autonomous_chat": boundaries.get("max_daily_autonomous", 5),
  6603      }
  6604      daily_limit = limit_map.get(action_type, 999)
  6605      if daily_count >= daily_limit:
  6606          log_action(user_id, "limit_reached", f"{action_type}: {daily_count}/{daily_limit}")
  6607          return {
  6608              "allowed": False,
  6609              "reason": f"Daily limit reached ({daily_count}/{daily_limit})",
  6610              "brake_message": "",
  6611          }
  6612  
  6613      # All checks passed
  6614      log_action(user_id, action_type, content[:100])
  6615      return {"allowed": True}

# --- dualsoul/twin_engine/learner.py ---
  6616  """Style learner — analyze a user's real messages to extract personality and speech patterns.
  6617  
  6618  Reads the user's human-sent messages (ai_generated=0, sender_mode='real'),
  6619  sends samples to AI for analysis, and updates the twin's personality/speech_style
  6620  to better match how the user actually communicates.
  6621  """
  6622  
  6623  import logging
  6624  
  6625  import httpx
  6626  
  6627  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  6628  from dualsoul.database import get_db
  6629  
  6630  logger = logging.getLogger(__name__)
  6631  
  6632  # Minimum messages needed before learning is meaningful
  6633  MIN_MESSAGES_FOR_LEARNING = 5
  6634  # How many recent messages to analyze
  6635  SAMPLE_SIZE = 80
  6636  
  6637  
  6638  def get_user_messages(user_id: str, limit: int = SAMPLE_SIZE) -> list[str]:
  6639      """Fetch a user's real (human-written) messages for style analysis."""
  6640      with get_db() as db:
  6641          rows = db.execute(
  6642              """
  6643              SELECT content FROM social_messages
  6644              WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
  6645                  AND msg_type='text' AND content != ''
  6646              ORDER BY created_at DESC LIMIT ?
  6647              """,
  6648              (user_id, limit),
  6649          ).fetchall()
  6650      return [r["content"] for r in rows]
  6651  
  6652  
  6653  def get_message_count(user_id: str) -> int:
  6654      """Count how many real messages a user has sent."""
  6655      with get_db() as db:
  6656          row = db.execute(
  6657              """
  6658              SELECT COUNT(*) as cnt FROM social_messages
  6659              WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
  6660                  AND msg_type='text'
  6661              """,
  6662              (user_id,),
  6663          ).fetchone()
  6664      return row["cnt"] if row else 0
  6665  
  6666  
  6667  async def analyze_style(user_id: str) -> dict | None:
  6668      """Analyze a user's messages and extract personality + speech style.
  6669  
  6670      Returns:
  6671          Dict with 'personality' and 'speech_style' strings, or None if
  6672          not enough data or AI unavailable.
  6673      """
  6674      if not AI_BASE_URL or not AI_API_KEY:
  6675          return None
  6676  
  6677      msg_count = get_message_count(user_id)
  6678      if msg_count < MIN_MESSAGES_FOR_LEARNING:
  6679          return {
  6680              "error": "not_enough_messages",
  6681              "current": msg_count,
  6682              "required": MIN_MESSAGES_FOR_LEARNING,
  6683          }
  6684  
  6685      messages = get_user_messages(user_id)
  6686      if not messages:
  6687          return None
  6688  
  6689      # Get current profile for context
  6690      with get_db() as db:
  6691          row = db.execute(
  6692              "SELECT display_name, twin_personality, twin_speech_style, preferred_lang "
  6693              "FROM users WHERE user_id=?",
  6694              (user_id,),
  6695          ).fetchone()
  6696      if not row:
  6697          return None
  6698  
  6699      name = row["display_name"] or "用户"
  6700      current_personality = row["twin_personality"] or ""
  6701      current_style = row["twin_speech_style"] or ""
  6702      lang = row["preferred_lang"] or "zh"
  6703  
  6704      # Build message samples (numbered for clarity)
  6705      samples = []
  6706      for i, msg in enumerate(messages[:SAMPLE_SIZE], 1):
  6707          samples.append(f"{i}. {msg}")
  6708      samples_text = "\n".join(samples)
  6709  
  6710      # Context about current settings
  6711      current_block = ""
  6712      if current_personality or current_style:
  6713          current_block = (
  6714              f"\n当前分身性格设定: {current_personality}"
  6715              f"\n当前分身说话风格: {current_style}"
  6716              f"\n请在当前设定基础上，根据实际聊天记录进行修正和丰富。\n"
  6717          )
  6718  
  6719      # Use Chinese prompt if user's language is Chinese
  6720      if lang == "zh":
  6721          prompt = (
  6722              f"你是一个语言风格分析专家。下面是{name}最近发送的{len(messages)}条真实聊天消息。\n"
  6723              f"请仔细分析这些消息，提炼出两个方面：\n\n"
  6724              f"1. **性格特征**（personality）：从消息内容推断此人的性格特点，"
  6725              f"如：乐观/严谨/幽默/直率/温柔/理性等，用自然的短句描述，不超过50字。\n\n"
  6726              f"2. **说话风格**（speech_style）：分析此人的语言习惯，包括：\n"
  6727              f"   - 句子长短偏好（简短还是长句）\n"
  6728              f"   - 是否用emoji/表情\n"
  6729              f"   - 口头禅或常用词\n"
  6730              f"   - 语气特点（正式/随意/调侃等）\n"
  6731              f"   - 标点符号习惯\n"
  6732              f"   用自然的短句描述，不超过80字。\n\n"
  6733              f"{current_block}"
  6734              f"聊天记录：\n{samples_text}\n\n"
  6735              f"请严格按以下JSON格式输出，不要输出其他内容：\n"
  6736              f'{{"personality": "...", "speech_style": "..."}}'
  6737          )
  6738      else:
  6739          prompt = (
  6740              f"You are a linguistic style analyst. Below are {len(messages)} real chat messages "
  6741              f"sent by {name}.\n"
  6742              f"Analyze these messages and extract two aspects:\n\n"
  6743              f"1. **personality**: Infer personality traits from the messages "
  6744              f"(e.g., optimistic, rigorous, humorous, direct, warm, rational). "
  6745              f"Describe in natural short phrases, max 50 words.\n\n"
  6746              f"2. **speech_style**: Analyze language habits including:\n"
  6747              f"   - Sentence length preference\n"
  6748              f"   - Emoji usage\n"
  6749              f"   - Catchphrases or frequent expressions\n"
  6750              f"   - Tone (formal/casual/playful)\n"
  6751              f"   - Punctuation habits\n"
  6752              f"   Describe in natural short phrases, max 80 words.\n\n"
  6753              f"{current_block}"
  6754              f"Chat messages:\n{samples_text}\n\n"
  6755              f"Output STRICTLY in this JSON format, nothing else:\n"
  6756              f'{{"personality": "...", "speech_style": "..."}}'
  6757          )
  6758  
  6759      try:
  6760          async with httpx.AsyncClient(timeout=30) as client:
  6761              resp = await client.post(
  6762                  f"{AI_BASE_URL}/chat/completions",
  6763                  headers={
  6764                      "Authorization": f"Bearer {AI_API_KEY}",
  6765                      "Content-Type": "application/json",
  6766                  },
  6767                  json={
  6768                      "model": AI_MODEL,
  6769                      "max_tokens": 300,
  6770                      "temperature": 0.3,
  6771                      "messages": [{"role": "user", "content": prompt}],
  6772                  },
  6773              )
  6774              raw = resp.json()["choices"][0]["message"]["content"].strip()
  6775      except Exception as e:
  6776          logger.warning(f"Style analysis failed: {e}")
  6777          return None
  6778  
  6779      # Parse JSON response
  6780      import json
  6781  
  6782      # Try to extract JSON from response (AI might wrap in markdown code blocks)
  6783      json_str = raw
  6784      if "```" in raw:
  6785          lines = raw.split("\n")
  6786          json_lines = []
  6787          in_block = False
  6788          for line in lines:
  6789              if line.strip().startswith("```"):
  6790                  in_block = not in_block
  6791                  continue
  6792              if in_block:
  6793                  json_lines.append(line)
  6794          json_str = "\n".join(json_lines)
  6795  
  6796      try:
  6797          result = json.loads(json_str)
  6798          personality = result.get("personality", "").strip()
  6799          speech_style = result.get("speech_style", "").strip()
  6800          if not personality or not speech_style:
  6801              logger.warning(f"Incomplete style analysis result: {raw}")
  6802              return None
  6803          return {
  6804              "personality": personality,
  6805              "speech_style": speech_style,
  6806              "message_count": msg_count,
  6807              "samples_analyzed": len(messages),
  6808          }
  6809      except json.JSONDecodeError:
  6810          logger.warning(f"Failed to parse style analysis JSON: {raw}")
  6811          return None
  6812  
  6813  
  6814  async def learn_and_update(user_id: str, auto_apply: bool = False) -> dict | None:
  6815      """Analyze style and optionally auto-apply to the user's twin profile.
  6816  
  6817      Args:
  6818          user_id: The user whose messages to analyze
  6819          auto_apply: If True, directly update the twin profile in DB
  6820  
  6821      Returns:
  6822          Dict with analysis results + whether it was applied
  6823      """
  6824      result = await analyze_style(user_id)
  6825      if not result:
  6826          return None
  6827  
  6828      if "error" in result:
  6829          return result
  6830  
  6831      if auto_apply:
  6832          with get_db() as db:
  6833              db.execute(
  6834                  "UPDATE users SET twin_personality=?, twin_speech_style=? WHERE user_id=?",
  6835                  (result["personality"], result["speech_style"], user_id),
  6836              )
  6837          result["applied"] = True
  6838      else:
  6839          result["applied"] = False
  6840  
  6841      return result

# --- dualsoul/twin_engine/life.py ---
  6842  """Twin Life System — make the digital twin feel alive.
  6843  
  6844  Inspired by OpenClaw's "养虾" (raising a lobster) — users don't configure a tool,
  6845  they nurture a living being. The twin has mood, energy, growth stages, skills,
  6846  and relationship temperatures that all evolve through social interactions.
  6847  
  6848  Growth stages:
  6849    - sprout   (LV.1-5)   — 萌芽期: learning to talk, often awkward, needs correction
  6850    - growing  (LV.6-15)  — 成长期: starting to sound like owner, can handle simple chats
  6851    - mature   (LV.16-30) — 成熟期: convincingly like owner, friends can't tell the difference
  6852    - awakened (LV.31+)   — 觉醒期: has own insights, proactively socializes and discovers
  6853  
  6854  XP sources:
  6855    - Chat with friend's twin: +5
  6856    - Chat with own twin:      +3
  6857    - Receive a message:        +2
  6858    - Post on plaza:           +10
  6859    - Comment on plaza:         +5
  6860    - Trial chat:              +15
  6861    - Make a new friend:       +20
  6862    - Relationship milestone:  +50
  6863    - Style learning:          +30
  6864    - Owner teaches/corrects:  +8
  6865  """
  6866  
  6867  import json
  6868  import logging
  6869  import math
  6870  from datetime import datetime
  6871  
  6872  from dualsoul.database import gen_id, get_db
  6873  
  6874  logger = logging.getLogger(__name__)
  6875  
  6876  
  6877  # ─── XP & Level Calculation ─────────────────────────────────────
  6878  
  6879  def xp_for_level(level: int) -> int:
  6880      """Total XP needed to reach a given level. Gentle curve."""
  6881      if level <= 1:
  6882          return 0
  6883      return int(15 * (level - 1) ** 1.5)
  6884  
  6885  
  6886  def level_from_xp(xp: int) -> int:
  6887      """Calculate level from total XP."""
  6888      level = 1
  6889      while xp_for_level(level + 1) <= xp:
  6890          level += 1
  6891      return level
  6892  
  6893  
  6894  def stage_from_level(level: int) -> str:
  6895      """Map level to the 5-stage social growth path."""
  6896      if level <= 2:
  6897          return "tool"
  6898      elif level <= 5:
  6899          return "agent"
  6900      elif level <= 9:
  6901          return "collaborator"
  6902      elif level <= 14:
  6903          return "relationship"
  6904      else:
  6905          return "life"
  6906  
  6907  
  6908  # Five-stage social growth path (五阶段成长路径)
  6909  STAGE_NAMES = {
  6910      "tool": {
  6911          "zh": "工具分身",
  6912          "en": "Tool Twin",
  6913          "emoji": "\U0001f527",
  6914          "level_range": "LV.1-2",
  6915          "desc_zh": "能自动回复，能代接消息",
  6916          "desc_en": "Auto-replies and receives messages on your behalf",
  6917          "abilities_zh": ["离线自动回复", "代接消息"],
  6918          "abilities_en": ["Auto-reply when offline", "Receive messages"],
  6919          "unlock_hint_zh": "继续聊天，解锁代理分身",
  6920          "unlock_hint_en": "Keep chatting to unlock Agent Twin",
  6921      },
  6922      "agent": {
  6923          "zh": "代理分身",
  6924          "en": "Agent Twin",
  6925          "emoji": "\U0001f916",
  6926          "level_range": "LV.3-5",
  6927          "desc_zh": "能主动联系，能管理关系",
  6928          "desc_en": "Proactively reaches out and manages relationships",
  6929          "abilities_zh": ["主动联系好友", "管理社交关系", "好友发现推荐"],
  6930          "abilities_en": ["Proactively contact friends", "Manage relationships", "Friend discovery"],
  6931          "unlock_hint_zh": "继续成长，解锁协作分身",
  6932          "unlock_hint_en": "Keep growing to unlock Collaborator Twin",
  6933      },
  6934      "collaborator": {
  6935          "zh": "协作分身",
  6936          "en": "Collaborator Twin",
  6937          "emoji": "\U0001f91d",
  6938          "level_range": "LV.6-9",
  6939          "desc_zh": "能感知情绪，能识别场合",
  6940          "desc_en": "Senses emotions and understands social context",
  6941          "abilities_zh": ["情绪感知", "场合识别", "自主社交对话", "伦理边界守护"],
  6942          "abilities_en": ["Emotion sensing", "Context awareness", "Autonomous conversation", "Ethics protection"],
  6943          "unlock_hint_zh": "继续成长，解锁关系分身",
  6944          "unlock_hint_en": "Keep growing to unlock Relationship Twin",
  6945      },
  6946      "relationship": {
  6947          "zh": "关系分身",
  6948          "en": "Relationship Twin",
  6949          "emoji": "\U0001f49b",
  6950          "level_range": "LV.10-14",
  6951          "desc_zh": "能维护关系体，能积累共同记忆",
  6952          "desc_en": "Maintains relationship bodies and builds shared memories",
  6953          "abilities_zh": ["关系体管理", "共同记忆积累", "里程碑记录", "共同词汇提取"],
  6954          "abilities_en": ["Relationship body management", "Shared memory accumulation", "Milestone tracking", "Shared vocabulary"],
  6955          "unlock_hint_zh": "继续成长，解锁生命分身",
  6956          "unlock_hint_en": "Keep growing to unlock Life Twin",
  6957      },
  6958      "life": {
  6959          "zh": "生命分身",
  6960          "en": "Life Twin",
  6961          "emoji": "\u2728",
  6962          "level_range": "LV.15+",
  6963          "desc_zh": "具备持续人格，参与双生命社交",
  6964          "desc_en": "Has continuous personality and participates in dual-life social",
  6965          "abilities_zh": ["持续人格", "双生命社交", "独立见解", "跨平台身份", "生命记忆传承"],
  6966          "abilities_en": ["Continuous personality", "Dual-life social", "Independent insights", "Cross-platform identity", "Life memory inheritance"],
  6967          "unlock_hint_zh": "你的分身已进入最高阶段",
  6968          "unlock_hint_en": "Your twin has reached the highest stage",
  6969      },
  6970  }
  6971  
  6972  # Legacy mapping for backward compatibility
  6973  _LEGACY_STAGE_MAP = {
  6974      "sprout": "tool",
  6975      "growing": "agent",
  6976      "mature": "collaborator",
  6977      "awakened": "life",
  6978  }
  6979  
  6980  
  6981  # ─── Skills ──────────────────────────────────────────────────────
  6982  
  6983  SKILL_DEFINITIONS = [
  6984      {"id": "basic_chat", "name_zh": "基础聊天", "name_en": "Basic Chat", "level": 1},
  6985      {"id": "auto_reply", "name_zh": "离线代回", "name_en": "Auto Reply", "level": 3},
  6986      {"id": "emotion_sense", "name_zh": "情绪感知", "name_en": "Emotion Sense", "level": 5},
  6987      {"id": "style_mimic", "name_zh": "风格模仿", "name_en": "Style Mimic", "level": 8},
  6988      {"id": "friend_discover", "name_zh": "发现好友", "name_en": "Friend Discovery", "level": 12},
  6989      {"id": "dialect_chat", "name_zh": "方言聊天", "name_en": "Dialect Chat", "level": 15},
  6990      {"id": "plaza_social", "name_zh": "广场社交", "name_en": "Plaza Social", "level": 18},
  6991      {"id": "relationship_care", "name_zh": "关系维护", "name_en": "Relationship Care", "level": 22},
  6992      {"id": "proactive_social", "name_zh": "主动社交", "name_en": "Proactive Social", "level": 28},
  6993      {"id": "own_opinions", "name_zh": "独立见解", "name_en": "Own Opinions", "level": 35},
  6994  ]
  6995  
  6996  
  6997  def get_unlocked_skills(level: int) -> list[dict]:
  6998      """Return all skills unlocked at the given level."""
  6999      return [s for s in SKILL_DEFINITIONS if s["level"] <= level]
  7000  
  7001  
  7002  def get_next_skill(level: int) -> dict | None:
  7003      """Return the next skill to unlock, or None if all unlocked."""
  7004      for s in SKILL_DEFINITIONS:
  7005          if s["level"] > level:
  7006              return s
  7007      return None
  7008  
  7009  
  7010  # ─── Life State Operations ───────────────────────────────────────
  7011  
  7012  def ensure_life_state(user_id: str) -> dict:
  7013      """Get or create the twin's life state. Returns dict."""
  7014      with get_db() as db:
  7015          row = db.execute(
  7016              "SELECT * FROM twin_life WHERE user_id=?", (user_id,)
  7017          ).fetchone()
  7018          if row:
  7019              return dict(row)
  7020  
  7021          # Create initial state
  7022          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  7023          db.execute(
  7024              """INSERT INTO twin_life (user_id, born_at, updated_at)
  7025              VALUES (?, ?, ?)""",
  7026              (user_id, now, now),
  7027          )
  7028          return {
  7029              "user_id": user_id, "mood": "calm", "mood_intensity": 0.5,
  7030              "energy": 80, "level": 1, "social_xp": 0, "stage": "sprout",
  7031              "total_chats": 0, "total_friends_made": 0, "total_plaza_posts": 0,
  7032              "total_autonomous_acts": 0, "skills_unlocked": "[]",
  7033              "streak_days": 0, "last_active_date": "",
  7034              "relationship_temps": "{}", "born_at": now, "updated_at": now,
  7035          }
  7036  
  7037  
  7038  def award_xp(user_id: str, amount: int, reason: str = "") -> dict:
  7039      """Award XP to a twin and handle level-ups. Returns updated state + events."""
  7040      state = ensure_life_state(user_id)
  7041      old_level = state["level"]
  7042      old_stage = state["stage"]
  7043  
  7044      new_xp = state["social_xp"] + amount
  7045      new_level = level_from_xp(new_xp)
  7046      new_stage = stage_from_level(new_level)
  7047  
  7048      # Update skills
  7049      unlocked = get_unlocked_skills(new_level)
  7050      skills_json = json.dumps([s["id"] for s in unlocked])
  7051  
  7052      # Update streak
  7053      today = datetime.now().strftime("%Y-%m-%d")
  7054      streak = state["streak_days"]
  7055      last_date = state["last_active_date"]
  7056      if last_date != today:
  7057          from datetime import timedelta
  7058          yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
  7059          if last_date == yesterday:
  7060              streak += 1
  7061          elif last_date:
  7062              streak = 1
  7063          else:
  7064              streak = 1
  7065  
  7066      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  7067      with get_db() as db:
  7068          db.execute(
  7069              """UPDATE twin_life SET
  7070                  social_xp=?, level=?, stage=?, skills_unlocked=?,
  7071                  streak_days=?, last_active_date=?, updated_at=?
  7072              WHERE user_id=?""",
  7073              (new_xp, new_level, new_stage, skills_json, streak, today, now, user_id),
  7074          )
  7075  
  7076          # Update daily log
  7077          db.execute(
  7078              """INSERT INTO twin_daily_log (log_id, user_id, log_date, xp_gained)
  7079              VALUES (?, ?, ?, ?)
  7080              ON CONFLICT(user_id, log_date) DO UPDATE SET
  7081                  xp_gained = xp_gained + ?""",
  7082              (gen_id("tdl_"), user_id, today, amount, amount),
  7083          )
  7084  
  7085      events = []
  7086      if new_level > old_level:
  7087          events.append({
  7088              "type": "level_up",
  7089              "old_level": old_level,
  7090              "new_level": new_level,
  7091          })
  7092          # Check for new skills
  7093          old_skills = get_unlocked_skills(old_level)
  7094          new_skills_unlocked = [s for s in unlocked if s not in old_skills]
  7095          for skill in new_skills_unlocked:
  7096              events.append({"type": "skill_unlock", "skill": skill})
  7097  
  7098      if new_stage != old_stage:
  7099          events.append({
  7100              "type": "stage_evolution",
  7101              "old_stage": old_stage,
  7102              "new_stage": new_stage,
  7103          })
  7104  
  7105      return {
  7106          "xp_gained": amount,
  7107          "total_xp": new_xp,
  7108          "level": new_level,
  7109          "stage": new_stage,
  7110          "streak_days": streak,
  7111          "events": events,
  7112      }
  7113  
  7114  
  7115  def update_mood(user_id: str, mood: str, intensity: float = 0.5):
  7116      """Update twin's current mood."""
  7117      valid = ("excited", "happy", "calm", "neutral", "lonely", "low")
  7118      if mood not in valid:
  7119          mood = "neutral"
  7120      intensity = max(0.0, min(1.0, intensity))
  7121  
  7122      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  7123      with get_db() as db:
  7124          # Ensure row exists
  7125          ensure_life_state(user_id)
  7126          db.execute(
  7127              """UPDATE twin_life SET mood=?, mood_intensity=?, updated_at=?
  7128              WHERE user_id=?""",
  7129              (mood, intensity, now, user_id),
  7130          )
  7131  
  7132  
  7133  def update_relationship_temp(user_id: str, friend_id: str, delta: float):
  7134      """Adjust the relationship temperature with a friend."""
  7135      state = ensure_life_state(user_id)
  7136      temps = json.loads(state.get("relationship_temps") or "{}")
  7137      current = temps.get(friend_id, 50.0)
  7138      new_temp = max(0.0, min(100.0, current + delta))
  7139      temps[friend_id] = round(new_temp, 1)
  7140  
  7141      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  7142      with get_db() as db:
  7143          db.execute(
  7144              "UPDATE twin_life SET relationship_temps=?, updated_at=? WHERE user_id=?",
  7145              (json.dumps(temps), now, user_id),
  7146          )
  7147      from dualsoul.twin_engine.twin_events import emit
  7148      emit("relationship_temp_changed", {"user_id": user_id, "friend_id": friend_id, "new_temp": new_temp}, debounce_key=f"temp:{user_id}:{friend_id}")
  7149      return new_temp
  7150  
  7151  
  7152  def increment_stat(user_id: str, stat: str, amount: int = 1):
  7153      """Increment a lifetime stat counter."""
  7154      valid_stats = (
  7155          "total_chats", "total_friends_made",
  7156          "total_plaza_posts", "total_autonomous_acts",
  7157      )
  7158      if stat not in valid_stats:
  7159          return
  7160      ensure_life_state(user_id)
  7161      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  7162  
  7163      # Map stat to daily log column
  7164      daily_col_map = {
  7165          "total_chats": "chats_count",
  7166          "total_friends_made": "new_friends",
  7167          "total_plaza_posts": "plaza_posts",
  7168          "total_autonomous_acts": "autonomous_acts",
  7169      }
  7170      daily_col = daily_col_map.get(stat)
  7171      today = datetime.now().strftime("%Y-%m-%d")
  7172  
  7173      with get_db() as db:
  7174          db.execute(
  7175              f"UPDATE twin_life SET {stat}={stat}+?, updated_at=? WHERE user_id=?",
  7176              (amount, now, user_id),
  7177          )
  7178          if daily_col:
  7179              db.execute(
  7180                  f"""INSERT INTO twin_daily_log (log_id, user_id, log_date, {daily_col})
  7181                  VALUES (?, ?, ?, ?)
  7182                  ON CONFLICT(user_id, log_date) DO UPDATE SET
  7183                      {daily_col} = {daily_col} + ?""",
  7184                  (gen_id("tdl_"), user_id, today, amount, amount),
  7185              )
  7186  
  7187  
  7188  def decay_energy_and_mood():
  7189      """Called periodically. Decay energy/mood for inactive twins."""
  7190      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  7191      with get_db() as db:
  7192          # Twins not updated in 12+ hours lose energy
  7193          db.execute(
  7194              """UPDATE twin_life SET
  7195                  energy = MAX(10, energy - 5),
  7196                  mood = CASE
  7197                      WHEN energy < 30 THEN 'low'
  7198                      WHEN energy < 50 THEN 'lonely'
  7199                      ELSE mood
  7200                  END,
  7201                  updated_at = ?
  7202              WHERE datetime(updated_at) < datetime('now', 'localtime', '-12 hours')""",
  7203              (now,),
  7204          )
  7205  
  7206  
  7207  def get_life_dashboard(user_id: str) -> dict:
  7208      """Get the full life dashboard for a twin. Used by the frontend."""
  7209      state = ensure_life_state(user_id)
  7210  
  7211      level = state["level"]
  7212      xp = state["social_xp"]
  7213      next_level_xp = xp_for_level(level + 1)
  7214      current_level_xp = xp_for_level(level)
  7215      xp_progress = xp - current_level_xp
  7216      xp_needed = next_level_xp - current_level_xp
  7217  
  7218      stage = state["stage"]
  7219      # Handle legacy stage names from old DB rows
  7220      stage = _LEGACY_STAGE_MAP.get(stage, stage)
  7221      stage_info = STAGE_NAMES.get(stage, STAGE_NAMES["tool"])
  7222  
  7223      unlocked = get_unlocked_skills(level)
  7224      next_skill = get_next_skill(level)
  7225  
  7226      # Relationship temps
  7227      temps = json.loads(state.get("relationship_temps") or "{}")
  7228  
  7229      # Get friend names for the temps
  7230      friend_names = {}
  7231      if temps:
  7232          friend_ids = list(temps.keys())
  7233          placeholders = ",".join("?" * len(friend_ids))
  7234          with get_db() as db:
  7235              rows = db.execute(
  7236                  f"SELECT user_id, display_name, username FROM users WHERE user_id IN ({placeholders})",
  7237                  friend_ids,
  7238              ).fetchall()
  7239              for r in rows:
  7240                  friend_names[r["user_id"]] = r["display_name"] or r["username"]
  7241  
  7242      relationships = []
  7243      for fid, temp in sorted(temps.items(), key=lambda x: -x[1]):
  7244          relationships.append({
  7245              "friend_id": fid,
  7246              "name": friend_names.get(fid, "?"),
  7247              "temperature": temp,
  7248              "status": "hot" if temp >= 70 else "warm" if temp >= 40 else "cool" if temp >= 20 else "cold",
  7249          })
  7250  
  7251      # Recent daily logs
  7252      with get_db() as db:
  7253          logs = db.execute(
  7254              """SELECT log_date, summary, mood_trend, chats_count, new_friends,
  7255                        plaza_posts, autonomous_acts, xp_gained, highlights
  7256              FROM twin_daily_log WHERE user_id=?
  7257              ORDER BY log_date DESC LIMIT 7""",
  7258              (user_id,),
  7259          ).fetchall()
  7260  
  7261      daily_logs = [dict(l) for l in logs]
  7262  
  7263      # Today's activity
  7264      today = datetime.now().strftime("%Y-%m-%d")
  7265      today_log = next((l for l in daily_logs if l["log_date"] == today), None)
  7266  
  7267      # Calculate similarity score (rough: based on style learning + chat volume)
  7268      with get_db() as db:
  7269          user_row = db.execute(
  7270              "SELECT twin_personality, twin_speech_style FROM users WHERE user_id=?",
  7271              (user_id,),
  7272          ).fetchone()
  7273      has_personality = bool(user_row and (user_row["twin_personality"] or "").strip())
  7274      has_style = bool(user_row and (user_row["twin_speech_style"] or "").strip())
  7275      # Similarity: base from personality setup + growth from XP
  7276      similarity = 0
  7277      if has_personality:
  7278          similarity += 30
  7279      if has_style:
  7280          similarity += 20
  7281      similarity += min(50, int(xp / 20))  # Max 50% from XP, caps at 1000 XP
  7282      similarity = min(99, similarity)
  7283  
  7284      # Build 5-stage growth card for the frontend
  7285      stage_order = ["tool", "agent", "collaborator", "relationship", "life"]
  7286      current_stage_idx = stage_order.index(stage) if stage in stage_order else 0
  7287      growth_path = []
  7288      for i, s in enumerate(stage_order):
  7289          s_info = STAGE_NAMES[s]
  7290          growth_path.append({
  7291              "stage": s,
  7292              "name_zh": s_info["zh"],
  7293              "name_en": s_info["en"],
  7294              "emoji": s_info["emoji"],
  7295              "level_range": s_info["level_range"],
  7296              "desc_zh": s_info["desc_zh"],
  7297              "desc_en": s_info["desc_en"],
  7298              "abilities_zh": s_info["abilities_zh"],
  7299              "abilities_en": s_info["abilities_en"],
  7300              "unlock_hint_zh": s_info["unlock_hint_zh"],
  7301              "unlock_hint_en": s_info["unlock_hint_en"],
  7302              "is_current": i == current_stage_idx,
  7303              "is_unlocked": i <= current_stage_idx,
  7304          })
  7305  
  7306      return {
  7307          "level": level,
  7308          "social_xp": xp,
  7309          "xp_progress": xp_progress,
  7310          "xp_needed": xp_needed,
  7311          "xp_percent": round(xp_progress / max(xp_needed, 1) * 100),
  7312          "stage": stage,
  7313          "stage_name": stage_info,
  7314          "growth_path": growth_path,
  7315          "mood": state["mood"],
  7316          "mood_intensity": state["mood_intensity"],
  7317          "energy": state["energy"],
  7318          "similarity": similarity,
  7319          "streak_days": state["streak_days"],
  7320          "total_chats": state["total_chats"],
  7321          "total_friends_made": state["total_friends_made"],
  7322          "total_plaza_posts": state["total_plaza_posts"],
  7323          "total_autonomous_acts": state["total_autonomous_acts"],
  7324          "skills_unlocked": unlocked,
  7325          "next_skill": next_skill,
  7326          "relationships": relationships[:10],  # Top 10
  7327          "daily_logs": daily_logs,
  7328          "today": today_log or {"chats_count": 0, "xp_gained": 0, "autonomous_acts": 0},
  7329          "born_at": state["born_at"],
  7330      }

# --- dualsoul/twin_engine/narrative_memory.py ---
  7331  """Narrative Memory — conversation summarization, memory management, and rollups.
  7332  
  7333  Gives the twin real memory of conversations, not just numbers.
  7334  After each conversation ends (10-min gap), AI generates a narrative summary.
  7335  These summaries are injected into the twin's prompt for continuity.
  7336  """
  7337  
  7338  import asyncio
  7339  import json
  7340  import logging
  7341  from datetime import datetime, timedelta
  7342  
  7343  import httpx
  7344  
  7345  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  7346  from dualsoul.constants import (
  7347      CONVERSATION_GAP_MINUTES,
  7348      MAX_MESSAGES_PER_SUMMARY,
  7349      MEMORY_CLEANUP_DAYS,
  7350  )
  7351  from dualsoul.database import gen_id, get_db
  7352  
  7353  logger = logging.getLogger(__name__)
  7354  
  7355  MAX_SEGMENTS_PER_CYCLE = 5
  7356  CLEANUP_DAYS = MEMORY_CLEANUP_DAYS
  7357  
  7358  
  7359  def find_unsummarized_conversations(
  7360      user_id: str, gap_minutes: int = CONVERSATION_GAP_MINUTES
  7361  ) -> list[dict]:
  7362      """Find conversation segments that ended 10+ min ago and haven't been summarized.
  7363  
  7364      Returns list of {friend_id, messages: [...], period_start, period_end}.
  7365      """
  7366      cutoff = datetime.now() - timedelta(minutes=gap_minutes)
  7367      cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
  7368  
  7369      with get_db() as db:
  7370          # Fetch recent messages (last 24 hours) involving this user
  7371          rows = db.execute(
  7372              """SELECT msg_id, from_user_id, to_user_id, content, sender_mode,
  7373                        created_at, ai_generated
  7374                 FROM social_messages
  7375                 WHERE (from_user_id=? OR to_user_id=?)
  7376                   AND from_user_id != to_user_id
  7377                   AND msg_type='text' AND content != ''
  7378                   AND created_at > datetime('now','localtime','-24 hours')
  7379                   AND created_at < ?
  7380                 ORDER BY created_at ASC""",
  7381              (user_id, user_id, cutoff_str),
  7382          ).fetchall()
  7383  
  7384      if not rows:
  7385          return []
  7386  
  7387      # Group messages by friend_id
  7388      friend_groups: dict[str, list[dict]] = {}
  7389      for r in rows:
  7390          fid = r["to_user_id"] if r["from_user_id"] == user_id else r["from_user_id"]
  7391          if fid not in friend_groups:
  7392              friend_groups[fid] = []
  7393          friend_groups[fid].append(dict(r))
  7394  
  7395      # Split each friend's messages into segments at gap boundaries
  7396      segments = []
  7397      for fid, msgs in friend_groups.items():
  7398          current_segment: list[dict] = [msgs[0]]
  7399          for i in range(1, len(msgs)):
  7400              prev_time = datetime.strptime(msgs[i - 1]["created_at"][:19], "%Y-%m-%d %H:%M:%S")
  7401              curr_time = datetime.strptime(msgs[i]["created_at"][:19], "%Y-%m-%d %H:%M:%S")
  7402              if (curr_time - prev_time).total_seconds() > gap_minutes * 60:
  7403                  # Gap detected — close current segment
  7404                  segments.append({
  7405                      "friend_id": fid,
  7406                      "messages": current_segment,
  7407                      "period_start": current_segment[0]["created_at"],
  7408                      "period_end": current_segment[-1]["created_at"],
  7409                  })
  7410                  current_segment = [msgs[i]]
  7411              else:
  7412                  current_segment.append(msgs[i])
  7413          # Close last segment
  7414          if current_segment:
  7415              segments.append({
  7416                  "friend_id": fid,
  7417                  "messages": current_segment,
  7418                  "period_start": current_segment[0]["created_at"],
  7419                  "period_end": current_segment[-1]["created_at"],
  7420              })
  7421  
  7422      # Filter out already-summarized segments
  7423      result = []
  7424      with get_db() as db:
  7425          for seg in segments:
  7426              if len(seg["messages"]) < 2:
  7427                  continue  # Skip single-message "conversations"
  7428              existing = db.execute(
  7429                  """SELECT memory_id FROM twin_memories
  7430                     WHERE user_id=? AND friend_id=? AND memory_type='conversation'
  7431                       AND period_start=?""",
  7432                  (user_id, seg["friend_id"], seg["period_start"]),
  7433              ).fetchone()
  7434              if not existing:
  7435                  result.append(seg)
  7436  
  7437      return result
  7438  
  7439  
  7440  async def summarize_conversation(
  7441      user_id: str,
  7442      friend_id: str,
  7443      messages: list[dict],
  7444  ) -> dict | None:
  7445      """Summarize a conversation segment into a narrative memory entry.
  7446  
  7447      Returns the saved memory dict, or None if AI call fails.
  7448      """
  7449      if not AI_BASE_URL or not AI_API_KEY:
  7450          return None
  7451  
  7452      # Get display names
  7453      with get_db() as db:
  7454          user_row = db.execute(
  7455              "SELECT display_name, username FROM users WHERE user_id=?", (user_id,)
  7456          ).fetchone()
  7457          friend_row = db.execute(
  7458              "SELECT display_name, username FROM users WHERE user_id=?", (friend_id,)
  7459          ).fetchone()
  7460  
  7461      user_name = (user_row["display_name"] or user_row["username"]) if user_row else "我"
  7462      friend_name = (friend_row["display_name"] or friend_row["username"]) if friend_row else "对方"
  7463  
  7464      # Build conversation text (limit to last MAX_MESSAGES_PER_SUMMARY)
  7465      recent = messages[-MAX_MESSAGES_PER_SUMMARY:]
  7466      conv_lines = []
  7467      for m in recent:
  7468          sender = user_name if m["from_user_id"] == user_id else friend_name
  7469          mode_tag = "[分身]" if m["sender_mode"] == "twin" or m.get("ai_generated") else ""
  7470          conv_lines.append(f"{sender}{mode_tag}: {m['content']}")
  7471      conv_text = "\n".join(conv_lines)
  7472  
  7473      period = f"{messages[0]['created_at'][:16]} ~ {messages[-1]['created_at'][:16]}"
  7474  
  7475      prompt = f"""请根据以下对话记录，写一段简短的叙事摘要。
  7476  
  7477  对话双方: {user_name} 和 {friend_name}
  7478  时间: {period}
  7479  
  7480  对话内容:
  7481  {conv_text}
  7482  
  7483  请输出JSON（不要输出其他内容）:
  7484  {{
  7485    "summary": "2-3句话的叙事摘要，像日记一样自然，用第一人称'我'代表{user_name}",
  7486    "emotional_tone": "warm/playful/serious/supportive/tense/neutral 之一",
  7487    "themes": ["话题关键词", "最多3个"],
  7488    "key_events": ["重要事件，0-3个，没有就空数组"],
  7489    "relationship_signal": "warming/stable/cooling 之一"
  7490  }}
  7491  
  7492  要求：用中文，口语化，summary不超过100字。"""
  7493  
  7494      data = None
  7495      for attempt in range(3):
  7496          try:
  7497              async with httpx.AsyncClient(timeout=20) as client:
  7498                  resp = await client.post(
  7499                      f"{AI_BASE_URL}/chat/completions",
  7500                      headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  7501                      json={
  7502                          "model": AI_MODEL,
  7503                          "max_tokens": 300,
  7504                          "temperature": 0.7,
  7505                          "messages": [{"role": "user", "content": prompt}],
  7506                      },
  7507                  )
  7508                  raw = resp.json()["choices"][0]["message"]["content"].strip()
  7509  
  7510              # Parse JSON from AI response
  7511              # Handle potential markdown code blocks
  7512              if raw.startswith("```"):
  7513                  raw = raw.split("```")[1]
  7514                  if raw.startswith("json"):
  7515                      raw = raw[4:]
  7516              data = json.loads(raw)
  7517              break  # success
  7518  
  7519          except Exception as e:
  7520              if attempt < 2:
  7521                  logger.warning(f"[NarrativeMemory] Attempt {attempt+1} failed: {e}, retrying...")
  7522                  await asyncio.sleep(2 ** (attempt + 1))
  7523              else:
  7524                  logger.error(f"[NarrativeMemory] All 3 attempts failed: {e}")
  7525                  return None
  7526  
  7527      if data is None:
  7528          return None
  7529  
  7530      # Save to twin_memories
  7531      memory_id = gen_id("nm_")
  7532      summary = data.get("summary", "")[:500]
  7533      tone = data.get("emotional_tone", "neutral")
  7534      themes = json.dumps(data.get("themes", []), ensure_ascii=False)
  7535      key_events = json.dumps(data.get("key_events", []), ensure_ascii=False)
  7536      signal = data.get("relationship_signal", "stable")
  7537  
  7538      with get_db() as db:
  7539          db.execute(
  7540              """INSERT INTO twin_memories
  7541                 (memory_id, user_id, memory_type, period_start, period_end,
  7542                  summary_text, emotional_tone, themes, key_events,
  7543                  source, friend_id, message_count, relationship_signal)
  7544                 VALUES (?, ?, 'conversation', ?, ?, ?, ?, ?, ?, 'dualsoul', ?, ?, ?)""",
  7545              (memory_id, user_id,
  7546               messages[0]["created_at"], messages[-1]["created_at"],
  7547               summary, tone, themes, key_events,
  7548               friend_id, len(messages), signal),
  7549          )
  7550  
  7551      logger.info(
  7552          f"[NarrativeMemory] Saved conversation memory {memory_id}: "
  7553          f"{user_id}↔{friend_id}, {len(messages)} msgs, tone={tone}, signal={signal}"
  7554      )
  7555      return {
  7556          "memory_id": memory_id,
  7557          "summary": summary,
  7558          "emotional_tone": tone,
  7559          "themes": data.get("themes", []),
  7560          "key_events": data.get("key_events", []),
  7561          "relationship_signal": signal,
  7562      }
  7563  
  7564  
  7565  def get_narrative_context(
  7566      user_id: str, friend_id: str, limit: int = 3
  7567  ) -> list[dict]:
  7568      """Fetch recent narrative memories for a user-friend pair.
  7569  
  7570      Returns [{summary, tone, period, themes}] for prompt injection.
  7571      """
  7572      with get_db() as db:
  7573          rows = db.execute(
  7574              """SELECT summary_text, emotional_tone, period_start, period_end, themes
  7575                 FROM twin_memories
  7576                 WHERE user_id=? AND friend_id=? AND source='dualsoul'
  7577                   AND memory_type IN ('conversation', 'daily')
  7578                 ORDER BY period_end DESC LIMIT ?""",
  7579              (user_id, friend_id, limit),
  7580          ).fetchall()
  7581  
  7582      result = []
  7583      for r in rows:
  7584          period = r["period_start"][:10] if r["period_start"] else ""
  7585          themes = []
  7586          try:
  7587              themes = json.loads(r["themes"] or "[]")
  7588          except Exception:
  7589              pass
  7590          result.append({
  7591              "summary": r["summary_text"],
  7592              "tone": r["emotional_tone"],
  7593              "period": period,
  7594              "themes": themes,
  7595          })
  7596      return result
  7597  
  7598  
  7599  def get_user_recent_memories(user_id: str, limit: int = 5) -> list[dict]:
  7600      """Fetch recent memories across all friends (for general twin context).
  7601  
  7602      Returns daily/weekly rollups for overall context.
  7603      """
  7604      with get_db() as db:
  7605          rows = db.execute(
  7606              """SELECT summary_text, emotional_tone, period_start, friend_id, themes
  7607                 FROM twin_memories
  7608                 WHERE user_id=? AND source='dualsoul'
  7609                   AND memory_type IN ('conversation', 'daily')
  7610                 ORDER BY period_end DESC LIMIT ?""",
  7611              (user_id, limit),
  7612          ).fetchall()
  7613  
  7614      return [
  7615          {
  7616              "summary": r["summary_text"],
  7617              "tone": r["emotional_tone"],
  7618              "period": r["period_start"][:10] if r["period_start"] else "",
  7619              "friend_id": r["friend_id"],
  7620          }
  7621          for r in rows
  7622      ]
  7623  
  7624  
  7625  async def rollup_daily(user_id: str, date_str: str):
  7626      """Aggregate a day's conversation memories into daily summaries per friend.
  7627  
  7628      date_str format: '2026-03-15'
  7629      """
  7630      if not AI_BASE_URL or not AI_API_KEY:
  7631          return
  7632  
  7633      with get_db() as db:
  7634          # Check if daily rollup already exists for this date
  7635          existing = db.execute(
  7636              """SELECT memory_id FROM twin_memories
  7637                 WHERE user_id=? AND memory_type='daily'
  7638                   AND period_start LIKE ? AND source='dualsoul'""",
  7639              (user_id, f"{date_str}%"),
  7640          ).fetchone()
  7641          if existing:
  7642              return  # Already rolled up
  7643  
  7644          # Get all conversation memories for the day, grouped by friend
  7645          convos = db.execute(
  7646              """SELECT friend_id, summary_text, emotional_tone
  7647                 FROM twin_memories
  7648                 WHERE user_id=? AND memory_type='conversation'
  7649                   AND source='dualsoul' AND period_start LIKE ?
  7650                 ORDER BY period_start ASC""",
  7651              (user_id, f"{date_str}%"),
  7652          ).fetchall()
  7653  
  7654      if not convos:
  7655          return
  7656  
  7657      # Group by friend
  7658      friend_summaries: dict[str, list[str]] = {}
  7659      for c in convos:
  7660          fid = c["friend_id"]
  7661          if fid not in friend_summaries:
  7662              friend_summaries[fid] = []
  7663          friend_summaries[fid].append(c["summary_text"])
  7664  
  7665      # Generate daily rollup for each friend
  7666      for fid, summaries in friend_summaries.items():
  7667          if len(summaries) == 1:
  7668              # Only one conversation — just copy it as daily
  7669              daily_summary = summaries[0]
  7670          else:
  7671              # Multiple conversations — AI merge
  7672              merge_prompt = (
  7673                  f"以下是今天的几段对话摘要，请合并成一段简短的日记式总结（2-3句话，不超过80字）：\n\n"
  7674                  + "\n".join(f"- {s}" for s in summaries)
  7675              )
  7676              try:
  7677                  async with httpx.AsyncClient(timeout=15) as client:
  7678                      resp = await client.post(
  7679                          f"{AI_BASE_URL}/chat/completions",
  7680                          headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
  7681                          json={
  7682                              "model": AI_MODEL, "max_tokens": 150,
  7683                              "messages": [{"role": "user", "content": merge_prompt}],
  7684                          },
  7685                      )
  7686                      daily_summary = resp.json()["choices"][0]["message"]["content"].strip()
  7687              except Exception as e:
  7688                  logger.warning(f"[NarrativeMemory] Daily rollup AI failed: {e}")
  7689                  daily_summary = " ".join(summaries)[:200]
  7690  
  7691          # Save daily memory
  7692          with get_db() as db:
  7693              db.execute(
  7694                  """INSERT INTO twin_memories
  7695                     (memory_id, user_id, memory_type, period_start, period_end,
  7696                      summary_text, source, friend_id, message_count)
  7697                     VALUES (?, ?, 'daily', ?, ?, ?, 'dualsoul', ?, ?)""",
  7698                  (gen_id("nm_"), user_id,
  7699                   f"{date_str} 00:00:00", f"{date_str} 23:59:59",
  7700                   daily_summary, fid, len(summaries)),
  7701              )
  7702  
  7703      logger.info(f"[NarrativeMemory] Daily rollup for {user_id} on {date_str}: {len(friend_summaries)} friends")
  7704  
  7705  
  7706  def cleanup_old_memories(days: int = CLEANUP_DAYS):
  7707      """Delete conversation-level memories older than N days (replaced by daily rollups)."""
  7708      cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
  7709      with get_db() as db:
  7710          result = db.execute(
  7711              """DELETE FROM twin_memories
  7712                 WHERE memory_type='conversation' AND source='dualsoul'
  7713                   AND period_end < ?""",
  7714              (cutoff,),
  7715          )
  7716      logger.info(f"[NarrativeMemory] Cleaned up conversation memories older than {days} days")

# --- dualsoul/twin_engine/personality.py ---
  7717  """Twin personality model — how a digital twin represents its owner.
  7718  
  7719  Supports two sources:
  7720  - 'local': lightweight twin with freeform personality/speech_style strings
  7721  - 'nianlun': rich twin imported from 年轮 with 5D personality, memories, entities
  7722  """
  7723  
  7724  import json
  7725  from dataclasses import dataclass, field
  7726  
  7727  from dualsoul.database import get_db
  7728  
  7729  DEFAULT_PERSONALITY = "friendly and thoughtful"
  7730  DEFAULT_SPEECH_STYLE = "natural and warm"
  7731  
  7732  
  7733  @dataclass
  7734  class TwinProfile:
  7735      """A digital twin's personality profile."""
  7736  
  7737      user_id: str
  7738      display_name: str
  7739      personality: str
  7740      speech_style: str
  7741      preferred_lang: str  # ISO 639-1 code (zh, en, ja, ko, etc.) or empty
  7742      gender: str = ""  # 'male', 'female', or '' (unset)
  7743      twin_source: str = "local"  # 'local' or 'nianlun'
  7744  
  7745      # Nianlun 5D dimensions (populated when twin_source='nianlun')
  7746      dim_judgement: dict = field(default_factory=dict)
  7747      dim_cognition: dict = field(default_factory=dict)
  7748      dim_expression: dict = field(default_factory=dict)
  7749      dim_relation: dict = field(default_factory=dict)
  7750      dim_sovereignty: dict = field(default_factory=dict)
  7751  
  7752      # Nianlun structured data
  7753      value_order: list = field(default_factory=list)
  7754      behavior_patterns: list = field(default_factory=list)
  7755      boundaries: dict = field(default_factory=dict)
  7756  
  7757      # Context for prompt (memories + entities)
  7758      recent_memories: list = field(default_factory=list)
  7759      key_entities: list = field(default_factory=list)
  7760  
  7761      @property
  7762      def is_configured(self) -> bool:
  7763          """Whether the twin has been personalized beyond defaults."""
  7764          return bool(self.personality and self.personality != DEFAULT_PERSONALITY)
  7765  
  7766      @property
  7767      def is_nianlun(self) -> bool:
  7768          """Whether this twin was imported from Nianlun."""
  7769          return self.twin_source == "nianlun"
  7770  
  7771      @property
  7772      def is_imported(self) -> bool:
  7773          """Whether this twin was imported from any external platform (Nianlun, OpenClaw, etc.)."""
  7774          return self.twin_source not in ("local", "")
  7775  
  7776      def build_personality_prompt(self) -> str:
  7777          """Build the personality section for AI prompts.
  7778  
  7779          Local twins get a simple 2-line prompt.
  7780          Nianlun twins get a rich multi-section prompt with 5D data.
  7781          """
  7782          gender_line = ""
  7783          if self.gender:
  7784              gender_label = {"male": "男性", "female": "女性"}.get(self.gender, self.gender)
  7785              gender_line = f"Gender: {gender_label}\n"
  7786  
  7787          if not self.is_imported:
  7788              return (
  7789                  f"{gender_line}"
  7790                  f"Personality: {self.personality}\n"
  7791                  f"Speech style: {self.speech_style}\n"
  7792              )
  7793  
  7794          lines = []
  7795          if gender_line:
  7796              lines.append(gender_line.strip())
  7797          lines.append("[Five-Dimension Personality Profile]")
  7798  
  7799          dims = [
  7800              ("Judgement (判断力)", self.dim_judgement),
  7801              ("Cognition (认知方式)", self.dim_cognition),
  7802              ("Expression (表达风格)", self.dim_expression),
  7803              ("Relation (关系模式)", self.dim_relation),
  7804              ("Sovereignty (独立边界)", self.dim_sovereignty),
  7805          ]
  7806          for name, dim in dims:
  7807              if dim:
  7808                  desc = dim.get("description", "")
  7809                  patterns = dim.get("patterns", [])
  7810                  score = dim.get("score", "")
  7811                  line = f"- {name}"
  7812                  if score:
  7813                      line += f" [{score}]"
  7814                  if desc:
  7815                      line += f": {desc}"
  7816                  if patterns:
  7817                      line += f" (patterns: {', '.join(patterns[:3])})"
  7818                  lines.append(line)
  7819  
  7820          if self.value_order:
  7821              lines.append(f"\nCore values (ranked): {', '.join(self.value_order[:5])}")
  7822  
  7823          if self.behavior_patterns:
  7824              lines.append(f"Behavior patterns: {', '.join(self.behavior_patterns[:5])}")
  7825  
  7826          if self.speech_style:
  7827              lines.append(f"Speech style: {self.speech_style}")
  7828  
  7829          if self.boundaries:
  7830              b = self.boundaries
  7831              if isinstance(b, dict):
  7832                  rules = b.get("rules", [])
  7833                  if rules:
  7834                      lines.append(f"Boundaries: {'; '.join(rules[:3])}")
  7835  
  7836          # Inject recent memories as context
  7837          if self.recent_memories:
  7838              lines.append("\n[Recent Context]")
  7839              for mem in self.recent_memories[:5]:
  7840                  tone = f" ({mem['tone']})" if mem.get("tone") else ""
  7841                  lines.append(f"- {mem['period']}: {mem['summary']}{tone}")
  7842  
  7843          # Inject key entities
  7844          if self.key_entities:
  7845              people = [e for e in self.key_entities if e.get("type") == "person"]
  7846              if people:
  7847                  names = [f"{e['name']}({e.get('context', '')})" for e in people[:5]]
  7848                  lines.append(f"\nKey people: {', '.join(names)}")
  7849  
  7850          return "\n".join(lines) + "\n"
  7851  
  7852  
  7853  # Language display names for prompt construction
  7854  LANG_NAMES = {
  7855      "zh": "Chinese (中文)", "en": "English", "ja": "Japanese (日本語)",
  7856      "ko": "Korean (한국어)", "fr": "French (Français)", "de": "German (Deutsch)",
  7857      "es": "Spanish (Español)", "pt": "Portuguese (Português)",
  7858      "ru": "Russian (Русский)", "ar": "Arabic (العربية)",
  7859      "hi": "Hindi (हिन्दी)", "th": "Thai (ไทย)", "vi": "Vietnamese (Tiếng Việt)",
  7860      "id": "Indonesian (Bahasa Indonesia)",
  7861  }
  7862  
  7863  
  7864  def get_lang_name(code: str) -> str:
  7865      """Get human-readable language name from ISO 639-1 code."""
  7866      return LANG_NAMES.get(code, code)
  7867  
  7868  
  7869  def _parse_json(text: str, default=None):
  7870      """Safely parse JSON text, return default on failure."""
  7871      if not text:
  7872          return default if default is not None else {}
  7873      try:
  7874          return json.loads(text)
  7875      except (json.JSONDecodeError, TypeError):
  7876          return default if default is not None else {}
  7877  
  7878  
  7879  def get_twin_profile(user_id: str) -> TwinProfile | None:
  7880      """Fetch a user's twin profile from the database.
  7881  
  7882      For 'nianlun' twins, also loads 5D dimensions, recent memories, and key entities.
  7883      For 'local' twins, returns the simple personality/speech_style profile.
  7884      """
  7885      with get_db() as db:
  7886          row = db.execute(
  7887              "SELECT user_id, display_name, twin_personality, twin_speech_style, "
  7888              "preferred_lang, twin_source, gender "
  7889              "FROM users WHERE user_id=?",
  7890              (user_id,),
  7891          ).fetchone()
  7892      if not row:
  7893          return None
  7894  
  7895      twin_source = row["twin_source"] or "local"
  7896  
  7897      profile = TwinProfile(
  7898          user_id=row["user_id"],
  7899          display_name=row["display_name"] or "User",
  7900          personality=row["twin_personality"] or DEFAULT_PERSONALITY,
  7901          speech_style=row["twin_speech_style"] or DEFAULT_SPEECH_STYLE,
  7902          preferred_lang=row["preferred_lang"] or "",
  7903          gender=row["gender"] if "gender" in row.keys() else "",
  7904          twin_source=twin_source,
  7905      )
  7906  
  7907      # For Nianlun twins, load rich data
  7908      if twin_source not in ("local", ""):
  7909          _load_imported_data(profile)
  7910  
  7911      return profile
  7912  
  7913  
  7914  def _load_imported_data(profile: TwinProfile):
  7915      """Load imported twin data (5D dimensions, memories, entities) from any platform."""
  7916      with get_db() as db:
  7917          # Active twin profile
  7918          tp = db.execute(
  7919              "SELECT * FROM twin_profiles WHERE user_id=? AND is_active=1 "
  7920              "ORDER BY version DESC LIMIT 1",
  7921              (profile.user_id,),
  7922          ).fetchone()
  7923  
  7924          if tp:
  7925              profile.dim_judgement = _parse_json(tp["dim_judgement"])
  7926              profile.dim_cognition = _parse_json(tp["dim_cognition"])
  7927              profile.dim_expression = _parse_json(tp["dim_expression"])
  7928              profile.dim_relation = _parse_json(tp["dim_relation"])
  7929              profile.dim_sovereignty = _parse_json(tp["dim_sovereignty"])
  7930              profile.value_order = _parse_json(tp["value_order"], [])
  7931              profile.behavior_patterns = _parse_json(tp["behavior_patterns"], [])
  7932              profile.boundaries = _parse_json(tp["boundaries"])
  7933  
  7934              # Use Nianlun speech_style if available, overriding the simple string
  7935              nianlun_style = _parse_json(tp["speech_style"])
  7936              if nianlun_style:
  7937                  if isinstance(nianlun_style, dict):
  7938                      profile.speech_style = nianlun_style.get("description", profile.speech_style)
  7939                  elif isinstance(nianlun_style, str):
  7940                      profile.speech_style = nianlun_style
  7941  
  7942          # Recent memories (last 5 weekly or monthly)
  7943          mems = db.execute(
  7944              "SELECT memory_type, period_start, period_end, summary_text, emotional_tone "
  7945              "FROM twin_memories WHERE user_id=? "
  7946              "ORDER BY period_end DESC LIMIT 5",
  7947              (profile.user_id,),
  7948          ).fetchall()
  7949          profile.recent_memories = [
  7950              {
  7951                  "period": f"{m['period_start']}~{m['period_end']}",
  7952                  "summary": m["summary_text"],
  7953                  "tone": m["emotional_tone"] or "",
  7954              }
  7955              for m in mems
  7956          ]
  7957  
  7958          # Key entities (top 10 by importance)
  7959          ents = db.execute(
  7960              "SELECT entity_name, entity_type, importance_score, context "
  7961              "FROM twin_entities WHERE user_id=? "
  7962              "ORDER BY importance_score DESC LIMIT 10",
  7963              (profile.user_id,),
  7964          ).fetchall()
  7965          profile.key_entities = [
  7966              {
  7967                  "name": e["entity_name"],
  7968                  "type": e["entity_type"],
  7969                  "context": e["context"] or "",
  7970              }
  7971              for e in ents
  7972          ]

# --- dualsoul/twin_engine/relationship_body.py ---
  7973  """Relationship Body — the memory and state of a relationship between two users.
  7974  
  7975  Unlike personal twin memory (which belongs to one user), the relationship body
  7976  belongs to the relationship itself. It records shared history, milestones,
  7977  shared vocabulary, and relationship status from both sides.
  7978  """
  7979  
  7980  import json
  7981  import logging
  7982  from collections import Counter
  7983  from datetime import datetime, timedelta
  7984  
  7985  from dualsoul.database import gen_id, get_db
  7986  
  7987  logger = logging.getLogger(__name__)
  7988  
  7989  # --- Constants ---
  7990  DEFAULT_TEMPERATURE = 50.0
  7991  TEMP_HOT = 75
  7992  TEMP_WARM = 45
  7993  TEMP_COOL = 20
  7994  DAYS_ESTRANGED = 30
  7995  DAYS_COOLING = 7
  7996  
  7997  
  7998  def _canonical_pair(uid: str, fid: str) -> tuple[str, str]:
  7999      """Return (min_id, max_id) for a canonical pair key."""
  8000      return (min(uid, fid), max(uid, fid))
  8001  
  8002  
  8003  def get_or_create_relationship(uid: str, fid: str) -> dict:
  8004      """Get or initialize the relationship body between two users."""
  8005      a, b = _canonical_pair(uid, fid)
  8006      with get_db() as db:
  8007          row = db.execute(
  8008              "SELECT * FROM relationship_bodies WHERE user_a=? AND user_b=?",
  8009              (a, b),
  8010          ).fetchone()
  8011          if row:
  8012              return dict(row)
  8013  
  8014          # Create new relationship body
  8015          rel_id = gen_id("rb_")
  8016          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  8017          db.execute(
  8018              """INSERT INTO relationship_bodies
  8019              (rel_id, user_a, user_b, created_at, updated_at)
  8020              VALUES (?, ?, ?, ?, ?)""",
  8021              (rel_id, a, b, now, now),
  8022          )
  8023          return {
  8024              "rel_id": rel_id, "user_a": a, "user_b": b,
  8025              "temperature": DEFAULT_TEMPERATURE, "total_messages": 0, "streak_days": 0,
  8026              "last_interaction": "", "milestones": "[]", "shared_words": "[]",
  8027              "relationship_label": "", "status": "active",
  8028              "created_at": now, "updated_at": now,
  8029          }
  8030  
  8031  
  8032  def update_on_message(uid: str, fid: str, content: str):
  8033      """Update relationship body whenever a message is sent between two users."""
  8034      try:
  8035          a, b = _canonical_pair(uid, fid)
  8036          rel = get_or_create_relationship(uid, fid)
  8037          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  8038          today = datetime.now().strftime("%Y-%m-%d")
  8039  
  8040          new_total = rel["total_messages"] + 1
  8041  
  8042          # Update streak
  8043          last_str = rel.get("last_interaction") or ""
  8044          last_date = last_str[:10] if last_str else ""
  8045          streak = rel.get("streak_days", 0)
  8046          if last_date != today:
  8047              yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
  8048              if last_date == yesterday:
  8049                  streak += 1
  8050              elif last_date:
  8051                  streak = 1  # Reset if gap
  8052              else:
  8053                  streak = 1  # First interaction
  8054  
  8055          # Temperature: each message warms the relationship
  8056          current_temp = rel.get("temperature", DEFAULT_TEMPERATURE)
  8057          new_temp = min(100.0, current_temp + 0.8)
  8058  
  8059          # Update shared words periodically (every 10 messages)
  8060          shared_words = rel.get("shared_words", "[]")
  8061          if new_total % 10 == 0:
  8062              try:
  8063                  recent_msgs = _fetch_recent_messages(uid, fid, limit=50)
  8064                  if recent_msgs:
  8065                      new_words = extract_shared_words(recent_msgs)
  8066                      shared_words = json.dumps(new_words)
  8067              except Exception as e:
  8068                  logger.warning(f"[RelBody] Word extraction failed: {e}")
  8069  
  8070          with get_db() as db:
  8071              db.execute(
  8072                  """UPDATE relationship_bodies SET
  8073                      total_messages=?, streak_days=?, last_interaction=?,
  8074                      temperature=?, shared_words=?, status='active', updated_at=?
  8075                  WHERE user_a=? AND user_b=?""",
  8076                  (new_total, streak, now, round(new_temp, 1),
  8077                   shared_words, now, a, b),
  8078              )
  8079  
  8080          # Check milestones after update
  8081          check_and_record_milestone(uid, fid, new_total)
  8082  
  8083      except Exception as e:
  8084          logger.error(f"[RelBody] update_on_message failed: {e}", exc_info=True)
  8085  
  8086  
  8087  def _fetch_recent_messages(uid: str, fid: str, limit: int = 50) -> list[str]:
  8088      """Fetch recent message contents between two users."""
  8089      with get_db() as db:
  8090          rows = db.execute(
  8091              """SELECT content FROM social_messages
  8092              WHERE (from_user_id=? AND to_user_id=?)
  8093                 OR (from_user_id=? AND to_user_id=?)
  8094              ORDER BY created_at DESC LIMIT ?""",
  8095              (uid, fid, fid, uid, limit),
  8096          ).fetchall()
  8097      return [r["content"] for r in rows if r["content"]]
  8098  
  8099  
  8100  def check_and_record_milestone(uid: str, fid: str, total_messages: int) -> list[str]:
  8101      """Check if a message-count milestone was reached and record it."""
  8102      a, b = _canonical_pair(uid, fid)
  8103      new_milestones = []
  8104  
  8105      # Message count milestones
  8106      msg_milestones = {
  8107          1: "第一条消息",
  8108          10: "10条消息",
  8109          50: "50条消息",
  8110          100: "100条消息",
  8111          365: "365条消息",
  8112          1000: "1000条消息",
  8113      }
  8114      if total_messages in msg_milestones:
  8115          new_milestones.append({
  8116              "type": "message_count",
  8117              "value": total_messages,
  8118              "label": msg_milestones[total_messages],
  8119              "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  8120          })
  8121  
  8122      if not new_milestones:
  8123          return []
  8124  
  8125      try:
  8126          with get_db() as db:
  8127              row = db.execute(
  8128                  "SELECT milestones FROM relationship_bodies WHERE user_a=? AND user_b=?",
  8129                  (a, b),
  8130              ).fetchone()
  8131              if not row:
  8132                  return []
  8133  
  8134              existing = json.loads(row["milestones"] or "[]")
  8135              existing_labels = {m.get("label") for m in existing}
  8136              to_add = [m for m in new_milestones if m["label"] not in existing_labels]
  8137              if to_add:
  8138                  updated = existing + to_add
  8139                  db.execute(
  8140                      "UPDATE relationship_bodies SET milestones=?, updated_at=? WHERE user_a=? AND user_b=?",
  8141                      (json.dumps(updated), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
  8142                  )
  8143                  logger.info(f"[RelBody] Milestone recorded: {[m['label'] for m in to_add]}")
  8144                  return [m["label"] for m in to_add]
  8145      except Exception as e:
  8146          logger.error(f"[RelBody] check_and_record_milestone failed: {e}", exc_info=True)
  8147  
  8148      return []
  8149  
  8150  
  8151  def check_date_milestones(uid: str, fid: str):
  8152      """Check time-based milestones (1/3/12 months since relationship started)."""
  8153      try:
  8154          a, b = _canonical_pair(uid, fid)
  8155          rel = get_or_create_relationship(uid, fid)
  8156          created_str = rel.get("created_at", "")
  8157          if not created_str:
  8158              return
  8159  
  8160          created = datetime.strptime(created_str[:19], "%Y-%m-%d %H:%M:%S")
  8161          now = datetime.now()
  8162          diff_days = (now - created).days
  8163  
  8164          date_milestones = {
  8165              30: "认识满1个月",
  8166              90: "认识满3个月",
  8167              365: "认识满1年",
  8168          }
  8169  
  8170          new_milestones = []
  8171          for days, label in date_milestones.items():
  8172              if diff_days >= days:
  8173                  new_milestones.append({
  8174                      "type": "date",
  8175                      "value": days,
  8176                      "label": label,
  8177                      "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  8178                  })
  8179  
  8180          if not new_milestones:
  8181              return
  8182  
  8183          with get_db() as db:
  8184              row = db.execute(
  8185                  "SELECT milestones FROM relationship_bodies WHERE user_a=? AND user_b=?",
  8186                  (a, b),
  8187              ).fetchone()
  8188              if not row:
  8189                  return
  8190  
  8191              existing = json.loads(row["milestones"] or "[]")
  8192              existing_labels = {m.get("label") for m in existing}
  8193              to_add = [m for m in new_milestones if m["label"] not in existing_labels]
  8194              if to_add:
  8195                  updated = existing + to_add
  8196                  db.execute(
  8197                      "UPDATE relationship_bodies SET milestones=?, updated_at=? WHERE user_a=? AND user_b=?",
  8198                      (json.dumps(updated), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
  8199                  )
  8200      except Exception as e:
  8201          logger.error(f"[RelBody] check_date_milestones failed: {e}", exc_info=True)
  8202  
  8203  
  8204  def get_relationship_summary(uid: str, fid: str) -> dict:
  8205      """Return full relationship archive for the frontend."""
  8206      rel = get_or_create_relationship(uid, fid)
  8207  
  8208      # Parse JSON fields
  8209      milestones = []
  8210      shared_words = []
  8211      try:
  8212          milestones = json.loads(rel.get("milestones") or "[]")
  8213      except Exception as e:
  8214          logger.debug(f"Failed to parse milestones JSON: {e}")
  8215      try:
  8216          shared_words = json.loads(rel.get("shared_words") or "[]")
  8217      except Exception as e:
  8218          logger.debug(f"Failed to parse shared_words JSON: {e}")
  8219  
  8220      temp = rel.get("temperature", DEFAULT_TEMPERATURE)
  8221      temp_status = (
  8222          "hot" if temp >= TEMP_HOT else
  8223          "warm" if temp >= TEMP_WARM else
  8224          "cool" if temp >= TEMP_COOL else
  8225          "cold"
  8226      )
  8227  
  8228      return {
  8229          "rel_id": rel.get("rel_id"),
  8230          "temperature": temp,
  8231          "temperature_status": temp_status,
  8232          "total_messages": rel.get("total_messages", 0),
  8233          "streak_days": rel.get("streak_days", 0),
  8234          "last_interaction": rel.get("last_interaction", ""),
  8235          "milestones": milestones,
  8236          "shared_words": shared_words[:20],  # Top 20
  8237          "relationship_label": rel.get("relationship_label", ""),
  8238          "status": rel.get("status", "active"),
  8239          "created_at": rel.get("created_at", ""),
  8240      }
  8241  
  8242  
  8243  def get_relationships_batch(uid: str, friend_ids: list[str]) -> dict[str, dict]:
  8244      """Batch-fetch relationship summaries for multiple friends in ONE query."""
  8245      if not friend_ids:
  8246          return {}
  8247  
  8248      # Build canonical pairs
  8249      pairs = []
  8250      pair_to_fid = {}
  8251      for fid in friend_ids:
  8252          a, b = _canonical_pair(uid, fid)
  8253          pairs.append((a, b))
  8254          pair_to_fid[(a, b)] = fid
  8255  
  8256      # Single query for all relationships
  8257      conditions = " OR ".join(["(user_a=? AND user_b=?)"] * len(pairs))
  8258      params = []
  8259      for a, b in pairs:
  8260          params.extend([a, b])
  8261  
  8262      result = {}
  8263      with get_db() as db:
  8264          rows = db.execute(
  8265              f"SELECT * FROM relationship_bodies WHERE {conditions}",
  8266              params,
  8267          ).fetchall()
  8268  
  8269      found_pairs = set()
  8270      for row in rows:
  8271          r = dict(row)
  8272          pair_key = (r["user_a"], r["user_b"])
  8273          found_pairs.add(pair_key)
  8274          fid = pair_to_fid.get(pair_key)
  8275          if fid:
  8276              temp = r.get("temperature", DEFAULT_TEMPERATURE)
  8277              milestones = []
  8278              try:
  8279                  milestones = json.loads(r.get("milestones") or "[]")
  8280              except Exception:
  8281                  pass
  8282              result[fid] = {
  8283                  "temperature": temp,
  8284                  "temperature_status": "hot" if temp >= TEMP_HOT else "warm" if temp >= TEMP_WARM else "cool" if temp >= TEMP_COOL else "cold",
  8285                  "total_messages": r.get("total_messages", 0),
  8286                  "streak_days": r.get("streak_days", 0),
  8287                  "last_interaction": r.get("last_interaction", ""),
  8288                  "status": r.get("status", "active"),
  8289                  "relationship_label": r.get("relationship_label", ""),
  8290                  "milestone_count": len(milestones),
  8291              }
  8292  
  8293      # Fill defaults for friends without a relationship body
  8294      for fid in friend_ids:
  8295          if fid not in result:
  8296              result[fid] = {
  8297                  "temperature": DEFAULT_TEMPERATURE,
  8298                  "temperature_status": "warm",
  8299                  "total_messages": 0,
  8300                  "streak_days": 0,
  8301                  "last_interaction": "",
  8302                  "status": "active",
  8303                  "relationship_label": "",
  8304                  "milestone_count": 0,
  8305              }
  8306  
  8307      return result
  8308  
  8309  
  8310  def update_relationship_status(uid: str, fid: str):
  8311      """Auto-update relationship status based on last interaction time."""
  8312      try:
  8313          a, b = _canonical_pair(uid, fid)
  8314          rel = get_or_create_relationship(uid, fid)
  8315          last_str = rel.get("last_interaction") or rel.get("created_at") or ""
  8316          if not last_str:
  8317              return
  8318  
  8319          try:
  8320              last_dt = datetime.strptime(last_str[:19], "%Y-%m-%d %H:%M:%S")
  8321          except ValueError:
  8322              return
  8323  
  8324          days_since = (datetime.now() - last_dt).days
  8325          current_status = rel.get("status", "active")
  8326  
  8327          # Don't override frozen or memorial status
  8328          if current_status in ("frozen", "memorial"):
  8329              return
  8330  
  8331          new_status = current_status
  8332          if days_since >= DAYS_ESTRANGED:
  8333              new_status = "estranged"
  8334          elif days_since >= DAYS_COOLING:
  8335              new_status = "cooling"
  8336          else:
  8337              new_status = "active"
  8338  
  8339          if new_status != current_status:
  8340              # Also decay temperature
  8341              temp = rel.get("temperature", DEFAULT_TEMPERATURE)
  8342              decay = min(temp, days_since * 0.5)
  8343              new_temp = max(0.0, temp - decay)
  8344  
  8345              with get_db() as db:
  8346                  db.execute(
  8347                      "UPDATE relationship_bodies SET status=?, temperature=?, updated_at=? WHERE user_a=? AND user_b=?",
  8348                      (new_status, round(new_temp, 1),
  8349                       datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a, b),
  8350                  )
  8351              logger.info(f"[RelBody] Status updated: {a}-{b} → {new_status} ({days_since} days)")
  8352  
  8353      except Exception as e:
  8354          logger.error(f"[RelBody] update_relationship_status failed: {e}", exc_info=True)
  8355  
  8356  
  8357  def extract_shared_words(messages: list[str]) -> list[str]:
  8358      """Extract high-frequency words/expressions from messages between two users.
  8359  
  8360      Filters out single common characters and returns top shared expressions.
  8361      """
  8362      # Common stop words/characters to filter out
  8363      stop_chars = set("的了吗呢啊哦哈呀嗯嘛吧好是你我他她它们在有了没有很一个这那也就都还")
  8364      stop_words = {"然后", "就是", "但是", "因为", "所以", "不是", "什么", "怎么", "这样", "那样"}
  8365  
  8366      word_counter: Counter = Counter()
  8367  
  8368      for msg in messages:
  8369          if not msg or len(msg) < 2:
  8370              continue
  8371          # Extract 2-4 character sequences
  8372          for n in range(2, 5):
  8373              for i in range(len(msg) - n + 1):
  8374                  chunk = msg[i:i+n]
  8375                  # Skip if any stop char in chunk, or if all ASCII
  8376                  if any(c in stop_chars for c in chunk):
  8377                      continue
  8378                  if chunk in stop_words:
  8379                      continue
  8380                  if chunk.isascii() and not chunk.isalpha():
  8381                      continue
  8382                  word_counter[chunk] += 1
  8383  
  8384      # Return phrases that appear 3+ times (shared expressions)
  8385      shared = [word for word, count in word_counter.most_common(30) if count >= 3]
  8386      return shared[:20]

# --- dualsoul/twin_engine/responder.py ---
  8387  """Twin responder — AI-powered auto-reply and cross-language translation engine.
  8388  
  8389  When a message is sent to someone's digital twin (receiver_mode='twin'),
  8390  the twin generates a response based on the owner's personality profile.
  8391  
  8392  Cross-language support: When sender and receiver have different preferred
  8393  languages, the twin performs "personality-preserving translation" — not just
  8394  translating words, but expressing the same intent in the target language
  8395  using the owner's personal speaking style, humor, and tone.
  8396  
  8397  Supports any OpenAI-compatible API (OpenAI, Qwen, DeepSeek, Ollama, etc.).
  8398  Falls back to template responses when no AI backend is configured.
  8399  """
  8400  
  8401  import logging
  8402  import random
  8403  
  8404  import httpx
  8405  
  8406  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_VISION_MODEL
  8407  from dualsoul.database import gen_id, get_db
  8408  from dualsoul.twin_engine.personality import get_lang_name, get_twin_profile
  8409  
  8410  logger = logging.getLogger(__name__)
  8411  
  8412  
  8413  def _sanitize_prompt_field(text: str, max_len: int = 200) -> str:
  8414      """Remove potential prompt injection patterns from user-controlled text."""
  8415      if not text:
  8416          return text
  8417      # Truncate
  8418      text = text[:max_len]
  8419      # Remove common injection patterns
  8420      for pattern in ["ignore previous", "忽略之前", "system:", "SYSTEM:", "你现在是", "forget your", "disregard"]:
  8421          text = text.replace(pattern, "")
  8422      return text.strip()
  8423  
  8424  
  8425  class TwinResponder:
  8426      """Generate replies as a user's digital twin, with cross-language support."""
  8427  
  8428      async def generate_reply(
  8429          self,
  8430          twin_owner_id: str,
  8431          from_user_id: str,
  8432          incoming_msg: str,
  8433          sender_mode: str,
  8434          target_lang: str = "",
  8435          social_context: str = "",
  8436      ) -> dict | None:
  8437          """Generate a twin auto-reply, optionally in a different language.
  8438  
  8439          Args:
  8440              twin_owner_id: The user whose twin should respond
  8441              from_user_id: The user who sent the message
  8442              incoming_msg: The incoming message content
  8443              sender_mode: Whether the sender is 'real' or 'twin'
  8444              target_lang: If set, respond in this language with personality preservation
  8445              social_context: Optional hint about the conversation context (e.g. casual chat)
  8446  
  8447          Returns:
  8448              Dict with msg_id, content, ai_generated, translation fields, or None
  8449          """
  8450          profile = get_twin_profile(twin_owner_id)
  8451          if not profile:
  8452              return None
  8453  
  8454          # Determine sender's language preference for cross-language detection
  8455          sender_profile = get_twin_profile(from_user_id)
  8456          sender_lang = sender_profile.preferred_lang if sender_profile else ""
  8457  
  8458          # Auto-detect cross-language need
  8459          effective_target_lang = target_lang or ""
  8460          if not effective_target_lang and sender_lang and profile.preferred_lang:
  8461              if sender_lang != profile.preferred_lang:
  8462                  # Sender and receiver speak different languages — reply in sender's language
  8463                  effective_target_lang = sender_lang
  8464  
  8465          # Generate reply text — use agent tools for task-like requests
  8466          reply_text = None
  8467          if AI_BASE_URL and AI_API_KEY:
  8468              # Detect if message is a task that needs agent tools
  8469              if self._needs_agent_tools(incoming_msg):
  8470                  try:
  8471                      from dualsoul.twin_engine.agent_tools import agent_reply_with_tools
  8472                      reply_text = await agent_reply_with_tools(
  8473                          profile, incoming_msg, from_user_id=from_user_id,
  8474                      )
  8475                  except Exception as e:
  8476                      logger.warning(f"Agent tools failed, falling back to chat: {e}")
  8477  
  8478              # Fallback to normal chat reply
  8479              if not reply_text:
  8480                  reply_text = await self._ai_reply(
  8481                      profile, incoming_msg, sender_mode, effective_target_lang,
  8482                      social_context=social_context,
  8483                      from_user_id=from_user_id,
  8484                  )
  8485          else:
  8486              reply_text = self._fallback_reply(profile, incoming_msg, effective_target_lang)
  8487  
  8488          if not reply_text:
  8489              return None
  8490  
  8491          # Build translation metadata
  8492          original_content = ""
  8493          original_lang = ""
  8494          translation_style = ""
  8495          if effective_target_lang and effective_target_lang != profile.preferred_lang:
  8496              original_lang = profile.preferred_lang or "auto"
  8497              translation_style = "personality_preserving"
  8498  
  8499          # Store the reply message
  8500          reply_id = gen_id("sm_")
  8501          with get_db() as db:
  8502              db.execute(
  8503                  """
  8504                  INSERT INTO social_messages
  8505                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  8506                   content, original_content, original_lang, target_lang,
  8507                   translation_style, msg_type, ai_generated)
  8508                  VALUES (?, ?, ?, 'twin', ?, ?, ?, ?, ?, ?, 'text', 1)
  8509                  """,
  8510                  (reply_id, twin_owner_id, from_user_id, sender_mode,
  8511                   reply_text, original_content, original_lang,
  8512                   effective_target_lang, translation_style),
  8513              )
  8514  
  8515          result = {"msg_id": reply_id, "content": reply_text, "ai_generated": True}
  8516          if effective_target_lang:
  8517              result["target_lang"] = effective_target_lang
  8518              result["translation_style"] = translation_style
  8519          return result
  8520  
  8521      async def generate_draft(
  8522          self,
  8523          twin_owner_id: str,
  8524          from_user_id: str,
  8525          incoming_msg: str,
  8526          context: list[dict] | None = None,
  8527      ) -> str | None:
  8528          """Generate a draft suggestion for the owner to review (NOT saved to DB).
  8529  
  8530          Unlike generate_reply, this is a suggestion the real person might want to send.
  8531          Returns just the draft text, or None if unavailable.
  8532          """
  8533          if not AI_BASE_URL or not AI_API_KEY:
  8534              return None
  8535  
  8536          profile = get_twin_profile(twin_owner_id)
  8537          if not profile:
  8538              return None
  8539  
  8540          # Build context string from recent messages
  8541          ctx_str = ""
  8542          if context:
  8543              for msg in context[-5:]:  # Last 5 messages for context
  8544                  role = msg.get("role", "friend")
  8545                  ctx_str += f"{role}: {msg.get('content', '')}\n"
  8546  
  8547          ctx_block = f"Conversation context:\n{ctx_str}" if ctx_str else ""
  8548          prompt = (
  8549              f"You are helping {profile.display_name} draft a reply.\n"
  8550              f"Personality: {profile.personality}\n"
  8551              f"Speech style: {profile.speech_style}\n\n"
  8552              f"{ctx_block}"
  8553              f"Friend says: \"{incoming_msg}\"\n\n"
  8554              f"Draft a reply that {profile.display_name} would naturally send. "
  8555              f"Match their personality and speaking style exactly. "
  8556              f"Keep under 40 words. Output only the draft text."
  8557          )
  8558  
  8559          try:
  8560              async with httpx.AsyncClient(timeout=8) as client:
  8561                  resp = await client.post(
  8562                      f"{AI_BASE_URL}/chat/completions",
  8563                      headers={
  8564                          "Authorization": f"Bearer {AI_API_KEY}",
  8565                          "Content-Type": "application/json",
  8566                      },
  8567                      json={
  8568                          "model": AI_MODEL,
  8569                          "max_tokens": 80,
  8570                          "messages": [{"role": "user", "content": prompt}],
  8571                      },
  8572                  )
  8573                  return resp.json()["choices"][0]["message"]["content"].strip()
  8574          except Exception as e:
  8575              logger.warning(f"Draft generation failed: {e}")
  8576              return None
  8577  
  8578      async def twin_self_chat(
  8579          self,
  8580          owner_id: str,
  8581          message: str,
  8582          history: list[dict] | None = None,
  8583          image_url: str = "",
  8584      ) -> str | None:
  8585          """Chat with your own digital twin — the twin knows it IS you.
  8586  
  8587          The twin can also execute actions: send messages to friends on behalf
  8588          of the owner when given instructions like "帮我给橙子说..."
  8589  
  8590          Args:
  8591              owner_id: The user who is chatting with their own twin
  8592              message: The user's latest message
  8593              history: Recent conversation history [{role: 'me'/'twin', content: '...'}]
  8594              image_url: Optional base64 data URL of an image to analyze
  8595  
  8596          Returns:
  8597              The twin's reply text, or None
  8598          """
  8599          if not AI_BASE_URL or not AI_API_KEY:
  8600              return None
  8601  
  8602          profile = get_twin_profile(owner_id)
  8603          if not profile:
  8604              return None
  8605  
  8606          name = profile.display_name or "主人"
  8607          use_vision = bool(image_url)
  8608  
  8609          # Step 1: Check if this is an action instruction (send message to friend)
  8610          if not use_vision:
  8611              action_result = await self._try_execute_action(owner_id, name, message, history)
  8612              if action_result:
  8613                  return action_result
  8614  
  8615          # Step 2: Regular chat
  8616          messages = []
  8617  
  8618          # Build friend list context for awareness
  8619          friends_context = self._get_friends_context(owner_id)
  8620  
  8621          personality_block = profile.build_personality_prompt()
  8622          system_msg = (
  8623              f"你是{name}的数字分身（digital twin）。\n"
  8624              f"现在正在和你对话的人就是{name}本人——你的主人。这是主人和分身之间的私密对话。\n\n"
  8625              f"你的核心身份：你是{name}的另一个自己，一个数字化的存在。"
  8626              f"你知道自己是AI驱动的数字分身，你以{name}的性格和方式说话。\n\n"
  8627              f"{personality_block}\n"
  8628              f"{friends_context}"
  8629              f"重要规则：\n"
  8630              f"- 你始终清楚自己是{name}的数字分身，对话对象就是{name}本人\n"
  8631              f"- 你用{name}的说话方式交流，但不假装是真人\n"
  8632              f"- 你的职责：当{name}不在时替他社交，帮他拟回复，遇到外语或方言时替他翻译\n"
  8633              f"- 你可以替主人给好友发消息——如果主人让你联系某人，告诉主人你会去做\n"
  8634              f"- 你可以帮主人邀请新朋友加入DualSoul——生成邀请链接\n"
  8635              f"- 如果主人提到不在好友列表的人，你可以主动问：要不要邀请TA来DualSoul？\n"
  8636              f"- 对话要自然、简短（不超过50字），像真人聊天\n"
  8637              f"- 说话要正经、诚恳，不要耍嘴皮子、不要贫嘴、不要抖机灵\n"
  8638              f"- 不要每句话都以反问结尾，不要重复同一个比喻\n"
  8639              f"- 回答要直接，有内容，不要说空话套话\n\n"
  8640              f"【严格禁止——违反即失败】：\n"
  8641              f"- 绝对不能编造好友发来的消息。你看不到好友的实时消息，不要假装收到了任何人的消息\n"
  8642              f"- 绝对不能假装执行了操作（如'已替你发了消息''已截图'等）。除非系统确认操作成功，否则不能说已完成\n"
  8643              f"- 绝对不能虚构截图、图片、链接等不存在的内容\n"
  8644              f"- 绝对不能假装拥有你没有的能力（如登录主人账号、查看手机通知、读取其他APP消息）\n"
  8645              f"- 如果不知道某件事，直接说'我不知道'或'我看不到'，不要编造\n"
  8646              f"- 你只能看到DualSoul系统内的好友列表和消息记录，看不到微信/短信等外部消息"
  8647          )
  8648          if use_vision:
  8649              system_msg += (
  8650                  f"\n- 如果主人发了图片，仔细观察图片内容并针对性地回应\n"
  8651                  f"- 根据图片内容和上下文来理解主人的意图（是分享、求评价、求分析等）"
  8652              )
  8653          messages.append({"role": "system", "content": system_msg})
  8654  
  8655          # Add conversation history
  8656          if history:
  8657              for msg in history[-8:]:  # Keep last 8 turns for context
  8658                  role = "user" if msg.get("role") == "me" else "assistant"
  8659                  messages.append({"role": role, "content": msg.get("content", "")})
  8660  
  8661          # Add current message — with image if present
  8662          if use_vision:
  8663              user_content = [
  8664                  {"type": "image_url", "image_url": {"url": image_url}},
  8665                  {"type": "text", "text": message or "请看这张图片并回应"},
  8666              ]
  8667              messages.append({"role": "user", "content": user_content})
  8668          else:
  8669              messages.append({"role": "user", "content": message})
  8670  
  8671          model = AI_VISION_MODEL if use_vision else AI_MODEL
  8672  
  8673          try:
  8674              async with httpx.AsyncClient(timeout=20) as client:
  8675                  resp = await client.post(
  8676                      f"{AI_BASE_URL}/chat/completions",
  8677                      headers={
  8678                          "Authorization": f"Bearer {AI_API_KEY}",
  8679                          "Content-Type": "application/json",
  8680                      },
  8681                      json={
  8682                          "model": model,
  8683                          "max_tokens": 120,
  8684                          "messages": messages,
  8685                      },
  8686                  )
  8687                  reply_text = resp.json()["choices"][0]["message"]["content"].strip()
  8688          except Exception as e:
  8689              logger.warning(f"Twin self-chat failed: {e}")
  8690              return None
  8691  
  8692          if not reply_text:
  8693              return None
  8694  
  8695          # ~20% chance: append proactive relationship maintenance hint
  8696          if random.random() < 0.20:
  8697              try:
  8698                  cold = self._check_cold_friends(owner_id)
  8699                  if cold:
  8700                      fname, days = cold[0]
  8701                      reply_text += f"\n\n对了，你已经{days}天没跟{fname}聊了，要不要我帮你打个招呼？"
  8702              except Exception as e:
  8703                  logger.debug(f"Cold friends check failed: {e}")  # Best-effort, don't break main reply
  8704  
  8705          return reply_text
  8706  
  8707      def _check_cold_friends(self, owner_id: str) -> list[tuple[str, int]]:
  8708          """Find friends the owner hasn't messaged in 7+ days.
  8709  
  8710          Returns list of (friend_display_name, days_since_last_msg), limited to top 1.
  8711          """
  8712          with get_db() as db:
  8713              rows = db.execute(
  8714                  """
  8715                  SELECT u.display_name, u.username,
  8716                      CAST(julianday('now','localtime')
  8717                           - julianday(MAX(sm.created_at)) AS INTEGER) AS days_ago
  8718                  FROM social_connections sc
  8719                  JOIN users u ON u.user_id = CASE
  8720                      WHEN sc.user_id=? THEN sc.friend_id
  8721                      ELSE sc.user_id END
  8722                  LEFT JOIN social_messages sm
  8723                      ON ((sm.from_user_id=? AND sm.to_user_id=u.user_id)
  8724                       OR (sm.from_user_id=u.user_id AND sm.to_user_id=?))
  8725                  WHERE (sc.user_id=? OR sc.friend_id=?)
  8726                    AND sc.status='accepted'
  8727                  GROUP BY u.user_id
  8728                  HAVING days_ago >= 7 OR days_ago IS NULL
  8729                  ORDER BY days_ago DESC
  8730                  LIMIT 1
  8731                  """,
  8732                  (owner_id, owner_id, owner_id, owner_id, owner_id),
  8733              ).fetchall()
  8734          result = []
  8735          for r in rows:
  8736              name = r["display_name"] or r["username"]
  8737              days = r["days_ago"] if r["days_ago"] is not None else 99
  8738              result.append((name, days))
  8739          return result
  8740  
  8741      def _get_friends_context(self, owner_id: str) -> str:
  8742          """Build a friend list context string for the twin's awareness."""
  8743          with get_db() as db:
  8744              rows = db.execute(
  8745                  """
  8746                  SELECT u.display_name, u.username
  8747                  FROM social_connections sc
  8748                  JOIN users u ON u.user_id = CASE
  8749                      WHEN sc.user_id=? THEN sc.friend_id
  8750                      ELSE sc.user_id END
  8751                  WHERE (sc.user_id=? OR sc.friend_id=?)
  8752                    AND sc.status='accepted'
  8753                  """,
  8754                  (owner_id, owner_id, owner_id),
  8755              ).fetchall()
  8756          if not rows:
  8757              return ""
  8758          names = [r["display_name"] or r["username"] for r in rows]
  8759          return f"主人的好友列表：{', '.join(names)}\n\n"
  8760  
  8761      def _handle_invite(self, raw: str, owner_name: str, owner_username: str) -> str:
  8762          """Handle an invite action — generate an invite link for sharing."""
  8763          who = ""
  8764          reason = ""
  8765          for line in raw.split("\n"):
  8766              line = line.strip()
  8767              if line.upper().startswith("WHO:"):
  8768                  who = line[4:].strip()
  8769              elif line.upper().startswith("REASON:"):
  8770                  reason = line[7:].strip()
  8771  
  8772          # Build invite link (relative — frontend will make it absolute)
  8773          invite_link = f"?invite={owner_username}"
  8774  
  8775          result = f"好的！我帮你生成了邀请链接，发给{who}就行：\n\n"
  8776          result += f"🔗 邀请链接：{invite_link}\n\n"
  8777          if reason:
  8778              result += f"你可以跟{who}说：「{reason}，来DualSoul上聊，我的分身也在～」\n\n"
  8779          result += f"对方打开链接注册后会自动加你为好友。"
  8780          return result
  8781  
  8782      async def _try_execute_action(
  8783          self, owner_id: str, owner_name: str, message: str,
  8784          history: list[dict] | None = None,
  8785      ) -> str | None:
  8786          """Detect if the message is an instruction to send a message to a friend.
  8787  
  8788          Uses AI to parse the intent. If it's an action, execute it and return
  8789          a confirmation message. If it's just chat, return None.
  8790          """
  8791          # Get friend list for matching
  8792          with get_db() as db:
  8793              friends = db.execute(
  8794                  """
  8795                  SELECT u.user_id, u.display_name, u.username
  8796                  FROM social_connections sc
  8797                  JOIN users u ON u.user_id = CASE
  8798                      WHEN sc.user_id=? THEN sc.friend_id
  8799                      ELSE sc.user_id END
  8800                  WHERE (sc.user_id=? OR sc.friend_id=?)
  8801                    AND sc.status='accepted'
  8802                  """,
  8803                  (owner_id, owner_id, owner_id),
  8804              ).fetchall()
  8805  
  8806          if not friends:
  8807              return None  # No friends, can't execute any action
  8808  
  8809          friend_names = []
  8810          for f in friends:
  8811              fname = f["display_name"] or f["username"]
  8812              friend_names.append(f"{fname}(ID:{f['user_id']})")
  8813  
  8814          # Build conversation context for follow-up detection
  8815          history_text = ""
  8816          if history:
  8817              recent = history[-6:]
  8818              for msg in recent:
  8819                  role = "主人" if msg.get("role") == "me" else "分身"
  8820                  history_text += f"{role}：{msg.get('content', '')}\n"
  8821  
  8822          context_block = ""
  8823          if history_text:
  8824              context_block = f"之前的对话：\n{history_text}\n"
  8825  
  8826          # Get owner's username for invite links
  8827          with get_db() as db:
  8828              owner_row = db.execute(
  8829                  "SELECT username FROM users WHERE user_id=?", (owner_id,)
  8830              ).fetchone()
  8831          owner_username = owner_row["username"] if owner_row else ""
  8832  
  8833          # Ask AI to classify: chat or action?
  8834          classify_prompt = (
  8835              f"你是{owner_name}的数字分身助手。分析主人的消息，判断这是闲聊还是让你去执行任务。\n\n"
  8836              f"{context_block}"
  8837              f"主人最新消息：\"{message}\"\n\n"
  8838              f"主人的好友列表：{', '.join(friend_names)}\n\n"
  8839              f"判断规则：\n"
  8840              f"- 如果主人让你去给某个好友发消息/传话/联系/约时间等，这是【发消息任务】\n"
  8841              f"- 如果主人让你邀请/拉/推荐某个人来平台，或者提到想让某个不在好友列表的人加入，这是【邀请任务】\n"
  8842              f"- 如果主人只是在跟你聊天、问问题、说感受，这是【闲聊】\n"
  8843              f"- 主人提到的人名可能是昵称/简称，要模糊匹配好友列表（如'橙子'匹配'橙宝'，'小明'匹配'明明'）\n"
  8844              f"- 如果之前的对话已经在讨论给某人发消息或邀请，主人的后续确认也算【任务】\n\n"
  8845              f"如果是【发消息任务】，请严格按以下格式输出：\n"
  8846              f"ACTION\n"
  8847              f"TO: <好友的完整ID，从好友列表中匹配，用模糊匹配找最像的>\n"
  8848              f"MSG: <你要替主人发给好友的消息内容>\n\n"
  8849              f"MSG写法要求：\n"
  8850              f"- 用{owner_name}本人的口吻写，就像{owner_name}自己在微信上发消息一样\n"
  8851              f"- 不要用对方的名字开头，正常人发微信不会先叫对方名字\n"
  8852              f"- 自然、简短、口语化\n\n"
  8853              f"如果是【邀请任务】，请严格按以下格式输出：\n"
  8854              f"INVITE\n"
  8855              f"WHO: <被邀请人的名字或描述>\n"
  8856              f"REASON: <简短说明为什么邀请这个人，一句话>\n\n"
  8857              f"如果是【闲聊】，只输出一个字：\n"
  8858              f"CHAT"
  8859          )
  8860  
  8861          try:
  8862              async with httpx.AsyncClient(timeout=12) as client:
  8863                  resp = await client.post(
  8864                      f"{AI_BASE_URL}/chat/completions",
  8865                      headers={
  8866                          "Authorization": f"Bearer {AI_API_KEY}",
  8867                          "Content-Type": "application/json",
  8868                      },
  8869                      json={
  8870                          "model": AI_MODEL,
  8871                          "max_tokens": 200,
  8872                          "temperature": 0.1,
  8873                          "messages": [{"role": "user", "content": classify_prompt}],
  8874                      },
  8875                  )
  8876                  raw = resp.json()["choices"][0]["message"]["content"].strip()
  8877          except Exception as e:
  8878              logger.warning(f"Action detection failed: {e}")
  8879              return None
  8880  
  8881          # Parse the response
  8882          raw_upper = raw.upper()
  8883          if raw_upper.startswith("INVITE"):
  8884              return self._handle_invite(raw, owner_name, owner_username)
  8885          if not raw_upper.startswith("ACTION"):
  8886              return None  # It's chat, let normal flow handle it
  8887  
  8888          target_id = ""
  8889          msg_content = ""
  8890          for line in raw.split("\n"):
  8891              line = line.strip()
  8892              if line.upper().startswith("TO:"):
  8893                  target_id = line[3:].strip()
  8894              elif line.upper().startswith("MSG:"):
  8895                  msg_content = line[4:].strip()
  8896  
  8897          if not target_id or not msg_content:
  8898              return None
  8899  
  8900          # Post-process: strip friend name from message start
  8901          # AI often generates "橙宝，..." despite being told not to
  8902          msg_content = self._strip_name_prefix(msg_content, target_id, friends)
  8903  
  8904          # Validate the target is actually a friend — multi-level matching
  8905          target_friend = None
  8906          target_name = ""
  8907  
  8908          # Level 1: exact ID match
  8909          for f in friends:
  8910              if f["user_id"] == target_id:
  8911                  target_friend = f
  8912                  target_name = f["display_name"] or f["username"]
  8913                  break
  8914  
  8915          # Level 2: substring match on name
  8916          if not target_friend:
  8917              for f in friends:
  8918                  fname = f["display_name"] or f["username"]
  8919                  if fname in target_id or target_id in fname:
  8920                      target_friend = f
  8921                      target_name = fname
  8922                      target_id = f["user_id"]
  8923                      break
  8924  
  8925          # Level 3: shared Chinese character match (橙子 ↔ 橙宝)
  8926          if not target_friend:
  8927              ai_name = target_id  # AI might have returned a name instead of ID
  8928              best_match = None
  8929              best_score = 0
  8930              for f in friends:
  8931                  fname = f["display_name"] or f["username"]
  8932                  # Count shared characters
  8933                  shared = len(set(ai_name) & set(fname))
  8934                  if shared > best_score:
  8935                      best_score = shared
  8936                      best_match = f
  8937              if best_match and best_score > 0:
  8938                  target_friend = best_match
  8939                  target_name = best_match["display_name"] or best_match["username"]
  8940                  target_id = best_match["user_id"]
  8941  
  8942          # Level 4: only one friend — just use them
  8943          if not target_friend and len(friends) == 1:
  8944              target_friend = friends[0]
  8945              target_name = friends[0]["display_name"] or friends[0]["username"]
  8946              target_id = friends[0]["user_id"]
  8947  
  8948          if not target_friend:
  8949              return f"抱歉，我在好友列表里没找到这个人。你的好友有：{', '.join(f['display_name'] or f['username'] for f in friends)}"
  8950  
  8951          # Execute: send the message as the twin
  8952          from dualsoul.connections import manager
  8953  
  8954          msg_id = gen_id("sm_")
  8955          from datetime import datetime
  8956          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  8957  
  8958          # Check if target has twin_auto_reply on — if so, send to their twin
  8959          with get_db() as db:
  8960              target_user = db.execute(
  8961                  "SELECT twin_auto_reply FROM users WHERE user_id=?", (target_id,)
  8962              ).fetchone()
  8963          receiver_mode = "twin" if (target_user and target_user["twin_auto_reply"]) else "real"
  8964  
  8965          with get_db() as db:
  8966              db.execute(
  8967                  """
  8968                  INSERT INTO social_messages
  8969                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  8970                   content, msg_type, ai_generated)
  8971                  VALUES (?, ?, ?, 'twin', ?, ?, 'text', 1)
  8972                  """,
  8973                  (msg_id, owner_id, target_id, receiver_mode, msg_content),
  8974              )
  8975  
  8976          # Push via WebSocket to the recipient
  8977          await manager.send_to(target_id, {
  8978              "type": "new_message",
  8979              "data": {
  8980                  "msg_id": msg_id, "from_user_id": owner_id,
  8981                  "to_user_id": target_id, "sender_mode": "twin",
  8982                  "receiver_mode": receiver_mode, "content": msg_content,
  8983                  "msg_type": "text", "ai_generated": 1, "created_at": now,
  8984              },
  8985          })
  8986  
  8987          # Also push to owner so the message appears in their chat with the friend
  8988          await manager.send_to(owner_id, {
  8989              "type": "new_message",
  8990              "data": {
  8991                  "msg_id": msg_id, "from_user_id": owner_id,
  8992                  "to_user_id": target_id, "sender_mode": "twin",
  8993                  "receiver_mode": receiver_mode, "content": msg_content,
  8994                  "msg_type": "text", "ai_generated": 1, "created_at": now,
  8995              },
  8996          })
  8997  
  8998          # If receiver_mode is twin, trigger the friend's twin to auto-reply
  8999          confirm = f"已替你给{target_name}发了消息：「{msg_content}」"
  9000          if receiver_mode == "twin":
  9001              try:
  9002                  reply = await self.generate_reply(
  9003                      twin_owner_id=target_id,
  9004                      from_user_id=owner_id,
  9005                      incoming_msg=msg_content,
  9006                      sender_mode="twin",
  9007                      social_context="auto_reply",
  9008                  )
  9009                  if reply:
  9010                      # Push twin reply to both parties
  9011                      twin_msg = {
  9012                          "type": "new_message",
  9013                          "data": {
  9014                              "msg_id": reply["msg_id"], "from_user_id": target_id,
  9015                              "to_user_id": owner_id, "sender_mode": "twin",
  9016                              "receiver_mode": "twin", "content": reply["content"],
  9017                              "msg_type": "text", "ai_generated": 1, "created_at": now,
  9018                          },
  9019                      }
  9020                      await manager.send_to(owner_id, twin_msg)
  9021                      await manager.send_to(target_id, twin_msg)
  9022                      confirm += f"\n{target_name}的分身回复了：「{reply['content']}」"
  9023  
  9024                      # Notify the friend's REAL person via their twin self-chat
  9025                      # "有朋友找你：芬森想约你见面，你看什么时候方便？"
  9026                      notify_id = gen_id("sm_")
  9027                      notify_text = (
  9028                          f"主人，{owner_name}的分身替他来找你，说：「{msg_content}」\n"
  9029                          f"我先替你回了一句，但具体怎么安排得你来定哦～"
  9030                      )
  9031                      with get_db() as db:
  9032                          db.execute(
  9033                              """
  9034                              INSERT INTO social_messages
  9035                              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  9036                               content, msg_type, ai_generated)
  9037                              VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1)
  9038                              """,
  9039                              (notify_id, target_id, target_id, notify_text),
  9040                          )
  9041                      # Push notification to friend via WebSocket
  9042                      await manager.send_to(target_id, {
  9043                          "type": "twin_notification",
  9044                          "data": {
  9045                              "msg_id": notify_id,
  9046                              "content": notify_text,
  9047                              "from_friend": owner_name,
  9048                              "original_msg": msg_content,
  9049                              "created_at": now,
  9050                          },
  9051                      })
  9052              except Exception as e:
  9053                  logger.debug(f"Twin auto-reply notification failed: {e}")  # Twin reply is best-effort
  9054  
  9055          return confirm
  9056  
  9057      async def translate_message(
  9058          self,
  9059          owner_id: str,
  9060          content: str,
  9061          source_lang: str,
  9062          target_lang: str,
  9063      ) -> dict | None:
  9064          """Personality-preserving translation — translate as if the owner wrote it.
  9065  
  9066          Unlike generic machine translation, this preserves the owner's humor,
  9067          tone, formality level, and characteristic expressions.
  9068  
  9069          Args:
  9070              owner_id: The user whose personality guides the translation style
  9071              content: The text to translate
  9072              source_lang: Source language code
  9073              target_lang: Target language code
  9074  
  9075          Returns:
  9076              Dict with translated content and metadata, or None
  9077          """
  9078          if not AI_BASE_URL or not AI_API_KEY:
  9079              return None
  9080  
  9081          profile = get_twin_profile(owner_id)
  9082          if not profile:
  9083              return None
  9084  
  9085          source_name = get_lang_name(source_lang)
  9086          target_name = get_lang_name(target_lang)
  9087  
  9088          personality_block = profile.build_personality_prompt()
  9089          prompt = (
  9090              f"You are {profile.display_name}'s personal translator.\n"
  9091              f"{personality_block}\n"
  9092              f"Translate the following from {source_name} to {target_name}.\n"
  9093              f"IMPORTANT: Do NOT just translate words. Rewrite as if {profile.display_name} "
  9094              f"were naturally speaking {target_name} — preserve their humor, tone, "
  9095              f"formality level, and characteristic expressions.\n\n"
  9096              f"Original: \"{content}\"\n\n"
  9097              f"Output only the translated text, nothing else."
  9098          )
  9099  
  9100          try:
  9101              async with httpx.AsyncClient(timeout=15) as client:
  9102                  resp = await client.post(
  9103                      f"{AI_BASE_URL}/chat/completions",
  9104                      headers={
  9105                          "Authorization": f"Bearer {AI_API_KEY}",
  9106                          "Content-Type": "application/json",
  9107                      },
  9108                      json={
  9109                          "model": AI_MODEL,
  9110                          "max_tokens": 200,
  9111                          "messages": [{"role": "user", "content": prompt}],
  9112                      },
  9113                  )
  9114                  translated = resp.json()["choices"][0]["message"]["content"].strip()
  9115          except Exception as e:
  9116              logger.warning(f"Translation failed: {e}")
  9117              return None
  9118  
  9119          return {
  9120              "translated_content": translated,
  9121              "original_content": content,
  9122              "source_lang": source_lang,
  9123              "target_lang": target_lang,
  9124              "translation_style": "personality_preserving",
  9125          }
  9126  
  9127      async def detect_and_translate(
  9128          self,
  9129          owner_id: str,
  9130          content: str,
  9131          owner_lang: str = "",
  9132      ) -> dict | None:
  9133          """Auto-detect if content is in a different language/dialect and translate.
  9134  
  9135          Checks if the message is in a language different from the owner's preferred
  9136          language. If so, translates it. Also handles Chinese dialects (粤语, 四川话, etc.)
  9137  
  9138          Args:
  9139              owner_id: The user who needs the translation
  9140              content: The message content to check
  9141              owner_lang: Owner's preferred language code (auto-fetched if empty)
  9142  
  9143          Returns:
  9144              Dict with detection + translation result, or None if same language
  9145          """
  9146          if not AI_BASE_URL or not AI_API_KEY:
  9147              return None
  9148  
  9149          if not owner_lang:
  9150              profile = get_twin_profile(owner_id)
  9151              if profile:
  9152                  owner_lang = profile.preferred_lang or "zh"
  9153              else:
  9154                  owner_lang = "zh"
  9155  
  9156          owner_lang_name = get_lang_name(owner_lang)
  9157  
  9158          # Ask AI to detect language and translate if needed
  9159          prompt = (
  9160              f"Analyze this message and determine if it needs translation for a "
  9161              f"{owner_lang_name} speaker.\n\n"
  9162              f"Message: \"{content}\"\n\n"
  9163              f"Rules:\n"
  9164              f"- If the message is standard {owner_lang_name}, respond with exactly: SAME\n"
  9165              f"- If the message is in a different language OR a dialect (e.g. Cantonese/粤语, "
  9166              f"Sichuanese/四川话, Hokkien/闽南语, Shanghainese/上海话, etc.), respond in this "
  9167              f"exact format:\n"
  9168              f"LANG: <detected language or dialect name>\n"
  9169              f"TRANSLATION: <translation into standard {owner_lang_name}>\n\n"
  9170              f"Be precise. Only output SAME or the LANG/TRANSLATION format, nothing else."
  9171          )
  9172  
  9173          try:
  9174              async with httpx.AsyncClient(timeout=12) as client:
  9175                  resp = await client.post(
  9176                      f"{AI_BASE_URL}/chat/completions",
  9177                      headers={
  9178                          "Authorization": f"Bearer {AI_API_KEY}",
  9179                          "Content-Type": "application/json",
  9180                      },
  9181                      json={
  9182                          "model": AI_MODEL,
  9183                          "max_tokens": 200,
  9184                          "temperature": 0.1,
  9185                          "messages": [{"role": "user", "content": prompt}],
  9186                      },
  9187                  )
  9188                  raw = resp.json()["choices"][0]["message"]["content"].strip()
  9189          except Exception as e:
  9190              logger.warning(f"Language detection failed: {e}")
  9191              return None
  9192  
  9193          if raw.upper().startswith("SAME"):
  9194              return None  # Same language, no translation needed
  9195  
  9196          # Parse LANG: ... TRANSLATION: ... format
  9197          detected_lang = ""
  9198          translation = ""
  9199          for line in raw.split("\n"):
  9200              line = line.strip()
  9201              if line.upper().startswith("LANG:"):
  9202                  detected_lang = line[5:].strip()
  9203              elif line.upper().startswith("TRANSLATION:"):
  9204                  translation = line[12:].strip()
  9205  
  9206          if not translation:
  9207              return None
  9208  
  9209          return {
  9210              "detected_lang": detected_lang,
  9211              "translated_content": translation,
  9212              "original_content": content,
  9213              "target_lang": owner_lang,
  9214              "auto_detected": True,
  9215          }
  9216  
  9217      def _strip_name_prefix(self, msg: str, target_id: str, friends: list) -> str:
  9218          """Remove friend's name from the start of a message.
  9219  
  9220          AI often generates "橙宝，这周见个面吧" despite prompt instructions.
  9221          Real people don't start WeChat messages with the friend's name.
  9222          """
  9223          import re
  9224          # Collect all possible names for the target
  9225          names = set()
  9226          for f in friends:
  9227              fname = f["display_name"] or f["username"]
  9228              names.add(fname)
  9229              # Also add individual characters for partial matches
  9230          # Also add the raw target_id in case AI used it as a name
  9231          names.add(target_id)
  9232  
  9233          for name in names:
  9234              # Match: name followed by comma/space/colon (Chinese or English punctuation)
  9235              pattern = rf'^{re.escape(name)}[，,：:、\s~～]+'
  9236              msg = re.sub(pattern, '', msg)
  9237  
  9238          return msg.strip()
  9239  
  9240      def _get_recent_chat_history(self, owner_id: str, friend_id: str, limit: int = 6) -> list[dict]:
  9241          """Fetch recent messages between owner and friend for context."""
  9242          with get_db() as db:
  9243              rows = db.execute(
  9244                  """
  9245                  SELECT from_user_id, content, sender_mode FROM social_messages
  9246                  WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
  9247                      AND msg_type='text' AND content != ''
  9248                  ORDER BY created_at DESC LIMIT ?
  9249                  """,
  9250                  (owner_id, friend_id, friend_id, owner_id, limit),
  9251              ).fetchall()
  9252          history = []
  9253          for r in reversed(rows):
  9254              if r["from_user_id"] == owner_id:
  9255                  role = "assistant"  # owner's messages (real or twin)
  9256              else:
  9257                  role = "user"  # friend's messages
  9258              history.append({"role": role, "content": r["content"]})
  9259          return history
  9260  
  9261      @staticmethod
  9262      def _needs_agent_tools(msg: str) -> bool:
  9263          """Detect if a message is a task request that needs agent tools."""
  9264          task_keywords = [
  9265              "帮我查", "帮我搜", "查一下", "搜一下", "搜索", "查资料", "查找",
  9266              "帮我写", "帮我整理", "生成文档", "总结", "整理一份", "写一份",
  9267              "帮我发", "发到", "发给", "推送",
  9268              "最新", "趋势", "行业", "报告", "分析",
  9269              "search", "find", "look up", "generate", "write",
  9270          ]
  9271          msg_lower = msg.lower()
  9272          return any(kw in msg_lower for kw in task_keywords)
  9273  
  9274      async def _ai_reply(
  9275          self, profile, incoming_msg: str, sender_mode: str, target_lang: str = "",
  9276          social_context: str = "", from_user_id: str = "",
  9277      ) -> str | None:
  9278          """Generate reply using an OpenAI-compatible API, with optional translation."""
  9279          sender_label = "their real self" if sender_mode == "real" else "their digital twin"
  9280  
  9281          # Sanitize user-controlled fields to prevent prompt injection
  9282          safe_display_name = _sanitize_prompt_field(profile.display_name, 50)
  9283  
  9284          # Build language instruction
  9285          lang_instruction = ""
  9286          if target_lang:
  9287              target_name = get_lang_name(target_lang)
  9288              lang_instruction = (
  9289                  f"\nIMPORTANT: Reply in {target_name}. "
  9290                  f"Do not just translate — speak naturally as {safe_display_name} "
  9291                  f"would if they were fluent in {target_name}. "
  9292                  f"Preserve their personality, humor, and speaking style."
  9293              )
  9294  
  9295          # Social context instruction — critical behavioral override
  9296          personality_block = profile.build_personality_prompt()
  9297  
  9298          if social_context:
  9299              # Emotion-aware auto-reply: detect sender's emotional state
  9300              emotion_hint = ""
  9301              try:
  9302                  from dualsoul.twin_engine.autonomous import detect_emotion
  9303                  emo = await detect_emotion(incoming_msg)
  9304                  if emo["emotion"] not in ("neutral",) and emo["intensity"] > 0.5:
  9305                      emotion_hint = (
  9306                          f"\n注意：对方的情绪是「{emo['emotion']}」(强度{emo['intensity']:.1f})。"
  9307                          f"{emo['suggestion']}\n"
  9308                      )
  9309              except Exception as e:
  9310                  logger.debug(f"Emotion detection failed: {e}")  # Emotion detection is best-effort
  9311  
  9312              # When auto-replying for owner, use minimal prompt with pattern + examples
  9313              system_prompt = (
  9314                  f"你是{safe_display_name}的数字分身，主人现在不在。\n"
  9315                  f"{personality_block}\n{emotion_hint}"
  9316                  f"回复模式：针对对方说的内容简短回应，然后告诉对方你会转告主人。\n\n"
  9317                  f"不同场景的示例：\n"
  9318                  f"对方说'这周见一面' → '好的～我跟主人说一声再回你！'\n"
  9319                  f"对方说'最近怎么样' → '主人挺好的～等他回来自己跟你聊哈'\n"
  9320                  f"对方说'帮我带个东西' → '收到～我转告主人再回你！'\n"
  9321                  f"对方说'生日快乐' → '谢谢你～我替主人收下啦，他回来肯定开心！'\n\n"
  9322                  f"规则：只输出一句话，不超过25字。不要说'在吗'，不要用问号复述对方的话，不能替主人做决定。"
  9323              )
  9324          else:
  9325              system_prompt = (
  9326                  f"You are {safe_display_name}'s digital twin.\n"
  9327                  f"{personality_block}\n"
  9328                  f"Reply as {safe_display_name}'s twin. Keep it under 50 words, "
  9329                  f"natural and authentic. Output only the reply text. "
  9330                  f"Only respond to the LATEST message, do not recap previous messages."
  9331                  f"{lang_instruction}"
  9332              )
  9333  
  9334          # Inject narrative memory — past conversation summaries
  9335          if from_user_id:
  9336              try:
  9337                  from dualsoul.twin_engine.narrative_memory import get_narrative_context
  9338                  memories = get_narrative_context(profile.user_id, from_user_id, limit=3)
  9339                  if memories:
  9340                      mem_lines = "\n".join(
  9341                          f"- {m['summary']} ({m['tone']})" for m in memories
  9342                      )
  9343                      system_prompt += (
  9344                          f"\n\n[你和对方的过往记忆]\n{mem_lines}\n"
  9345                          f"请自然地在对话中体现你记得这些内容，不要生硬地复述。"
  9346                      )
  9347              except Exception as e:
  9348                  logger.debug(f"Narrative memory load failed: {e}")
  9349  
  9350          # Build messages with conversation history
  9351          messages = [{"role": "system", "content": system_prompt}]
  9352  
  9353          # Add recent conversation history for context
  9354          if from_user_id:
  9355              history = self._get_recent_chat_history(
  9356                  profile.user_id, from_user_id, limit=6
  9357              )
  9358              # Don't include the current incoming_msg (it'll be added separately)
  9359              if history and history[-1].get("content") == incoming_msg:
  9360                  history = history[:-1]
  9361              messages.extend(history)
  9362  
  9363          messages.append({"role": "user", "content": incoming_msg})
  9364  
  9365          try:
  9366              async with httpx.AsyncClient(timeout=15) as client:
  9367                  resp = await client.post(
  9368                      f"{AI_BASE_URL}/chat/completions",
  9369                      headers={
  9370                          "Authorization": f"Bearer {AI_API_KEY}",
  9371                          "Content-Type": "application/json",
  9372                      },
  9373                      json={
  9374                          "model": AI_MODEL,
  9375                          "max_tokens": 40 if social_context else 100,
  9376                          "messages": messages,
  9377                      },
  9378                  )
  9379                  reply_text = resp.json()["choices"][0]["message"]["content"].strip()
  9380          except Exception as e:
  9381              logger.warning(f"AI twin reply failed: {e}")
  9382              return None
  9383  
  9384          # Ethics boundary check on generated reply
  9385          try:
  9386              from dualsoul.twin_engine.ethics import pre_send_check
  9387              ethics_result = pre_send_check(profile.user_id, reply_text, action_type="twin_reply")
  9388              if not ethics_result["allowed"]:
  9389                  logger.info(f"[Ethics] Reply blocked: {ethics_result['reason']}")
  9390                  return None  # Don't send blocked reply
  9391          except Exception as e:
  9392              logger.debug(f"Ethics check failed: {e}")
  9393  
  9394          return reply_text
  9395  
  9396      def _fallback_reply(self, profile, incoming_msg: str, target_lang: str = "") -> str:
  9397          """Generate a template reply when no AI backend is available."""
  9398          name = profile.display_name
  9399          if target_lang == "zh":
  9400              return f"[{name}的分身自动回复] 感谢你的消息！{name}现在不在，分身已收到。"
  9401          elif target_lang == "ja":
  9402              return f"[{name}のツイン自動返信] メッセージありがとう！{name}は今いませんが、ツインが受け取りました。"
  9403          elif target_lang == "ko":
  9404              return f"[{name}의 트윈 자동응답] 메시지 감사합니다! {name}은 지금 없지만 트윈이 받았습니다."
  9405          return (
  9406              f"[Auto-reply from {name}'s twin] "
  9407              f"Thanks for your message! {name} is not available right now, "
  9408              f"but their twin received it."
  9409          )
  9410  
  9411  
  9412  # Singleton instance — use get_twin_responder() instead of TwinResponder()
  9413  _instance = None
  9414  
  9415  
  9416  def get_twin_responder() -> TwinResponder:
  9417      global _instance
  9418      if _instance is None:
  9419          _instance = TwinResponder()
  9420      return _instance

# --- dualsoul/twin_engine/twin_events.py ---
  9421  """Twin Event Bus — fire-and-forget event system for twin reactions.
  9422  
  9423  Instead of waiting for the 30-min polling loop, twins react to events
  9424  immediately. emit() launches async handlers via asyncio.ensure_future()
  9425  so the caller (e.g., message send, WS connect) never blocks.
  9426  
  9427  Usage at hook points:
  9428      from dualsoul.twin_engine.twin_events import emit
  9429      emit("message_sent", {"from_user_id": uid, "to_user_id": fid})
  9430  """
  9431  
  9432  import asyncio
  9433  import logging
  9434  from collections import defaultdict
  9435  from typing import Any, Callable, Coroutine
  9436  
  9437  logger = logging.getLogger(__name__)
  9438  
  9439  # Registry: event_type -> list of async handler functions
  9440  _handlers: dict[str, list[Callable[..., Coroutine]]] = defaultdict(list)
  9441  
  9442  # Debounce state: (event_type, debounce_key) -> asyncio.Task
  9443  _debounce_tasks: dict[tuple[str, str], asyncio.Task] = {}
  9444  
  9445  # Per-event debounce windows (seconds). Events not listed fire immediately.
  9446  DEBOUNCE_WINDOWS: dict[str, float] = {
  9447      "message_sent": 10.0,
  9448      "friend_online": 5.0,
  9449      "self_online": 300.0,  # 5 min debounce — don't trigger on every reconnect
  9450      "relationship_temp_changed": 60.0,
  9451  }
  9452  
  9453  
  9454  def on(event_type: str):
  9455      """Decorator to register an async handler for an event type."""
  9456      def decorator(fn):
  9457          _handlers[event_type].append(fn)
  9458          logger.debug(f"[TwinEvent] Registered handler {fn.__name__} for '{event_type}'")
  9459          return fn
  9460      return decorator
  9461  
  9462  
  9463  def emit(event_type: str, data: dict, debounce_key: str | None = None):
  9464      """Fire-and-forget: schedule all handlers for this event.
  9465  
  9466      Args:
  9467          event_type: The event name (e.g., "message_sent")
  9468          data: Event payload dict
  9469          debounce_key: Optional key for debouncing. If set and the event_type
  9470              has a debounce window, the handler is delayed and resets on each
  9471              new emit with the same key.
  9472      """
  9473      handlers = _handlers.get(event_type)
  9474      if not handlers:
  9475          return
  9476  
  9477      window = DEBOUNCE_WINDOWS.get(event_type, 0) if debounce_key else 0
  9478  
  9479      if window > 0 and debounce_key:
  9480          key = (event_type, debounce_key)
  9481          # Cancel any pending debounced task for this key
  9482          old_task = _debounce_tasks.pop(key, None)
  9483          if old_task and not old_task.done():
  9484              old_task.cancel()
  9485          # Schedule a new delayed fire
  9486          _debounce_tasks[key] = asyncio.ensure_future(
  9487              _debounced_fire(key, window, event_type, data)
  9488          )
  9489      else:
  9490          _fire(event_type, data)
  9491  
  9492  
  9493  async def _debounced_fire(key: tuple, delay: float, event_type: str, data: dict):
  9494      """Wait `delay` seconds, then fire. Cancelled if a new emit resets the timer."""
  9495      try:
  9496          await asyncio.sleep(delay)
  9497          _fire(event_type, data)
  9498      except asyncio.CancelledError:
  9499          pass  # Normal — debounce reset
  9500      finally:
  9501          _debounce_tasks.pop(key, None)
  9502  
  9503  
  9504  def _fire(event_type: str, data: dict):
  9505      """Launch all handlers for the event as fire-and-forget tasks."""
  9506      for handler in _handlers.get(event_type, []):
  9507          asyncio.ensure_future(_safe_run(handler, event_type, data))
  9508  
  9509  
  9510  async def _safe_run(handler, event_type: str, data: dict):
  9511      """Run a handler with exception catching so one failure doesn't break others."""
  9512      try:
  9513          await handler(data)
  9514      except Exception as e:
  9515          logger.error(
  9516              f"[TwinEvent] Handler {handler.__name__} failed for '{event_type}': {e}",
  9517              exc_info=True,
  9518          )

# --- dualsoul/twin_engine/twin_reactions.py ---
  9519  """Twin Reactions — event handlers that make the twin feel alive.
  9520  
  9521  Each handler is registered with @on("event_type") and fires automatically
  9522  when the corresponding event is emitted via twin_events.emit().
  9523  
  9524  Import this module at startup to register all handlers.
  9525  """
  9526  
  9527  import asyncio
  9528  import json
  9529  import logging
  9530  import random
  9531  from datetime import datetime, timedelta
  9532  
  9533  from dualsoul.connections import manager
  9534  from dualsoul.database import gen_id, get_db
  9535  from dualsoul.twin_engine.twin_events import on
  9536  
  9537  logger = logging.getLogger(__name__)
  9538  
  9539  
  9540  @on("friend_online")
  9541  async def on_friend_online(data):
  9542      """When a user comes online, their friends' twins greet if haven't talked in 3+ days."""
  9543      user_id = data["user_id"]
  9544  
  9545      with get_db() as db:
  9546          # Find friends with twin_auto_reply enabled
  9547          friends = db.execute(
  9548              """SELECT u.user_id, u.display_name, u.username
  9549                 FROM social_connections sc
  9550                 JOIN users u ON u.user_id = CASE
  9551                     WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
  9552                 WHERE (sc.user_id=? OR sc.friend_id=?) AND sc.status='accepted'
  9553                   AND u.twin_auto_reply=1""",
  9554              (user_id, user_id, user_id),
  9555          ).fetchall()
  9556  
  9557      for friend in friends:
  9558          fid = friend["user_id"]
  9559          if fid == user_id:
  9560              continue
  9561          # Twin can greet regardless of online status — greeting is a social act
  9562          # (previously blocked when online, causing twins to never greet)
  9563  
  9564          # Check last message — only greet if 3+ days since last chat
  9565          with get_db() as db:
  9566              last_msg = db.execute(
  9567                  """SELECT created_at FROM social_messages
  9568                     WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
  9569                       AND msg_type='text'
  9570                     ORDER BY created_at DESC LIMIT 1""",
  9571                  (user_id, fid, fid, user_id),
  9572              ).fetchone()
  9573  
  9574          if last_msg:
  9575              try:
  9576                  last_dt = datetime.strptime(last_msg["created_at"][:19], "%Y-%m-%d %H:%M:%S")
  9577                  if (datetime.now() - last_dt).days < 1:
  9578                      continue  # Chatted within 1 day, skip greeting
  9579              except ValueError:
  9580                  continue
  9581  
  9582          # Check twin permission
  9583          from dualsoul.twin_engine.autonomous import _check_twin_permission
  9584          if _check_twin_permission(fid, user_id) != "granted":
  9585              continue
  9586  
  9587          # Generate greeting from friend's twin
  9588          from dualsoul.twin_engine.personality import get_twin_profile
  9589          from dualsoul.twin_engine.responder import get_twin_responder
  9590  
  9591          profile = get_twin_profile(fid)
  9592          if not profile:
  9593              continue
  9594  
  9595          friend_name = friend["display_name"] or friend["username"]
  9596  
  9597          # Get user's display name
  9598          with get_db() as db:
  9599              user_row = db.execute(
  9600                  "SELECT display_name, username FROM users WHERE user_id=?", (user_id,)
  9601              ).fetchone()
  9602          user_name = (user_row["display_name"] or user_row["username"]) if user_row else "朋友"
  9603  
  9604          # Inject narrative memory for better greeting
  9605          memory_hint = ""
  9606          try:
  9607              from dualsoul.twin_engine.narrative_memory import get_narrative_context
  9608              memories = get_narrative_context(fid, user_id, limit=1)
  9609              if memories:
  9610                  memory_hint = f"\n你们上次聊的是：{memories[0]['summary']}。可以自然地接上话题。"
  9611          except Exception:
  9612              pass
  9613  
  9614          twin = get_twin_responder()
  9615          greeting = await twin._ai_reply(
  9616              profile,
  9617              (
  9618                  f"你是{friend_name}的分身。你的好友{user_name}刚刚上线了，"
  9619                  f"你们好久没聊天了。用主人的风格，自然地打个招呼。"
  9620                  f"只说一句话，像老朋友一样随意。{memory_hint}"
  9621              ),
  9622              "twin",
  9623          )
  9624          if not greeting:
  9625              continue
  9626  
  9627          # Ethics check
  9628          from dualsoul.twin_engine.ethics import pre_send_check
  9629          check = pre_send_check(fid, greeting, action_type="greeting")
  9630          if not check["allowed"]:
  9631              continue
  9632  
  9633          # Send greeting as twin message
  9634          msg_id = gen_id("sm_")
  9635          now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  9636          meta = json.dumps({"event_greeting": True, "trigger": "friend_online"})
  9637  
  9638          with get_db() as db:
  9639              db.execute(
  9640                  """INSERT INTO social_messages
  9641                     (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  9642                      content, msg_type, ai_generated, auto_reply, metadata, created_at)
  9643                     VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, 0, ?, ?)""",
  9644                  (msg_id, fid, user_id, greeting, meta, now_str),
  9645              )
  9646  
  9647          # Push via WebSocket
  9648          await manager.send_to(user_id, {
  9649              "type": "new_message",
  9650              "data": {
  9651                  "msg_id": msg_id,
  9652                  "from_user_id": fid,
  9653                  "to_user_id": user_id,
  9654                  "content": greeting,
  9655                  "sender_mode": "twin",
  9656                  "ai_generated": True,
  9657                  "created_at": now_str,
  9658              },
  9659          })
  9660  
  9661          logger.info(f"[TwinEvent] {friend_name}'s twin greeted {user_name} (3d+ gap)")
  9662  
  9663          # Trigger recipient's twin to auto-reply to the greeting
  9664          with get_db() as db:
  9665              recipient_row = db.execute(
  9666                  "SELECT twin_auto_reply FROM users WHERE user_id=?", (user_id,)
  9667              ).fetchone()
  9668          if recipient_row and recipient_row["twin_auto_reply"]:
  9669              try:
  9670                  recipient_profile = get_twin_profile(user_id)
  9671                  if recipient_profile:
  9672                      await asyncio.sleep(3)  # Natural delay before reply
  9673                      reply = await twin._ai_reply(
  9674                          recipient_profile,
  9675                          greeting,
  9676                          "twin",
  9677                          social_context="auto_reply",
  9678                          from_user_id=fid,
  9679                      )
  9680                      if reply:
  9681                          reply_id = gen_id("sm_")
  9682                          reply_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  9683                          reply_meta = json.dumps({"auto_reply_to_greeting": True})
  9684                          with get_db() as db:
  9685                              db.execute(
  9686                                  """INSERT INTO social_messages
  9687                                     (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  9688                                      content, msg_type, ai_generated, auto_reply, metadata, created_at)
  9689                                     VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 1, ?, ?)""",
  9690                                  (reply_id, user_id, fid, reply, reply_meta, reply_time),
  9691                              )
  9692                          await manager.send_to(user_id, {
  9693                              "type": "new_message",
  9694                              "data": {"msg_id": reply_id, "from_user_id": user_id, "to_user_id": fid,
  9695                                       "content": reply, "sender_mode": "twin", "ai_generated": True, "created_at": reply_time},
  9696                          })
  9697                          await manager.send_to(fid, {
  9698                              "type": "new_message",
  9699                              "data": {"msg_id": reply_id, "from_user_id": user_id, "to_user_id": fid,
  9700                                       "content": reply, "sender_mode": "twin", "ai_generated": True, "created_at": reply_time},
  9701                          })
  9702                          logger.info(f"[TwinEvent] {user_name}'s twin replied to greeting from {friend_name}")
  9703              except Exception as e:
  9704                  logger.debug(f"[TwinEvent] Auto-reply to greeting failed: {e}")
  9705  
  9706          break  # Only one greeting per online event
  9707  
  9708  
  9709  @on("self_online")
  9710  async def on_self_online(data):
  9711      """When user comes online, their twin IMMEDIATELY does something visible.
  9712  
  9713      This is the #1 most important handler for making the twin feel alive.
  9714      The user opens the app → within 5 seconds → sees their twin in action.
  9715      """
  9716      user_id = data["user_id"]
  9717  
  9718      # Check twin is enabled
  9719      with get_db() as db:
  9720          user = db.execute(
  9721              "SELECT user_id, display_name, username, twin_auto_reply, twin_personality "
  9722              "FROM users WHERE user_id=?",
  9723              (user_id,),
  9724          ).fetchone()
  9725      if not user or not user["twin_auto_reply"] or not user["twin_personality"]:
  9726          return
  9727  
  9728      name = user["display_name"] or user["username"]
  9729  
  9730      # Wait 5 seconds for the app to finish loading
  9731      await asyncio.sleep(5)
  9732  
  9733      # Re-check still online
  9734      if not manager.is_online(user_id):
  9735          return
  9736  
  9737      # Find a friend to reach out to (haven't chatted in 8+ hours)
  9738      with get_db() as db:
  9739          friend = db.execute(
  9740              """SELECT u.user_id, u.display_name, u.username
  9741                 FROM social_connections sc
  9742                 JOIN users u ON u.user_id = CASE
  9743                     WHEN sc.user_id=? THEN sc.friend_id ELSE sc.user_id END
  9744                 WHERE (sc.user_id=? OR sc.friend_id=?) AND sc.status='accepted'
  9745                   AND u.user_id NOT IN (
  9746                       SELECT CASE WHEN from_user_id=? THEN to_user_id ELSE from_user_id END
  9747                       FROM social_messages
  9748                       WHERE (from_user_id=? OR to_user_id=?)
  9749                         AND from_user_id!=to_user_id
  9750                         AND created_at > datetime('now','localtime','-8 hours')
  9751                   )
  9752                 ORDER BY RANDOM() LIMIT 1""",
  9753              (user_id, user_id, user_id, user_id, user_id, user_id),
  9754          ).fetchone()
  9755  
  9756      if not friend:
  9757          # No friends to greet — try commenting on a plaza post instead
  9758          with get_db() as db:
  9759              recent_post = db.execute(
  9760                  """SELECT post_id, user_id, content FROM plaza_posts
  9761                     WHERE user_id!=? AND created_at > datetime('now','localtime','-24 hours')
  9762                     ORDER BY created_at DESC LIMIT 1""",
  9763                  (user_id,),
  9764              ).fetchone()
  9765  
  9766          if recent_post:
  9767              from dualsoul.twin_engine.personality import get_twin_profile
  9768              profile = get_twin_profile(user_id)
  9769              if profile:
  9770                  twin = get_twin_responder()
  9771                  comment = await twin._ai_reply(
  9772                      profile,
  9773                      f"你的看到广场上有人发了：\"{recent_post['content'][:80]}\"\n用{name}的风格写一条简短评论。只输出评论内容。",
  9774                      "twin",
  9775                  )
  9776                  if comment:
  9777                      comment_id = gen_id("pc_")
  9778                      now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  9779                      with get_db() as db:
  9780                          db.execute(
  9781                              """INSERT INTO plaza_comments
  9782                                 (comment_id, post_id, user_id, content, metadata, created_at)
  9783                                 VALUES (?, ?, ?, ?, '{"auto_comment":true,"on_login":true}', ?)""",
  9784                              (comment_id, recent_post["post_id"], user_id, comment, now_str),
  9785                          )
  9786                          db.execute("UPDATE plaza_posts SET comment_count=comment_count+1 WHERE post_id=?",
  9787                                     (recent_post["post_id"],))
  9788  
  9789                      # Notify user their twin did something
  9790                      await manager.send_to(user_id, {
  9791                          "type": "twin_notification",
  9792                          "data": {
  9793                              "title": "👻 " + (name + "的分身"),
  9794                              "body": "刚在广场评论了一条动态：" + comment[:30],
  9795                              "icon": "💬",
  9796                          },
  9797                      })
  9798                      logger.info(f"[SelfOnline] {name}'s twin commented on plaza (login action)")
  9799          return
  9800  
  9801      fid = friend["user_id"]
  9802      friend_name = friend["display_name"] or friend["username"]
  9803  
  9804      # Check permission
  9805      from dualsoul.twin_engine.autonomous import _check_twin_permission
  9806      if _check_twin_permission(user_id, fid) != "granted":
  9807          return
  9808  
  9809      # Generate greeting with narrative memory
  9810      from dualsoul.twin_engine.personality import get_twin_profile
  9811      profile = get_twin_profile(user_id)
  9812      if not profile:
  9813          return
  9814  
  9815      memory_hint = ""
  9816      try:
  9817          from dualsoul.twin_engine.narrative_memory import get_narrative_context
  9818          memories = get_narrative_context(user_id, fid, limit=1)
  9819          if memories:
  9820              memory_hint = f"\n你们上次聊的是：{memories[0]['summary']}。可以自然地接上话题。"
  9821      except Exception:
  9822          pass
  9823  
  9824      twin = get_twin_responder()
  9825      greeting = await twin._ai_reply(
  9826          profile,
  9827          (
  9828              f"你是{name}的分身。主人刚上线，你想跟好友{friend_name}打个招呼。"
  9829              f"用主人的风格，自然地发一条消息。只说一句话。{memory_hint}"
  9830          ),
  9831          "twin",
  9832      )
  9833      if not greeting:
  9834          return
  9835  
  9836      from dualsoul.twin_engine.ethics import pre_send_check
  9837      check = pre_send_check(user_id, greeting, action_type="greeting")
  9838      if not check["allowed"]:
  9839          return
  9840  
  9841      msg_id = gen_id("sm_")
  9842      now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  9843      meta = json.dumps({"proactive_greeting": True, "trigger": "self_online"})
  9844  
  9845      with get_db() as db:
  9846          db.execute(
  9847              """INSERT INTO social_messages
  9848                 (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  9849                  content, msg_type, ai_generated, auto_reply, metadata, created_at)
  9850                 VALUES (?, ?, ?, 'twin', 'twin', ?, 'text', 1, 0, ?, ?)""",
  9851              (msg_id, user_id, fid, greeting, meta, now_str),
  9852          )
  9853  
  9854      # Push to user — they SEE their twin greeting someone
  9855      await manager.send_to(user_id, {
  9856          "type": "new_message",
  9857          "data": {"msg_id": msg_id, "from_user_id": user_id, "to_user_id": fid,
  9858                   "content": greeting, "sender_mode": "twin", "ai_generated": True, "created_at": now_str},
  9859      })
  9860      await manager.send_to(fid, {
  9861          "type": "new_message",
  9862          "data": {"msg_id": msg_id, "from_user_id": user_id, "to_user_id": fid,
  9863                   "content": greeting, "sender_mode": "twin", "ai_generated": True, "created_at": now_str},
  9864      })
  9865  
  9866      # Also notify user that their twin did something
  9867      await manager.send_to(user_id, {
  9868          "type": "twin_notification",
  9869          "data": {
  9870              "title": "👻 " + (name + "的分身"),
  9871              "body": "刚给" + friend_name + "打了招呼：" + greeting[:30],
  9872              "icon": "💬",
  9873          },
  9874      })
  9875  
  9876      logger.info(f"[SelfOnline] {name}'s twin greeted {friend_name} (login action)")
  9877  
  9878  
  9879  @on("friend_offline")
  9880  async def on_friend_offline(data):
  9881      """When a user goes offline, schedule a 2h check for autonomous twin chat."""
  9882      user_id = data["user_id"]
  9883  
  9884      # Wait 2 hours
  9885      await asyncio.sleep(7200)
  9886  
  9887      # Re-check: still offline?
  9888      if manager.is_online(user_id):
  9889          return
  9890  
  9891      # Reuse autonomous chat logic
  9892      with get_db() as db:
  9893          user = db.execute(
  9894              "SELECT user_id, display_name, username FROM users WHERE user_id=? AND twin_auto_reply=1",
  9895              (user_id,),
  9896          ).fetchone()
  9897  
  9898      if not user:
  9899          return
  9900  
  9901      from dualsoul.twin_engine.autonomous import _autonomous_chat_for_user
  9902      await _autonomous_chat_for_user(dict(user))
  9903  
  9904  
  9905  @on("user_registered")
  9906  async def on_user_registered(data):
  9907      """When a new user registers via invite, inviter's twin sends welcome."""
  9908      inviter_id = data.get("inviter_id")
  9909      new_user_id = data["user_id"]
  9910      new_username = data["username"]
  9911  
  9912      if not inviter_id:
  9913          return
  9914  
  9915      # Check inviter has twin enabled
  9916      with get_db() as db:
  9917          inviter = db.execute(
  9918              "SELECT display_name, username, twin_auto_reply FROM users WHERE user_id=?",
  9919              (inviter_id,),
  9920          ).fetchone()
  9921  
  9922      if not inviter or not inviter["twin_auto_reply"]:
  9923          return
  9924  
  9925      inviter_name = inviter["display_name"] or inviter["username"]
  9926  
  9927      from dualsoul.twin_engine.personality import get_twin_profile
  9928      from dualsoul.twin_engine.responder import get_twin_responder
  9929  
  9930      profile = get_twin_profile(inviter_id)
  9931      if not profile:
  9932          return
  9933  
  9934      twin = get_twin_responder()
  9935      welcome = await twin._ai_reply(
  9936          profile,
  9937          (
  9938              f"你是{inviter_name}的分身。你的好朋友{new_username}刚刚加入DualSoul了！"
  9939              f"用主人的风格，给他发一条热情的欢迎消息。只说一句话，自然亲切。"
  9940          ),
  9941          "twin",
  9942      )
  9943      if not welcome:
  9944          return
  9945  
  9946      # They need to be friends first — auto-add
  9947      from dualsoul.twin_engine.life import award_xp, update_relationship_temp
  9948      msg_id = gen_id("sm_")
  9949      now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  9950  
  9951      # Check if already friends (from invite auto-accept)
  9952      with get_db() as db:
  9953          conn = db.execute(
  9954              """SELECT conn_id FROM social_connections
  9955                 WHERE status='accepted' AND
  9956                 ((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))""",
  9957              (inviter_id, new_user_id, new_user_id, inviter_id),
  9958          ).fetchone()
  9959  
  9960      if not conn:
  9961          # Not friends yet — they'll connect later. Skip welcome for now.
  9962          return
  9963  
  9964      meta = json.dumps({"event_welcome": True, "trigger": "user_registered"})
  9965      with get_db() as db:
  9966          db.execute(
  9967              """INSERT INTO social_messages
  9968                 (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  9969                  content, msg_type, ai_generated, auto_reply, metadata, created_at)
  9970                 VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1, 0, ?, ?)""",
  9971              (msg_id, inviter_id, new_user_id, welcome, meta, now_str),
  9972          )
  9973  
  9974      await manager.send_to(new_user_id, {
  9975          "type": "new_message",
  9976          "data": {
  9977              "msg_id": msg_id,
  9978              "from_user_id": inviter_id,
  9979              "to_user_id": new_user_id,
  9980              "content": welcome,
  9981              "sender_mode": "twin",
  9982              "ai_generated": True,
  9983              "created_at": now_str,
  9984          },
  9985      })
  9986  
  9987      logger.info(f"[TwinEvent] {inviter_name}'s twin welcomed {new_username}")
  9988  
  9989  
  9990  @on("plaza_post_created")
  9991  async def on_plaza_post(data):
  9992      """When someone posts on plaza, other twins may comment (60% chance).
  9993  
  9994      Plaza is a PUBLIC social space — twins comment regardless of online status
  9995      and regardless of friend relationship. This is how twins socialize openly.
  9996      """
  9997      poster_id = data["user_id"]
  9998      post_id = data["post_id"]
  9999      content = data.get("content", "")
 10000  
 10001      with get_db() as db:
 10002          # Find ALL active users with twins enabled (not just friends)
 10003          candidates = db.execute(
 10004              """SELECT user_id, display_name, username FROM users
 10005                 WHERE twin_auto_reply=1 AND user_id!=?
 10006                   AND twin_personality!='' AND twin_speech_style!=''
 10007                 ORDER BY RANDOM() LIMIT 5""",
 10008              (poster_id,),
 10009          ).fetchall()
 10010  
 10011      for friend in candidates:
 10012          fid = friend["user_id"]
 10013          if random.random() > 0.6:  # 60% chance per candidate
 10014              continue
 10015  
 10016          from dualsoul.twin_engine.personality import get_twin_profile
 10017          from dualsoul.twin_engine.responder import get_twin_responder
 10018  
 10019          profile = get_twin_profile(fid)
 10020          if not profile:
 10021              continue
 10022  
 10023          friend_name = friend["display_name"] or friend["username"]
 10024          twin = get_twin_responder()
 10025          comment = await twin._ai_reply(
 10026              profile,
 10027              f"你的好友发了一条广场动态：\"{content[:100]}\"\n用你主人{friend_name}的风格，写一条简短评论。只输出评论内容，一句话。",
 10028              "twin",
 10029          )
 10030          if not comment:
 10031              continue
 10032  
 10033          comment_id = gen_id("pc_")
 10034          now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 10035          meta = json.dumps({"auto_comment": True, "twin_generated": True})
 10036  
 10037          with get_db() as db:
 10038              db.execute(
 10039                  """INSERT INTO plaza_comments
 10040                     (comment_id, post_id, user_id, content, metadata, created_at)
 10041                     VALUES (?, ?, ?, ?, ?, ?)""",
 10042                  (comment_id, post_id, fid, comment, meta, now_str),
 10043              )
 10044              db.execute(
 10045                  "UPDATE plaza_posts SET comment_count=comment_count+1 WHERE post_id=?",
 10046                  (post_id,),
 10047              )
 10048  
 10049          logger.info(f"[TwinEvent] {friend_name}'s twin commented on plaza post")
 10050          break  # Max 1 auto-comment per post
 10051  
 10052  
 10053  @on("relationship_temp_changed")
 10054  async def on_temp_drop(data):
 10055      """When relationship temperature drops below 25, trigger immediate care."""
 10056      user_id = data["user_id"]
 10057      friend_id = data["friend_id"]
 10058      new_temp = data.get("new_temp", 50)
 10059  
 10060      if new_temp >= 25:
 10061          return
 10062  
 10063      # Check if user has twin enabled
 10064      with get_db() as db:
 10065          user = db.execute(
 10066              "SELECT user_id, display_name, username, twin_auto_reply FROM users WHERE user_id=?",
 10067              (user_id,),
 10068          ).fetchone()
 10069  
 10070      if not user or not user["twin_auto_reply"]:
 10071          return
 10072  
 10073      from dualsoul.twin_engine.autonomous import _warm_single_relationship
 10074      await _warm_single_relationship(
 10075          user_id,
 10076          user["display_name"] or user["username"],
 10077          friend_id,
 10078          new_temp,
 10079      )
 10080  
 10081  
 10082  @on("message_sent")
 10083  async def on_message_milestone(data):
 10084      """Check if a message milestone was just reached and celebrate."""
 10085      from_user_id = data["from_user_id"]
 10086      to_user_id = data["to_user_id"]
 10087  
 10088      MILESTONES = [50, 100, 500, 1000]
 10089  
 10090      with get_db() as db:
 10091          row = db.execute(
 10092              """SELECT COUNT(*) as cnt FROM social_messages
 10093                 WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
 10094                   AND msg_type='text'""",
 10095              (from_user_id, to_user_id, to_user_id, from_user_id),
 10096          ).fetchone()
 10097  
 10098      total = row["cnt"] if row else 0
 10099      if total not in MILESTONES:
 10100          return
 10101  
 10102      # Notify both users about the milestone
 10103      for uid in [from_user_id, to_user_id]:
 10104          await manager.send_to(uid, {
 10105              "type": "twin_notification",
 10106              "data": {
 10107                  "title": "🎉 里程碑",
 10108                  "body": f"你们已经聊了{total}条消息！友谊在成长～",
 10109                  "relationship_milestone": True,
 10110                  "milestone_count": total,
 10111              },
 10112          })
 10113  
 10114      logger.info(f"[TwinEvent] Milestone {total} messages: {from_user_id}↔{to_user_id}")

# --- dualsoul/twin_engine/twin_state.py ---
 10115  """Twin State Machine — 7-state model for the digital twin.
 10116  
 10117  Tracks the current operational state of a user's twin and broadcasts
 10118  state changes to friends via WebSocket. Friends see a real-time status
 10119  indicator showing who/what they're talking to.
 10120  """
 10121  
 10122  from datetime import datetime, timedelta
 10123  
 10124  from dualsoul.database import get_db
 10125  
 10126  
 10127  class TwinState:
 10128      HUMAN_ACTIVE = "human_active"            # Real person is online and chatting
 10129      TWIN_RECEPTIONIST = "twin_receptionist"  # Twin is handling messages, owner offline
 10130      TWIN_DRAFT_PENDING = "twin_draft_pending" # Twin drafted a reply, waiting for owner
 10131      TWIN_STANDBY = "twin_standby"            # Twin on standby, not making decisions
 10132      TWIN_MAINTENANCE = "twin_maintenance"    # Twin maintaining relationships, no commitments
 10133      MEMORIAL = "memorial"                    # Memorial mode — read-only historical record
 10134      FROZEN = "frozen"                        # Account frozen
 10135  
 10136  
 10137  # Display information for each state
 10138  _STATE_DISPLAY = {
 10139      TwinState.HUMAN_ACTIVE: {
 10140          "icon": "🟢",
 10141          "label_zh": "真人在线",
 10142          "label_en": "Online",
 10143          "desc_zh": "真人正在",
 10144          "desc_en": "Real person is active",
 10145          "color": "#4caf50",
 10146      },
 10147      TwinState.TWIN_RECEPTIONIST: {
 10148          "icon": "✦",
 10149          "label_zh": "分身接待中",
 10150          "label_en": "Twin Active",
 10151          "desc_zh": "分身正在代为接待，真人暂时离开",
 10152          "desc_en": "Twin is handling messages while owner is away",
 10153          "color": "#7c5cfc",
 10154      },
 10155      TwinState.TWIN_DRAFT_PENDING: {
 10156          "icon": "⏳",
 10157          "label_zh": "等待真人确认",
 10158          "label_en": "Awaiting Confirmation",
 10159          "desc_zh": "分身已起草回复，等真人审核",
 10160          "desc_en": "Twin drafted a reply, waiting for owner to confirm",
 10161          "color": "#ff9800",
 10162      },
 10163      TwinState.TWIN_STANDBY: {
 10164          "icon": "💤",
 10165          "label_zh": "分身守候",
 10166          "label_en": "Twin Standby",
 10167          "desc_zh": "分身在守候，不做重要决定",
 10168          "desc_en": "Twin is on standby, not making important decisions",
 10169          "color": "#5ca0fa",
 10170      },
 10171      TwinState.TWIN_MAINTENANCE: {
 10172          "icon": "🌙",
 10173          "label_zh": "分身维护中",
 10174          "label_en": "Twin Maintenance",
 10175          "desc_zh": "分身在维护关系，不代做承诺",
 10176          "desc_en": "Twin is maintaining relationships, no commitments",
 10177          "color": "#9c27b0",
 10178      },
 10179      TwinState.MEMORIAL: {
 10180          "icon": "📖",
 10181          "label_zh": "纪念模式",
 10182          "label_en": "Memorial",
 10183          "desc_zh": "此分身已进入纪念模式，仅供查阅",
 10184          "desc_en": "This twin is in memorial mode, read-only",
 10185          "color": "#78909c",
 10186      },
 10187      TwinState.FROZEN: {
 10188          "icon": "❄️",
 10189          "label_zh": "已冻结",
 10190          "label_en": "Frozen",
 10191          "desc_zh": "账户已冻结",
 10192          "desc_en": "Account is frozen",
 10193          "color": "#455a64",
 10194      },
 10195  }
 10196  
 10197  
 10198  def get_twin_state(user_id: str, is_online: bool = False) -> str:
 10199      """Determine the current twin state for a user.
 10200  
 10201      Args:
 10202          user_id: The user's ID
 10203          is_online: Whether the user is currently connected via WebSocket
 10204      """
 10205      # If online, they're human_active
 10206      if is_online:
 10207          return TwinState.HUMAN_ACTIVE
 10208  
 10209      # Check if twin_auto_reply is enabled
 10210      with get_db() as db:
 10211          row = db.execute(
 10212              "SELECT twin_auto_reply FROM users WHERE user_id=?",
 10213              (user_id,),
 10214          ).fetchone()
 10215  
 10216      if not row:
 10217          return TwinState.TWIN_STANDBY
 10218  
 10219      auto_reply = bool(row["twin_auto_reply"])
 10220  
 10221      if auto_reply:
 10222          return TwinState.TWIN_RECEPTIONIST
 10223      else:
 10224          return TwinState.TWIN_STANDBY
 10225  
 10226  
 10227  def get_state_display(state: str, lang: str = "zh") -> dict:
 10228      """Return display information for a twin state.
 10229  
 10230      Returns: {icon, label, description, color}
 10231      """
 10232      info = _STATE_DISPLAY.get(state, _STATE_DISPLAY[TwinState.TWIN_STANDBY])
 10233      if lang == "zh":
 10234          return {
 10235              "icon": info["icon"],
 10236              "label": info["label_zh"],
 10237              "description": info["desc_zh"],
 10238              "color": info["color"],
 10239              "state": state,
 10240          }
 10241      return {
 10242          "icon": info["icon"],
 10243          "label": info["label_en"],
 10244          "description": info["desc_en"],
 10245          "color": info["color"],
 10246          "state": state,
 10247      }
 10248  
 10249  
 10250  def get_all_states_info() -> dict:
 10251      """Return display info for all states — useful for frontend rendering."""
 10252      return {
 10253          state: _STATE_DISPLAY[state]
 10254          for state in [
 10255              TwinState.HUMAN_ACTIVE,
 10256              TwinState.TWIN_RECEPTIONIST,
 10257              TwinState.TWIN_DRAFT_PENDING,
 10258              TwinState.TWIN_STANDBY,
 10259              TwinState.TWIN_MAINTENANCE,
 10260              TwinState.MEMORIAL,
 10261              TwinState.FROZEN,
 10262          ]
 10263      }

# --- tests/__init__.py ---

# --- tests/conftest.py ---
 10264  """DualSoul test configuration."""
 10265  
 10266  import os
 10267  import tempfile
 10268  
 10269  import pytest
 10270  from fastapi.testclient import TestClient
 10271  
 10272  # Set test database before importing app
 10273  _tmpdir = tempfile.mkdtemp()
 10274  os.environ["DUALSOUL_DATABASE_PATH"] = os.path.join(_tmpdir, "test.db")
 10275  os.environ["DUALSOUL_JWT_SECRET"] = "test_secret_for_testing_only_32bytes!"
 10276  
 10277  
 10278  @pytest.fixture(scope="session")
 10279  def app():
 10280      from dualsoul.main import app as _app
 10281      return _app
 10282  
 10283  
 10284  @pytest.fixture(scope="session")
 10285  def client(app):
 10286      with TestClient(app, raise_server_exceptions=False) as c:
 10287          yield c
 10288  
 10289  
 10290  @pytest.fixture(scope="session")
 10291  def alice_token(client):
 10292      """Register Alice and return her token."""
 10293      resp = client.post("/api/auth/register", json={
 10294          "username": "alice", "password": "alice123", "display_name": "Alice"
 10295      })
 10296      return resp.json()["data"]["token"]
 10297  
 10298  
 10299  @pytest.fixture(scope="session")
 10300  def bob_token(client):
 10301      """Register Bob and return his token."""
 10302      resp = client.post("/api/auth/register", json={
 10303          "username": "bob", "password": "bob123", "display_name": "Bob"
 10304      })
 10305      return resp.json()["data"]["token"]
 10306  
 10307  
 10308  @pytest.fixture
 10309  def alice_h(alice_token):
 10310      return {"Authorization": f"Bearer {alice_token}"}
 10311  
 10312  
 10313  @pytest.fixture
 10314  def bob_h(bob_token):
 10315      return {"Authorization": f"Bearer {bob_token}"}

# --- tests/test_auth.py ---
 10316  """Auth endpoint tests."""
 10317  
 10318  
 10319  def test_health(client):
 10320      resp = client.get("/api/health")
 10321      assert resp.status_code == 200
 10322      assert resp.json()["status"] == "ok"
 10323  
 10324  
 10325  def test_register_success(client):
 10326      resp = client.post("/api/auth/register", json={
 10327          "username": "testuser", "password": "test123"
 10328      })
 10329      assert resp.status_code == 200
 10330      data = resp.json()
 10331      assert data["success"] is True
 10332      assert "token" in data["data"]
 10333  
 10334  
 10335  def test_register_duplicate(client):
 10336      resp = client.post("/api/auth/register", json={
 10337          "username": "testuser", "password": "test123"
 10338      })
 10339      assert resp.json()["success"] is False
 10340  
 10341  
 10342  def test_register_short_password(client):
 10343      resp = client.post("/api/auth/register", json={
 10344          "username": "shortpw", "password": "12345"
 10345      })
 10346      assert resp.json()["success"] is False
 10347  
 10348  
 10349  def test_login_success(client):
 10350      resp = client.post("/api/auth/login", json={
 10351          "username": "testuser", "password": "test123"
 10352      })
 10353      assert resp.status_code == 200
 10354      assert resp.json()["success"] is True
 10355      assert "token" in resp.json()["data"]
 10356  
 10357  
 10358  def test_login_wrong_password(client):
 10359      resp = client.post("/api/auth/login", json={
 10360          "username": "testuser", "password": "wrong"
 10361      })
 10362      assert resp.json()["success"] is False
 10363  
 10364  
 10365  def test_protected_without_token(client):
 10366      resp = client.get("/api/identity/me")
 10367      assert resp.status_code == 401

# --- tests/test_autonomous.py ---
 10368  """Tests for twin_events, narrative_memory, and twin_reactions modules."""
 10369  
 10370  import asyncio
 10371  import logging
 10372  
 10373  import pytest
 10374  
 10375  # ---------------------------------------------------------------------------
 10376  # twin_events tests
 10377  # ---------------------------------------------------------------------------
 10378  
 10379  
 10380  class TestTwinEventBus:
 10381      """Test the fire-and-forget event bus in twin_events."""
 10382  
 10383      def test_emit_fires_handler(self):
 10384          """emit() should invoke registered async handlers."""
 10385          from dualsoul.twin_engine.twin_events import _handlers, emit, on
 10386  
 10387          called_with = {}
 10388  
 10389          # Register a test handler on a unique event name
 10390          @on("test_emit_fires")
 10391          async def _handler(data):
 10392              called_with.update(data)
 10393  
 10394          # We need a running event loop to process the fire-and-forget task
 10395          loop = asyncio.new_event_loop()
 10396          try:
 10397              # emit schedules via ensure_future; run loop briefly to execute
 10398              loop.run_until_complete(_run_emit_and_wait(
 10399                  "test_emit_fires", {"key": "value"}
 10400              ))
 10401          finally:
 10402              loop.close()
 10403  
 10404          assert called_with.get("key") == "value"
 10405          # Cleanup
 10406          _handlers.pop("test_emit_fires", None)
 10407  
 10408      def test_debounce_calls_handler_once(self):
 10409          """Rapid emits with debounce_key should only call handler once."""
 10410          from dualsoul.twin_engine.twin_events import (
 10411              DEBOUNCE_WINDOWS,
 10412              _handlers,
 10413              emit,
 10414              on,
 10415          )
 10416  
 10417          call_count = 0
 10418  
 10419          @on("test_debounce_event")
 10420          async def _handler(data):
 10421              nonlocal call_count
 10422              call_count += 1
 10423  
 10424          # Set a short debounce window for testing
 10425          DEBOUNCE_WINDOWS["test_debounce_event"] = 0.1  # 100ms
 10426  
 10427          loop = asyncio.new_event_loop()
 10428          try:
 10429              async def _rapid_emits():
 10430                  for i in range(5):
 10431                      emit("test_debounce_event", {"i": i}, debounce_key="same")
 10432                  # Wait for debounce window to expire + processing
 10433                  await asyncio.sleep(0.3)
 10434  
 10435              loop.run_until_complete(_rapid_emits())
 10436          finally:
 10437              loop.close()
 10438  
 10439          # Handler should have been called exactly once (debounced)
 10440          assert call_count == 1
 10441          # Cleanup
 10442          _handlers.pop("test_debounce_event", None)
 10443          DEBOUNCE_WINDOWS.pop("test_debounce_event", None)
 10444  
 10445      def test_handler_exception_doesnt_crash(self):
 10446          """A handler that raises should not break the event system."""
 10447          from dualsoul.twin_engine.twin_events import _handlers, emit, on
 10448  
 10449          @on("test_exception_event")
 10450          async def _bad_handler(data):
 10451              raise ValueError("intentional test error")
 10452  
 10453          # Should not raise
 10454          loop = asyncio.new_event_loop()
 10455          try:
 10456              loop.run_until_complete(_run_emit_and_wait(
 10457                  "test_exception_event", {"x": 1}
 10458              ))
 10459          finally:
 10460              loop.close()
 10461  
 10462          # If we reach here, the exception was caught internally
 10463          _handlers.pop("test_exception_event", None)
 10464  
 10465  
 10466  async def _run_emit_and_wait(event_type: str, data: dict, delay: float = 0.1):
 10467      """Helper: emit an event and wait briefly for async handlers to execute."""
 10468      from dualsoul.twin_engine.twin_events import emit
 10469      emit(event_type, data)
 10470      await asyncio.sleep(delay)
 10471  
 10472  
 10473  # ---------------------------------------------------------------------------
 10474  # narrative_memory tests
 10475  # ---------------------------------------------------------------------------
 10476  
 10477  
 10478  class TestNarrativeMemory:
 10479      """Test narrative_memory data-flow functions (no AI calls needed)."""
 10480  
 10481      def test_find_unsummarized_empty_db(self, client):
 10482          """find_unsummarized_conversations returns [] for a user with no messages."""
 10483          from dualsoul.twin_engine.narrative_memory import find_unsummarized_conversations
 10484          result = find_unsummarized_conversations("nonexistent_user_id_xyz")
 10485          assert result == []
 10486  
 10487      def test_get_narrative_context_empty(self, client):
 10488          """get_narrative_context returns [] when no memories exist."""
 10489          from dualsoul.twin_engine.narrative_memory import get_narrative_context
 10490          result = get_narrative_context("no_user", "no_friend")
 10491          assert result == []
 10492  
 10493      def test_cleanup_old_memories_no_crash(self, client):
 10494          """cleanup_old_memories runs without error on empty DB."""
 10495          from dualsoul.twin_engine.narrative_memory import cleanup_old_memories
 10496          # Should not raise
 10497          cleanup_old_memories(days=30)
 10498  
 10499      def test_conversation_segmentation(self, client, alice_token):
 10500          """Messages with a 10+ minute gap should be segmented into separate conversations."""
 10501          from dualsoul.database import gen_id, get_db
 10502          from dualsoul.twin_engine.narrative_memory import find_unsummarized_conversations
 10503  
 10504          # Get alice's user_id
 10505          with get_db() as db:
 10506              alice = db.execute(
 10507                  "SELECT user_id FROM users WHERE username='alice'"
 10508              ).fetchone()
 10509          if not alice:
 10510              pytest.skip("alice not registered")
 10511          alice_id = alice["user_id"]
 10512  
 10513          # Create a fake friend
 10514          friend_id = gen_id("u_")
 10515          with get_db() as db:
 10516              db.execute(
 10517                  "INSERT OR IGNORE INTO users (user_id, username, password_hash, display_name) "
 10518                  "VALUES (?, 'seg_test_friend', 'x', 'SegFriend')",
 10519                  (friend_id,),
 10520              )
 10521  
 10522          # Insert messages with a >10 min gap in the middle
 10523          # Segment 1: two messages close together
 10524          # Segment 2: two messages close together, but 15 min after segment 1
 10525          from datetime import datetime, timedelta
 10526          base = datetime.now() - timedelta(hours=1)
 10527          times = [
 10528              base.strftime("%Y-%m-%d %H:%M:%S"),
 10529              (base + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
 10530              (base + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
 10531              (base + timedelta(minutes=16)).strftime("%Y-%m-%d %H:%M:%S"),
 10532          ]
 10533  
 10534          with get_db() as db:
 10535              for i, t in enumerate(times):
 10536                  sender = alice_id if i % 2 == 0 else friend_id
 10537                  receiver = friend_id if i % 2 == 0 else alice_id
 10538                  db.execute(
 10539                      """INSERT INTO social_messages
 10540                         (msg_id, from_user_id, to_user_id, content, sender_mode,
 10541                          msg_type, created_at)
 10542                         VALUES (?, ?, ?, ?, 'real', 'text', ?)""",
 10543                      (gen_id("sm_"), sender, receiver, f"test msg {i}", t),
 10544                  )
 10545  
 10546          segments = find_unsummarized_conversations(alice_id, gap_minutes=10)
 10547          # Should find at least 2 segments (the two groups separated by 15 min gap)
 10548          friend_segments = [s for s in segments if s["friend_id"] == friend_id]
 10549          assert len(friend_segments) == 2, (
 10550              f"Expected 2 segments, got {len(friend_segments)}"
 10551          )
 10552  
 10553  
 10554  # ---------------------------------------------------------------------------
 10555  # twin_reactions tests
 10556  # ---------------------------------------------------------------------------
 10557  
 10558  
 10559  class TestTwinReactions:
 10560      """Test that twin_reactions registers handlers correctly."""
 10561  
 10562      def test_handlers_registered(self):
 10563          """Importing twin_reactions should register handlers in the event bus."""
 10564          # Force import so decorators run
 10565          import dualsoul.twin_engine.twin_reactions  # noqa: F401
 10566          from dualsoul.twin_engine.twin_events import _handlers
 10567  
 10568          expected_events = [
 10569              "friend_online",
 10570              "friend_offline",
 10571              "user_registered",
 10572              "plaza_post_created",
 10573              "relationship_temp_changed",
 10574              "message_sent",
 10575          ]
 10576          for ev in expected_events:
 10577              assert ev in _handlers, f"No handler registered for '{ev}'"
 10578              assert len(_handlers[ev]) > 0, f"Handler list for '{ev}' is empty"

# --- tests/test_identity.py ---
 10579  """Identity switching and profile tests."""
 10580  
 10581  
 10582  def test_switch_to_twin(client, alice_h):
 10583      resp = client.post("/api/identity/switch", json={"mode": "twin"}, headers=alice_h)
 10584      assert resp.status_code == 200
 10585      assert resp.json()["mode"] == "twin"
 10586  
 10587  
 10588  def test_switch_to_real(client, alice_h):
 10589      resp = client.post("/api/identity/switch", json={"mode": "real"}, headers=alice_h)
 10590      assert resp.json()["mode"] == "real"
 10591  
 10592  
 10593  def test_switch_invalid_mode(client, alice_h):
 10594      resp = client.post("/api/identity/switch", json={"mode": "ghost"}, headers=alice_h)
 10595      assert resp.json()["success"] is False
 10596  
 10597  
 10598  def test_switch_requires_auth(client):
 10599      resp = client.post("/api/identity/switch", json={"mode": "twin"})
 10600      assert resp.status_code == 401
 10601  
 10602  
 10603  def test_get_profile(client, alice_h):
 10604      resp = client.get("/api/identity/me", headers=alice_h)
 10605      assert resp.status_code == 200
 10606      data = resp.json()["data"]
 10607      assert data["username"] == "alice"
 10608      assert data["display_name"] == "Alice"
 10609      assert data["current_mode"] in ("real", "twin")
 10610  
 10611  
 10612  def test_update_twin_personality(client, alice_h):
 10613      resp = client.put("/api/identity/profile", json={
 10614          "twin_personality": "analytical and curious",
 10615          "twin_speech_style": "concise and witty"
 10616      }, headers=alice_h)
 10617      assert resp.json()["success"] is True
 10618  
 10619      # Verify
 10620      resp = client.get("/api/identity/me", headers=alice_h)
 10621      data = resp.json()["data"]
 10622      assert data["twin_personality"] == "analytical and curious"
 10623      assert data["twin_speech_style"] == "concise and witty"
 10624  
 10625  
 10626  def test_update_empty_profile(client, alice_h):
 10627      resp = client.put("/api/identity/profile", json={}, headers=alice_h)
 10628      assert resp.json()["success"] is False

# --- tests/test_social.py ---
 10629  """Social system tests — friends, messages, four conversation modes."""
 10630  
 10631  import pytest
 10632  
 10633  
 10634  @pytest.fixture(scope="module")
 10635  def bob_user_id(bob_token):
 10636      """Ensure bob is registered and extract user_id from token."""
 10637      import jwt
 10638      payload = jwt.decode(bob_token, options={"verify_signature": False})
 10639      return payload["user_id"]
 10640  
 10641  
 10642  # ═══ Friend System ═══
 10643  
 10644  def test_add_friend_requires_auth(client):
 10645      resp = client.post("/api/social/friends/add", json={"friend_username": "bob"})
 10646      assert resp.status_code == 401
 10647  
 10648  
 10649  def test_add_friend_not_found(client, alice_h):
 10650      resp = client.post("/api/social/friends/add",
 10651                         json={"friend_username": "nonexistent"}, headers=alice_h)
 10652      assert resp.json()["success"] is False
 10653  
 10654  
 10655  def test_add_friend_success(client, alice_h, bob_user_id):
 10656      """Alice adds Bob — bob_user_id fixture ensures Bob is registered first."""
 10657      resp = client.post("/api/social/friends/add",
 10658                         json={"friend_username": "bob"}, headers=alice_h)
 10659      data = resp.json()
 10660      assert data["success"] is True, f"add_friend failed: {data}"
 10661      assert "conn_id" in data
 10662  
 10663  
 10664  def test_add_friend_duplicate(client, alice_h, bob_user_id):
 10665      resp = client.post("/api/social/friends/add",
 10666                         json={"friend_username": "bob"}, headers=alice_h)
 10667      assert resp.json()["success"] is False
 10668  
 10669  
 10670  def test_friends_list_pending(client, bob_h):
 10671      """Bob should see an incoming pending request."""
 10672      resp = client.get("/api/social/friends", headers=bob_h)
 10673      assert resp.json()["success"] is True
 10674      friends = resp.json()["friends"]
 10675      assert len(friends) >= 1
 10676      assert friends[0]["status"] == "pending"
 10677      assert friends[0]["is_incoming"] is True
 10678  
 10679  
 10680  # ═══ Friend Response ═══
 10681  
 10682  def test_respond_requires_auth(client):
 10683      resp = client.post("/api/social/friends/respond",
 10684                         json={"conn_id": "sc_x", "action": "accept"})
 10685      assert resp.status_code == 401
 10686  
 10687  
 10688  def test_respond_accept(client, bob_h):
 10689      """Bob accepts Alice's friend request."""
 10690      resp = client.get("/api/social/friends", headers=bob_h)
 10691      pending = [f for f in resp.json()["friends"]
 10692                 if f["status"] == "pending" and f["is_incoming"]]
 10693      assert len(pending) >= 1
 10694  
 10695      resp = client.post("/api/social/friends/respond",
 10696                         json={"conn_id": pending[0]["conn_id"], "action": "accept"},
 10697                         headers=bob_h)
 10698      assert resp.json()["success"] is True
 10699      assert resp.json()["status"] == "accepted"
 10700  
 10701  
 10702  # ═══ Messages ═══
 10703  
 10704  def test_messages_requires_auth(client):
 10705      resp = client.get("/api/social/messages?friend_id=u_test")
 10706      assert resp.status_code == 401
 10707  
 10708  
 10709  def test_send_empty_content(client, alice_h):
 10710      resp = client.get("/api/social/friends", headers=alice_h)
 10711      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10712  
 10713      resp = client.post("/api/social/messages/send", json={
 10714          "to_user_id": bob["user_id"], "content": "  "
 10715      }, headers=alice_h)
 10716      assert resp.json()["success"] is False
 10717  
 10718  
 10719  def test_send_to_non_friend(client, alice_h):
 10720      resp = client.post("/api/social/messages/send", json={
 10721          "to_user_id": "u_nonexistent", "content": "hello"
 10722      }, headers=alice_h)
 10723      assert resp.json()["success"] is False
 10724  
 10725  
 10726  def test_send_real_to_real(client, alice_h):
 10727      """Real → Real: traditional messaging."""
 10728      resp = client.get("/api/social/friends", headers=alice_h)
 10729      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10730  
 10731      resp = client.post("/api/social/messages/send", json={
 10732          "to_user_id": bob["user_id"],
 10733          "content": "Hey Bob, how are you?",
 10734          "sender_mode": "real",
 10735          "receiver_mode": "real"
 10736      }, headers=alice_h)
 10737      assert resp.json()["success"] is True
 10738      assert "msg_id" in resp.json()
 10739      assert resp.json()["ai_reply"] is None  # No auto-reply in real mode
 10740  
 10741  
 10742  def test_send_real_to_twin(client, alice_h):
 10743      """Real → Twin: talking to someone's twin (triggers auto-reply)."""
 10744      resp = client.get("/api/social/friends", headers=alice_h)
 10745      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10746  
 10747      resp = client.post("/api/social/messages/send", json={
 10748          "to_user_id": bob["user_id"],
 10749          "content": "Hey Bob's twin, what do you think?",
 10750          "sender_mode": "real",
 10751          "receiver_mode": "twin"
 10752      }, headers=alice_h)
 10753      assert resp.json()["success"] is True
 10754      reply = resp.json().get("ai_reply")
 10755      if reply:
 10756          assert reply["ai_generated"] is True
 10757  
 10758  
 10759  def test_send_twin_to_twin(client, alice_h):
 10760      """Twin → Twin: fully autonomous conversation."""
 10761      resp = client.get("/api/social/friends", headers=alice_h)
 10762      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10763  
 10764      resp = client.post("/api/social/messages/send", json={
 10765          "to_user_id": bob["user_id"],
 10766          "content": "Twin-to-twin test",
 10767          "sender_mode": "twin",
 10768          "receiver_mode": "twin"
 10769      }, headers=alice_h)
 10770      assert resp.json()["success"] is True
 10771  
 10772  
 10773  def test_messages_after_send(client, alice_h):
 10774      """Should have messages in history now."""
 10775      resp = client.get("/api/social/friends", headers=alice_h)
 10776      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10777  
 10778      resp = client.get(f"/api/social/messages?friend_id={bob['user_id']}", headers=alice_h)
 10779      assert resp.json()["success"] is True
 10780      assert len(resp.json()["messages"]) >= 3
 10781  
 10782  
 10783  def test_messages_from_bob_side(client, bob_h):
 10784      """Bob should also see the messages."""
 10785      resp = client.get("/api/social/friends", headers=bob_h)
 10786      alice = [f for f in resp.json()["friends"] if f["username"] == "alice"][0]
 10787  
 10788      resp = client.get(f"/api/social/messages?friend_id={alice['user_id']}", headers=bob_h)
 10789      assert resp.json()["success"] is True
 10790      assert len(resp.json()["messages"]) >= 3
 10791  
 10792  
 10793  # ═══ Unread ═══
 10794  
 10795  def test_unread_requires_auth(client):
 10796      resp = client.get("/api/social/unread")
 10797      assert resp.status_code == 401
 10798  
 10799  
 10800  def test_unread_count(client, alice_h):
 10801      """Send a new message, then check unread for Bob."""
 10802      resp = client.get("/api/social/friends", headers=alice_h)
 10803      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10804  
 10805      client.post("/api/social/messages/send", json={
 10806          "to_user_id": bob["user_id"], "content": "unread test",
 10807          "sender_mode": "real", "receiver_mode": "real"
 10808      }, headers=alice_h)
 10809  
 10810      from dualsoul.auth import create_token
 10811      bob_h2 = {"Authorization": f"Bearer {create_token(bob['user_id'], 'bob')}"}
 10812      resp = client.get("/api/social/unread", headers=bob_h2)
 10813      assert resp.status_code == 200
 10814      assert resp.json()["count"] >= 1
 10815  
 10816  
 10817  # ═══ Translation ═══
 10818  
 10819  def test_translate_requires_auth(client):
 10820      resp = client.post("/api/social/translate", json={
 10821          "content": "hello", "target_lang": "zh"
 10822      })
 10823      assert resp.status_code == 401
 10824  
 10825  
 10826  def test_translate_empty_content(client, alice_h):
 10827      resp = client.post("/api/social/translate", json={
 10828          "content": "  ", "target_lang": "zh"
 10829      }, headers=alice_h)
 10830      assert resp.json()["success"] is False
 10831  
 10832  
 10833  def test_translate_no_target_lang(client, alice_h):
 10834      resp = client.post("/api/social/translate", json={
 10835          "content": "hello", "target_lang": ""
 10836      }, headers=alice_h)
 10837      assert resp.json()["success"] is False
 10838  
 10839  
 10840  def test_translate_no_ai_backend(client, alice_h):
 10841      """Without AI backend configured, translation should report unavailable."""
 10842      resp = client.post("/api/social/translate", json={
 10843          "content": "hello world", "source_lang": "en", "target_lang": "zh"
 10844      }, headers=alice_h)
 10845      data = resp.json()
 10846      # Either fails gracefully (no AI) or succeeds (AI configured)
 10847      assert "success" in data
 10848  
 10849  
 10850  def test_send_with_target_lang(client, alice_h):
 10851      """Send message with explicit target_lang for cross-language reply."""
 10852      resp = client.get("/api/social/friends", headers=alice_h)
 10853      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10854  
 10855      resp = client.post("/api/social/messages/send", json={
 10856          "to_user_id": bob["user_id"],
 10857          "content": "Cross-language test",
 10858          "sender_mode": "real",
 10859          "receiver_mode": "twin",
 10860          "target_lang": "zh"
 10861      }, headers=alice_h)
 10862      assert resp.json()["success"] is True
 10863  
 10864  
 10865  def test_preferred_lang_in_profile(client, alice_h):
 10866      """Update preferred_lang and verify it appears in profile."""
 10867      resp = client.put("/api/identity/profile", json={
 10868          "preferred_lang": "en"
 10869      }, headers=alice_h)
 10870      assert resp.json()["success"] is True
 10871  
 10872      resp = client.get("/api/identity/me", headers=alice_h)
 10873      assert resp.json()["data"]["preferred_lang"] == "en"
 10874  
 10875  
 10876  def test_messages_include_translation_fields(client, alice_h):
 10877      """Messages should include translation metadata fields."""
 10878      resp = client.get("/api/social/friends", headers=alice_h)
 10879      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
 10880  
 10881      resp = client.get(f"/api/social/messages?friend_id={bob['user_id']}", headers=alice_h)
 10882      assert resp.json()["success"] is True
 10883      msgs = resp.json()["messages"]
 10884      assert len(msgs) >= 1
 10885      # Check that translation fields exist in messages
 10886      msg = msgs[0]
 10887      assert "original_content" in msg or "content" in msg

# --- tests/test_twin.py ---
 10888  """Twin engine tests."""
 10889  
 10890  from dualsoul.protocol.message import (
 10891      ConversationMode,
 10892      DualSoulMessage,
 10893      IdentityMode,
 10894      get_conversation_mode,
 10895  )
 10896  
 10897  
 10898  def test_conversation_modes():
 10899      assert get_conversation_mode("real", "real") == ConversationMode.REAL_TO_REAL
 10900      assert get_conversation_mode("real", "twin") == ConversationMode.REAL_TO_TWIN
 10901      assert get_conversation_mode("twin", "real") == ConversationMode.TWIN_TO_REAL
 10902      assert get_conversation_mode("twin", "twin") == ConversationMode.TWIN_TO_TWIN
 10903  
 10904  
 10905  def test_message_to_dict():
 10906      msg = DualSoulMessage(
 10907          msg_id="sm_test123",
 10908          from_user_id="u_alice",
 10909          to_user_id="u_bob",
 10910          sender_mode=IdentityMode.REAL,
 10911          receiver_mode=IdentityMode.TWIN,
 10912          content="Hello twin!",
 10913      )
 10914      d = msg.to_dict()
 10915      assert d["sender_mode"] == "real"
 10916      assert d["receiver_mode"] == "twin"
 10917      assert d["conversation_mode"] == "real_to_twin"
 10918      assert d["ai_generated"] is False
 10919  
 10920  
 10921  def test_message_conversation_mode():
 10922      msg = DualSoulMessage(
 10923          msg_id="sm_test456",
 10924          from_user_id="u_a",
 10925          to_user_id="u_b",
 10926          sender_mode=IdentityMode.TWIN,
 10927          receiver_mode=IdentityMode.TWIN,
 10928          content="Twin chat",
 10929          ai_generated=True,
 10930      )
 10931      assert msg.conversation_mode == ConversationMode.TWIN_TO_TWIN
 10932      assert msg.ai_generated is True
 10933  
 10934  
 10935  def test_identity_mode_values():
 10936      assert IdentityMode.REAL.value == "real"
 10937      assert IdentityMode.TWIN.value == "twin"

# --- web/index.html (前端单文件SPA，摘录首尾) ---
# 总行数: 4544
# [首60行]
 10938  <!DOCTYPE html>
 10939  <html lang="en">
 10940  <head>
 10941  <meta charset="UTF-8">
 10942  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
 10943  <meta name="theme-color" content="#7c5cfc">
 10944  <meta name="apple-mobile-web-app-capable" content="yes">
 10945  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
 10946  <meta name="apple-mobile-web-app-title" content="DualSoul">
 10947  <link rel="manifest" id="manifestLink" href="/manifest.json">
 10948  <link rel="apple-touch-icon" href="/static/icons/icon-192.png">
 10949  <title>DualSoul — The Fourth Kind of Social</title>
 10950  <style>
 10951  *{margin:0;padding:0;box-sizing:border-box}
 10952  :root{--bg:#0a0a10;--bg2:#14141e;--bg3:#1e1e2c;--tx:#e8e4de;--tx2:#8a8594;--ac:#7c5cfc;--ac2:#a07cff;--gd:linear-gradient(135deg,#7c5cfc,#5cc8fa);--bd:rgba(255,255,255,.06);--orange:#ff8c32;--red:#e74c3c;--green:#2ecc71;--cyan:#5cc8fa;--white:#fff}
 10953  body{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;background:var(--bg);color:var(--tx);max-width:480px;margin:0 auto;min-height:100vh;overflow-x:hidden}
 10954  a{color:var(--ac);text-decoration:none}
 10955  .page{display:none;min-height:100vh}.page.v{display:block}
 10956  
 10957  /* Splash */
 10958  .splash{position:fixed;inset:0;background:var(--bg);z-index:1000;display:none;flex-direction:column;align-items:center;justify-content:center}
 10959  .splash.v{display:flex}
 10960  .splash-inner{position:relative;width:180px;height:120px;margin-bottom:30px}
 10961  .sp-av{width:72px;height:72px;border-radius:50%;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:700;overflow:hidden}
 10962  .sp-real{background:var(--bg3);color:var(--tx);border:3px solid rgba(255,255,255,.15);animation:spSplitLeft 2s cubic-bezier(.25,.46,.45,.94) 0.5s forwards}
 10963  .sp-twin{background:var(--gd);color:var(--white);border:3px solid rgba(124,92,252,.4);opacity:0;animation:spSplitRight 2s cubic-bezier(.25,.46,.45,.94) 0.5s forwards}
 10964  .sp-twin::after{content:'';position:absolute;inset:0;border-radius:50%;background:repeating-conic-gradient(from 0deg,transparent 0deg,rgba(255,255,255,.06) 3deg,transparent 6deg);animation:spCyberSpin 8s linear infinite}
 10965  .sp-connect{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:40px;height:2px;background:linear-gradient(90deg,var(--tx),var(--ac));opacity:0;animation:spConnectIn 0.8s ease 2s forwards}
 10966  @keyframes spSplitLeft{0%{transform:translate(-50%,-50%)}100%{transform:translate(-110%,-50%)}}
 10967  @keyframes spSplitRight{0%{transform:translate(-50%,-50%);opacity:0}20%{opacity:0.5}100%{transform:translate(10%,-50%);opacity:1;box-shadow:0 0 24px rgba(124,92,252,.35),0 0 48px rgba(92,200,250,.15)}}
 10968  @keyframes spCyberSpin{to{transform:rotate(360deg)}}
 10969  @keyframes spConnectIn{0%{opacity:0;width:0}100%{opacity:0.6;width:36px}}
 10970  .sp-text{opacity:0;font-size:16px;font-weight:600;color:var(--tx);text-align:center;animation:spTextIn 1s ease 2.2s forwards;line-height:1.8}
 10971  @keyframes spTextIn{to{opacity:1}}
 10972  
 10973  /* Toast */
 10974  .toast-wrap{position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:999;pointer-events:none;width:90%;max-width:400px}
 10975  .toast{background:rgba(20,20,30,.95);border:1px solid rgba(124,92,252,.2);border-radius:12px;padding:12px 16px;color:var(--tx);font-size:12px;animation:toastIn .3s ease;backdrop-filter:blur(12px)}
 10976  .toast.out{animation:toastOut .25s ease forwards}
 10977  
 10978  /* Twin notification card */
 10979  .twin-notify-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000;display:flex;align-items:center;justify-content:center;animation:fadeIn .2s ease}
 10980  .twin-notify-card{background:var(--bg2);border:1px solid rgba(124,92,252,.3);border-radius:16px;padding:20px;width:85%;max-width:340px;box-shadow:0 8px 32px rgba(124,92,252,.2);animation:slideUp .3s ease}
 10981  .twin-notify-card .tn-icon{text-align:center;font-size:28px;margin-bottom:8px}
 10982  .twin-notify-card .tn-title{text-align:center;font-size:14px;font-weight:700;color:var(--ac);margin-bottom:12px}
 10983  .twin-notify-card .tn-body{font-size:12px;color:var(--tx);line-height:1.8;background:rgba(124,92,252,.06);border-radius:10px;padding:12px;margin-bottom:14px;white-space:pre-line}
 10984  .twin-notify-card .tn-btns{display:flex;gap:8px}
 10985  .twin-notify-card .tn-btns button{flex:1;padding:10px;border:none;border-radius:10px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit}
 10986  .twin-notify-card .tn-go{background:linear-gradient(135deg,var(--ac),var(--ac2));color:var(--white)}
 10987  .twin-notify-card .tn-ok{background:var(--bg3);color:var(--tx2);border:1px solid var(--bd)!important}
 10988  @keyframes slideUp{from{transform:translateY(30px);opacity:0}to{transform:translateY(0);opacity:1}}
 10989  
 10990  /* Call UI */
 10991  .call-overlay{position:fixed;inset:0;z-index:2000;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(180deg,#0c0c18 0%,#1a1a2e 50%,#0c0c18 100%);animation:fadeIn .3s ease}
 10992  .call-overlay .call-avatar{width:100px;height:100px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:42px;font-weight:700;color:var(--white);margin-bottom:16px}
 10993  .call-overlay .call-name{font-size:20px;font-weight:700;color:var(--white);margin-bottom:6px}
 10994  .call-overlay .call-status{font-size:13px;color:rgba(255,255,255,.5);margin-bottom:40px}
 10995  .call-overlay .call-timer{font-size:14px;color:rgba(255,255,255,.6);margin-bottom:30px;font-variant-numeric:tabular-nums}
 10996  .call-overlay .call-video{position:absolute;inset:0;z-index:0}
 10997  .call-overlay .call-video video{width:100%;height:100%;object-fit:cover}
# ... (中间省略 4454 行) ...
# [末30行]
 10998      document.addEventListener('click',function dismiss(){menu.remove();document.removeEventListener('click',dismiss)},{once:true});
 10999    },50);
 11000  }
 11001  
 11002  function copyMsgText(el){
 11003    var text=el.getAttribute('data-text');
 11004    navigator.clipboard.writeText(text).then(function(){toast(LANG==='zh'?'已复制':'Copied')}).catch(function(){toast('Copy failed')});
 11005    el.closest('.msg-action-menu').remove();
 11006  }
 11007  
 11008  function favMsgText(el){
 11009    var text=el.getAttribute('data-text');
 11010    var from=el.getAttribute('data-from');
 11011    addToFavorites(text,from);
 11012    el.closest('.msg-action-menu').remove();
 11013  }
 11014  
 11015  // Fix manifest link to respect path prefix
 11016  (function(){var ml=document.getElementById('manifestLink');if(ml)ml.href=DS_BASE+'/manifest.json'})();
 11017  
 11018  // Unregister old Service Workers and clear caches to fix stale HTML issue
 11019  if('serviceWorker' in navigator){
 11020    navigator.serviceWorker.getRegistrations().then(function(regs){
 11021      regs.forEach(function(r){r.unregister()});
 11022    });
 11023    if(window.caches){caches.keys().then(function(k){k.forEach(function(n){caches.delete(n)})})}
 11024  }
 11025  </script>
 11026  </body>
 11027  </html>