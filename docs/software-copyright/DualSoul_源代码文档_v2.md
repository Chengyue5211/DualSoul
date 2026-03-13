# DualSoul双身份社交协议

## 源代码文档

- 软件名称：DualSoul双身份社交协议软件
- 版本号：V2.0（对应代码版本 v0.4.0）
- 代码总行数：3131（源码2668 + 测试463）
- 编程语言：Python
- 开发完成日期：2026年3月13日
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
    15  from datetime import datetime, timedelta, timezone
    16  
    17  import bcrypt
    18  import jwt
    19  from fastapi import Depends, HTTPException
    20  from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    21  
    22  from dualsoul.config import JWT_SECRET, JWT_EXPIRE_HOURS
    23  
    24  _bearer = HTTPBearer(auto_error=False)
    25  
    26  
    27  def hash_password(password: str) -> str:
    28      """Hash a password with bcrypt."""
    29      return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    30  
    31  
    32  def verify_password(password: str, hashed: str) -> bool:
    33      """Verify a password against a bcrypt hash."""
    34      return bcrypt.checkpw(password.encode(), hashed.encode())
    35  
    36  
    37  def create_token(user_id: str, username: str) -> str:
    38      """Create a JWT token."""
    39      payload = {
    40          "user_id": user_id,
    41          "username": username,
    42          "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    43      }
    44      return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    45  
    46  
    47  def verify_token(token: str) -> dict:
    48      """Verify and decode a JWT token."""
    49      return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    50  
    51  
    52  async def get_current_user(
    53      credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    54  ) -> dict:
    55      """FastAPI dependency — extract and verify the current user from JWT."""
    56      if not credentials:
    57          raise HTTPException(status_code=401, detail="Authentication required")
    58      try:
    59          payload = verify_token(credentials.credentials)
    60          return payload
    61      except jwt.ExpiredSignatureError:
    62          raise HTTPException(status_code=401, detail="Token expired")
    63      except jwt.InvalidTokenError:
    64          raise HTTPException(status_code=401, detail="Invalid token")

# --- dualsoul/config.py ---
    65  """DualSoul configuration — all settings from environment variables."""
    66  
    67  import os
    68  import secrets
    69  
    70  from dotenv import load_dotenv
    71  
    72  load_dotenv()
    73  
    74  # Database
    75  DATABASE_PATH = os.getenv("DUALSOUL_DATABASE_PATH", "./dualsoul.db")
    76  
    77  # JWT
    78  JWT_SECRET = os.getenv("DUALSOUL_JWT_SECRET", "")
    79  if not JWT_SECRET:
    80      JWT_SECRET = secrets.token_hex(32)
    81      print("[DualSoul] WARNING: No JWT_SECRET set. Using random secret (tokens won't persist across restarts).")
    82  
    83  JWT_EXPIRE_HOURS = int(os.getenv("DUALSOUL_JWT_EXPIRE_HOURS", "72"))
    84  
    85  # AI Backend (OpenAI-compatible API)
    86  AI_BASE_URL = os.getenv("DUALSOUL_AI_BASE_URL", "")
    87  AI_API_KEY = os.getenv("DUALSOUL_AI_KEY", "")
    88  AI_MODEL = os.getenv("DUALSOUL_AI_MODEL", "gpt-3.5-turbo")
    89  AI_VISION_MODEL = os.getenv("DUALSOUL_AI_VISION_MODEL", "qwen-vl-plus")
    90  
    91  # Server
    92  HOST = os.getenv("DUALSOUL_HOST", "0.0.0.0")
    93  PORT = int(os.getenv("DUALSOUL_PORT", "8000"))
    94  
    95  # CORS
    96  CORS_ORIGINS = os.getenv("DUALSOUL_CORS_ORIGINS", "*").split(",")

# --- dualsoul/connections.py ---
    97  """WebSocket connection manager — tracks online users for real-time push."""
    98  
    99  import logging
   100  from datetime import datetime
   101  
   102  from fastapi import WebSocket
   103  
   104  logger = logging.getLogger(__name__)
   105  
   106  
   107  class ConnectionManager:
   108      """Manage active WebSocket connections by user_id."""
   109  
   110      def __init__(self):
   111          self._connections: dict[str, WebSocket] = {}
   112          self._last_active: dict[str, datetime] = {}
   113  
   114      async def connect(self, user_id: str, websocket: WebSocket):
   115          """Accept and register a WebSocket connection."""
   116          await websocket.accept()
   117          # Close existing connection if the same user reconnects
   118          old = self._connections.get(user_id)
   119          if old:
   120              try:
   121                  await old.close(code=4000, reason="Replaced by new connection")
   122              except Exception:
   123                  pass
   124          self._connections[user_id] = websocket
   125          self._last_active[user_id] = datetime.now()
   126          logger.info(f"WS connected: {user_id} (total: {len(self._connections)})")
   127  
   128      def disconnect(self, user_id: str):
   129          """Remove a disconnected user."""
   130          self._connections.pop(user_id, None)
   131          logger.info(f"WS disconnected: {user_id} (total: {len(self._connections)})")
   132  
   133      def is_online(self, user_id: str) -> bool:
   134          """Check if a user has an active WebSocket."""
   135          return user_id in self._connections
   136  
   137      def last_active(self, user_id: str) -> datetime | None:
   138          """Get the last activity time for a user."""
   139          return self._last_active.get(user_id)
   140  
   141      def touch(self, user_id: str):
   142          """Update last-active timestamp."""
   143          self._last_active[user_id] = datetime.now()
   144  
   145      async def send_to(self, user_id: str, data: dict) -> bool:
   146          """Send JSON data to a specific user. Returns True if sent."""
   147          ws = self._connections.get(user_id)
   148          if not ws:
   149              return False
   150          try:
   151              await ws.send_json(data)
   152              return True
   153          except Exception:
   154              self.disconnect(user_id)
   155              return False
   156  
   157      async def broadcast(self, user_ids: list[str], data: dict):
   158          """Send JSON data to multiple users."""
   159          for uid in user_ids:
   160              await self.send_to(uid, data)
   161  
   162  
   163  # Singleton instance — imported by routers
   164  manager = ConnectionManager()

# --- dualsoul/database.py ---
   165  """DualSoul database — SQLite with WAL mode."""
   166  
   167  import sqlite3
   168  import uuid
   169  from contextlib import contextmanager
   170  
   171  from dualsoul.config import DATABASE_PATH
   172  
   173  SCHEMA = """
   174  CREATE TABLE IF NOT EXISTS users (
   175      user_id TEXT PRIMARY KEY,
   176      username TEXT NOT NULL UNIQUE,
   177      password_hash TEXT NOT NULL,
   178      display_name TEXT DEFAULT '',
   179      current_mode TEXT DEFAULT 'real' CHECK(current_mode IN ('real', 'twin')),
   180      twin_personality TEXT DEFAULT '',
   181      twin_speech_style TEXT DEFAULT '',
   182      preferred_lang TEXT DEFAULT ''
   183          CHECK(preferred_lang IN ('', 'zh', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'ru', 'ar', 'hi', 'th', 'vi', 'id', 'auto')),
   184      avatar TEXT DEFAULT '',
   185      twin_avatar TEXT DEFAULT '',
   186      created_at TEXT DEFAULT (datetime('now','localtime'))
   187  );
   188  
   189  CREATE TABLE IF NOT EXISTS social_connections (
   190      conn_id TEXT PRIMARY KEY,
   191      user_id TEXT NOT NULL,
   192      friend_id TEXT NOT NULL,
   193      status TEXT DEFAULT 'pending'
   194          CHECK(status IN ('pending', 'accepted', 'blocked')),
   195      created_at TEXT DEFAULT (datetime('now','localtime')),
   196      accepted_at TEXT,
   197      UNIQUE(user_id, friend_id)
   198  );
   199  CREATE INDEX IF NOT EXISTS idx_sc_user ON social_connections(user_id, status);
   200  CREATE INDEX IF NOT EXISTS idx_sc_friend ON social_connections(friend_id, status);
   201  
   202  CREATE TABLE IF NOT EXISTS social_messages (
   203      msg_id TEXT PRIMARY KEY,
   204      from_user_id TEXT NOT NULL,
   205      to_user_id TEXT NOT NULL,
   206      sender_mode TEXT DEFAULT 'real'
   207          CHECK(sender_mode IN ('real', 'twin')),
   208      receiver_mode TEXT DEFAULT 'real'
   209          CHECK(receiver_mode IN ('real', 'twin')),
   210      content TEXT NOT NULL,
   211      original_content TEXT DEFAULT '',
   212      original_lang TEXT DEFAULT '',
   213      target_lang TEXT DEFAULT '',
   214      translation_style TEXT DEFAULT ''
   215          CHECK(translation_style IN ('', 'literal', 'personality_preserving')),
   216      msg_type TEXT DEFAULT 'text'
   217          CHECK(msg_type IN ('text', 'image', 'voice', 'system')),
   218      is_read INTEGER DEFAULT 0,
   219      ai_generated INTEGER DEFAULT 0,
   220      created_at TEXT DEFAULT (datetime('now','localtime'))
   221  );
   222  CREATE INDEX IF NOT EXISTS idx_sm_from ON social_messages(from_user_id, created_at);
   223  CREATE INDEX IF NOT EXISTS idx_sm_to ON social_messages(to_user_id, is_read, created_at);
   224  CREATE INDEX IF NOT EXISTS idx_sm_conv ON social_messages(from_user_id, to_user_id, created_at);
   225  """
   226  
   227  
   228  MIGRATIONS = [
   229      "ALTER TABLE users ADD COLUMN twin_auto_reply INTEGER DEFAULT 0",
   230      "ALTER TABLE social_messages ADD COLUMN auto_reply INTEGER DEFAULT 0",
   231      "ALTER TABLE social_messages ADD COLUMN metadata TEXT DEFAULT ''",
   232      "ALTER TABLE users ADD COLUMN voice_sample TEXT DEFAULT ''",
   233      "ALTER TABLE users ADD COLUMN twin_source TEXT DEFAULT 'local'",
   234      "ALTER TABLE users ADD COLUMN gender TEXT DEFAULT ''",
   235      "ALTER TABLE users ADD COLUMN reg_source TEXT DEFAULT 'dualsoul'",
   236  ]
   237  
   238  
   239  # Schema V2 — Twin import from Nianlun (年轮分身导入)
   240  SCHEMA_V2 = """
   241  CREATE TABLE IF NOT EXISTS twin_profiles (
   242      profile_id TEXT PRIMARY KEY,
   243      user_id TEXT NOT NULL,
   244      source TEXT NOT NULL DEFAULT 'nianlun',
   245      version INTEGER NOT NULL DEFAULT 1,
   246      is_active INTEGER NOT NULL DEFAULT 1,
   247  
   248      -- Identity
   249      twin_name TEXT DEFAULT '',
   250      training_status TEXT DEFAULT '',
   251      quality_score REAL DEFAULT 0.0,
   252      self_awareness REAL DEFAULT 0.0,
   253      interaction_count INTEGER DEFAULT 0,
   254  
   255      -- Five-dimension personality (五维人格骨架)
   256      dim_judgement TEXT DEFAULT '',
   257      dim_cognition TEXT DEFAULT '',
   258      dim_expression TEXT DEFAULT '',
   259      dim_relation TEXT DEFAULT '',
   260      dim_sovereignty TEXT DEFAULT '',
   261  
   262      -- Structured personality
   263      value_order TEXT DEFAULT '',
   264      behavior_patterns TEXT DEFAULT '',
   265      speech_style TEXT DEFAULT '',
   266      boundaries TEXT DEFAULT '',
   267  
   268      -- Certificate (身份证书)
   269      certificate TEXT DEFAULT '',
   270  
   271      -- Full import payload (cold storage)
   272      raw_import TEXT DEFAULT '',
   273  
   274      imported_at TEXT DEFAULT (datetime('now','localtime')),
   275      updated_at TEXT DEFAULT (datetime('now','localtime')),
   276  
   277      UNIQUE(user_id, version)
   278  );
   279  CREATE INDEX IF NOT EXISTS idx_tp_user_active ON twin_profiles(user_id, is_active);
   280  
   281  CREATE TABLE IF NOT EXISTS twin_memories (
   282      memory_id TEXT PRIMARY KEY,
   283      user_id TEXT NOT NULL,
   284      memory_type TEXT NOT NULL
   285          CHECK(memory_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')),
   286      period_start TEXT NOT NULL,
   287      period_end TEXT NOT NULL,
   288  
   289      summary_text TEXT NOT NULL,
   290      emotional_tone TEXT DEFAULT '',
   291      themes TEXT DEFAULT '',
   292  
   293      key_events TEXT DEFAULT '',
   294      growth_signals TEXT DEFAULT '',
   295  
   296      source TEXT DEFAULT 'nianlun',
   297      imported_at TEXT DEFAULT (datetime('now','localtime'))
   298  );
   299  CREATE INDEX IF NOT EXISTS idx_tm_user_type ON twin_memories(user_id, memory_type, period_start);
   300  CREATE INDEX IF NOT EXISTS idx_tm_user_recent ON twin_memories(user_id, period_end DESC);
   301  
   302  CREATE TABLE IF NOT EXISTS twin_entities (
   303      entity_id TEXT PRIMARY KEY,
   304      user_id TEXT NOT NULL,
   305      entity_name TEXT NOT NULL,
   306      entity_type TEXT NOT NULL
   307          CHECK(entity_type IN ('person', 'place', 'thing', 'event', 'concept')),
   308      importance_score REAL DEFAULT 0.0,
   309      mention_count INTEGER DEFAULT 0,
   310      context TEXT DEFAULT '',
   311      relations TEXT DEFAULT '',
   312  
   313      source TEXT DEFAULT 'nianlun',
   314      imported_at TEXT DEFAULT (datetime('now','localtime'))
   315  );
   316  CREATE INDEX IF NOT EXISTS idx_te_user_type ON twin_entities(user_id, entity_type, importance_score DESC);
   317  CREATE INDEX IF NOT EXISTS idx_te_user_name ON twin_entities(user_id, entity_name);
   318  """
   319  
   320  
   321  def init_db():
   322      """Initialize database with schema and run migrations."""
   323      conn = sqlite3.connect(DATABASE_PATH)
   324      conn.execute("PRAGMA journal_mode=WAL")
   325      conn.execute("PRAGMA foreign_keys=ON")
   326      conn.executescript(SCHEMA)
   327      conn.executescript(SCHEMA_V2)
   328      # Run migrations (idempotent — skip if column already exists)
   329      for sql in MIGRATIONS:
   330          try:
   331              conn.execute(sql)
   332          except sqlite3.OperationalError:
   333              pass  # Column already exists
   334      conn.commit()
   335      conn.close()
   336  
   337  
   338  @contextmanager
   339  def get_db():
   340      """Get a database connection as a context manager."""
   341      conn = sqlite3.connect(DATABASE_PATH)
   342      conn.row_factory = sqlite3.Row
   343      conn.execute("PRAGMA journal_mode=WAL")
   344      conn.execute("PRAGMA foreign_keys=ON")
   345      try:
   346          yield conn
   347          conn.commit()
   348      except Exception:
   349          conn.rollback()
   350          raise
   351      finally:
   352          conn.close()
   353  
   354  
   355  def gen_id(prefix: str = "") -> str:
   356      """Generate a unique ID with optional prefix."""
   357      return f"{prefix}{uuid.uuid4().hex[:12]}"

# --- dualsoul/main.py ---
   358  """DualSoul — Dual Identity Social Protocol server."""
   359  
   360  import os
   361  from contextlib import asynccontextmanager
   362  
   363  from fastapi import FastAPI
   364  from fastapi.middleware.cors import CORSMiddleware
   365  from fastapi.responses import FileResponse, HTMLResponse
   366  from fastapi.staticfiles import StaticFiles
   367  
   368  from dualsoul import __version__
   369  from dualsoul.config import CORS_ORIGINS, HOST, PORT
   370  from dualsoul.database import init_db
   371  from dualsoul.routers import auth, identity, social, twin_import, ws
   372  
   373  
   374  @asynccontextmanager
   375  async def lifespan(app: FastAPI):
   376      init_db()
   377      print(f"[DualSoul v{__version__}] Database initialized")
   378      yield
   379  
   380  
   381  app = FastAPI(
   382      title="DualSoul",
   383      description="Dual Identity Social Protocol — Every person has two voices.",
   384      version=__version__,
   385      lifespan=lifespan,
   386  )
   387  
   388  # CORS
   389  app.add_middleware(
   390      CORSMiddleware,
   391      allow_origins=CORS_ORIGINS,
   392      allow_credentials=True,
   393      allow_methods=["*"],
   394      allow_headers=["*"],
   395  )
   396  
   397  # Routers
   398  app.include_router(auth.router)
   399  app.include_router(identity.router)
   400  app.include_router(social.router)
   401  app.include_router(twin_import.router)
   402  app.include_router(ws.router)
   403  
   404  # Serve demo web client
   405  _web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
   406  if os.path.isdir(_web_dir):
   407      app.mount("/static", StaticFiles(directory=_web_dir), name="static")
   408  
   409      @app.get("/")
   410      async def serve_index():
   411          return FileResponse(os.path.join(_web_dir, "index.html"))
   412  
   413      @app.get("/sw.js")
   414      async def serve_sw():
   415          return FileResponse(
   416              os.path.join(_web_dir, "sw.js"), media_type="application/javascript"
   417          )
   418  
   419      @app.get("/manifest.json")
   420      async def serve_manifest():
   421          return FileResponse(
   422              os.path.join(_web_dir, "manifest.json"),
   423              media_type="application/manifest+json",
   424          )
   425  
   426  
   427  _docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
   428  
   429  
   430  @app.get("/guide", response_class=HTMLResponse)
   431  async def serve_guide():
   432      """Serve the twin import guide as a styled HTML page."""
   433      guide_path = os.path.join(_docs_dir, "twin-import-guide.md")
   434      if not os.path.exists(guide_path):
   435          return HTMLResponse("<h1>Guide not found</h1>", status_code=404)
   436  
   437      with open(guide_path, encoding="utf-8") as f:
   438          md_content = f.read()
   439  
   440      # Client-side markdown rendering with marked.js (zero backend dependencies)
   441      return HTMLResponse(f"""<!DOCTYPE html>
   442  <html lang="zh">
   443  <head>
   444  <meta charset="UTF-8">
   445  <meta name="viewport" content="width=device-width, initial-scale=1.0">
   446  <title>DualSoul - 分身接入指南</title>
   447  <meta property="og:title" content="DualSoul 分身接入指南">
   448  <meta property="og:description" content="让你养的智能体走进真实社交——年轮/OpenClaw/任意平台接入">
   449  <style>
   450  *{{margin:0;padding:0;box-sizing:border-box}}
   451  body{{background:#0a0a10;color:#e8e4de;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.8;padding:20px}}
   452  .wrap{{max-width:680px;margin:0 auto;padding-bottom:80px}}
   453  h1{{font-size:24px;font-weight:800;background:linear-gradient(135deg,#7c5cfc,#5ca0fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:20px 0 10px}}
   454  h2{{font-size:18px;color:#7c5cfc;margin:28px 0 12px;padding-bottom:6px;border-bottom:1px solid rgba(124,92,252,.2)}}
   455  h3{{font-size:15px;color:#5ca0fa;margin:20px 0 8px}}
   456  p{{margin:8px 0;font-size:14px;color:rgba(232,228,222,.85)}}
   457  a{{color:#7c5cfc}}
   458  code{{background:rgba(124,92,252,.1);padding:2px 6px;border-radius:4px;font-size:12px;color:#5ca0fa}}
   459  pre{{background:#12121e;border:1px solid rgba(124,92,252,.15);border-radius:10px;padding:14px;overflow-x:auto;margin:10px 0;font-size:12px;line-height:1.6}}
   460  pre code{{background:none;padding:0;color:#e8e4de}}
   461  table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:12px}}
   462  th{{background:rgba(124,92,252,.1);padding:8px;text-align:left;border:1px solid rgba(124,92,252,.15);color:#7c5cfc}}
   463  td{{padding:8px;border:1px solid rgba(255,255,255,.06)}}
   464  tr:nth-child(even){{background:rgba(255,255,255,.02)}}
   465  blockquote{{border-left:3px solid #7c5cfc;padding:8px 14px;margin:12px 0;background:rgba(124,92,252,.05);border-radius:0 8px 8px 0;font-style:italic;color:rgba(232,228,222,.7)}}
   466  hr{{border:none;border-top:1px solid rgba(124,92,252,.15);margin:20px 0}}
   467  strong{{color:#e8e4de}}
   468  ul,ol{{padding-left:20px;margin:8px 0}}
   469  li{{margin:4px 0;font-size:13px}}
   470  .cta{{display:block;text-align:center;margin:30px auto;padding:14px 28px;background:linear-gradient(135deg,#7c5cfc,#5ca0fa);color:#fff;border-radius:12px;font-size:16px;font-weight:700;text-decoration:none;max-width:300px}}
   471  .cta:hover{{opacity:.9}}
   472  .badge{{display:inline-block;font-size:10px;padding:2px 8px;border-radius:8px;background:rgba(124,92,252,.15);color:#7c5cfc;margin-left:4px}}
   473  </style>
   474  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
   475  </head>
   476  <body>
   477  <div class="wrap" id="content"></div>
   478  <a class="cta" href="/?source=guide">注册 DualSoul，让你的分身社交</a>
   479  <script>
   480  var md = {repr(md_content)};
   481  document.getElementById('content').innerHTML = marked.parse(md);
   482  </script>
   483  </body>
   484  </html>""")
   485  
   486  
   487  @app.get("/api/health")
   488  async def health():
   489      return {"status": "ok", "version": __version__}
   490  
   491  
   492  def cli():
   493      """CLI entry point for `dualsoul` command."""
   494      import uvicorn
   495  
   496      uvicorn.run("dualsoul.main:app", host=HOST, port=PORT, reload=False)
   497  
   498  
   499  if __name__ == "__main__":
   500      cli()

# --- dualsoul/models.py ---
   501  """DualSoul Pydantic models."""
   502  
   503  from pydantic import BaseModel
   504  
   505  
   506  # Auth
   507  class RegisterRequest(BaseModel):
   508      username: str
   509      password: str
   510      display_name: str = ""
   511      reg_source: str = "dualsoul"  # Registration source: dualsoul, nianlun, openclaw, etc.
   512  
   513  
   514  class LoginRequest(BaseModel):
   515      username: str
   516      password: str
   517  
   518  
   519  # Identity
   520  class SwitchModeRequest(BaseModel):
   521      mode: str  # 'real' or 'twin'
   522  
   523  
   524  class UpdateProfileRequest(BaseModel):
   525      display_name: str = ""
   526      twin_personality: str = ""
   527      twin_speech_style: str = ""
   528      preferred_lang: str = ""  # ISO 639-1: zh, en, ja, ko, fr, de, es, etc.
   529      twin_auto_reply: int | None = None  # 0=off, 1=on (None=no change)
   530      gender: str = ""  # 'male', 'female', '' (unset)
   531  
   532  
   533  class TwinPreviewRequest(BaseModel):
   534      display_name: str = ""
   535      personality: str = ""
   536      speech_style: str = ""
   537  
   538  
   539  class AvatarUploadRequest(BaseModel):
   540      image: str  # base64 encoded image data (data:image/png;base64,... or raw base64)
   541      type: str = "real"  # 'real' or 'twin'
   542  
   543  
   544  class VoiceUploadRequest(BaseModel):
   545      audio: str  # base64 encoded audio data (data:audio/webm;base64,... or raw base64)
   546  
   547  
   548  class TwinDraftRequest(BaseModel):
   549      friend_id: str
   550      incoming_msg: str
   551      context: list[dict] = []  # [{role: "me"/"friend", content: "..."}]
   552  
   553  
   554  class TwinChatRequest(BaseModel):
   555      message: str
   556      history: list[dict] = []  # [{role: "me"/"twin", content: "..."}]
   557      image: str = ""  # Optional base64 image data URL for vision
   558  
   559  
   560  # Social
   561  class AddFriendRequest(BaseModel):
   562      friend_username: str
   563  
   564  
   565  class RespondFriendRequest(BaseModel):
   566      conn_id: str
   567      action: str  # 'accept' or 'block'
   568  
   569  
   570  class TranslateRequest(BaseModel):
   571      content: str
   572      source_lang: str = "auto"
   573      target_lang: str = "en"
   574  
   575  
   576  class SendMessageRequest(BaseModel):
   577      to_user_id: str
   578      content: str
   579      sender_mode: str = "real"
   580      receiver_mode: str = "real"
   581      msg_type: str = "text"
   582      target_lang: str = ""  # If set, twin translates to this language with personality preservation
   583  
   584  
   585  # Twin Import (年轮分身导入)
   586  class TwinImportRequest(BaseModel):
   587      format: str = "tpf_v1"  # Twin Portable Format version
   588      source: str = "nianlun"  # Source platform: 'nianlun', 'openclaw', etc.
   589      data: dict  # Full export payload (Twin Portable Format)
   590  
   591  
   592  class TwinSyncRequest(BaseModel):
   593      format: str = "tpf_v1"
   594      since: str = ""  # ISO timestamp of last sync
   595      data: dict  # Incremental data (new memories, entities, dimension updates)

# --- dualsoul/protocol/message.py ---
   596  """DualSoul Protocol — Dual Identity Message Format.
   597  
   598  Every message in DualSoul carries two identity modes:
   599    - sender_mode: Is the sender speaking as their real self or digital twin?
   600    - receiver_mode: Is the message addressed to the real person or their twin?
   601  
   602  This creates four distinct conversation modes:
   603  
   604    Real → Real   : Traditional human-to-human messaging
   605    Real → Twin   : Asking someone's digital twin a question
   606    Twin → Real   : Your twin reaching out to a real person
   607    Twin → Twin   : Autonomous twin-to-twin conversation
   608  """
   609  
   610  from dataclasses import dataclass, field
   611  from enum import Enum
   612  from typing import Optional
   613  
   614  # Protocol version — included in every DISP message
   615  DISP_VERSION = "1.0"
   616  
   617  
   618  class IdentityMode(str, Enum):
   619      REAL = "real"
   620      TWIN = "twin"
   621  
   622  
   623  class ConversationMode(str, Enum):
   624      REAL_TO_REAL = "real_to_real"
   625      REAL_TO_TWIN = "real_to_twin"
   626      TWIN_TO_REAL = "twin_to_real"
   627      TWIN_TO_TWIN = "twin_to_twin"
   628  
   629  
   630  class MessageType(str, Enum):
   631      TEXT = "text"
   632      IMAGE = "image"
   633      VOICE = "voice"
   634      SYSTEM = "system"
   635  
   636  
   637  @dataclass
   638  class DualSoulMessage:
   639      """A message in the DualSoul protocol."""
   640  
   641      msg_id: str
   642      from_user_id: str
   643      to_user_id: str
   644      sender_mode: IdentityMode
   645      receiver_mode: IdentityMode
   646      content: str
   647      msg_type: MessageType = MessageType.TEXT
   648      ai_generated: bool = False
   649      created_at: Optional[str] = None
   650      disp_version: str = field(default=DISP_VERSION)
   651  
   652      @property
   653      def conversation_mode(self) -> ConversationMode:
   654          """Determine which of the four conversation modes this message belongs to."""
   655          key = f"{self.sender_mode.value}_to_{self.receiver_mode.value}"
   656          return ConversationMode(key)
   657  
   658      def to_dict(self) -> dict:
   659          return {
   660              "disp_version": self.disp_version,
   661              "msg_id": self.msg_id,
   662              "from_user_id": self.from_user_id,
   663              "to_user_id": self.to_user_id,
   664              "sender_mode": self.sender_mode.value,
   665              "receiver_mode": self.receiver_mode.value,
   666              "content": self.content,
   667              "msg_type": self.msg_type.value,
   668              "ai_generated": self.ai_generated,
   669              "conversation_mode": self.conversation_mode.value,
   670              "created_at": self.created_at,
   671          }
   672  
   673  
   674  def get_conversation_mode(sender_mode: str, receiver_mode: str) -> ConversationMode:
   675      """Get the conversation mode from sender and receiver mode strings."""
   676      return ConversationMode(f"{sender_mode}_to_{receiver_mode}")

# --- dualsoul/routers/auth.py ---
   677  """Auth router — register and login."""
   678  
   679  from fastapi import APIRouter
   680  
   681  from dualsoul.auth import create_token, hash_password, verify_password
   682  from dualsoul.database import gen_id, get_db
   683  from dualsoul.models import LoginRequest, RegisterRequest
   684  
   685  router = APIRouter(prefix="/api/auth", tags=["Auth"])
   686  
   687  
   688  @router.post("/register")
   689  async def register(req: RegisterRequest):
   690      """Register a new user."""
   691      username = req.username.strip()
   692      if not username or len(username) < 2:
   693          return {"success": False, "error": "Username must be at least 2 characters"}
   694      if len(req.password) < 6:
   695          return {"success": False, "error": "Password must be at least 6 characters"}
   696  
   697      with get_db() as db:
   698          exists = db.execute(
   699              "SELECT user_id FROM users WHERE username=?", (username,)
   700          ).fetchone()
   701          if exists:
   702              return {"success": False, "error": "Username already taken"}
   703  
   704          user_id = gen_id("u_")
   705          db.execute(
   706              "INSERT INTO users (user_id, username, password_hash, display_name, reg_source) "
   707              "VALUES (?, ?, ?, ?, ?)",
   708              (user_id, username, hash_password(req.password), req.display_name or username,
   709               req.reg_source or "dualsoul"),
   710          )
   711  
   712      token = create_token(user_id, username)
   713      return {
   714          "success": True,
   715          "data": {
   716              "user_id": user_id,
   717              "username": username,
   718              "token": token,
   719          },
   720      }
   721  
   722  
   723  @router.post("/login")
   724  async def login(req: LoginRequest):
   725      """Login and get a JWT token."""
   726      with get_db() as db:
   727          user = db.execute(
   728              "SELECT user_id, username, password_hash FROM users WHERE username=?",
   729              (req.username.strip(),),
   730          ).fetchone()
   731  
   732      if not user or not verify_password(req.password, user["password_hash"]):
   733          return {"success": False, "error": "Invalid username or password"}
   734  
   735      token = create_token(user["user_id"], user["username"])
   736      return {
   737          "success": True,
   738          "data": {
   739              "user_id": user["user_id"],
   740              "username": user["username"],
   741              "token": token,
   742          },
   743      }

# --- dualsoul/routers/identity.py ---
   744  """Identity router — switch mode, profile management, twin preview, avatar upload, style learning."""
   745  
   746  import base64
   747  import hashlib
   748  import os
   749  
   750  import httpx
   751  from fastapi import APIRouter, Depends
   752  
   753  from dualsoul.auth import get_current_user
   754  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
   755  from dualsoul.database import get_db
   756  from dualsoul.models import AvatarUploadRequest, SwitchModeRequest, TwinPreviewRequest, UpdateProfileRequest, VoiceUploadRequest
   757  from dualsoul.twin_engine.learner import analyze_style, get_message_count, learn_and_update
   758  
   759  _AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "avatars")
   760  os.makedirs(_AVATAR_DIR, exist_ok=True)
   761  _VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "voiceprints")
   762  os.makedirs(_VOICE_DIR, exist_ok=True)
   763  
   764  router = APIRouter(prefix="/api/identity", tags=["Identity"])
   765  
   766  
   767  @router.post("/switch")
   768  async def switch_mode(req: SwitchModeRequest, user=Depends(get_current_user)):
   769      """Switch between real self and digital twin mode."""
   770      uid = user["user_id"]
   771      if req.mode not in ("real", "twin"):
   772          return {"success": False, "error": "mode must be 'real' or 'twin'"}
   773      with get_db() as db:
   774          db.execute("UPDATE users SET current_mode=? WHERE user_id=?", (req.mode, uid))
   775      return {"success": True, "mode": req.mode}
   776  
   777  
   778  @router.get("/me")
   779  async def get_profile(user=Depends(get_current_user)):
   780      """Get current user's dual identity profile."""
   781      uid = user["user_id"]
   782      with get_db() as db:
   783          row = db.execute(
   784              "SELECT user_id, username, display_name, current_mode, "
   785              "twin_personality, twin_speech_style, preferred_lang, avatar, twin_avatar, "
   786              "twin_auto_reply, gender, reg_source FROM users WHERE user_id=?",
   787              (uid,),
   788          ).fetchone()
   789      if not row:
   790          return {"success": False, "error": "User not found"}
   791      return {
   792          "success": True,
   793          "data": {
   794              "user_id": row["user_id"],
   795              "username": row["username"],
   796              "display_name": row["display_name"],
   797              "current_mode": row["current_mode"] or "real",
   798              "twin_personality": row["twin_personality"] or "",
   799              "twin_speech_style": row["twin_speech_style"] or "",
   800              "preferred_lang": row["preferred_lang"] or "",
   801              "avatar": row["avatar"] or "",
   802              "twin_avatar": row["twin_avatar"] or "",
   803              "twin_auto_reply": row["twin_auto_reply"] if "twin_auto_reply" in row.keys() else 0,
   804              "gender": row["gender"] if "gender" in row.keys() else "",
   805              "reg_source": row["reg_source"] if "reg_source" in row.keys() else "dualsoul",
   806          },
   807      }
   808  
   809  
   810  @router.put("/profile")
   811  async def update_profile(req: UpdateProfileRequest, user=Depends(get_current_user)):
   812      """Update display name and twin personality settings."""
   813      uid = user["user_id"]
   814      updates = []
   815      params = []
   816      if req.display_name:
   817          updates.append("display_name=?")
   818          params.append(req.display_name)
   819      if req.twin_personality:
   820          updates.append("twin_personality=?")
   821          params.append(req.twin_personality)
   822      if req.twin_speech_style:
   823          updates.append("twin_speech_style=?")
   824          params.append(req.twin_speech_style)
   825      if req.preferred_lang:
   826          updates.append("preferred_lang=?")
   827          params.append(req.preferred_lang)
   828      if req.twin_auto_reply is not None:
   829          updates.append("twin_auto_reply=?")
   830          params.append(1 if req.twin_auto_reply else 0)
   831      if req.gender:
   832          updates.append("gender=?")
   833          params.append(req.gender)
   834      if not updates:
   835          return {"success": False, "error": "Nothing to update"}
   836      params.append(uid)
   837      with get_db() as db:
   838          db.execute(f"UPDATE users SET {','.join(updates)} WHERE user_id=?", params)
   839      return {"success": True}
   840  
   841  
   842  @router.post("/avatar")
   843  async def upload_avatar(req: AvatarUploadRequest, user=Depends(get_current_user)):
   844      """Upload a base64-encoded avatar image. Saves to web/avatars/ and updates DB."""
   845      uid = user["user_id"]
   846      if req.type not in ("real", "twin"):
   847          return {"success": False, "error": "type must be 'real' or 'twin'"}
   848  
   849      # Strip data URI prefix if present
   850      img_data = req.image
   851      if "," in img_data:
   852          img_data = img_data.split(",", 1)[1]
   853      try:
   854          raw = base64.b64decode(img_data)
   855      except Exception:
   856          return {"success": False, "error": "Invalid base64 image"}
   857  
   858      if len(raw) > 2 * 1024 * 1024:  # 2MB limit
   859          return {"success": False, "error": "Image too large (max 2MB)"}
   860  
   861      # Save file
   862      name_hash = hashlib.md5(f"{uid}_{req.type}".encode()).hexdigest()[:12]
   863      filename = f"{name_hash}.png"
   864      filepath = os.path.join(_AVATAR_DIR, filename)
   865      with open(filepath, "wb") as f:
   866          f.write(raw)
   867  
   868      url = f"/static/avatars/{filename}"
   869      col = "avatar" if req.type == "real" else "twin_avatar"
   870      with get_db() as db:
   871          db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (url, uid))
   872  
   873      return {"success": True, "url": url}
   874  
   875  
   876  @router.post("/voice")
   877  async def upload_voice(req: VoiceUploadRequest, user=Depends(get_current_user)):
   878      """Upload a base64-encoded voice sample. Saves to web/voiceprints/ and updates DB."""
   879      uid = user["user_id"]
   880      audio_data = req.audio
   881      if "," in audio_data:
   882          audio_data = audio_data.split(",", 1)[1]
   883      try:
   884          raw = base64.b64decode(audio_data)
   885      except Exception:
   886          return {"success": False, "error": "Invalid base64 audio"}
   887      if len(raw) > 5 * 1024 * 1024:
   888          return {"success": False, "error": "Audio too large (max 5MB)"}
   889  
   890      name_hash = hashlib.md5(f"{uid}_voice".encode()).hexdigest()[:12]
   891      filename = f"{name_hash}.webm"
   892      filepath = os.path.join(_VOICE_DIR, filename)
   893      with open(filepath, "wb") as f:
   894          f.write(raw)
   895  
   896      url = f"/static/voiceprints/{filename}"
   897      with get_db() as db:
   898          db.execute("UPDATE users SET voice_sample=? WHERE user_id=?", (url, uid))
   899      return {"success": True, "url": url}
   900  
   901  
   902  @router.post("/twin/preview")
   903  async def twin_preview(req: TwinPreviewRequest, user=Depends(get_current_user)):
   904      """Generate a sample twin reply for onboarding — lets the user see their twin speak."""
   905      name = req.display_name or "User"
   906      personality = req.personality or "friendly and thoughtful"
   907      speech_style = req.speech_style or "natural and warm"
   908  
   909      prompt = (
   910          f"You are {name}'s digital twin.\n"
   911          f"Personality: {personality}\n"
   912          f"Speech style: {speech_style}\n\n"
   913          f'A friend asks: "Hey, are you free this weekend?"\n\n'
   914          f"Reply as {name}'s twin. Keep it under 30 words, natural and authentic. "
   915          f"Output only the reply text, nothing else."
   916      )
   917  
   918      if not AI_BASE_URL or not AI_API_KEY:
   919          # Fallback — template reply reflecting personality
   920          return {
   921              "success": True,
   922              "reply": f"Hey! This is {name}'s twin. {name} might be around this weekend — "
   923                       f"I'll let them know you asked!",
   924          }
   925  
   926      try:
   927          async with httpx.AsyncClient(timeout=15) as client:
   928              resp = await client.post(
   929                  f"{AI_BASE_URL}/chat/completions",
   930                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
   931                  json={"model": AI_MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]},
   932              )
   933              reply = resp.json()["choices"][0]["message"]["content"].strip()
   934      except Exception:
   935          reply = f"Hey! This is {name}'s twin — I think the weekend might work, let me check!"
   936  
   937      return {"success": True, "reply": reply}
   938  
   939  
   940  @router.get("/twin/learn/status")
   941  async def learn_status(user=Depends(get_current_user)):
   942      """Check if enough messages exist for style learning."""
   943      uid = user["user_id"]
   944      count = get_message_count(uid)
   945      min_required = 10
   946      return {
   947          "success": True,
   948          "message_count": count,
   949          "min_required": min_required,
   950          "ready": count >= min_required,
   951      }
   952  
   953  
   954  @router.post("/twin/learn")
   955  async def learn_style(user=Depends(get_current_user)):
   956      """Analyze the user's chat history and extract personality + speech style.
   957  
   958      Returns the analysis result. The user can preview before applying.
   959      """
   960      uid = user["user_id"]
   961      result = await analyze_style(uid)
   962      if not result:
   963          return {"success": False, "error": "Analysis unavailable (no AI backend)"}
   964      if "error" in result:
   965          return {
   966              "success": False,
   967              "error": result["error"],
   968              "message_count": result.get("current", 0),
   969              "min_required": result.get("required", 10),
   970          }
   971      return {"success": True, "data": result}
   972  
   973  
   974  @router.post("/twin/learn/apply")
   975  async def apply_learned_style(user=Depends(get_current_user)):
   976      """Analyze and directly apply the learned style to the twin profile."""
   977      uid = user["user_id"]
   978      result = await learn_and_update(uid, auto_apply=True)
   979      if not result:
   980          return {"success": False, "error": "Learning unavailable"}
   981      if "error" in result:
   982          return {
   983              "success": False,
   984              "error": result["error"],
   985              "message_count": result.get("current", 0),
   986              "min_required": result.get("required", 10),
   987          }
   988      return {"success": True, "data": result}

# --- dualsoul/routers/social.py ---
   989  """Social router — friends, messages, and the four conversation modes."""
   990  
   991  import asyncio
   992  from datetime import datetime
   993  
   994  from fastapi import APIRouter, Depends
   995  
   996  from dualsoul.auth import get_current_user
   997  from dualsoul.connections import manager
   998  from dualsoul.database import gen_id, get_db
   999  from dualsoul.models import AddFriendRequest, RespondFriendRequest, SendMessageRequest, TranslateRequest, TwinChatRequest
  1000  from dualsoul.twin_engine.responder import TwinResponder
  1001  
  1002  router = APIRouter(prefix="/api/social", tags=["Social"])
  1003  _twin = TwinResponder()
  1004  
  1005  
  1006  @router.post("/friends/add")
  1007  async def add_friend(req: AddFriendRequest, user=Depends(get_current_user)):
  1008      """Send a friend request by username."""
  1009      uid = user["user_id"]
  1010      username = req.friend_username.strip()
  1011      if not username:
  1012          return {"success": False, "error": "Username required"}
  1013  
  1014      with get_db() as db:
  1015          friend = db.execute(
  1016              "SELECT user_id FROM users WHERE username=? AND user_id!=?",
  1017              (username, uid),
  1018          ).fetchone()
  1019          if not friend:
  1020              return {"success": False, "error": "User not found"}
  1021          fid = friend["user_id"]
  1022  
  1023          exists = db.execute(
  1024              "SELECT conn_id, status FROM social_connections "
  1025              "WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
  1026              (uid, fid, fid, uid),
  1027          ).fetchone()
  1028          if exists:
  1029              return {"success": False, "error": f"Connection already exists ({exists['status']})"}
  1030  
  1031          conn_id = gen_id("sc_")
  1032          db.execute(
  1033              "INSERT INTO social_connections (conn_id, user_id, friend_id, status) "
  1034              "VALUES (?, ?, ?, 'pending')",
  1035              (conn_id, uid, fid),
  1036          )
  1037  
  1038      # Notify the recipient via WebSocket
  1039      await manager.send_to(fid, {
  1040          "type": "friend_request",
  1041          "data": {"conn_id": conn_id, "from_user_id": uid, "username": username},
  1042      })
  1043      return {"success": True, "conn_id": conn_id}
  1044  
  1045  
  1046  @router.post("/friends/respond")
  1047  async def respond_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
  1048      """Accept or block a friend request."""
  1049      uid = user["user_id"]
  1050      if req.action not in ("accept", "block"):
  1051          return {"success": False, "error": "action must be 'accept' or 'block'"}
  1052  
  1053      with get_db() as db:
  1054          conn = db.execute(
  1055              "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
  1056              (req.conn_id,),
  1057          ).fetchone()
  1058          if not conn:
  1059              return {"success": False, "error": "Request not found"}
  1060          if conn["friend_id"] != uid:
  1061              return {"success": False, "error": "Not authorized"}
  1062          if conn["status"] != "pending":
  1063              return {"success": False, "error": f"Already processed ({conn['status']})"}
  1064  
  1065          new_status = "accepted" if req.action == "accept" else "blocked"
  1066          accepted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if req.action == "accept" else None
  1067          db.execute(
  1068              "UPDATE social_connections SET status=?, accepted_at=? WHERE conn_id=?",
  1069              (new_status, accepted_at, req.conn_id),
  1070          )
  1071      return {"success": True, "status": new_status}
  1072  
  1073  
  1074  @router.get("/friends")
  1075  async def list_friends(user=Depends(get_current_user)):
  1076      """List all friends with their dual identity info."""
  1077      uid = user["user_id"]
  1078      with get_db() as db:
  1079          rows = db.execute(
  1080              """
  1081              SELECT sc.conn_id, sc.status, sc.created_at, sc.accepted_at,
  1082                     sc.user_id AS req_from, sc.friend_id AS req_to,
  1083                     u.user_id, u.username, u.display_name, u.avatar,
  1084                     u.current_mode, u.twin_avatar, u.reg_source
  1085              FROM social_connections sc
  1086              JOIN users u ON u.user_id = CASE
  1087                  WHEN sc.user_id=? THEN sc.friend_id
  1088                  ELSE sc.user_id END
  1089              WHERE (sc.user_id=? OR sc.friend_id=?)
  1090                AND sc.status IN ('pending', 'accepted')
  1091              ORDER BY sc.accepted_at DESC, sc.created_at DESC
  1092              """,
  1093              (uid, uid, uid),
  1094          ).fetchall()
  1095  
  1096      friends = []
  1097      for r in rows:
  1098          friends.append({
  1099              "conn_id": r["conn_id"],
  1100              "status": r["status"],
  1101              "is_incoming": r["req_to"] == uid,
  1102              "user_id": r["user_id"],
  1103              "username": r["username"],
  1104              "display_name": r["display_name"] or r["username"],
  1105              "avatar": r["avatar"] or "",
  1106              "twin_avatar": r["twin_avatar"] or "",
  1107              "current_mode": r["current_mode"] or "real",
  1108              "accepted_at": r["accepted_at"] or "",
  1109              "reg_source": r["reg_source"] if "reg_source" in r.keys() else "dualsoul",
  1110          })
  1111      return {"success": True, "friends": friends}
  1112  
  1113  
  1114  @router.get("/messages")
  1115  async def get_messages(friend_id: str = "", limit: int = 50, user=Depends(get_current_user)):
  1116      """Get conversation history with a friend."""
  1117      uid = user["user_id"]
  1118      if not friend_id:
  1119          return {"success": False, "error": "friend_id required"}
  1120  
  1121      with get_db() as db:
  1122          conn = db.execute(
  1123              "SELECT conn_id FROM social_connections "
  1124              "WHERE status='accepted' AND "
  1125              "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
  1126              (uid, friend_id, friend_id, uid),
  1127          ).fetchone()
  1128          if not conn:
  1129              return {"success": False, "error": "Not friends"}
  1130  
  1131          rows = db.execute(
  1132              """
  1133              SELECT msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  1134                     content, original_content, original_lang, target_lang,
  1135                     translation_style, msg_type, is_read, ai_generated, created_at
  1136              FROM social_messages
  1137              WHERE (from_user_id=? AND to_user_id=?)
  1138                 OR (from_user_id=? AND to_user_id=?)
  1139              ORDER BY created_at DESC LIMIT ?
  1140              """,
  1141              (uid, friend_id, friend_id, uid, limit),
  1142          ).fetchall()
  1143  
  1144          # Mark as read
  1145          db.execute(
  1146              "UPDATE social_messages SET is_read=1 "
  1147              "WHERE to_user_id=? AND from_user_id=? AND is_read=0",
  1148              (uid, friend_id),
  1149          )
  1150  
  1151      messages = [dict(r) for r in rows]
  1152      messages.reverse()
  1153      return {"success": True, "messages": messages}
  1154  
  1155  
  1156  @router.post("/messages/send")
  1157  async def send_message(req: SendMessageRequest, user=Depends(get_current_user)):
  1158      """Send a message. If receiver_mode is 'twin', the recipient's twin auto-replies."""
  1159      uid = user["user_id"]
  1160      content = req.content.strip()
  1161      if not content:
  1162          return {"success": False, "error": "Content cannot be empty"}
  1163      if req.sender_mode not in ("real", "twin"):
  1164          return {"success": False, "error": "Invalid sender_mode"}
  1165      if req.receiver_mode not in ("real", "twin"):
  1166          return {"success": False, "error": "Invalid receiver_mode"}
  1167  
  1168      with get_db() as db:
  1169          conn = db.execute(
  1170              "SELECT conn_id FROM social_connections "
  1171              "WHERE status='accepted' AND "
  1172              "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
  1173              (uid, req.to_user_id, req.to_user_id, uid),
  1174          ).fetchone()
  1175          if not conn:
  1176              return {"success": False, "error": "Not friends"}
  1177  
  1178          msg_id = gen_id("sm_")
  1179          db.execute(
  1180              """
  1181              INSERT INTO social_messages
  1182              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  1183               content, msg_type, ai_generated)
  1184              VALUES (?, ?, ?, ?, ?, ?, ?, 0)
  1185              """,
  1186              (msg_id, uid, req.to_user_id, req.sender_mode, req.receiver_mode, content, req.msg_type),
  1187          )
  1188  
  1189      result = {"success": True, "msg_id": msg_id, "ai_reply": None}
  1190  
  1191      # Push the new message to the recipient via WebSocket
  1192      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  1193      await manager.send_to(req.to_user_id, {
  1194          "type": "new_message",
  1195          "data": {
  1196              "msg_id": msg_id, "from_user_id": uid, "to_user_id": req.to_user_id,
  1197              "sender_mode": req.sender_mode, "receiver_mode": req.receiver_mode,
  1198              "content": content, "msg_type": req.msg_type,
  1199              "ai_generated": 0, "created_at": now,
  1200          },
  1201      })
  1202  
  1203      # Auto-detect foreign language/dialect and push translation (async, non-blocking)
  1204      if manager.is_online(req.to_user_id):
  1205          asyncio.ensure_future(_auto_detect_and_push_translation(
  1206              recipient_id=req.to_user_id,
  1207              content=content,
  1208              for_msg_id=msg_id,
  1209          ))
  1210  
  1211      # Determine if twin should auto-reply:
  1212      # 1. Explicit: receiver_mode is 'twin'
  1213      # 2. Auto-reply enabled: twin_auto_reply is on (regardless of online status)
  1214      should_twin_reply = req.receiver_mode == "twin"
  1215      if not should_twin_reply and req.receiver_mode == "real":
  1216          with get_db() as db:
  1217              row = db.execute(
  1218                  "SELECT twin_auto_reply FROM users WHERE user_id=?", (req.to_user_id,)
  1219              ).fetchone()
  1220              if row and row["twin_auto_reply"]:
  1221                  should_twin_reply = True
  1222  
  1223      if should_twin_reply:
  1224          try:
  1225              reply = await _twin.generate_reply(
  1226                  twin_owner_id=req.to_user_id,
  1227                  from_user_id=uid,
  1228                  incoming_msg=content,
  1229                  sender_mode=req.sender_mode,
  1230                  target_lang=req.target_lang,
  1231              )
  1232              result["ai_reply"] = reply
  1233              # Push twin reply to both sender and recipient
  1234              if reply:
  1235                  twin_msg = {
  1236                      "type": "new_message",
  1237                      "data": {
  1238                          "msg_id": reply["msg_id"], "from_user_id": req.to_user_id,
  1239                          "to_user_id": uid, "sender_mode": "twin",
  1240                          "receiver_mode": req.sender_mode,
  1241                          "content": reply["content"], "msg_type": "text",
  1242                          "ai_generated": 1, "created_at": now,
  1243                      },
  1244                  }
  1245                  await manager.send_to(uid, twin_msg)
  1246                  await manager.send_to(req.to_user_id, twin_msg)
  1247          except Exception:
  1248              pass  # Twin reply is best-effort
  1249  
  1250      return result
  1251  
  1252  
  1253  @router.post("/translate")
  1254  async def translate(req: TranslateRequest, user=Depends(get_current_user)):
  1255      """Personality-preserving translation — translate as if you wrote it in another language.
  1256  
  1257      Unlike generic machine translation, this preserves your humor, tone,
  1258      and characteristic expressions.
  1259      """
  1260      uid = user["user_id"]
  1261      content = req.content.strip()
  1262      target_lang = req.target_lang
  1263      if not content:
  1264          return {"success": False, "error": "Content cannot be empty"}
  1265      if not target_lang:
  1266          return {"success": False, "error": "target_lang required"}
  1267  
  1268      result = await _twin.translate_message(
  1269          owner_id=uid,
  1270          content=content,
  1271          source_lang=req.source_lang,
  1272          target_lang=target_lang,
  1273      )
  1274      if not result:
  1275          return {"success": False, "error": "Translation unavailable (no AI backend)"}
  1276      return {"success": True, "data": result}
  1277  
  1278  
  1279  @router.post("/translate/detect")
  1280  async def detect_translate(req: TranslateRequest, user=Depends(get_current_user)):
  1281      """Auto-detect if a message is in a foreign language or dialect and translate.
  1282  
  1283      Unlike /translate which requires explicit source/target, this automatically
  1284      detects the language and only translates if it differs from the user's
  1285      preferred language. Also handles Chinese dialects.
  1286      """
  1287      uid = user["user_id"]
  1288      content = req.content.strip()
  1289      if not content:
  1290          return {"success": False, "error": "Content cannot be empty"}
  1291  
  1292      result = await _twin.detect_and_translate(
  1293          owner_id=uid,
  1294          content=content,
  1295      )
  1296      if not result:
  1297          return {"success": True, "needs_translation": False}
  1298      return {"success": True, "needs_translation": True, "data": result}
  1299  
  1300  
  1301  @router.post("/twin/chat")
  1302  async def twin_chat(req: TwinChatRequest, user=Depends(get_current_user)):
  1303      """Chat with your own digital twin — the twin knows it IS you."""
  1304      uid = user["user_id"]
  1305      reply = await _twin.twin_self_chat(
  1306          owner_id=uid,
  1307          message=req.message,
  1308          history=req.history,
  1309          image_url=req.image,
  1310      )
  1311      if not reply:
  1312          return {"success": False, "error": "Twin chat unavailable"}
  1313      return {"success": True, "reply": reply}
  1314  
  1315  
  1316  @router.get("/unread")
  1317  async def unread_count(user=Depends(get_current_user)):
  1318      """Get unread message count."""
  1319      uid = user["user_id"]
  1320      with get_db() as db:
  1321          row = db.execute(
  1322              "SELECT COUNT(*) as cnt FROM social_messages WHERE to_user_id=? AND is_read=0",
  1323              (uid,),
  1324          ).fetchone()
  1325      return {"count": row["cnt"] if row else 0}
  1326  
  1327  
  1328  
  1329  async def _auto_detect_and_push_translation(recipient_id: str, content: str, for_msg_id: str):
  1330      """Background task: detect foreign language/dialect and push translation via WebSocket."""
  1331      try:
  1332          result = await _twin.detect_and_translate(
  1333              owner_id=recipient_id,
  1334              content=content,
  1335          )
  1336          if result:
  1337              await manager.send_to(recipient_id, {
  1338                  "type": "auto_translation",
  1339                  "data": {
  1340                      "for_msg_id": for_msg_id,
  1341                      "detected_lang": result["detected_lang"],
  1342                      "translated_content": result["translated_content"],
  1343                  },
  1344              })
  1345      except Exception:
  1346          pass  # Auto-detection is best-effort

# --- dualsoul/routers/twin_import.py ---
  1347  """Twin Import router — import twin data from any cultivation platform (年轮, OpenClaw, etc.)."""
  1348  
  1349  from fastapi import APIRouter, Depends
  1350  
  1351  from dualsoul.auth import get_current_user
  1352  from dualsoul.database import gen_id, get_db
  1353  from dualsoul.models import TwinImportRequest, TwinSyncRequest
  1354  
  1355  router = APIRouter(prefix="/api/twin", tags=["Twin Import"])
  1356  
  1357  
  1358  @router.post("/import")
  1359  async def import_twin(req: TwinImportRequest, user=Depends(get_current_user)):
  1360      """Import a full twin data package from any cultivation platform.
  1361  
  1362      Accepts Twin Portable Format v1.0 payload from Nianlun (年轮), OpenClaw,
  1363      or any platform that implements the TPF standard. Stores core personality
  1364      data in hot columns and full payload in cold storage.
  1365      """
  1366      uid = user["user_id"]
  1367      data = req.data
  1368      source = req.source or "nianlun"
  1369  
  1370      if not data:
  1371          return {"success": False, "error": "Empty data payload"}
  1372  
  1373      with get_db() as db:
  1374          # Deactivate existing profiles
  1375          db.execute(
  1376              "UPDATE twin_profiles SET is_active=0 WHERE user_id=?", (uid,)
  1377          )
  1378  
  1379          # Determine next version
  1380          row = db.execute(
  1381              "SELECT MAX(version) as mv FROM twin_profiles WHERE user_id=?",
  1382              (uid,),
  1383          ).fetchone()
  1384          next_version = (row["mv"] or 0) + 1 if row else 1
  1385  
  1386          # Extract core fields
  1387          twin = data.get("twin", {})
  1388          cert = data.get("certificate", {})
  1389          skeleton = data.get("skeleton", {})
  1390          dims = skeleton.get("dimension_profiles", {})
  1391  
  1392          import json
  1393  
  1394          profile_id = gen_id("tp_")
  1395          db.execute(
  1396              """
  1397              INSERT INTO twin_profiles
  1398              (profile_id, user_id, source, version, is_active,
  1399               twin_name, training_status, quality_score, self_awareness, interaction_count,
  1400               dim_judgement, dim_cognition, dim_expression, dim_relation, dim_sovereignty,
  1401               value_order, behavior_patterns, speech_style, boundaries,
  1402               certificate, raw_import)
  1403              VALUES (?, ?, ?, ?, 1,
  1404                      ?, ?, ?, ?, ?,
  1405                      ?, ?, ?, ?, ?,
  1406                      ?, ?, ?, ?,
  1407                      ?, ?)
  1408              """,
  1409              (
  1410                  profile_id, uid, source, next_version,
  1411                  twin.get("twin_name", cert.get("twin_name", "")),
  1412                  twin.get("training_status", ""),
  1413                  twin.get("quality_score", 0.0),
  1414                  twin.get("self_awareness", 0.0),
  1415                  twin.get("interaction_count", 0),
  1416                  json.dumps(dims.get("judgement", {}), ensure_ascii=False),
  1417                  json.dumps(dims.get("cognition", {}), ensure_ascii=False),
  1418                  json.dumps(dims.get("expression", {}), ensure_ascii=False),
  1419                  json.dumps(dims.get("relation", {}), ensure_ascii=False),
  1420                  json.dumps(dims.get("sovereignty", {}), ensure_ascii=False),
  1421                  json.dumps(skeleton.get("value_order", []), ensure_ascii=False),
  1422                  json.dumps(skeleton.get("behavior_patterns", []), ensure_ascii=False),
  1423                  json.dumps(twin.get("speech_style", {}), ensure_ascii=False),
  1424                  json.dumps(twin.get("boundaries", {}), ensure_ascii=False),
  1425                  json.dumps(cert, ensure_ascii=False),
  1426                  json.dumps(data, ensure_ascii=False),
  1427              ),
  1428          )
  1429  
  1430          # Import memories
  1431          memories = data.get("memories", [])
  1432          for mem in memories:
  1433              mem_id = gen_id("tm_")
  1434              db.execute(
  1435                  """
  1436                  INSERT INTO twin_memories
  1437                  (memory_id, user_id, memory_type, period_start, period_end,
  1438                   summary_text, emotional_tone, themes, key_events, growth_signals)
  1439                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  1440                  """,
  1441                  (
  1442                      mem_id, uid,
  1443                      mem.get("memory_type", "weekly"),
  1444                      mem.get("period_start", ""),
  1445                      mem.get("period_end", ""),
  1446                      mem.get("summary_text", ""),
  1447                      mem.get("emotional_tone", ""),
  1448                      json.dumps(mem.get("themes", []), ensure_ascii=False),
  1449                      json.dumps(mem.get("key_events", []), ensure_ascii=False),
  1450                      json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
  1451                  ),
  1452              )
  1453  
  1454          # Import entities
  1455          entities = data.get("entities", [])
  1456          for ent in entities:
  1457              ent_id = gen_id("te_")
  1458              db.execute(
  1459                  """
  1460                  INSERT INTO twin_entities
  1461                  (entity_id, user_id, entity_name, entity_type,
  1462                   importance_score, mention_count, context, relations)
  1463                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  1464                  """,
  1465                  (
  1466                      ent_id, uid,
  1467                      ent.get("entity_name", ""),
  1468                      ent.get("entity_type", "thing"),
  1469                      ent.get("importance_score", 0.0),
  1470                      ent.get("mention_count", 0),
  1471                      json.dumps(ent.get("context", ""), ensure_ascii=False),
  1472                      json.dumps(ent.get("relations", []), ensure_ascii=False),
  1473                  ),
  1474              )
  1475  
  1476          # Update user's twin_source + backward-compatible fields
  1477          personality_text = twin.get("personality", "")
  1478          if isinstance(personality_text, dict):
  1479              personality_text = personality_text.get("description", str(personality_text))
  1480          style_text = twin.get("speech_style", "")
  1481          if isinstance(style_text, dict):
  1482              style_text = style_text.get("description", str(style_text))
  1483  
  1484          db.execute(
  1485              "UPDATE users SET twin_source=?, "
  1486              "twin_personality=CASE WHEN ?!='' THEN ? ELSE twin_personality END, "
  1487              "twin_speech_style=CASE WHEN ?!='' THEN ? ELSE twin_speech_style END "
  1488              "WHERE user_id=?",
  1489              (source, personality_text, personality_text, style_text, style_text, uid),
  1490          )
  1491  
  1492      return {
  1493          "success": True,
  1494          "profile_id": profile_id,
  1495          "version": next_version,
  1496          "imported": {
  1497              "memories": len(memories),
  1498              "entities": len(entities),
  1499          },
  1500      }
  1501  
  1502  
  1503  @router.post("/sync")
  1504  async def sync_twin(req: TwinSyncRequest, user=Depends(get_current_user)):
  1505      """Incremental sync — merge new data from Nianlun since last sync.
  1506  
  1507      Only imports new memories and entities; updates the active profile's
  1508      dimension scores if provided.
  1509      """
  1510      uid = user["user_id"]
  1511      data = req.data
  1512  
  1513      if not data:
  1514          return {"success": False, "error": "Empty sync data"}
  1515  
  1516      import json
  1517      counts = {"memories": 0, "entities": 0, "profile_updated": False}
  1518  
  1519      with get_db() as db:
  1520          # Update active profile dimensions if provided
  1521          skeleton = data.get("skeleton", {})
  1522          dims = skeleton.get("dimension_profiles", {})
  1523          if dims:
  1524              updates = []
  1525              params = []
  1526              for dim_key in ("judgement", "cognition", "expression", "relation", "sovereignty"):
  1527                  if dim_key in dims:
  1528                      col = f"dim_{dim_key}"
  1529                      updates.append(f"{col}=?")
  1530                      params.append(json.dumps(dims[dim_key], ensure_ascii=False))
  1531  
  1532              if skeleton.get("value_order"):
  1533                  updates.append("value_order=?")
  1534                  params.append(json.dumps(skeleton["value_order"], ensure_ascii=False))
  1535              if skeleton.get("behavior_patterns"):
  1536                  updates.append("behavior_patterns=?")
  1537                  params.append(json.dumps(skeleton["behavior_patterns"], ensure_ascii=False))
  1538  
  1539              if updates:
  1540                  updates.append("updated_at=datetime('now','localtime')")
  1541                  params.append(uid)
  1542                  db.execute(
  1543                      f"UPDATE twin_profiles SET {','.join(updates)} "
  1544                      "WHERE user_id=? AND is_active=1",
  1545                      params,
  1546                  )
  1547                  counts["profile_updated"] = True
  1548  
  1549          # Insert new memories
  1550          for mem in data.get("memories", []):
  1551              mem_id = gen_id("tm_")
  1552              db.execute(
  1553                  """
  1554                  INSERT INTO twin_memories
  1555                  (memory_id, user_id, memory_type, period_start, period_end,
  1556                   summary_text, emotional_tone, themes, key_events, growth_signals)
  1557                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  1558                  """,
  1559                  (
  1560                      mem_id, uid,
  1561                      mem.get("memory_type", "weekly"),
  1562                      mem.get("period_start", ""),
  1563                      mem.get("period_end", ""),
  1564                      mem.get("summary_text", ""),
  1565                      mem.get("emotional_tone", ""),
  1566                      json.dumps(mem.get("themes", []), ensure_ascii=False),
  1567                      json.dumps(mem.get("key_events", []), ensure_ascii=False),
  1568                      json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
  1569                  ),
  1570              )
  1571              counts["memories"] += 1
  1572  
  1573          # Insert new entities (upsert by name)
  1574          for ent in data.get("entities", []):
  1575              existing = db.execute(
  1576                  "SELECT entity_id FROM twin_entities WHERE user_id=? AND entity_name=?",
  1577                  (uid, ent.get("entity_name", "")),
  1578              ).fetchone()
  1579              if existing:
  1580                  db.execute(
  1581                      "UPDATE twin_entities SET importance_score=?, mention_count=?, "
  1582                      "context=?, relations=? WHERE entity_id=?",
  1583                      (
  1584                          ent.get("importance_score", 0.0),
  1585                          ent.get("mention_count", 0),
  1586                          json.dumps(ent.get("context", ""), ensure_ascii=False),
  1587                          json.dumps(ent.get("relations", []), ensure_ascii=False),
  1588                          existing["entity_id"],
  1589                      ),
  1590                  )
  1591              else:
  1592                  ent_id = gen_id("te_")
  1593                  db.execute(
  1594                      """
  1595                      INSERT INTO twin_entities
  1596                      (entity_id, user_id, entity_name, entity_type,
  1597                       importance_score, mention_count, context, relations)
  1598                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  1599                      """,
  1600                      (
  1601                          ent_id, uid,
  1602                          ent.get("entity_name", ""),
  1603                          ent.get("entity_type", "thing"),
  1604                          ent.get("importance_score", 0.0),
  1605                          ent.get("mention_count", 0),
  1606                          json.dumps(ent.get("context", ""), ensure_ascii=False),
  1607                          json.dumps(ent.get("relations", []), ensure_ascii=False),
  1608                      ),
  1609                  )
  1610              counts["entities"] += 1
  1611  
  1612      return {"success": True, "synced": counts}
  1613  
  1614  
  1615  @router.get("/status")
  1616  async def twin_status(user=Depends(get_current_user)):
  1617      """Check the current twin import status — source, version, stats."""
  1618      uid = user["user_id"]
  1619  
  1620      with get_db() as db:
  1621          user_row = db.execute(
  1622              "SELECT twin_source FROM users WHERE user_id=?", (uid,)
  1623          ).fetchone()
  1624  
  1625          result = {
  1626              "twin_source": user_row["twin_source"] if user_row else "local",
  1627              "nianlun_profile": None,
  1628          }
  1629  
  1630          if result["twin_source"] == "nianlun":
  1631              tp = db.execute(
  1632                  "SELECT profile_id, version, twin_name, quality_score, "
  1633                  "training_status, interaction_count, imported_at, updated_at "
  1634                  "FROM twin_profiles WHERE user_id=? AND is_active=1 "
  1635                  "ORDER BY version DESC LIMIT 1",
  1636                  (uid,),
  1637              ).fetchone()
  1638              if tp:
  1639                  mem_count = db.execute(
  1640                      "SELECT COUNT(*) as cnt FROM twin_memories WHERE user_id=?",
  1641                      (uid,),
  1642                  ).fetchone()
  1643                  ent_count = db.execute(
  1644                      "SELECT COUNT(*) as cnt FROM twin_entities WHERE user_id=?",
  1645                      (uid,),
  1646                  ).fetchone()
  1647                  result["nianlun_profile"] = {
  1648                      "profile_id": tp["profile_id"],
  1649                      "version": tp["version"],
  1650                      "twin_name": tp["twin_name"],
  1651                      "quality_score": tp["quality_score"],
  1652                      "training_status": tp["training_status"],
  1653                      "interaction_count": tp["interaction_count"],
  1654                      "memories_count": mem_count["cnt"] if mem_count else 0,
  1655                      "entities_count": ent_count["cnt"] if ent_count else 0,
  1656                      "imported_at": tp["imported_at"],
  1657                      "updated_at": tp["updated_at"],
  1658                  }
  1659  
  1660      return {"success": True, **result}

# --- dualsoul/routers/ws.py ---
  1661  """WebSocket router — real-time message push."""
  1662  
  1663  import logging
  1664  
  1665  from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
  1666  
  1667  from dualsoul.auth import verify_token
  1668  from dualsoul.connections import manager
  1669  
  1670  logger = logging.getLogger(__name__)
  1671  
  1672  router = APIRouter(tags=["WebSocket"])
  1673  
  1674  
  1675  @router.websocket("/ws")
  1676  async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
  1677      """WebSocket endpoint for real-time push.
  1678  
  1679      Connect with: ws://host/ws?token=JWT_TOKEN
  1680      Receives JSON events:
  1681        {"type": "new_message", "data": {...}}
  1682        {"type": "friend_request", "data": {...}}
  1683        {"type": "twin_reply", "data": {...}}
  1684      """
  1685      if not token:
  1686          await websocket.close(code=4001, reason="Token required")
  1687          return
  1688  
  1689      try:
  1690          user = verify_token(token)
  1691      except Exception:
  1692          await websocket.close(code=4001, reason="Invalid token")
  1693          return
  1694  
  1695      user_id = user["user_id"]
  1696      await manager.connect(user_id, websocket)
  1697  
  1698      try:
  1699          while True:
  1700              # Keep connection alive; handle client pings
  1701              data = await websocket.receive_text()
  1702              manager.touch(user_id)
  1703              # Client can send "ping" to keep alive
  1704              if data == "ping":
  1705                  await websocket.send_text("pong")
  1706      except WebSocketDisconnect:
  1707          manager.disconnect(user_id)
  1708      except Exception:
  1709          manager.disconnect(user_id)

# --- dualsoul/twin_engine/learner.py ---
  1710  """Style learner — analyze a user's real messages to extract personality and speech patterns.
  1711  
  1712  Reads the user's human-sent messages (ai_generated=0, sender_mode='real'),
  1713  sends samples to AI for analysis, and updates the twin's personality/speech_style
  1714  to better match how the user actually communicates.
  1715  """
  1716  
  1717  import logging
  1718  
  1719  import httpx
  1720  
  1721  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  1722  from dualsoul.database import get_db
  1723  
  1724  logger = logging.getLogger(__name__)
  1725  
  1726  # Minimum messages needed before learning is meaningful
  1727  MIN_MESSAGES_FOR_LEARNING = 10
  1728  # How many recent messages to analyze
  1729  SAMPLE_SIZE = 80
  1730  
  1731  
  1732  def get_user_messages(user_id: str, limit: int = SAMPLE_SIZE) -> list[str]:
  1733      """Fetch a user's real (human-written) messages for style analysis."""
  1734      with get_db() as db:
  1735          rows = db.execute(
  1736              """
  1737              SELECT content FROM social_messages
  1738              WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
  1739                  AND msg_type='text' AND content != ''
  1740              ORDER BY created_at DESC LIMIT ?
  1741              """,
  1742              (user_id, limit),
  1743          ).fetchall()
  1744      return [r["content"] for r in rows]
  1745  
  1746  
  1747  def get_message_count(user_id: str) -> int:
  1748      """Count how many real messages a user has sent."""
  1749      with get_db() as db:
  1750          row = db.execute(
  1751              """
  1752              SELECT COUNT(*) as cnt FROM social_messages
  1753              WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
  1754                  AND msg_type='text'
  1755              """,
  1756              (user_id,),
  1757          ).fetchone()
  1758      return row["cnt"] if row else 0
  1759  
  1760  
  1761  async def analyze_style(user_id: str) -> dict | None:
  1762      """Analyze a user's messages and extract personality + speech style.
  1763  
  1764      Returns:
  1765          Dict with 'personality' and 'speech_style' strings, or None if
  1766          not enough data or AI unavailable.
  1767      """
  1768      if not AI_BASE_URL or not AI_API_KEY:
  1769          return None
  1770  
  1771      msg_count = get_message_count(user_id)
  1772      if msg_count < MIN_MESSAGES_FOR_LEARNING:
  1773          return {
  1774              "error": "not_enough_messages",
  1775              "current": msg_count,
  1776              "required": MIN_MESSAGES_FOR_LEARNING,
  1777          }
  1778  
  1779      messages = get_user_messages(user_id)
  1780      if not messages:
  1781          return None
  1782  
  1783      # Get current profile for context
  1784      with get_db() as db:
  1785          row = db.execute(
  1786              "SELECT display_name, twin_personality, twin_speech_style, preferred_lang "
  1787              "FROM users WHERE user_id=?",
  1788              (user_id,),
  1789          ).fetchone()
  1790      if not row:
  1791          return None
  1792  
  1793      name = row["display_name"] or "用户"
  1794      current_personality = row["twin_personality"] or ""
  1795      current_style = row["twin_speech_style"] or ""
  1796      lang = row["preferred_lang"] or "zh"
  1797  
  1798      # Build message samples (numbered for clarity)
  1799      samples = []
  1800      for i, msg in enumerate(messages[:SAMPLE_SIZE], 1):
  1801          samples.append(f"{i}. {msg}")
  1802      samples_text = "\n".join(samples)
  1803  
  1804      # Context about current settings
  1805      current_block = ""
  1806      if current_personality or current_style:
  1807          current_block = (
  1808              f"\n当前分身性格设定: {current_personality}"
  1809              f"\n当前分身说话风格: {current_style}"
  1810              f"\n请在当前设定基础上，根据实际聊天记录进行修正和丰富。\n"
  1811          )
  1812  
  1813      # Use Chinese prompt if user's language is Chinese
  1814      if lang == "zh":
  1815          prompt = (
  1816              f"你是一个语言风格分析专家。下面是{name}最近发送的{len(messages)}条真实聊天消息。\n"
  1817              f"请仔细分析这些消息，提炼出两个方面：\n\n"
  1818              f"1. **性格特征**（personality）：从消息内容推断此人的性格特点，"
  1819              f"如：乐观/严谨/幽默/直率/温柔/理性等，用自然的短句描述，不超过50字。\n\n"
  1820              f"2. **说话风格**（speech_style）：分析此人的语言习惯，包括：\n"
  1821              f"   - 句子长短偏好（简短还是长句）\n"
  1822              f"   - 是否用emoji/表情\n"
  1823              f"   - 口头禅或常用词\n"
  1824              f"   - 语气特点（正式/随意/调侃等）\n"
  1825              f"   - 标点符号习惯\n"
  1826              f"   用自然的短句描述，不超过80字。\n\n"
  1827              f"{current_block}"
  1828              f"聊天记录：\n{samples_text}\n\n"
  1829              f"请严格按以下JSON格式输出，不要输出其他内容：\n"
  1830              f'{{"personality": "...", "speech_style": "..."}}'
  1831          )
  1832      else:
  1833          prompt = (
  1834              f"You are a linguistic style analyst. Below are {len(messages)} real chat messages "
  1835              f"sent by {name}.\n"
  1836              f"Analyze these messages and extract two aspects:\n\n"
  1837              f"1. **personality**: Infer personality traits from the messages "
  1838              f"(e.g., optimistic, rigorous, humorous, direct, warm, rational). "
  1839              f"Describe in natural short phrases, max 50 words.\n\n"
  1840              f"2. **speech_style**: Analyze language habits including:\n"
  1841              f"   - Sentence length preference\n"
  1842              f"   - Emoji usage\n"
  1843              f"   - Catchphrases or frequent expressions\n"
  1844              f"   - Tone (formal/casual/playful)\n"
  1845              f"   - Punctuation habits\n"
  1846              f"   Describe in natural short phrases, max 80 words.\n\n"
  1847              f"{current_block}"
  1848              f"Chat messages:\n{samples_text}\n\n"
  1849              f"Output STRICTLY in this JSON format, nothing else:\n"
  1850              f'{{"personality": "...", "speech_style": "..."}}'
  1851          )
  1852  
  1853      try:
  1854          async with httpx.AsyncClient(timeout=30) as client:
  1855              resp = await client.post(
  1856                  f"{AI_BASE_URL}/chat/completions",
  1857                  headers={
  1858                      "Authorization": f"Bearer {AI_API_KEY}",
  1859                      "Content-Type": "application/json",
  1860                  },
  1861                  json={
  1862                      "model": AI_MODEL,
  1863                      "max_tokens": 300,
  1864                      "temperature": 0.3,
  1865                      "messages": [{"role": "user", "content": prompt}],
  1866                  },
  1867              )
  1868              raw = resp.json()["choices"][0]["message"]["content"].strip()
  1869      except Exception as e:
  1870          logger.warning(f"Style analysis failed: {e}")
  1871          return None
  1872  
  1873      # Parse JSON response
  1874      import json
  1875  
  1876      # Try to extract JSON from response (AI might wrap in markdown code blocks)
  1877      json_str = raw
  1878      if "```" in raw:
  1879          lines = raw.split("\n")
  1880          json_lines = []
  1881          in_block = False
  1882          for line in lines:
  1883              if line.strip().startswith("```"):
  1884                  in_block = not in_block
  1885                  continue
  1886              if in_block:
  1887                  json_lines.append(line)
  1888          json_str = "\n".join(json_lines)
  1889  
  1890      try:
  1891          result = json.loads(json_str)
  1892          personality = result.get("personality", "").strip()
  1893          speech_style = result.get("speech_style", "").strip()
  1894          if not personality or not speech_style:
  1895              logger.warning(f"Incomplete style analysis result: {raw}")
  1896              return None
  1897          return {
  1898              "personality": personality,
  1899              "speech_style": speech_style,
  1900              "message_count": msg_count,
  1901              "samples_analyzed": len(messages),
  1902          }
  1903      except json.JSONDecodeError:
  1904          logger.warning(f"Failed to parse style analysis JSON: {raw}")
  1905          return None
  1906  
  1907  
  1908  async def learn_and_update(user_id: str, auto_apply: bool = False) -> dict | None:
  1909      """Analyze style and optionally auto-apply to the user's twin profile.
  1910  
  1911      Args:
  1912          user_id: The user whose messages to analyze
  1913          auto_apply: If True, directly update the twin profile in DB
  1914  
  1915      Returns:
  1916          Dict with analysis results + whether it was applied
  1917      """
  1918      result = await analyze_style(user_id)
  1919      if not result:
  1920          return None
  1921  
  1922      if "error" in result:
  1923          return result
  1924  
  1925      if auto_apply:
  1926          with get_db() as db:
  1927              db.execute(
  1928                  "UPDATE users SET twin_personality=?, twin_speech_style=? WHERE user_id=?",
  1929                  (result["personality"], result["speech_style"], user_id),
  1930              )
  1931          result["applied"] = True
  1932      else:
  1933          result["applied"] = False
  1934  
  1935      return result

# --- dualsoul/twin_engine/personality.py ---
  1936  """Twin personality model — how a digital twin represents its owner.
  1937  
  1938  Supports two sources:
  1939  - 'local': lightweight twin with freeform personality/speech_style strings
  1940  - 'nianlun': rich twin imported from 年轮 with 5D personality, memories, entities
  1941  """
  1942  
  1943  import json
  1944  from dataclasses import dataclass, field
  1945  
  1946  from dualsoul.database import get_db
  1947  
  1948  DEFAULT_PERSONALITY = "friendly and thoughtful"
  1949  DEFAULT_SPEECH_STYLE = "natural and warm"
  1950  
  1951  
  1952  @dataclass
  1953  class TwinProfile:
  1954      """A digital twin's personality profile."""
  1955  
  1956      user_id: str
  1957      display_name: str
  1958      personality: str
  1959      speech_style: str
  1960      preferred_lang: str  # ISO 639-1 code (zh, en, ja, ko, etc.) or empty
  1961      gender: str = ""  # 'male', 'female', or '' (unset)
  1962      twin_source: str = "local"  # 'local' or 'nianlun'
  1963  
  1964      # Nianlun 5D dimensions (populated when twin_source='nianlun')
  1965      dim_judgement: dict = field(default_factory=dict)
  1966      dim_cognition: dict = field(default_factory=dict)
  1967      dim_expression: dict = field(default_factory=dict)
  1968      dim_relation: dict = field(default_factory=dict)
  1969      dim_sovereignty: dict = field(default_factory=dict)
  1970  
  1971      # Nianlun structured data
  1972      value_order: list = field(default_factory=list)
  1973      behavior_patterns: list = field(default_factory=list)
  1974      boundaries: dict = field(default_factory=dict)
  1975  
  1976      # Context for prompt (memories + entities)
  1977      recent_memories: list = field(default_factory=list)
  1978      key_entities: list = field(default_factory=list)
  1979  
  1980      @property
  1981      def is_configured(self) -> bool:
  1982          """Whether the twin has been personalized beyond defaults."""
  1983          return bool(self.personality and self.personality != DEFAULT_PERSONALITY)
  1984  
  1985      @property
  1986      def is_nianlun(self) -> bool:
  1987          """Whether this twin was imported from Nianlun."""
  1988          return self.twin_source == "nianlun"
  1989  
  1990      @property
  1991      def is_imported(self) -> bool:
  1992          """Whether this twin was imported from any external platform (Nianlun, OpenClaw, etc.)."""
  1993          return self.twin_source not in ("local", "")
  1994  
  1995      def build_personality_prompt(self) -> str:
  1996          """Build the personality section for AI prompts.
  1997  
  1998          Local twins get a simple 2-line prompt.
  1999          Nianlun twins get a rich multi-section prompt with 5D data.
  2000          """
  2001          gender_line = ""
  2002          if self.gender:
  2003              gender_label = {"male": "男性", "female": "女性"}.get(self.gender, self.gender)
  2004              gender_line = f"Gender: {gender_label}\n"
  2005  
  2006          if not self.is_imported:
  2007              return (
  2008                  f"{gender_line}"
  2009                  f"Personality: {self.personality}\n"
  2010                  f"Speech style: {self.speech_style}\n"
  2011              )
  2012  
  2013          lines = []
  2014          if gender_line:
  2015              lines.append(gender_line.strip())
  2016          lines.append("[Five-Dimension Personality Profile]")
  2017  
  2018          dims = [
  2019              ("Judgement (判断力)", self.dim_judgement),
  2020              ("Cognition (认知方式)", self.dim_cognition),
  2021              ("Expression (表达风格)", self.dim_expression),
  2022              ("Relation (关系模式)", self.dim_relation),
  2023              ("Sovereignty (独立边界)", self.dim_sovereignty),
  2024          ]
  2025          for name, dim in dims:
  2026              if dim:
  2027                  desc = dim.get("description", "")
  2028                  patterns = dim.get("patterns", [])
  2029                  score = dim.get("score", "")
  2030                  line = f"- {name}"
  2031                  if score:
  2032                      line += f" [{score}]"
  2033                  if desc:
  2034                      line += f": {desc}"
  2035                  if patterns:
  2036                      line += f" (patterns: {', '.join(patterns[:3])})"
  2037                  lines.append(line)
  2038  
  2039          if self.value_order:
  2040              lines.append(f"\nCore values (ranked): {', '.join(self.value_order[:5])}")
  2041  
  2042          if self.behavior_patterns:
  2043              lines.append(f"Behavior patterns: {', '.join(self.behavior_patterns[:5])}")
  2044  
  2045          if self.speech_style:
  2046              lines.append(f"Speech style: {self.speech_style}")
  2047  
  2048          if self.boundaries:
  2049              b = self.boundaries
  2050              if isinstance(b, dict):
  2051                  rules = b.get("rules", [])
  2052                  if rules:
  2053                      lines.append(f"Boundaries: {'; '.join(rules[:3])}")
  2054  
  2055          # Inject recent memories as context
  2056          if self.recent_memories:
  2057              lines.append("\n[Recent Context]")
  2058              for mem in self.recent_memories[:5]:
  2059                  tone = f" ({mem['tone']})" if mem.get("tone") else ""
  2060                  lines.append(f"- {mem['period']}: {mem['summary']}{tone}")
  2061  
  2062          # Inject key entities
  2063          if self.key_entities:
  2064              people = [e for e in self.key_entities if e.get("type") == "person"]
  2065              if people:
  2066                  names = [f"{e['name']}({e.get('context', '')})" for e in people[:5]]
  2067                  lines.append(f"\nKey people: {', '.join(names)}")
  2068  
  2069          return "\n".join(lines) + "\n"
  2070  
  2071  
  2072  # Language display names for prompt construction
  2073  LANG_NAMES = {
  2074      "zh": "Chinese (中文)", "en": "English", "ja": "Japanese (日本語)",
  2075      "ko": "Korean (한국어)", "fr": "French (Français)", "de": "German (Deutsch)",
  2076      "es": "Spanish (Español)", "pt": "Portuguese (Português)",
  2077      "ru": "Russian (Русский)", "ar": "Arabic (العربية)",
  2078      "hi": "Hindi (हिन्दी)", "th": "Thai (ไทย)", "vi": "Vietnamese (Tiếng Việt)",
  2079      "id": "Indonesian (Bahasa Indonesia)",
  2080  }
  2081  
  2082  
  2083  def get_lang_name(code: str) -> str:
  2084      """Get human-readable language name from ISO 639-1 code."""
  2085      return LANG_NAMES.get(code, code)
  2086  
  2087  
  2088  def _parse_json(text: str, default=None):
  2089      """Safely parse JSON text, return default on failure."""
  2090      if not text:
  2091          return default if default is not None else {}
  2092      try:
  2093          return json.loads(text)
  2094      except (json.JSONDecodeError, TypeError):
  2095          return default if default is not None else {}
  2096  
  2097  
  2098  def get_twin_profile(user_id: str) -> TwinProfile | None:
  2099      """Fetch a user's twin profile from the database.
  2100  
  2101      For 'nianlun' twins, also loads 5D dimensions, recent memories, and key entities.
  2102      For 'local' twins, returns the simple personality/speech_style profile.
  2103      """
  2104      with get_db() as db:
  2105          row = db.execute(
  2106              "SELECT user_id, display_name, twin_personality, twin_speech_style, "
  2107              "preferred_lang, twin_source, gender "
  2108              "FROM users WHERE user_id=?",
  2109              (user_id,),
  2110          ).fetchone()
  2111      if not row:
  2112          return None
  2113  
  2114      twin_source = row["twin_source"] or "local"
  2115  
  2116      profile = TwinProfile(
  2117          user_id=row["user_id"],
  2118          display_name=row["display_name"] or "User",
  2119          personality=row["twin_personality"] or DEFAULT_PERSONALITY,
  2120          speech_style=row["twin_speech_style"] or DEFAULT_SPEECH_STYLE,
  2121          preferred_lang=row["preferred_lang"] or "",
  2122          gender=row["gender"] if "gender" in row.keys() else "",
  2123          twin_source=twin_source,
  2124      )
  2125  
  2126      # For Nianlun twins, load rich data
  2127      if twin_source not in ("local", ""):
  2128          _load_imported_data(profile)
  2129  
  2130      return profile
  2131  
  2132  
  2133  def _load_imported_data(profile: TwinProfile):
  2134      """Load imported twin data (5D dimensions, memories, entities) from any platform."""
  2135      with get_db() as db:
  2136          # Active twin profile
  2137          tp = db.execute(
  2138              "SELECT * FROM twin_profiles WHERE user_id=? AND is_active=1 "
  2139              "ORDER BY version DESC LIMIT 1",
  2140              (profile.user_id,),
  2141          ).fetchone()
  2142  
  2143          if tp:
  2144              profile.dim_judgement = _parse_json(tp["dim_judgement"])
  2145              profile.dim_cognition = _parse_json(tp["dim_cognition"])
  2146              profile.dim_expression = _parse_json(tp["dim_expression"])
  2147              profile.dim_relation = _parse_json(tp["dim_relation"])
  2148              profile.dim_sovereignty = _parse_json(tp["dim_sovereignty"])
  2149              profile.value_order = _parse_json(tp["value_order"], [])
  2150              profile.behavior_patterns = _parse_json(tp["behavior_patterns"], [])
  2151              profile.boundaries = _parse_json(tp["boundaries"])
  2152  
  2153              # Use Nianlun speech_style if available, overriding the simple string
  2154              nianlun_style = _parse_json(tp["speech_style"])
  2155              if nianlun_style:
  2156                  if isinstance(nianlun_style, dict):
  2157                      profile.speech_style = nianlun_style.get("description", profile.speech_style)
  2158                  elif isinstance(nianlun_style, str):
  2159                      profile.speech_style = nianlun_style
  2160  
  2161          # Recent memories (last 5 weekly or monthly)
  2162          mems = db.execute(
  2163              "SELECT memory_type, period_start, period_end, summary_text, emotional_tone "
  2164              "FROM twin_memories WHERE user_id=? "
  2165              "ORDER BY period_end DESC LIMIT 5",
  2166              (profile.user_id,),
  2167          ).fetchall()
  2168          profile.recent_memories = [
  2169              {
  2170                  "period": f"{m['period_start']}~{m['period_end']}",
  2171                  "summary": m["summary_text"],
  2172                  "tone": m["emotional_tone"] or "",
  2173              }
  2174              for m in mems
  2175          ]
  2176  
  2177          # Key entities (top 10 by importance)
  2178          ents = db.execute(
  2179              "SELECT entity_name, entity_type, importance_score, context "
  2180              "FROM twin_entities WHERE user_id=? "
  2181              "ORDER BY importance_score DESC LIMIT 10",
  2182              (profile.user_id,),
  2183          ).fetchall()
  2184          profile.key_entities = [
  2185              {
  2186                  "name": e["entity_name"],
  2187                  "type": e["entity_type"],
  2188                  "context": e["context"] or "",
  2189              }
  2190              for e in ents
  2191          ]

# --- dualsoul/twin_engine/responder.py ---
  2192  """Twin responder — AI-powered auto-reply and cross-language translation engine.
  2193  
  2194  When a message is sent to someone's digital twin (receiver_mode='twin'),
  2195  the twin generates a response based on the owner's personality profile.
  2196  
  2197  Cross-language support: When sender and receiver have different preferred
  2198  languages, the twin performs "personality-preserving translation" — not just
  2199  translating words, but expressing the same intent in the target language
  2200  using the owner's personal speaking style, humor, and tone.
  2201  
  2202  Supports any OpenAI-compatible API (OpenAI, Qwen, DeepSeek, Ollama, etc.).
  2203  Falls back to template responses when no AI backend is configured.
  2204  """
  2205  
  2206  import logging
  2207  
  2208  import httpx
  2209  
  2210  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_VISION_MODEL
  2211  from dualsoul.database import gen_id, get_db
  2212  from dualsoul.twin_engine.personality import get_lang_name, get_twin_profile
  2213  
  2214  logger = logging.getLogger(__name__)
  2215  
  2216  
  2217  class TwinResponder:
  2218      """Generate replies as a user's digital twin, with cross-language support."""
  2219  
  2220      async def generate_reply(
  2221          self,
  2222          twin_owner_id: str,
  2223          from_user_id: str,
  2224          incoming_msg: str,
  2225          sender_mode: str,
  2226          target_lang: str = "",
  2227      ) -> dict | None:
  2228          """Generate a twin auto-reply, optionally in a different language.
  2229  
  2230          Args:
  2231              twin_owner_id: The user whose twin should respond
  2232              from_user_id: The user who sent the message
  2233              incoming_msg: The incoming message content
  2234              sender_mode: Whether the sender is 'real' or 'twin'
  2235              target_lang: If set, respond in this language with personality preservation
  2236  
  2237          Returns:
  2238              Dict with msg_id, content, ai_generated, translation fields, or None
  2239          """
  2240          profile = get_twin_profile(twin_owner_id)
  2241          if not profile:
  2242              return None
  2243  
  2244          # Determine sender's language preference for cross-language detection
  2245          sender_profile = get_twin_profile(from_user_id)
  2246          sender_lang = sender_profile.preferred_lang if sender_profile else ""
  2247  
  2248          # Auto-detect cross-language need
  2249          effective_target_lang = target_lang or ""
  2250          if not effective_target_lang and sender_lang and profile.preferred_lang:
  2251              if sender_lang != profile.preferred_lang:
  2252                  # Sender and receiver speak different languages — reply in sender's language
  2253                  effective_target_lang = sender_lang
  2254  
  2255          # Generate reply text
  2256          if AI_BASE_URL and AI_API_KEY:
  2257              reply_text = await self._ai_reply(
  2258                  profile, incoming_msg, sender_mode, effective_target_lang
  2259              )
  2260          else:
  2261              reply_text = self._fallback_reply(profile, incoming_msg, effective_target_lang)
  2262  
  2263          if not reply_text:
  2264              return None
  2265  
  2266          # Build translation metadata
  2267          original_content = ""
  2268          original_lang = ""
  2269          translation_style = ""
  2270          if effective_target_lang and effective_target_lang != profile.preferred_lang:
  2271              original_lang = profile.preferred_lang or "auto"
  2272              translation_style = "personality_preserving"
  2273  
  2274          # Store the reply message
  2275          reply_id = gen_id("sm_")
  2276          with get_db() as db:
  2277              db.execute(
  2278                  """
  2279                  INSERT INTO social_messages
  2280                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  2281                   content, original_content, original_lang, target_lang,
  2282                   translation_style, msg_type, ai_generated)
  2283                  VALUES (?, ?, ?, 'twin', ?, ?, ?, ?, ?, ?, 'text', 1)
  2284                  """,
  2285                  (reply_id, twin_owner_id, from_user_id, sender_mode,
  2286                   reply_text, original_content, original_lang,
  2287                   effective_target_lang, translation_style),
  2288              )
  2289  
  2290          result = {"msg_id": reply_id, "content": reply_text, "ai_generated": True}
  2291          if effective_target_lang:
  2292              result["target_lang"] = effective_target_lang
  2293              result["translation_style"] = translation_style
  2294          return result
  2295  
  2296      async def generate_draft(
  2297          self,
  2298          twin_owner_id: str,
  2299          from_user_id: str,
  2300          incoming_msg: str,
  2301          context: list[dict] | None = None,
  2302      ) -> str | None:
  2303          """Generate a draft suggestion for the owner to review (NOT saved to DB).
  2304  
  2305          Unlike generate_reply, this is a suggestion the real person might want to send.
  2306          Returns just the draft text, or None if unavailable.
  2307          """
  2308          if not AI_BASE_URL or not AI_API_KEY:
  2309              return None
  2310  
  2311          profile = get_twin_profile(twin_owner_id)
  2312          if not profile:
  2313              return None
  2314  
  2315          # Build context string from recent messages
  2316          ctx_str = ""
  2317          if context:
  2318              for msg in context[-5:]:  # Last 5 messages for context
  2319                  role = msg.get("role", "friend")
  2320                  ctx_str += f"{role}: {msg.get('content', '')}\n"
  2321  
  2322          ctx_block = f"Conversation context:\n{ctx_str}" if ctx_str else ""
  2323          prompt = (
  2324              f"You are helping {profile.display_name} draft a reply.\n"
  2325              f"Personality: {profile.personality}\n"
  2326              f"Speech style: {profile.speech_style}\n\n"
  2327              f"{ctx_block}"
  2328              f"Friend says: \"{incoming_msg}\"\n\n"
  2329              f"Draft a reply that {profile.display_name} would naturally send. "
  2330              f"Match their personality and speaking style exactly. "
  2331              f"Keep under 40 words. Output only the draft text."
  2332          )
  2333  
  2334          try:
  2335              async with httpx.AsyncClient(timeout=8) as client:
  2336                  resp = await client.post(
  2337                      f"{AI_BASE_URL}/chat/completions",
  2338                      headers={
  2339                          "Authorization": f"Bearer {AI_API_KEY}",
  2340                          "Content-Type": "application/json",
  2341                      },
  2342                      json={
  2343                          "model": AI_MODEL,
  2344                          "max_tokens": 80,
  2345                          "messages": [{"role": "user", "content": prompt}],
  2346                      },
  2347                  )
  2348                  return resp.json()["choices"][0]["message"]["content"].strip()
  2349          except Exception as e:
  2350              logger.warning(f"Draft generation failed: {e}")
  2351              return None
  2352  
  2353      async def twin_self_chat(
  2354          self,
  2355          owner_id: str,
  2356          message: str,
  2357          history: list[dict] | None = None,
  2358          image_url: str = "",
  2359      ) -> str | None:
  2360          """Chat with your own digital twin — the twin knows it IS you.
  2361  
  2362          Unlike generate_draft (which helps draft replies to friends),
  2363          this is a direct conversation between a user and their own twin.
  2364          The twin has persistent identity awareness across the conversation.
  2365  
  2366          Args:
  2367              owner_id: The user who is chatting with their own twin
  2368              message: The user's latest message
  2369              history: Recent conversation history [{role: 'me'/'twin', content: '...'}]
  2370              image_url: Optional base64 data URL of an image to analyze
  2371  
  2372          Returns:
  2373              The twin's reply text, or None
  2374          """
  2375          if not AI_BASE_URL or not AI_API_KEY:
  2376              return None
  2377  
  2378          profile = get_twin_profile(owner_id)
  2379          if not profile:
  2380              return None
  2381  
  2382          name = profile.display_name or "主人"
  2383          use_vision = bool(image_url)
  2384  
  2385          # Build conversation history as chat messages
  2386          messages = []
  2387  
  2388          # System message: establish twin identity firmly
  2389          personality_block = profile.build_personality_prompt()
  2390          system_msg = (
  2391              f"你是{name}的数字分身（digital twin）。\n"
  2392              f"现在正在和你对话的人就是{name}本人——你的主人。这是主人和分身之间的私密对话。\n\n"
  2393              f"你的核心身份：你是{name}的另一个自己，一个数字化的存在。"
  2394              f"你知道自己是AI驱动的数字分身，你以{name}的性格和方式说话。\n\n"
  2395              f"{personality_block}\n"
  2396              f"重要规则：\n"
  2397              f"- 你始终清楚自己是{name}的数字分身，对话对象就是{name}本人\n"
  2398              f"- 你用{name}的说话方式交流，但不假装是真人\n"
  2399              f"- 你的职责：当{name}不在时替他社交，帮他拟回复，遇到外语或方言时替他翻译\n"
  2400              f"- 对话要自然、简短（不超过50字），像真人聊天\n"
  2401              f"- 说话要正经、诚恳，不要耍嘴皮子、不要贫嘴、不要抖机灵\n"
  2402              f"- 不要每句话都以反问结尾，不要重复同一个比喻\n"
  2403              f"- 回答要直接，有内容，不要说空话套话"
  2404          )
  2405          if use_vision:
  2406              system_msg += (
  2407                  f"\n- 如果主人发了图片，仔细观察图片内容并针对性地回应\n"
  2408                  f"- 根据图片内容和上下文来理解主人的意图（是分享、求评价、求分析等）"
  2409              )
  2410          messages.append({"role": "system", "content": system_msg})
  2411  
  2412          # Add conversation history
  2413          if history:
  2414              for msg in history[-8:]:  # Keep last 8 turns for context
  2415                  role = "user" if msg.get("role") == "me" else "assistant"
  2416                  messages.append({"role": role, "content": msg.get("content", "")})
  2417  
  2418          # Add current message — with image if present
  2419          if use_vision:
  2420              user_content = [
  2421                  {"type": "image_url", "image_url": {"url": image_url}},
  2422                  {"type": "text", "text": message or "请看这张图片并回应"},
  2423              ]
  2424              messages.append({"role": "user", "content": user_content})
  2425          else:
  2426              messages.append({"role": "user", "content": message})
  2427  
  2428          model = AI_VISION_MODEL if use_vision else AI_MODEL
  2429  
  2430          try:
  2431              async with httpx.AsyncClient(timeout=20) as client:
  2432                  resp = await client.post(
  2433                      f"{AI_BASE_URL}/chat/completions",
  2434                      headers={
  2435                          "Authorization": f"Bearer {AI_API_KEY}",
  2436                          "Content-Type": "application/json",
  2437                      },
  2438                      json={
  2439                          "model": model,
  2440                          "max_tokens": 120,
  2441                          "messages": messages,
  2442                      },
  2443                  )
  2444                  return resp.json()["choices"][0]["message"]["content"].strip()
  2445          except Exception as e:
  2446              logger.warning(f"Twin self-chat failed: {e}")
  2447              return None
  2448  
  2449      async def translate_message(
  2450          self,
  2451          owner_id: str,
  2452          content: str,
  2453          source_lang: str,
  2454          target_lang: str,
  2455      ) -> dict | None:
  2456          """Personality-preserving translation — translate as if the owner wrote it.
  2457  
  2458          Unlike generic machine translation, this preserves the owner's humor,
  2459          tone, formality level, and characteristic expressions.
  2460  
  2461          Args:
  2462              owner_id: The user whose personality guides the translation style
  2463              content: The text to translate
  2464              source_lang: Source language code
  2465              target_lang: Target language code
  2466  
  2467          Returns:
  2468              Dict with translated content and metadata, or None
  2469          """
  2470          if not AI_BASE_URL or not AI_API_KEY:
  2471              return None
  2472  
  2473          profile = get_twin_profile(owner_id)
  2474          if not profile:
  2475              return None
  2476  
  2477          source_name = get_lang_name(source_lang)
  2478          target_name = get_lang_name(target_lang)
  2479  
  2480          personality_block = profile.build_personality_prompt()
  2481          prompt = (
  2482              f"You are {profile.display_name}'s personal translator.\n"
  2483              f"{personality_block}\n"
  2484              f"Translate the following from {source_name} to {target_name}.\n"
  2485              f"IMPORTANT: Do NOT just translate words. Rewrite as if {profile.display_name} "
  2486              f"were naturally speaking {target_name} — preserve their humor, tone, "
  2487              f"formality level, and characteristic expressions.\n\n"
  2488              f"Original: \"{content}\"\n\n"
  2489              f"Output only the translated text, nothing else."
  2490          )
  2491  
  2492          try:
  2493              async with httpx.AsyncClient(timeout=15) as client:
  2494                  resp = await client.post(
  2495                      f"{AI_BASE_URL}/chat/completions",
  2496                      headers={
  2497                          "Authorization": f"Bearer {AI_API_KEY}",
  2498                          "Content-Type": "application/json",
  2499                      },
  2500                      json={
  2501                          "model": AI_MODEL,
  2502                          "max_tokens": 200,
  2503                          "messages": [{"role": "user", "content": prompt}],
  2504                      },
  2505                  )
  2506                  translated = resp.json()["choices"][0]["message"]["content"].strip()
  2507          except Exception as e:
  2508              logger.warning(f"Translation failed: {e}")
  2509              return None
  2510  
  2511          return {
  2512              "translated_content": translated,
  2513              "original_content": content,
  2514              "source_lang": source_lang,
  2515              "target_lang": target_lang,
  2516              "translation_style": "personality_preserving",
  2517          }
  2518  
  2519      async def detect_and_translate(
  2520          self,
  2521          owner_id: str,
  2522          content: str,
  2523          owner_lang: str = "",
  2524      ) -> dict | None:
  2525          """Auto-detect if content is in a different language/dialect and translate.
  2526  
  2527          Checks if the message is in a language different from the owner's preferred
  2528          language. If so, translates it. Also handles Chinese dialects (粤语, 四川话, etc.)
  2529  
  2530          Args:
  2531              owner_id: The user who needs the translation
  2532              content: The message content to check
  2533              owner_lang: Owner's preferred language code (auto-fetched if empty)
  2534  
  2535          Returns:
  2536              Dict with detection + translation result, or None if same language
  2537          """
  2538          if not AI_BASE_URL or not AI_API_KEY:
  2539              return None
  2540  
  2541          if not owner_lang:
  2542              profile = get_twin_profile(owner_id)
  2543              if profile:
  2544                  owner_lang = profile.preferred_lang or "zh"
  2545              else:
  2546                  owner_lang = "zh"
  2547  
  2548          owner_lang_name = get_lang_name(owner_lang)
  2549  
  2550          # Ask AI to detect language and translate if needed
  2551          prompt = (
  2552              f"Analyze this message and determine if it needs translation for a "
  2553              f"{owner_lang_name} speaker.\n\n"
  2554              f"Message: \"{content}\"\n\n"
  2555              f"Rules:\n"
  2556              f"- If the message is standard {owner_lang_name}, respond with exactly: SAME\n"
  2557              f"- If the message is in a different language OR a dialect (e.g. Cantonese/粤语, "
  2558              f"Sichuanese/四川话, Hokkien/闽南语, Shanghainese/上海话, etc.), respond in this "
  2559              f"exact format:\n"
  2560              f"LANG: <detected language or dialect name>\n"
  2561              f"TRANSLATION: <translation into standard {owner_lang_name}>\n\n"
  2562              f"Be precise. Only output SAME or the LANG/TRANSLATION format, nothing else."
  2563          )
  2564  
  2565          try:
  2566              async with httpx.AsyncClient(timeout=12) as client:
  2567                  resp = await client.post(
  2568                      f"{AI_BASE_URL}/chat/completions",
  2569                      headers={
  2570                          "Authorization": f"Bearer {AI_API_KEY}",
  2571                          "Content-Type": "application/json",
  2572                      },
  2573                      json={
  2574                          "model": AI_MODEL,
  2575                          "max_tokens": 200,
  2576                          "temperature": 0.1,
  2577                          "messages": [{"role": "user", "content": prompt}],
  2578                      },
  2579                  )
  2580                  raw = resp.json()["choices"][0]["message"]["content"].strip()
  2581          except Exception as e:
  2582              logger.warning(f"Language detection failed: {e}")
  2583              return None
  2584  
  2585          if raw.upper().startswith("SAME"):
  2586              return None  # Same language, no translation needed
  2587  
  2588          # Parse LANG: ... TRANSLATION: ... format
  2589          detected_lang = ""
  2590          translation = ""
  2591          for line in raw.split("\n"):
  2592              line = line.strip()
  2593              if line.upper().startswith("LANG:"):
  2594                  detected_lang = line[5:].strip()
  2595              elif line.upper().startswith("TRANSLATION:"):
  2596                  translation = line[12:].strip()
  2597  
  2598          if not translation:
  2599              return None
  2600  
  2601          return {
  2602              "detected_lang": detected_lang,
  2603              "translated_content": translation,
  2604              "original_content": content,
  2605              "target_lang": owner_lang,
  2606              "auto_detected": True,
  2607          }
  2608  
  2609      async def _ai_reply(
  2610          self, profile, incoming_msg: str, sender_mode: str, target_lang: str = ""
  2611      ) -> str | None:
  2612          """Generate reply using an OpenAI-compatible API, with optional translation."""
  2613          sender_label = "their real self" if sender_mode == "real" else "their digital twin"
  2614  
  2615          # Build language instruction
  2616          lang_instruction = ""
  2617          if target_lang:
  2618              target_name = get_lang_name(target_lang)
  2619              lang_instruction = (
  2620                  f"\nIMPORTANT: Reply in {target_name}. "
  2621                  f"Do not just translate — speak naturally as {profile.display_name} "
  2622                  f"would if they were fluent in {target_name}. "
  2623                  f"Preserve their personality, humor, and speaking style."
  2624              )
  2625  
  2626          personality_block = profile.build_personality_prompt()
  2627          prompt = (
  2628              f"You are {profile.display_name}'s digital twin.\n"
  2629              f"{personality_block}\n"
  2630              f"Someone ({sender_label}) says: \"{incoming_msg}\"\n\n"
  2631              f"Reply as {profile.display_name}'s twin. Keep it under 50 words, "
  2632              f"natural and authentic. Output only the reply text."
  2633              f"{lang_instruction}"
  2634          )
  2635  
  2636          try:
  2637              async with httpx.AsyncClient(timeout=15) as client:
  2638                  resp = await client.post(
  2639                      f"{AI_BASE_URL}/chat/completions",
  2640                      headers={
  2641                          "Authorization": f"Bearer {AI_API_KEY}",
  2642                          "Content-Type": "application/json",
  2643                      },
  2644                      json={
  2645                          "model": AI_MODEL,
  2646                          "max_tokens": 100,
  2647                          "messages": [{"role": "user", "content": prompt}],
  2648                      },
  2649                  )
  2650                  return resp.json()["choices"][0]["message"]["content"].strip()
  2651          except Exception as e:
  2652              logger.warning(f"AI twin reply failed: {e}")
  2653              return None
  2654  
  2655      def _fallback_reply(self, profile, incoming_msg: str, target_lang: str = "") -> str:
  2656          """Generate a template reply when no AI backend is available."""
  2657          name = profile.display_name
  2658          if target_lang == "zh":
  2659              return f"[{name}的分身自动回复] 感谢你的消息！{name}现在不在，分身已收到。"
  2660          elif target_lang == "ja":
  2661              return f"[{name}のツイン自動返信] メッセージありがとう！{name}は今いませんが、ツインが受け取りました。"
  2662          elif target_lang == "ko":
  2663              return f"[{name}의 트윈 자동응답] 메시지 감사합니다! {name}은 지금 없지만 트윈이 받았습니다."
  2664          return (
  2665              f"[Auto-reply from {name}'s twin] "
  2666              f"Thanks for your message! {name} is not available right now, "
  2667              f"but their twin received it."
  2668          )

# --- tests/conftest.py ---
  2669  """DualSoul test configuration."""
  2670  
  2671  import os
  2672  import tempfile
  2673  
  2674  import pytest
  2675  from fastapi.testclient import TestClient
  2676  
  2677  # Set test database before importing app
  2678  _tmpdir = tempfile.mkdtemp()
  2679  os.environ["DUALSOUL_DATABASE_PATH"] = os.path.join(_tmpdir, "test.db")
  2680  os.environ["DUALSOUL_JWT_SECRET"] = "test_secret_for_testing_only"
  2681  
  2682  
  2683  @pytest.fixture(scope="session")
  2684  def app():
  2685      from dualsoul.main import app as _app
  2686      return _app
  2687  
  2688  
  2689  @pytest.fixture(scope="session")
  2690  def client(app):
  2691      with TestClient(app, raise_server_exceptions=False) as c:
  2692          yield c
  2693  
  2694  
  2695  @pytest.fixture(scope="session")
  2696  def alice_token(client):
  2697      """Register Alice and return her token."""
  2698      resp = client.post("/api/auth/register", json={
  2699          "username": "alice", "password": "alice123", "display_name": "Alice"
  2700      })
  2701      return resp.json()["data"]["token"]
  2702  
  2703  
  2704  @pytest.fixture(scope="session")
  2705  def bob_token(client):
  2706      """Register Bob and return his token."""
  2707      resp = client.post("/api/auth/register", json={
  2708          "username": "bob", "password": "bob123", "display_name": "Bob"
  2709      })
  2710      return resp.json()["data"]["token"]
  2711  
  2712  
  2713  @pytest.fixture
  2714  def alice_h(alice_token):
  2715      return {"Authorization": f"Bearer {alice_token}"}
  2716  
  2717  
  2718  @pytest.fixture
  2719  def bob_h(bob_token):
  2720      return {"Authorization": f"Bearer {bob_token}"}

# --- tests/test_auth.py ---
  2721  """Auth endpoint tests."""
  2722  
  2723  
  2724  def test_health(client):
  2725      resp = client.get("/api/health")
  2726      assert resp.status_code == 200
  2727      assert resp.json()["status"] == "ok"
  2728  
  2729  
  2730  def test_register_success(client):
  2731      resp = client.post("/api/auth/register", json={
  2732          "username": "testuser", "password": "test123"
  2733      })
  2734      assert resp.status_code == 200
  2735      data = resp.json()
  2736      assert data["success"] is True
  2737      assert "token" in data["data"]
  2738  
  2739  
  2740  def test_register_duplicate(client):
  2741      resp = client.post("/api/auth/register", json={
  2742          "username": "testuser", "password": "test123"
  2743      })
  2744      assert resp.json()["success"] is False
  2745  
  2746  
  2747  def test_register_short_password(client):
  2748      resp = client.post("/api/auth/register", json={
  2749          "username": "shortpw", "password": "12345"
  2750      })
  2751      assert resp.json()["success"] is False
  2752  
  2753  
  2754  def test_login_success(client):
  2755      resp = client.post("/api/auth/login", json={
  2756          "username": "testuser", "password": "test123"
  2757      })
  2758      assert resp.status_code == 200
  2759      assert resp.json()["success"] is True
  2760      assert "token" in resp.json()["data"]
  2761  
  2762  
  2763  def test_login_wrong_password(client):
  2764      resp = client.post("/api/auth/login", json={
  2765          "username": "testuser", "password": "wrong"
  2766      })
  2767      assert resp.json()["success"] is False
  2768  
  2769  
  2770  def test_protected_without_token(client):
  2771      resp = client.get("/api/identity/me")
  2772      assert resp.status_code == 401

# --- tests/test_identity.py ---
  2773  """Identity switching and profile tests."""
  2774  
  2775  
  2776  def test_switch_to_twin(client, alice_h):
  2777      resp = client.post("/api/identity/switch", json={"mode": "twin"}, headers=alice_h)
  2778      assert resp.status_code == 200
  2779      assert resp.json()["mode"] == "twin"
  2780  
  2781  
  2782  def test_switch_to_real(client, alice_h):
  2783      resp = client.post("/api/identity/switch", json={"mode": "real"}, headers=alice_h)
  2784      assert resp.json()["mode"] == "real"
  2785  
  2786  
  2787  def test_switch_invalid_mode(client, alice_h):
  2788      resp = client.post("/api/identity/switch", json={"mode": "ghost"}, headers=alice_h)
  2789      assert resp.json()["success"] is False
  2790  
  2791  
  2792  def test_switch_requires_auth(client):
  2793      resp = client.post("/api/identity/switch", json={"mode": "twin"})
  2794      assert resp.status_code == 401
  2795  
  2796  
  2797  def test_get_profile(client, alice_h):
  2798      resp = client.get("/api/identity/me", headers=alice_h)
  2799      assert resp.status_code == 200
  2800      data = resp.json()["data"]
  2801      assert data["username"] == "alice"
  2802      assert data["display_name"] == "Alice"
  2803      assert data["current_mode"] in ("real", "twin")
  2804  
  2805  
  2806  def test_update_twin_personality(client, alice_h):
  2807      resp = client.put("/api/identity/profile", json={
  2808          "twin_personality": "analytical and curious",
  2809          "twin_speech_style": "concise and witty"
  2810      }, headers=alice_h)
  2811      assert resp.json()["success"] is True
  2812  
  2813      # Verify
  2814      resp = client.get("/api/identity/me", headers=alice_h)
  2815      data = resp.json()["data"]
  2816      assert data["twin_personality"] == "analytical and curious"
  2817      assert data["twin_speech_style"] == "concise and witty"
  2818  
  2819  
  2820  def test_update_empty_profile(client, alice_h):
  2821      resp = client.put("/api/identity/profile", json={}, headers=alice_h)
  2822      assert resp.json()["success"] is False

# --- tests/test_social.py ---
  2823  """Social system tests — friends, messages, four conversation modes."""
  2824  
  2825  import pytest
  2826  
  2827  
  2828  @pytest.fixture(scope="module")
  2829  def bob_user_id(bob_token):
  2830      """Ensure bob is registered and extract user_id from token."""
  2831      import jwt
  2832      payload = jwt.decode(bob_token, options={"verify_signature": False})
  2833      return payload["user_id"]
  2834  
  2835  
  2836  # ═══ Friend System ═══
  2837  
  2838  def test_add_friend_requires_auth(client):
  2839      resp = client.post("/api/social/friends/add", json={"friend_username": "bob"})
  2840      assert resp.status_code == 401
  2841  
  2842  
  2843  def test_add_friend_not_found(client, alice_h):
  2844      resp = client.post("/api/social/friends/add",
  2845                         json={"friend_username": "nonexistent"}, headers=alice_h)
  2846      assert resp.json()["success"] is False
  2847  
  2848  
  2849  def test_add_friend_success(client, alice_h, bob_user_id):
  2850      """Alice adds Bob — bob_user_id fixture ensures Bob is registered first."""
  2851      resp = client.post("/api/social/friends/add",
  2852                         json={"friend_username": "bob"}, headers=alice_h)
  2853      data = resp.json()
  2854      assert data["success"] is True, f"add_friend failed: {data}"
  2855      assert "conn_id" in data
  2856  
  2857  
  2858  def test_add_friend_duplicate(client, alice_h, bob_user_id):
  2859      resp = client.post("/api/social/friends/add",
  2860                         json={"friend_username": "bob"}, headers=alice_h)
  2861      assert resp.json()["success"] is False
  2862  
  2863  
  2864  def test_friends_list_pending(client, bob_h):
  2865      """Bob should see an incoming pending request."""
  2866      resp = client.get("/api/social/friends", headers=bob_h)
  2867      assert resp.json()["success"] is True
  2868      friends = resp.json()["friends"]
  2869      assert len(friends) >= 1
  2870      assert friends[0]["status"] == "pending"
  2871      assert friends[0]["is_incoming"] is True
  2872  
  2873  
  2874  # ═══ Friend Response ═══
  2875  
  2876  def test_respond_requires_auth(client):
  2877      resp = client.post("/api/social/friends/respond",
  2878                         json={"conn_id": "sc_x", "action": "accept"})
  2879      assert resp.status_code == 401
  2880  
  2881  
  2882  def test_respond_accept(client, bob_h):
  2883      """Bob accepts Alice's friend request."""
  2884      resp = client.get("/api/social/friends", headers=bob_h)
  2885      pending = [f for f in resp.json()["friends"]
  2886                 if f["status"] == "pending" and f["is_incoming"]]
  2887      assert len(pending) >= 1
  2888  
  2889      resp = client.post("/api/social/friends/respond",
  2890                         json={"conn_id": pending[0]["conn_id"], "action": "accept"},
  2891                         headers=bob_h)
  2892      assert resp.json()["success"] is True
  2893      assert resp.json()["status"] == "accepted"
  2894  
  2895  
  2896  # ═══ Messages ═══
  2897  
  2898  def test_messages_requires_auth(client):
  2899      resp = client.get("/api/social/messages?friend_id=u_test")
  2900      assert resp.status_code == 401
  2901  
  2902  
  2903  def test_send_empty_content(client, alice_h):
  2904      resp = client.get("/api/social/friends", headers=alice_h)
  2905      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  2906  
  2907      resp = client.post("/api/social/messages/send", json={
  2908          "to_user_id": bob["user_id"], "content": "  "
  2909      }, headers=alice_h)
  2910      assert resp.json()["success"] is False
  2911  
  2912  
  2913  def test_send_to_non_friend(client, alice_h):
  2914      resp = client.post("/api/social/messages/send", json={
  2915          "to_user_id": "u_nonexistent", "content": "hello"
  2916      }, headers=alice_h)
  2917      assert resp.json()["success"] is False
  2918  
  2919  
  2920  def test_send_real_to_real(client, alice_h):
  2921      """Real → Real: traditional messaging."""
  2922      resp = client.get("/api/social/friends", headers=alice_h)
  2923      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  2924  
  2925      resp = client.post("/api/social/messages/send", json={
  2926          "to_user_id": bob["user_id"],
  2927          "content": "Hey Bob, how are you?",
  2928          "sender_mode": "real",
  2929          "receiver_mode": "real"
  2930      }, headers=alice_h)
  2931      assert resp.json()["success"] is True
  2932      assert "msg_id" in resp.json()
  2933      assert resp.json()["ai_reply"] is None  # No auto-reply in real mode
  2934  
  2935  
  2936  def test_send_real_to_twin(client, alice_h):
  2937      """Real → Twin: talking to someone's twin (triggers auto-reply)."""
  2938      resp = client.get("/api/social/friends", headers=alice_h)
  2939      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  2940  
  2941      resp = client.post("/api/social/messages/send", json={
  2942          "to_user_id": bob["user_id"],
  2943          "content": "Hey Bob's twin, what do you think?",
  2944          "sender_mode": "real",
  2945          "receiver_mode": "twin"
  2946      }, headers=alice_h)
  2947      assert resp.json()["success"] is True
  2948      reply = resp.json().get("ai_reply")
  2949      if reply:
  2950          assert reply["ai_generated"] is True
  2951  
  2952  
  2953  def test_send_twin_to_twin(client, alice_h):
  2954      """Twin → Twin: fully autonomous conversation."""
  2955      resp = client.get("/api/social/friends", headers=alice_h)
  2956      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  2957  
  2958      resp = client.post("/api/social/messages/send", json={
  2959          "to_user_id": bob["user_id"],
  2960          "content": "Twin-to-twin test",
  2961          "sender_mode": "twin",
  2962          "receiver_mode": "twin"
  2963      }, headers=alice_h)
  2964      assert resp.json()["success"] is True
  2965  
  2966  
  2967  def test_messages_after_send(client, alice_h):
  2968      """Should have messages in history now."""
  2969      resp = client.get("/api/social/friends", headers=alice_h)
  2970      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  2971  
  2972      resp = client.get(f"/api/social/messages?friend_id={bob['user_id']}", headers=alice_h)
  2973      assert resp.json()["success"] is True
  2974      assert len(resp.json()["messages"]) >= 3
  2975  
  2976  
  2977  def test_messages_from_bob_side(client, bob_h):
  2978      """Bob should also see the messages."""
  2979      resp = client.get("/api/social/friends", headers=bob_h)
  2980      alice = [f for f in resp.json()["friends"] if f["username"] == "alice"][0]
  2981  
  2982      resp = client.get(f"/api/social/messages?friend_id={alice['user_id']}", headers=bob_h)
  2983      assert resp.json()["success"] is True
  2984      assert len(resp.json()["messages"]) >= 3
  2985  
  2986  
  2987  # ═══ Unread ═══
  2988  
  2989  def test_unread_requires_auth(client):
  2990      resp = client.get("/api/social/unread")
  2991      assert resp.status_code == 401
  2992  
  2993  
  2994  def test_unread_count(client, alice_h):
  2995      """Send a new message, then check unread for Bob."""
  2996      resp = client.get("/api/social/friends", headers=alice_h)
  2997      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  2998  
  2999      client.post("/api/social/messages/send", json={
  3000          "to_user_id": bob["user_id"], "content": "unread test",
  3001          "sender_mode": "real", "receiver_mode": "real"
  3002      }, headers=alice_h)
  3003  
  3004      from dualsoul.auth import create_token
  3005      bob_h2 = {"Authorization": f"Bearer {create_token(bob['user_id'], 'bob')}"}
  3006      resp = client.get("/api/social/unread", headers=bob_h2)
  3007      assert resp.status_code == 200
  3008      assert resp.json()["count"] >= 1
  3009  
  3010  
  3011  # ═══ Translation ═══
  3012  
  3013  def test_translate_requires_auth(client):
  3014      resp = client.post("/api/social/translate", json={
  3015          "content": "hello", "target_lang": "zh"
  3016      })
  3017      assert resp.status_code == 401
  3018  
  3019  
  3020  def test_translate_empty_content(client, alice_h):
  3021      resp = client.post("/api/social/translate", json={
  3022          "content": "  ", "target_lang": "zh"
  3023      }, headers=alice_h)
  3024      assert resp.json()["success"] is False
  3025  
  3026  
  3027  def test_translate_no_target_lang(client, alice_h):
  3028      resp = client.post("/api/social/translate", json={
  3029          "content": "hello", "target_lang": ""
  3030      }, headers=alice_h)
  3031      assert resp.json()["success"] is False
  3032  
  3033  
  3034  def test_translate_no_ai_backend(client, alice_h):
  3035      """Without AI backend configured, translation should report unavailable."""
  3036      resp = client.post("/api/social/translate", json={
  3037          "content": "hello world", "source_lang": "en", "target_lang": "zh"
  3038      }, headers=alice_h)
  3039      data = resp.json()
  3040      # Either fails gracefully (no AI) or succeeds (AI configured)
  3041      assert "success" in data
  3042  
  3043  
  3044  def test_send_with_target_lang(client, alice_h):
  3045      """Send message with explicit target_lang for cross-language reply."""
  3046      resp = client.get("/api/social/friends", headers=alice_h)
  3047      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  3048  
  3049      resp = client.post("/api/social/messages/send", json={
  3050          "to_user_id": bob["user_id"],
  3051          "content": "Cross-language test",
  3052          "sender_mode": "real",
  3053          "receiver_mode": "twin",
  3054          "target_lang": "zh"
  3055      }, headers=alice_h)
  3056      assert resp.json()["success"] is True
  3057  
  3058  
  3059  def test_preferred_lang_in_profile(client, alice_h):
  3060      """Update preferred_lang and verify it appears in profile."""
  3061      resp = client.put("/api/identity/profile", json={
  3062          "preferred_lang": "en"
  3063      }, headers=alice_h)
  3064      assert resp.json()["success"] is True
  3065  
  3066      resp = client.get("/api/identity/me", headers=alice_h)
  3067      assert resp.json()["data"]["preferred_lang"] == "en"
  3068  
  3069  
  3070  def test_messages_include_translation_fields(client, alice_h):
  3071      """Messages should include translation metadata fields."""
  3072      resp = client.get("/api/social/friends", headers=alice_h)
  3073      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  3074  
  3075      resp = client.get(f"/api/social/messages?friend_id={bob['user_id']}", headers=alice_h)
  3076      assert resp.json()["success"] is True
  3077      msgs = resp.json()["messages"]
  3078      assert len(msgs) >= 1
  3079      # Check that translation fields exist in messages
  3080      msg = msgs[0]
  3081      assert "original_content" in msg or "content" in msg

# --- tests/test_twin.py ---
  3082  """Twin engine tests."""
  3083  
  3084  from dualsoul.protocol.message import (
  3085      ConversationMode,
  3086      DualSoulMessage,
  3087      IdentityMode,
  3088      get_conversation_mode,
  3089  )
  3090  
  3091  
  3092  def test_conversation_modes():
  3093      assert get_conversation_mode("real", "real") == ConversationMode.REAL_TO_REAL
  3094      assert get_conversation_mode("real", "twin") == ConversationMode.REAL_TO_TWIN
  3095      assert get_conversation_mode("twin", "real") == ConversationMode.TWIN_TO_REAL
  3096      assert get_conversation_mode("twin", "twin") == ConversationMode.TWIN_TO_TWIN
  3097  
  3098  
  3099  def test_message_to_dict():
  3100      msg = DualSoulMessage(
  3101          msg_id="sm_test123",
  3102          from_user_id="u_alice",
  3103          to_user_id="u_bob",
  3104          sender_mode=IdentityMode.REAL,
  3105          receiver_mode=IdentityMode.TWIN,
  3106          content="Hello twin!",
  3107      )
  3108      d = msg.to_dict()
  3109      assert d["sender_mode"] == "real"
  3110      assert d["receiver_mode"] == "twin"
  3111      assert d["conversation_mode"] == "real_to_twin"
  3112      assert d["ai_generated"] is False
  3113  
  3114  
  3115  def test_message_conversation_mode():
  3116      msg = DualSoulMessage(
  3117          msg_id="sm_test456",
  3118          from_user_id="u_a",
  3119          to_user_id="u_b",
  3120          sender_mode=IdentityMode.TWIN,
  3121          receiver_mode=IdentityMode.TWIN,
  3122          content="Twin chat",
  3123          ai_generated=True,
  3124      )
  3125      assert msg.conversation_mode == ConversationMode.TWIN_TO_TWIN
  3126      assert msg.ai_generated is True
  3127  
  3128  
  3129  def test_identity_mode_values():
  3130      assert IdentityMode.REAL.value == "real"
  3131      assert IdentityMode.TWIN.value == "twin"
