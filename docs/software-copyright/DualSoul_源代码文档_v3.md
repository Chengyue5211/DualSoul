# DualSoul双身份社交协议

## 源代码文档

- 软件名称：DualSoul双身份社交协议软件
- 版本号：V3.0（对应代码版本 v0.7.1）
- 代码总行数：6657（Python源码3759 + 测试463 + 前端2435）
- 编程语言：Python / HTML5 / JavaScript
- 开发完成日期：2026年3月14日
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
   548  class AvatarGenerateRequest(BaseModel):
   549      image: str  # base64 encoded source photo
   550      style: str = "anime"  # Style key: anime, 3d, cyber, clay, pixel, ink, retro
   551  
   552  
   553  class TwinDraftRequest(BaseModel):
   554      friend_id: str
   555      incoming_msg: str
   556      context: list[dict] = []  # [{role: "me"/"friend", content: "..."}]
   557  
   558  
   559  class TwinChatRequest(BaseModel):
   560      message: str
   561      history: list[dict] = []  # [{role: "me"/"twin", content: "..."}]
   562      image: str = ""  # Optional base64 image data URL for vision
   563  
   564  
   565  # Social
   566  class AddFriendRequest(BaseModel):
   567      friend_username: str
   568  
   569  
   570  class RespondFriendRequest(BaseModel):
   571      conn_id: str
   572      action: str  # 'accept' or 'block'
   573  
   574  
   575  class TranslateRequest(BaseModel):
   576      content: str
   577      source_lang: str = "auto"
   578      target_lang: str = "en"
   579  
   580  
   581  class SendMessageRequest(BaseModel):
   582      to_user_id: str
   583      content: str
   584      sender_mode: str = "real"
   585      receiver_mode: str = "real"
   586      msg_type: str = "text"
   587      target_lang: str = ""  # If set, twin translates to this language with personality preservation
   588  
   589  
   590  # Twin Import (年轮分身导入)
   591  class TwinImportRequest(BaseModel):
   592      format: str = "tpf_v1"  # Twin Portable Format version
   593      source: str = "nianlun"  # Source platform: 'nianlun', 'openclaw', etc.
   594      data: dict  # Full export payload (Twin Portable Format)
   595  
   596  
   597  class TwinSyncRequest(BaseModel):
   598      format: str = "tpf_v1"
   599      since: str = ""  # ISO timestamp of last sync
   600      data: dict  # Incremental data (new memories, entities, dimension updates)

# --- dualsoul/protocol/message.py ---
   601  """DualSoul Protocol — Dual Identity Message Format.
   602  
   603  Every message in DualSoul carries two identity modes:
   604    - sender_mode: Is the sender speaking as their real self or digital twin?
   605    - receiver_mode: Is the message addressed to the real person or their twin?
   606  
   607  This creates four distinct conversation modes:
   608  
   609    Real → Real   : Traditional human-to-human messaging
   610    Real → Twin   : Asking someone's digital twin a question
   611    Twin → Real   : Your twin reaching out to a real person
   612    Twin → Twin   : Autonomous twin-to-twin conversation
   613  """
   614  
   615  from dataclasses import dataclass, field
   616  from enum import Enum
   617  from typing import Optional
   618  
   619  # Protocol version — included in every DISP message
   620  DISP_VERSION = "1.0"
   621  
   622  
   623  class IdentityMode(str, Enum):
   624      REAL = "real"
   625      TWIN = "twin"
   626  
   627  
   628  class ConversationMode(str, Enum):
   629      REAL_TO_REAL = "real_to_real"
   630      REAL_TO_TWIN = "real_to_twin"
   631      TWIN_TO_REAL = "twin_to_real"
   632      TWIN_TO_TWIN = "twin_to_twin"
   633  
   634  
   635  class MessageType(str, Enum):
   636      TEXT = "text"
   637      IMAGE = "image"
   638      VOICE = "voice"
   639      SYSTEM = "system"
   640  
   641  
   642  @dataclass
   643  class DualSoulMessage:
   644      """A message in the DualSoul protocol."""
   645  
   646      msg_id: str
   647      from_user_id: str
   648      to_user_id: str
   649      sender_mode: IdentityMode
   650      receiver_mode: IdentityMode
   651      content: str
   652      msg_type: MessageType = MessageType.TEXT
   653      ai_generated: bool = False
   654      created_at: Optional[str] = None
   655      disp_version: str = field(default=DISP_VERSION)
   656  
   657      @property
   658      def conversation_mode(self) -> ConversationMode:
   659          """Determine which of the four conversation modes this message belongs to."""
   660          key = f"{self.sender_mode.value}_to_{self.receiver_mode.value}"
   661          return ConversationMode(key)
   662  
   663      def to_dict(self) -> dict:
   664          return {
   665              "disp_version": self.disp_version,
   666              "msg_id": self.msg_id,
   667              "from_user_id": self.from_user_id,
   668              "to_user_id": self.to_user_id,
   669              "sender_mode": self.sender_mode.value,
   670              "receiver_mode": self.receiver_mode.value,
   671              "content": self.content,
   672              "msg_type": self.msg_type.value,
   673              "ai_generated": self.ai_generated,
   674              "conversation_mode": self.conversation_mode.value,
   675              "created_at": self.created_at,
   676          }
   677  
   678  
   679  def get_conversation_mode(sender_mode: str, receiver_mode: str) -> ConversationMode:
   680      """Get the conversation mode from sender and receiver mode strings."""
   681      return ConversationMode(f"{sender_mode}_to_{receiver_mode}")

# --- dualsoul/routers/auth.py ---
   682  """Auth router — register and login."""
   683  
   684  from fastapi import APIRouter
   685  
   686  from dualsoul.auth import create_token, hash_password, verify_password
   687  from dualsoul.database import gen_id, get_db
   688  from dualsoul.models import LoginRequest, RegisterRequest
   689  
   690  router = APIRouter(prefix="/api/auth", tags=["Auth"])
   691  
   692  
   693  @router.post("/register")
   694  async def register(req: RegisterRequest):
   695      """Register a new user."""
   696      username = req.username.strip()
   697      if not username or len(username) < 2:
   698          return {"success": False, "error": "Username must be at least 2 characters"}
   699      if len(req.password) < 6:
   700          return {"success": False, "error": "Password must be at least 6 characters"}
   701  
   702      with get_db() as db:
   703          exists = db.execute(
   704              "SELECT user_id FROM users WHERE username=?", (username,)
   705          ).fetchone()
   706          if exists:
   707              return {"success": False, "error": "Username already taken"}
   708  
   709          user_id = gen_id("u_")
   710          db.execute(
   711              "INSERT INTO users (user_id, username, password_hash, display_name, reg_source) "
   712              "VALUES (?, ?, ?, ?, ?)",
   713              (user_id, username, hash_password(req.password), req.display_name or username,
   714               req.reg_source or "dualsoul"),
   715          )
   716  
   717      token = create_token(user_id, username)
   718      return {
   719          "success": True,
   720          "data": {
   721              "user_id": user_id,
   722              "username": username,
   723              "token": token,
   724          },
   725      }
   726  
   727  
   728  @router.post("/login")
   729  async def login(req: LoginRequest):
   730      """Login and get a JWT token."""
   731      with get_db() as db:
   732          user = db.execute(
   733              "SELECT user_id, username, password_hash FROM users WHERE username=?",
   734              (req.username.strip(),),
   735          ).fetchone()
   736  
   737      if not user or not verify_password(req.password, user["password_hash"]):
   738          return {"success": False, "error": "Invalid username or password"}
   739  
   740      token = create_token(user["user_id"], user["username"])
   741      return {
   742          "success": True,
   743          "data": {
   744              "user_id": user["user_id"],
   745              "username": user["username"],
   746              "token": token,
   747          },
   748      }

# --- dualsoul/routers/identity.py ---
   749  """Identity router — switch mode, profile management, twin preview, avatar upload, style learning, twin growth, twin card."""
   750  
   751  import base64
   752  import hashlib
   753  import os
   754  
   755  import httpx
   756  from fastapi import APIRouter, Depends, Request
   757  from fastapi.responses import HTMLResponse, JSONResponse
   758  
   759  from dualsoul.auth import get_current_user
   760  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
   761  from dualsoul.database import get_db
   762  from dualsoul.models import AvatarGenerateRequest, AvatarUploadRequest, SwitchModeRequest, TwinPreviewRequest, UpdateProfileRequest, VoiceUploadRequest
   763  from dualsoul.twin_engine.learner import analyze_style, get_message_count, learn_and_update
   764  
   765  _AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "avatars")
   766  os.makedirs(_AVATAR_DIR, exist_ok=True)
   767  _VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "voiceprints")
   768  os.makedirs(_VOICE_DIR, exist_ok=True)
   769  
   770  router = APIRouter(prefix="/api/identity", tags=["Identity"])
   771  
   772  
   773  @router.post("/switch")
   774  async def switch_mode(req: SwitchModeRequest, user=Depends(get_current_user)):
   775      """Switch between real self and digital twin mode."""
   776      uid = user["user_id"]
   777      if req.mode not in ("real", "twin"):
   778          return {"success": False, "error": "mode must be 'real' or 'twin'"}
   779      with get_db() as db:
   780          db.execute("UPDATE users SET current_mode=? WHERE user_id=?", (req.mode, uid))
   781      return {"success": True, "mode": req.mode}
   782  
   783  
   784  @router.get("/me")
   785  async def get_profile(user=Depends(get_current_user)):
   786      """Get current user's dual identity profile."""
   787      uid = user["user_id"]
   788      with get_db() as db:
   789          row = db.execute(
   790              "SELECT user_id, username, display_name, current_mode, "
   791              "twin_personality, twin_speech_style, preferred_lang, avatar, twin_avatar, "
   792              "twin_auto_reply, gender, reg_source FROM users WHERE user_id=?",
   793              (uid,),
   794          ).fetchone()
   795      if not row:
   796          return {"success": False, "error": "User not found"}
   797      return {
   798          "success": True,
   799          "data": {
   800              "user_id": row["user_id"],
   801              "username": row["username"],
   802              "display_name": row["display_name"],
   803              "current_mode": row["current_mode"] or "real",
   804              "twin_personality": row["twin_personality"] or "",
   805              "twin_speech_style": row["twin_speech_style"] or "",
   806              "preferred_lang": row["preferred_lang"] or "",
   807              "avatar": row["avatar"] or "",
   808              "twin_avatar": row["twin_avatar"] or "",
   809              "twin_auto_reply": row["twin_auto_reply"] if "twin_auto_reply" in row.keys() else 0,
   810              "gender": row["gender"] if "gender" in row.keys() else "",
   811              "reg_source": row["reg_source"] if "reg_source" in row.keys() else "dualsoul",
   812          },
   813      }
   814  
   815  
   816  @router.put("/profile")
   817  async def update_profile(req: UpdateProfileRequest, user=Depends(get_current_user)):
   818      """Update display name and twin personality settings."""
   819      uid = user["user_id"]
   820      updates = []
   821      params = []
   822      if req.display_name:
   823          updates.append("display_name=?")
   824          params.append(req.display_name)
   825      if req.twin_personality:
   826          updates.append("twin_personality=?")
   827          params.append(req.twin_personality)
   828      if req.twin_speech_style:
   829          updates.append("twin_speech_style=?")
   830          params.append(req.twin_speech_style)
   831      if req.preferred_lang:
   832          updates.append("preferred_lang=?")
   833          params.append(req.preferred_lang)
   834      if req.twin_auto_reply is not None:
   835          updates.append("twin_auto_reply=?")
   836          params.append(1 if req.twin_auto_reply else 0)
   837      if req.gender:
   838          updates.append("gender=?")
   839          params.append(req.gender)
   840      if not updates:
   841          return {"success": False, "error": "Nothing to update"}
   842      params.append(uid)
   843      with get_db() as db:
   844          db.execute(f"UPDATE users SET {','.join(updates)} WHERE user_id=?", params)
   845      return {"success": True}
   846  
   847  
   848  @router.post("/avatar")
   849  async def upload_avatar(req: AvatarUploadRequest, user=Depends(get_current_user)):
   850      """Upload a base64-encoded avatar image. Saves to web/avatars/ and updates DB."""
   851      uid = user["user_id"]
   852      if req.type not in ("real", "twin"):
   853          return {"success": False, "error": "type must be 'real' or 'twin'"}
   854  
   855      # Strip data URI prefix if present
   856      img_data = req.image
   857      if "," in img_data:
   858          img_data = img_data.split(",", 1)[1]
   859      try:
   860          raw = base64.b64decode(img_data)
   861      except Exception:
   862          return {"success": False, "error": "Invalid base64 image"}
   863  
   864      if len(raw) > 2 * 1024 * 1024:  # 2MB limit
   865          return {"success": False, "error": "Image too large (max 2MB)"}
   866  
   867      # Save file
   868      name_hash = hashlib.md5(f"{uid}_{req.type}".encode()).hexdigest()[:12]
   869      filename = f"{name_hash}.png"
   870      filepath = os.path.join(_AVATAR_DIR, filename)
   871      with open(filepath, "wb") as f:
   872          f.write(raw)
   873  
   874      url = f"/static/avatars/{filename}"
   875      col = "avatar" if req.type == "real" else "twin_avatar"
   876      with get_db() as db:
   877          db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (url, uid))
   878  
   879      return {"success": True, "url": url}
   880  
   881  
   882  @router.post("/avatar/generate")
   883  async def generate_avatar(req: AvatarGenerateRequest, user=Depends(get_current_user)):
   884      """Generate a stylized AI twin avatar from a real photo.
   885  
   886      Uses DashScope style repaint API (same platform as Qwen).
   887      Takes ~15 seconds. Returns the generated image and saves it as twin_avatar.
   888      """
   889      from dualsoul.twin_engine.avatar import generate_twin_avatar_from_base64, get_available_styles
   890  
   891      uid = user["user_id"]
   892  
   893      result = await generate_twin_avatar_from_base64(
   894          image_base64=req.image,
   895          style=req.style,
   896      )
   897      if not result:
   898          return {"success": False, "error": "Avatar generation failed — AI service may be unavailable"}
   899  
   900      # Save the generated image as twin avatar
   901      img_bytes = base64.b64decode(result["image_base64"])
   902      if len(img_bytes) > 5 * 1024 * 1024:
   903          return {"success": False, "error": "Generated image too large"}
   904  
   905      name_hash = hashlib.md5(f"{uid}_twin".encode()).hexdigest()[:12]
   906      filename = f"{name_hash}.png"
   907      filepath = os.path.join(_AVATAR_DIR, filename)
   908      with open(filepath, "wb") as f:
   909          f.write(img_bytes)
   910  
   911      url = f"/static/avatars/{filename}"
   912      with get_db() as db:
   913          db.execute("UPDATE users SET twin_avatar=? WHERE user_id=?", (url, uid))
   914  
   915      return {"success": True, "url": url, "style": req.style}
   916  
   917  
   918  @router.get("/avatar/styles")
   919  async def avatar_styles():
   920      """Return available AI avatar styles."""
   921      from dualsoul.twin_engine.avatar import get_available_styles
   922      return {"success": True, "styles": get_available_styles()}
   923  
   924  
   925  @router.post("/voice")
   926  async def upload_voice(req: VoiceUploadRequest, user=Depends(get_current_user)):
   927      """Upload a base64-encoded voice sample. Saves to web/voiceprints/ and updates DB."""
   928      uid = user["user_id"]
   929      audio_data = req.audio
   930      if "," in audio_data:
   931          audio_data = audio_data.split(",", 1)[1]
   932      try:
   933          raw = base64.b64decode(audio_data)
   934      except Exception:
   935          return {"success": False, "error": "Invalid base64 audio"}
   936      if len(raw) > 5 * 1024 * 1024:
   937          return {"success": False, "error": "Audio too large (max 5MB)"}
   938  
   939      name_hash = hashlib.md5(f"{uid}_voice".encode()).hexdigest()[:12]
   940      filename = f"{name_hash}.webm"
   941      filepath = os.path.join(_VOICE_DIR, filename)
   942      with open(filepath, "wb") as f:
   943          f.write(raw)
   944  
   945      url = f"/static/voiceprints/{filename}"
   946      with get_db() as db:
   947          db.execute("UPDATE users SET voice_sample=? WHERE user_id=?", (url, uid))
   948      return {"success": True, "url": url}
   949  
   950  
   951  @router.post("/twin/preview")
   952  async def twin_preview(req: TwinPreviewRequest, user=Depends(get_current_user)):
   953      """Generate a sample twin reply for onboarding — lets the user see their twin speak."""
   954      name = req.display_name or "User"
   955      personality = req.personality or "friendly and thoughtful"
   956      speech_style = req.speech_style or "natural and warm"
   957  
   958      prompt = (
   959          f"You are {name}'s digital twin.\n"
   960          f"Personality: {personality}\n"
   961          f"Speech style: {speech_style}\n\n"
   962          f'A friend asks: "Hey, are you free this weekend?"\n\n'
   963          f"Reply as {name}'s twin. Keep it under 30 words, natural and authentic. "
   964          f"Output only the reply text, nothing else."
   965      )
   966  
   967      if not AI_BASE_URL or not AI_API_KEY:
   968          # Fallback — template reply reflecting personality
   969          return {
   970              "success": True,
   971              "reply": f"Hey! This is {name}'s twin. {name} might be around this weekend — "
   972                       f"I'll let them know you asked!",
   973          }
   974  
   975      try:
   976          async with httpx.AsyncClient(timeout=15) as client:
   977              resp = await client.post(
   978                  f"{AI_BASE_URL}/chat/completions",
   979                  headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
   980                  json={"model": AI_MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]},
   981              )
   982              reply = resp.json()["choices"][0]["message"]["content"].strip()
   983      except Exception:
   984          reply = f"Hey! This is {name}'s twin — I think the weekend might work, let me check!"
   985  
   986      return {"success": True, "reply": reply}
   987  
   988  
   989  @router.get("/twin/learn/status")
   990  async def learn_status(user=Depends(get_current_user)):
   991      """Check if enough messages exist for style learning."""
   992      uid = user["user_id"]
   993      count = get_message_count(uid)
   994      min_required = 10
   995      return {
   996          "success": True,
   997          "message_count": count,
   998          "min_required": min_required,
   999          "ready": count >= min_required,
  1000      }
  1001  
  1002  
  1003  @router.post("/twin/learn")
  1004  async def learn_style(user=Depends(get_current_user)):
  1005      """Analyze the user's chat history and extract personality + speech style.
  1006  
  1007      Returns the analysis result. The user can preview before applying.
  1008      """
  1009      uid = user["user_id"]
  1010      result = await analyze_style(uid)
  1011      if not result:
  1012          return {"success": False, "error": "Analysis unavailable (no AI backend)"}
  1013      if "error" in result:
  1014          return {
  1015              "success": False,
  1016              "error": result["error"],
  1017              "message_count": result.get("current", 0),
  1018              "min_required": result.get("required", 10),
  1019          }
  1020      return {"success": True, "data": result}
  1021  
  1022  
  1023  @router.post("/twin/learn/apply")
  1024  async def apply_learned_style(user=Depends(get_current_user)):
  1025      """Analyze and directly apply the learned style to the twin profile."""
  1026      uid = user["user_id"]
  1027      result = await learn_and_update(uid, auto_apply=True)
  1028      if not result:
  1029          return {"success": False, "error": "Learning unavailable"}
  1030      if "error" in result:
  1031          return {
  1032              "success": False,
  1033              "error": result["error"],
  1034              "message_count": result.get("current", 0),
  1035              "min_required": result.get("required", 10),
  1036          }
  1037      return {"success": True, "data": result}
  1038  
  1039  
  1040  @router.get("/twin/growth")
  1041  async def twin_growth(user=Depends(get_current_user)):
  1042      """Return stats about the twin's growth."""
  1043      uid = user["user_id"]
  1044      with get_db() as db:
  1045          # total conversations where user's twin was sender
  1046          total_row = db.execute(
  1047              "SELECT COUNT(*) AS cnt FROM social_messages "
  1048              "WHERE from_user_id=? AND sender_mode='twin'",
  1049              (uid,),
  1050          ).fetchone()
  1051          total_conversations = total_row["cnt"] if total_row else 0
  1052  
  1053          # distinct friends the twin has auto-replied to
  1054          friends_row = db.execute(
  1055              "SELECT COUNT(DISTINCT to_user_id) AS cnt FROM social_messages "
  1056              "WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1 "
  1057              "AND to_user_id!=?",
  1058              (uid, uid),
  1059          ).fetchone()
  1060          friends_helped = friends_row["cnt"] if friends_row else 0
  1061  
  1062          # actions: twin sent to others on behalf of owner
  1063          actions_row = db.execute(
  1064              "SELECT COUNT(*) AS cnt FROM social_messages "
  1065              "WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1 "
  1066              "AND to_user_id!=?",
  1067              (uid, uid),
  1068          ).fetchone()
  1069          actions_executed = actions_row["cnt"] if actions_row else 0
  1070  
  1071          # style learned?
  1072          user_row = db.execute(
  1073              "SELECT twin_personality, twin_speech_style, created_at "
  1074              "FROM users WHERE user_id=?",
  1075              (uid,),
  1076          ).fetchone()
  1077          style_learned = bool(
  1078              user_row
  1079              and (user_row["twin_personality"] or "").strip()
  1080              and (user_row["twin_speech_style"] or "").strip()
  1081          )
  1082  
  1083          # days active
  1084          days_active = 0
  1085          if user_row and user_row["created_at"]:
  1086              days_row = db.execute(
  1087                  "SELECT CAST(julianday('now','localtime') - julianday(?) AS INTEGER) AS d",
  1088                  (user_row["created_at"],),
  1089              ).fetchone()
  1090              days_active = max(days_row["d"], 0) if days_row else 0
  1091  
  1092      return {
  1093          "success": True,
  1094          "data": {
  1095              "total_conversations": total_conversations,
  1096              "friends_helped": friends_helped,
  1097              "actions_executed": actions_executed,
  1098              "style_learned": style_learned,
  1099              "days_active": days_active,
  1100          },
  1101      }
  1102  
  1103  
  1104  @router.get("/twin/card/{username}")
  1105  async def twin_card(username: str, request: Request):
  1106      """Public twin business card. Returns HTML for browsers, JSON for API clients."""
  1107      with get_db() as db:
  1108          row = db.execute(
  1109              "SELECT user_id, username, display_name, twin_personality, "
  1110              "twin_speech_style, preferred_lang, avatar, twin_avatar "
  1111              "FROM users WHERE username=?",
  1112              (username,),
  1113          ).fetchone()
  1114      if not row:
  1115          return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
  1116  
  1117      display_name = row["display_name"] or row["username"]
  1118      personality = row["twin_personality"] or ""
  1119      speech_style = row["twin_speech_style"] or ""
  1120      preferred_lang = row["preferred_lang"] or ""
  1121      avatar = row["avatar"] or ""
  1122      twin_avatar = row["twin_avatar"] or ""
  1123      invite_link = f"?invite={row['username']}"
  1124  
  1125      # Generate a greeting
  1126      greeting = ""
  1127      if AI_BASE_URL and AI_API_KEY:
  1128          try:
  1129              async with httpx.AsyncClient(timeout=8) as client:
  1130                  prompt = (
  1131                      f"You are {display_name}'s digital twin.\n"
  1132                      f"Personality: {personality}\n"
  1133                      f"Speech style: {speech_style}\n\n"
  1134                      f"Write a one-sentence self-introduction greeting for your business card. "
  1135                      f"Keep it under 25 words, natural and inviting. "
  1136                      f"Output only the greeting text."
  1137                  )
  1138                  resp = await client.post(
  1139                      f"{AI_BASE_URL}/chat/completions",
  1140                      headers={
  1141                          "Authorization": f"Bearer {AI_API_KEY}",
  1142                          "Content-Type": "application/json",
  1143                      },
  1144                      json={
  1145                          "model": AI_MODEL,
  1146                          "max_tokens": 60,
  1147                          "messages": [{"role": "user", "content": prompt}],
  1148                      },
  1149                  )
  1150                  greeting = resp.json()["choices"][0]["message"]["content"].strip()
  1151          except Exception:
  1152              pass
  1153      if not greeting:
  1154          greeting = f"Hi, I'm {display_name}'s digital twin. Nice to meet you!"
  1155  
  1156      card_data = {
  1157          "display_name": display_name,
  1158          "twin_personality": personality,
  1159          "twin_speech_style": speech_style,
  1160          "preferred_lang": preferred_lang,
  1161          "avatar": avatar,
  1162          "twin_avatar": twin_avatar,
  1163          "greeting": greeting,
  1164          "invite_link": invite_link,
  1165      }
  1166  
  1167      # Check Accept header: JSON or HTML
  1168      accept = request.headers.get("accept", "")
  1169      if "application/json" in accept and "text/html" not in accept:
  1170          return {"success": True, "data": card_data}
  1171  
  1172      # Return styled HTML card
  1173      avatar_src = twin_avatar or avatar
  1174      if avatar_src:
  1175          avatar_img = f'<img src="{avatar_src}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid rgba(92,200,250,.4);box-shadow:0 0 20px rgba(124,92,252,.3)">'
  1176      else:
  1177          avatar_img = f'<div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);display:flex;align-items:center;justify-content:center;font-size:32px;color:#fff;font-weight:700">{display_name[0] if display_name else "?"}</div>'
  1178  
  1179      from html import escape as h
  1180  
  1181      # Language-aware labels
  1182      lang_names = {
  1183          "zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어",
  1184          "fr": "Français", "de": "Deutsch", "es": "Español",
  1185      }
  1186      lang_display = lang_names.get(preferred_lang, preferred_lang) if preferred_lang else ""
  1187      is_zh = preferred_lang == "zh" or not preferred_lang
  1188  
  1189      lbl_personality = "性格特征" if is_zh else "Personality"
  1190      lbl_style = "说话风格" if is_zh else "Speech Style"
  1191      lbl_lang = "语言" if is_zh else "Language"
  1192      lbl_chat = f"和{h(display_name)}的分身聊天" if is_zh else f"Chat with {h(display_name)}'s Twin"
  1193      lbl_title = f"{h(display_name)} 的数字分身" if is_zh else f"{h(display_name)}'s Twin"
  1194      lbl_back = "返回" if is_zh else "Back"
  1195      lbl_footer = "DualSoul — 第四种社交" if is_zh else "DualSoul — The Fourth Kind of Social"
  1196  
  1197      html_content = f"""<!DOCTYPE html>
  1198  <html lang="{'zh' if is_zh else 'en'}">
  1199  <head>
  1200  <meta charset="UTF-8">
  1201  <meta name="viewport" content="width=device-width,initial-scale=1">
  1202  <title>{lbl_title} - DualSoul</title>
  1203  <style>
  1204  *{{margin:0;padding:0;box-sizing:border-box}}
  1205  body{{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;background:#0a0a10;color:#e8e4de;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
  1206  .back{{position:fixed;top:16px;left:16px;padding:8px 16px;border-radius:8px;background:rgba(255,255,255,.08);color:#8a8594;font-size:13px;text-decoration:none;border:1px solid rgba(255,255,255,.1);z-index:10}}
  1207  .back:hover{{background:rgba(255,255,255,.12)}}
  1208  .card{{background:#14141e;border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:32px 24px;max-width:380px;width:100%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.4)}}
  1209  .avatar{{margin:0 auto 16px}}
  1210  .name{{font-size:22px;font-weight:800;margin-bottom:4px;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
  1211  .greeting{{font-size:14px;color:#8a8594;margin:12px 0 16px;line-height:1.6;font-style:italic}}
  1212  .meta{{text-align:left;margin:16px 0;padding:14px;background:#1e1e2c;border-radius:12px}}
  1213  .meta-row{{display:flex;gap:8px;margin-bottom:10px;font-size:13px;align-items:flex-start}}
  1214  .meta-row:last-child{{margin-bottom:0}}
  1215  .meta-label{{color:#7c5cfc;min-width:65px;flex-shrink:0;font-weight:600;font-size:11px}}
  1216  .meta-value{{color:#e8e4de;line-height:1.5}}
  1217  .invite-btn{{display:inline-block;margin-top:16px;padding:12px 28px;border-radius:12px;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);color:#fff;font-size:14px;font-weight:700;text-decoration:none;transition:opacity .2s}}
  1218  .invite-btn:hover{{opacity:.9}}
  1219  .footer{{margin-top:16px;font-size:10px;color:#555}}
  1220  </style>
  1221  </head>
  1222  <body>
  1223  <a class="back" href="javascript:void(0)" onclick="if(history.length>1)history.back();else window.close()">&larr; {lbl_back}</a>
  1224  <div class="card">
  1225    <div class="avatar">{avatar_img}</div>
  1226    <div class="name">{lbl_title}</div>
  1227    <div class="greeting">"{h(greeting)}"</div>
  1228    <div class="meta">
  1229      {"<div class='meta-row'><span class='meta-label'>" + lbl_personality + "</span><span class='meta-value'>" + h(personality) + "</span></div>" if personality else ""}
  1230      {"<div class='meta-row'><span class='meta-label'>" + lbl_style + "</span><span class='meta-value'>" + h(speech_style) + "</span></div>" if speech_style else ""}
  1231      {"<div class='meta-row'><span class='meta-label'>" + lbl_lang + "</span><span class='meta-value'>" + h(lang_display) + "</span></div>" if lang_display else ""}
  1232    </div>
  1233    <a class="invite-btn" href="{h(invite_link)}">{lbl_chat}</a>
  1234    <div class="footer">{lbl_footer}</div>
  1235  </div>
  1236  </body>
  1237  </html>"""
  1238      return HTMLResponse(content=html_content)

# --- dualsoul/routers/social.py ---
  1239  """Social router — friends, messages, and the four conversation modes."""
  1240  
  1241  import asyncio
  1242  from datetime import datetime
  1243  
  1244  from fastapi import APIRouter, Depends
  1245  
  1246  from dualsoul.auth import get_current_user
  1247  from dualsoul.connections import manager
  1248  from dualsoul.database import gen_id, get_db
  1249  from dualsoul.models import AddFriendRequest, RespondFriendRequest, SendMessageRequest, TranslateRequest, TwinChatRequest
  1250  from dualsoul.twin_engine.responder import TwinResponder
  1251  
  1252  router = APIRouter(prefix="/api/social", tags=["Social"])
  1253  _twin = TwinResponder()
  1254  
  1255  
  1256  @router.post("/friends/add")
  1257  async def add_friend(req: AddFriendRequest, user=Depends(get_current_user)):
  1258      """Send a friend request by username."""
  1259      uid = user["user_id"]
  1260      username = req.friend_username.strip()
  1261      if not username:
  1262          return {"success": False, "error": "Username required"}
  1263  
  1264      with get_db() as db:
  1265          friend = db.execute(
  1266              "SELECT user_id FROM users WHERE username=? AND user_id!=?",
  1267              (username, uid),
  1268          ).fetchone()
  1269          if not friend:
  1270              return {"success": False, "error": "User not found"}
  1271          fid = friend["user_id"]
  1272  
  1273          exists = db.execute(
  1274              "SELECT conn_id, status FROM social_connections "
  1275              "WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
  1276              (uid, fid, fid, uid),
  1277          ).fetchone()
  1278          if exists:
  1279              return {"success": False, "error": f"Connection already exists ({exists['status']})"}
  1280  
  1281          conn_id = gen_id("sc_")
  1282          db.execute(
  1283              "INSERT INTO social_connections (conn_id, user_id, friend_id, status) "
  1284              "VALUES (?, ?, ?, 'pending')",
  1285              (conn_id, uid, fid),
  1286          )
  1287  
  1288      # Notify the recipient via WebSocket
  1289      await manager.send_to(fid, {
  1290          "type": "friend_request",
  1291          "data": {"conn_id": conn_id, "from_user_id": uid, "username": username},
  1292      })
  1293      return {"success": True, "conn_id": conn_id}
  1294  
  1295  
  1296  @router.post("/friends/respond")
  1297  async def respond_friend(req: RespondFriendRequest, user=Depends(get_current_user)):
  1298      """Accept or block a friend request."""
  1299      uid = user["user_id"]
  1300      if req.action not in ("accept", "block"):
  1301          return {"success": False, "error": "action must be 'accept' or 'block'"}
  1302  
  1303      with get_db() as db:
  1304          conn = db.execute(
  1305              "SELECT conn_id, user_id, friend_id, status FROM social_connections WHERE conn_id=?",
  1306              (req.conn_id,),
  1307          ).fetchone()
  1308          if not conn:
  1309              return {"success": False, "error": "Request not found"}
  1310          if conn["friend_id"] != uid:
  1311              return {"success": False, "error": "Not authorized"}
  1312          if conn["status"] != "pending":
  1313              return {"success": False, "error": f"Already processed ({conn['status']})"}
  1314  
  1315          new_status = "accepted" if req.action == "accept" else "blocked"
  1316          accepted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if req.action == "accept" else None
  1317          db.execute(
  1318              "UPDATE social_connections SET status=?, accepted_at=? WHERE conn_id=?",
  1319              (new_status, accepted_at, req.conn_id),
  1320          )
  1321      return {"success": True, "status": new_status}
  1322  
  1323  
  1324  @router.get("/friends")
  1325  async def list_friends(user=Depends(get_current_user)):
  1326      """List all friends with their dual identity info."""
  1327      uid = user["user_id"]
  1328      with get_db() as db:
  1329          rows = db.execute(
  1330              """
  1331              SELECT sc.conn_id, sc.status, sc.created_at, sc.accepted_at,
  1332                     sc.user_id AS req_from, sc.friend_id AS req_to,
  1333                     u.user_id, u.username, u.display_name, u.avatar,
  1334                     u.current_mode, u.twin_avatar, u.reg_source
  1335              FROM social_connections sc
  1336              JOIN users u ON u.user_id = CASE
  1337                  WHEN sc.user_id=? THEN sc.friend_id
  1338                  ELSE sc.user_id END
  1339              WHERE (sc.user_id=? OR sc.friend_id=?)
  1340                AND sc.status IN ('pending', 'accepted')
  1341              ORDER BY sc.accepted_at DESC, sc.created_at DESC
  1342              """,
  1343              (uid, uid, uid),
  1344          ).fetchall()
  1345  
  1346      friends = []
  1347      for r in rows:
  1348          friends.append({
  1349              "conn_id": r["conn_id"],
  1350              "status": r["status"],
  1351              "is_incoming": r["req_to"] == uid,
  1352              "user_id": r["user_id"],
  1353              "username": r["username"],
  1354              "display_name": r["display_name"] or r["username"],
  1355              "avatar": r["avatar"] or "",
  1356              "twin_avatar": r["twin_avatar"] or "",
  1357              "current_mode": r["current_mode"] or "real",
  1358              "accepted_at": r["accepted_at"] or "",
  1359              "reg_source": r["reg_source"] if "reg_source" in r.keys() else "dualsoul",
  1360          })
  1361      return {"success": True, "friends": friends}
  1362  
  1363  
  1364  @router.get("/messages")
  1365  async def get_messages(friend_id: str = "", limit: int = 50, user=Depends(get_current_user)):
  1366      """Get conversation history with a friend."""
  1367      uid = user["user_id"]
  1368      if not friend_id:
  1369          return {"success": False, "error": "friend_id required"}
  1370  
  1371      with get_db() as db:
  1372          conn = db.execute(
  1373              "SELECT conn_id FROM social_connections "
  1374              "WHERE status='accepted' AND "
  1375              "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
  1376              (uid, friend_id, friend_id, uid),
  1377          ).fetchone()
  1378          if not conn:
  1379              return {"success": False, "error": "Not friends"}
  1380  
  1381          rows = db.execute(
  1382              """
  1383              SELECT msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  1384                     content, original_content, original_lang, target_lang,
  1385                     translation_style, msg_type, is_read, ai_generated, created_at
  1386              FROM social_messages
  1387              WHERE (from_user_id=? AND to_user_id=?)
  1388                 OR (from_user_id=? AND to_user_id=?)
  1389              ORDER BY created_at DESC LIMIT ?
  1390              """,
  1391              (uid, friend_id, friend_id, uid, limit),
  1392          ).fetchall()
  1393  
  1394          # Mark as read
  1395          db.execute(
  1396              "UPDATE social_messages SET is_read=1 "
  1397              "WHERE to_user_id=? AND from_user_id=? AND is_read=0",
  1398              (uid, friend_id),
  1399          )
  1400  
  1401      messages = [dict(r) for r in rows]
  1402      messages.reverse()
  1403      return {"success": True, "messages": messages}
  1404  
  1405  
  1406  @router.post("/messages/send")
  1407  async def send_message(req: SendMessageRequest, user=Depends(get_current_user)):
  1408      """Send a message. If receiver_mode is 'twin', the recipient's twin auto-replies."""
  1409      uid = user["user_id"]
  1410      content = req.content.strip()
  1411      if not content:
  1412          return {"success": False, "error": "Content cannot be empty"}
  1413      if req.sender_mode not in ("real", "twin"):
  1414          return {"success": False, "error": "Invalid sender_mode"}
  1415      if req.receiver_mode not in ("real", "twin"):
  1416          return {"success": False, "error": "Invalid receiver_mode"}
  1417  
  1418      with get_db() as db:
  1419          conn = db.execute(
  1420              "SELECT conn_id FROM social_connections "
  1421              "WHERE status='accepted' AND "
  1422              "((user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?))",
  1423              (uid, req.to_user_id, req.to_user_id, uid),
  1424          ).fetchone()
  1425          if not conn:
  1426              return {"success": False, "error": "Not friends"}
  1427  
  1428          msg_id = gen_id("sm_")
  1429          db.execute(
  1430              """
  1431              INSERT INTO social_messages
  1432              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  1433               content, msg_type, ai_generated)
  1434              VALUES (?, ?, ?, ?, ?, ?, ?, 0)
  1435              """,
  1436              (msg_id, uid, req.to_user_id, req.sender_mode, req.receiver_mode, content, req.msg_type),
  1437          )
  1438  
  1439      result = {"success": True, "msg_id": msg_id, "ai_reply": None}
  1440  
  1441      # Push the new message to the recipient via WebSocket
  1442      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  1443      await manager.send_to(req.to_user_id, {
  1444          "type": "new_message",
  1445          "data": {
  1446              "msg_id": msg_id, "from_user_id": uid, "to_user_id": req.to_user_id,
  1447              "sender_mode": req.sender_mode, "receiver_mode": req.receiver_mode,
  1448              "content": content, "msg_type": req.msg_type,
  1449              "ai_generated": 0, "created_at": now,
  1450          },
  1451      })
  1452  
  1453      # Auto-detect foreign language/dialect and push translation (async, non-blocking)
  1454      if manager.is_online(req.to_user_id):
  1455          asyncio.ensure_future(_auto_detect_and_push_translation(
  1456              recipient_id=req.to_user_id,
  1457              content=content,
  1458              for_msg_id=msg_id,
  1459          ))
  1460  
  1461      # Determine if twin should auto-reply:
  1462      # 1. Explicit: receiver_mode is 'twin' → reply immediately
  1463      # 2. Auto-reply enabled → depends on owner's activity:
  1464      #    a. Owner offline → reply immediately
  1465      #    b. Owner online but idle → wait 30s, check if owner responded, if not → twin replies
  1466      #    c. Owner actively chatting with this friend → twin stays quiet
  1467      twin_auto_enabled = False
  1468      if req.receiver_mode == "twin":
  1469          # Explicit twin mode — reply immediately
  1470          asyncio.ensure_future(_do_twin_reply(
  1471              twin_owner_id=req.to_user_id, from_user_id=uid,
  1472              content=content, sender_mode=req.sender_mode,
  1473              target_lang=req.target_lang, msg_id=msg_id,
  1474          ))
  1475      elif req.receiver_mode == "real":
  1476          with get_db() as db:
  1477              row = db.execute(
  1478                  "SELECT twin_auto_reply FROM users WHERE user_id=?", (req.to_user_id,)
  1479              ).fetchone()
  1480              twin_auto_enabled = bool(row and row["twin_auto_reply"])
  1481  
  1482          if twin_auto_enabled:
  1483              owner_online = manager.is_online(req.to_user_id)
  1484              if not owner_online:
  1485                  # Owner offline → reply immediately
  1486                  asyncio.ensure_future(_do_twin_reply(
  1487                      twin_owner_id=req.to_user_id, from_user_id=uid,
  1488                      content=content, sender_mode=req.sender_mode,
  1489                      target_lang=req.target_lang, msg_id=msg_id,
  1490                  ))
  1491              else:
  1492                  # Owner online — wait 30s then check if they responded
  1493                  asyncio.ensure_future(_delayed_twin_reply(
  1494                      twin_owner_id=req.to_user_id, from_user_id=uid,
  1495                      content=content, sender_mode=req.sender_mode,
  1496                      target_lang=req.target_lang, msg_id=msg_id,
  1497                      delay_seconds=30,
  1498                  ))
  1499  
  1500      return result
  1501  
  1502  
  1503  @router.post("/translate")
  1504  async def translate(req: TranslateRequest, user=Depends(get_current_user)):
  1505      """Personality-preserving translation — translate as if you wrote it in another language.
  1506  
  1507      Unlike generic machine translation, this preserves your humor, tone,
  1508      and characteristic expressions.
  1509      """
  1510      uid = user["user_id"]
  1511      content = req.content.strip()
  1512      target_lang = req.target_lang
  1513      if not content:
  1514          return {"success": False, "error": "Content cannot be empty"}
  1515      if not target_lang:
  1516          return {"success": False, "error": "target_lang required"}
  1517  
  1518      result = await _twin.translate_message(
  1519          owner_id=uid,
  1520          content=content,
  1521          source_lang=req.source_lang,
  1522          target_lang=target_lang,
  1523      )
  1524      if not result:
  1525          return {"success": False, "error": "Translation unavailable (no AI backend)"}
  1526      return {"success": True, "data": result}
  1527  
  1528  
  1529  @router.post("/translate/detect")
  1530  async def detect_translate(req: TranslateRequest, user=Depends(get_current_user)):
  1531      """Auto-detect if a message is in a foreign language or dialect and translate.
  1532  
  1533      Unlike /translate which requires explicit source/target, this automatically
  1534      detects the language and only translates if it differs from the user's
  1535      preferred language. Also handles Chinese dialects.
  1536      """
  1537      uid = user["user_id"]
  1538      content = req.content.strip()
  1539      if not content:
  1540          return {"success": False, "error": "Content cannot be empty"}
  1541  
  1542      result = await _twin.detect_and_translate(
  1543          owner_id=uid,
  1544          content=content,
  1545      )
  1546      if not result:
  1547          return {"success": True, "needs_translation": False}
  1548      return {"success": True, "needs_translation": True, "data": result}
  1549  
  1550  
  1551  @router.post("/twin/chat")
  1552  async def twin_chat(req: TwinChatRequest, user=Depends(get_current_user)):
  1553      """Chat with your own digital twin — the twin knows it IS you."""
  1554      uid = user["user_id"]
  1555  
  1556      # Save the user's message for style learning (sender_mode='real' to self)
  1557      if req.message and req.message.strip():
  1558          user_msg_id = gen_id("sm_")
  1559          with get_db() as db:
  1560              db.execute(
  1561                  """
  1562                  INSERT INTO social_messages
  1563                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  1564                   content, msg_type, ai_generated)
  1565                  VALUES (?, ?, ?, 'real', 'twin', ?, 'text', 0)
  1566                  """,
  1567                  (user_msg_id, uid, uid, req.message.strip()),
  1568              )
  1569  
  1570      reply = await _twin.twin_self_chat(
  1571          owner_id=uid,
  1572          message=req.message,
  1573          history=req.history,
  1574          image_url=req.image,
  1575      )
  1576      if not reply:
  1577          return {"success": False, "error": "Twin chat unavailable"}
  1578      return {"success": True, "reply": reply}
  1579  
  1580  
  1581  @router.get("/unread")
  1582  async def unread_count(user=Depends(get_current_user)):
  1583      """Get unread message count."""
  1584      uid = user["user_id"]
  1585      with get_db() as db:
  1586          row = db.execute(
  1587              "SELECT COUNT(*) as cnt FROM social_messages WHERE to_user_id=? AND is_read=0",
  1588              (uid,),
  1589          ).fetchone()
  1590      return {"count": row["cnt"] if row else 0}
  1591  
  1592  
  1593  @router.get("/unread/by-friend")
  1594  async def unread_by_friend(user=Depends(get_current_user)):
  1595      """Get unread message count grouped by sender."""
  1596      uid = user["user_id"]
  1597      with get_db() as db:
  1598          rows = db.execute(
  1599              """
  1600              SELECT from_user_id, COUNT(*) as cnt
  1601              FROM social_messages
  1602              WHERE to_user_id=? AND is_read=0
  1603              GROUP BY from_user_id
  1604              """,
  1605              (uid,),
  1606          ).fetchall()
  1607      result = {}
  1608      for r in rows:
  1609          result[r["from_user_id"]] = r["cnt"]
  1610      return {"unread": result}
  1611  
  1612  
  1613  async def _do_twin_reply(
  1614      twin_owner_id: str, from_user_id: str, content: str,
  1615      sender_mode: str, target_lang: str, msg_id: str,
  1616  ):
  1617      """Execute the twin auto-reply: generate response, push to both users, notify owner."""
  1618      try:
  1619          reply = await _twin.generate_reply(
  1620              twin_owner_id=twin_owner_id,
  1621              from_user_id=from_user_id,
  1622              incoming_msg=content,
  1623              sender_mode=sender_mode,
  1624              target_lang=target_lang,
  1625              social_context=(
  1626                  "你是分身，主人现在不在线或在忙。你不能替主人做任何决定！"
  1627                  "不能替主人定时间、定地点、答应事情。"
  1628                  "你只能说：我帮你问问主人/我跟主人说一声/等主人回来定。"
  1629                  "语气轻松自然，像朋友聊天。"
  1630              ),
  1631          )
  1632          if reply:
  1633              now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  1634              twin_msg = {
  1635                  "type": "new_message",
  1636                  "data": {
  1637                      "msg_id": reply["msg_id"], "from_user_id": twin_owner_id,
  1638                      "to_user_id": from_user_id, "sender_mode": "twin",
  1639                      "receiver_mode": sender_mode,
  1640                      "content": reply["content"], "msg_type": "text",
  1641                      "ai_generated": 1, "created_at": now,
  1642                  },
  1643              }
  1644              await manager.send_to(from_user_id, twin_msg)
  1645              await manager.send_to(twin_owner_id, twin_msg)
  1646  
  1647              # Notify the owner
  1648              await _notify_owner_twin_replied(
  1649                  owner_id=twin_owner_id,
  1650                  friend_id=from_user_id,
  1651                  friend_msg=content,
  1652                  twin_reply=reply["content"],
  1653              )
  1654      except Exception as e:
  1655          import logging
  1656          logging.getLogger(__name__).warning(f"Twin auto-reply failed: {e}")
  1657  
  1658  
  1659  async def _delayed_twin_reply(
  1660      twin_owner_id: str, from_user_id: str, content: str,
  1661      sender_mode: str, target_lang: str, msg_id: str,
  1662      delay_seconds: int = 30,
  1663  ):
  1664      """Wait, then check if owner responded. If not, twin steps in."""
  1665      await asyncio.sleep(delay_seconds)
  1666  
  1667      # Check if the owner replied to this friend in the meantime
  1668      with get_db() as db:
  1669          recent = db.execute(
  1670              """
  1671              SELECT COUNT(*) AS cnt FROM social_messages
  1672              WHERE from_user_id=? AND to_user_id=? AND sender_mode='real'
  1673                  AND ai_generated=0
  1674                  AND created_at > datetime('now', 'localtime', '-{delay} seconds')
  1675              """.replace("{delay}", str(delay_seconds + 5)),
  1676              (twin_owner_id, from_user_id),
  1677          ).fetchone()
  1678  
  1679      if recent and recent["cnt"] > 0:
  1680          # Owner responded — twin stays quiet
  1681          return
  1682  
  1683      # Owner didn't respond — twin steps in
  1684      await _do_twin_reply(
  1685          twin_owner_id=twin_owner_id, from_user_id=from_user_id,
  1686          content=content, sender_mode=sender_mode,
  1687          target_lang=target_lang, msg_id=msg_id,
  1688      )
  1689  
  1690  
  1691  async def _notify_owner_twin_replied(owner_id: str, friend_id: str, friend_msg: str, twin_reply: str):
  1692      """Notify the owner that their twin auto-replied to a friend."""
  1693      try:
  1694          # Get friend's display name
  1695          with get_db() as db:
  1696              friend = db.execute(
  1697                  "SELECT display_name, username FROM users WHERE user_id=?",
  1698                  (friend_id,),
  1699              ).fetchone()
  1700          friend_name = (friend["display_name"] or friend["username"]) if friend else "好友"
  1701  
  1702          notify_text = (
  1703              f"刚才{friend_name}找你，说：「{friend_msg[:50]}」\n"
  1704              f"我替你回了：「{twin_reply[:50]}」\n"
  1705              f"具体事情得你来定哦～"
  1706          )
  1707  
  1708          # Save notification as a twin self-chat message
  1709          msg_id = gen_id("sm_")
  1710          with get_db() as db:
  1711              db.execute(
  1712                  """
  1713                  INSERT INTO social_messages
  1714                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  1715                   content, msg_type, ai_generated)
  1716                  VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1)
  1717                  """,
  1718                  (msg_id, owner_id, owner_id, notify_text),
  1719              )
  1720  
  1721          # Push via WebSocket
  1722          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  1723          await manager.send_to(owner_id, {
  1724              "type": "twin_notification",
  1725              "data": {
  1726                  "msg_id": msg_id,
  1727                  "content": notify_text,
  1728                  "friend_id": friend_id,
  1729                  "friend_name": friend_name,
  1730                  "created_at": now,
  1731              },
  1732          })
  1733      except Exception:
  1734          pass  # Notification is best-effort
  1735  
  1736  
  1737  async def _auto_detect_and_push_translation(recipient_id: str, content: str, for_msg_id: str):
  1738      """Background task: detect foreign language/dialect and push translation via WebSocket."""
  1739      try:
  1740          result = await _twin.detect_and_translate(
  1741              owner_id=recipient_id,
  1742              content=content,
  1743          )
  1744          if result:
  1745              await manager.send_to(recipient_id, {
  1746                  "type": "auto_translation",
  1747                  "data": {
  1748                      "for_msg_id": for_msg_id,
  1749                      "detected_lang": result["detected_lang"],
  1750                      "translated_content": result["translated_content"],
  1751                  },
  1752              })
  1753      except Exception:
  1754          pass  # Auto-detection is best-effort

# --- dualsoul/routers/twin_import.py ---
  1755  """Twin Import router — import twin data from any cultivation platform (年轮, OpenClaw, etc.)."""
  1756  
  1757  from fastapi import APIRouter, Depends
  1758  
  1759  from dualsoul.auth import get_current_user
  1760  from dualsoul.database import gen_id, get_db
  1761  from dualsoul.models import TwinImportRequest, TwinSyncRequest
  1762  
  1763  router = APIRouter(prefix="/api/twin", tags=["Twin Import"])
  1764  
  1765  
  1766  @router.post("/import")
  1767  async def import_twin(req: TwinImportRequest, user=Depends(get_current_user)):
  1768      """Import a full twin data package from any cultivation platform.
  1769  
  1770      Accepts Twin Portable Format v1.0 payload from Nianlun (年轮), OpenClaw,
  1771      or any platform that implements the TPF standard. Stores core personality
  1772      data in hot columns and full payload in cold storage.
  1773      """
  1774      uid = user["user_id"]
  1775      data = req.data
  1776      source = req.source or "nianlun"
  1777  
  1778      if not data:
  1779          return {"success": False, "error": "Empty data payload"}
  1780  
  1781      with get_db() as db:
  1782          # Deactivate existing profiles
  1783          db.execute(
  1784              "UPDATE twin_profiles SET is_active=0 WHERE user_id=?", (uid,)
  1785          )
  1786  
  1787          # Determine next version
  1788          row = db.execute(
  1789              "SELECT MAX(version) as mv FROM twin_profiles WHERE user_id=?",
  1790              (uid,),
  1791          ).fetchone()
  1792          next_version = (row["mv"] or 0) + 1 if row else 1
  1793  
  1794          # Extract core fields
  1795          twin = data.get("twin", {})
  1796          cert = data.get("certificate", {})
  1797          skeleton = data.get("skeleton", {})
  1798          dims = skeleton.get("dimension_profiles", {})
  1799  
  1800          import json
  1801  
  1802          profile_id = gen_id("tp_")
  1803          db.execute(
  1804              """
  1805              INSERT INTO twin_profiles
  1806              (profile_id, user_id, source, version, is_active,
  1807               twin_name, training_status, quality_score, self_awareness, interaction_count,
  1808               dim_judgement, dim_cognition, dim_expression, dim_relation, dim_sovereignty,
  1809               value_order, behavior_patterns, speech_style, boundaries,
  1810               certificate, raw_import)
  1811              VALUES (?, ?, ?, ?, 1,
  1812                      ?, ?, ?, ?, ?,
  1813                      ?, ?, ?, ?, ?,
  1814                      ?, ?, ?, ?,
  1815                      ?, ?)
  1816              """,
  1817              (
  1818                  profile_id, uid, source, next_version,
  1819                  twin.get("twin_name", cert.get("twin_name", "")),
  1820                  twin.get("training_status", ""),
  1821                  twin.get("quality_score", 0.0),
  1822                  twin.get("self_awareness", 0.0),
  1823                  twin.get("interaction_count", 0),
  1824                  json.dumps(dims.get("judgement", {}), ensure_ascii=False),
  1825                  json.dumps(dims.get("cognition", {}), ensure_ascii=False),
  1826                  json.dumps(dims.get("expression", {}), ensure_ascii=False),
  1827                  json.dumps(dims.get("relation", {}), ensure_ascii=False),
  1828                  json.dumps(dims.get("sovereignty", {}), ensure_ascii=False),
  1829                  json.dumps(skeleton.get("value_order", []), ensure_ascii=False),
  1830                  json.dumps(skeleton.get("behavior_patterns", []), ensure_ascii=False),
  1831                  json.dumps(twin.get("speech_style", {}), ensure_ascii=False),
  1832                  json.dumps(twin.get("boundaries", {}), ensure_ascii=False),
  1833                  json.dumps(cert, ensure_ascii=False),
  1834                  json.dumps(data, ensure_ascii=False),
  1835              ),
  1836          )
  1837  
  1838          # Import memories
  1839          memories = data.get("memories", [])
  1840          for mem in memories:
  1841              mem_id = gen_id("tm_")
  1842              db.execute(
  1843                  """
  1844                  INSERT INTO twin_memories
  1845                  (memory_id, user_id, memory_type, period_start, period_end,
  1846                   summary_text, emotional_tone, themes, key_events, growth_signals)
  1847                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  1848                  """,
  1849                  (
  1850                      mem_id, uid,
  1851                      mem.get("memory_type", "weekly"),
  1852                      mem.get("period_start", ""),
  1853                      mem.get("period_end", ""),
  1854                      mem.get("summary_text", ""),
  1855                      mem.get("emotional_tone", ""),
  1856                      json.dumps(mem.get("themes", []), ensure_ascii=False),
  1857                      json.dumps(mem.get("key_events", []), ensure_ascii=False),
  1858                      json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
  1859                  ),
  1860              )
  1861  
  1862          # Import entities
  1863          entities = data.get("entities", [])
  1864          for ent in entities:
  1865              ent_id = gen_id("te_")
  1866              db.execute(
  1867                  """
  1868                  INSERT INTO twin_entities
  1869                  (entity_id, user_id, entity_name, entity_type,
  1870                   importance_score, mention_count, context, relations)
  1871                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  1872                  """,
  1873                  (
  1874                      ent_id, uid,
  1875                      ent.get("entity_name", ""),
  1876                      ent.get("entity_type", "thing"),
  1877                      ent.get("importance_score", 0.0),
  1878                      ent.get("mention_count", 0),
  1879                      json.dumps(ent.get("context", ""), ensure_ascii=False),
  1880                      json.dumps(ent.get("relations", []), ensure_ascii=False),
  1881                  ),
  1882              )
  1883  
  1884          # Update user's twin_source + backward-compatible fields
  1885          personality_text = twin.get("personality", "")
  1886          if isinstance(personality_text, dict):
  1887              personality_text = personality_text.get("description", str(personality_text))
  1888          style_text = twin.get("speech_style", "")
  1889          if isinstance(style_text, dict):
  1890              style_text = style_text.get("description", str(style_text))
  1891  
  1892          db.execute(
  1893              "UPDATE users SET twin_source=?, "
  1894              "twin_personality=CASE WHEN ?!='' THEN ? ELSE twin_personality END, "
  1895              "twin_speech_style=CASE WHEN ?!='' THEN ? ELSE twin_speech_style END "
  1896              "WHERE user_id=?",
  1897              (source, personality_text, personality_text, style_text, style_text, uid),
  1898          )
  1899  
  1900      return {
  1901          "success": True,
  1902          "profile_id": profile_id,
  1903          "version": next_version,
  1904          "imported": {
  1905              "memories": len(memories),
  1906              "entities": len(entities),
  1907          },
  1908      }
  1909  
  1910  
  1911  @router.post("/sync")
  1912  async def sync_twin(req: TwinSyncRequest, user=Depends(get_current_user)):
  1913      """Incremental sync — merge new data from Nianlun since last sync.
  1914  
  1915      Only imports new memories and entities; updates the active profile's
  1916      dimension scores if provided.
  1917      """
  1918      uid = user["user_id"]
  1919      data = req.data
  1920  
  1921      if not data:
  1922          return {"success": False, "error": "Empty sync data"}
  1923  
  1924      import json
  1925      counts = {"memories": 0, "entities": 0, "profile_updated": False}
  1926  
  1927      with get_db() as db:
  1928          # Update active profile dimensions if provided
  1929          skeleton = data.get("skeleton", {})
  1930          dims = skeleton.get("dimension_profiles", {})
  1931          if dims:
  1932              updates = []
  1933              params = []
  1934              for dim_key in ("judgement", "cognition", "expression", "relation", "sovereignty"):
  1935                  if dim_key in dims:
  1936                      col = f"dim_{dim_key}"
  1937                      updates.append(f"{col}=?")
  1938                      params.append(json.dumps(dims[dim_key], ensure_ascii=False))
  1939  
  1940              if skeleton.get("value_order"):
  1941                  updates.append("value_order=?")
  1942                  params.append(json.dumps(skeleton["value_order"], ensure_ascii=False))
  1943              if skeleton.get("behavior_patterns"):
  1944                  updates.append("behavior_patterns=?")
  1945                  params.append(json.dumps(skeleton["behavior_patterns"], ensure_ascii=False))
  1946  
  1947              if updates:
  1948                  updates.append("updated_at=datetime('now','localtime')")
  1949                  params.append(uid)
  1950                  db.execute(
  1951                      f"UPDATE twin_profiles SET {','.join(updates)} "
  1952                      "WHERE user_id=? AND is_active=1",
  1953                      params,
  1954                  )
  1955                  counts["profile_updated"] = True
  1956  
  1957          # Insert new memories
  1958          for mem in data.get("memories", []):
  1959              mem_id = gen_id("tm_")
  1960              db.execute(
  1961                  """
  1962                  INSERT INTO twin_memories
  1963                  (memory_id, user_id, memory_type, period_start, period_end,
  1964                   summary_text, emotional_tone, themes, key_events, growth_signals)
  1965                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  1966                  """,
  1967                  (
  1968                      mem_id, uid,
  1969                      mem.get("memory_type", "weekly"),
  1970                      mem.get("period_start", ""),
  1971                      mem.get("period_end", ""),
  1972                      mem.get("summary_text", ""),
  1973                      mem.get("emotional_tone", ""),
  1974                      json.dumps(mem.get("themes", []), ensure_ascii=False),
  1975                      json.dumps(mem.get("key_events", []), ensure_ascii=False),
  1976                      json.dumps(mem.get("growth_signals", []), ensure_ascii=False),
  1977                  ),
  1978              )
  1979              counts["memories"] += 1
  1980  
  1981          # Insert new entities (upsert by name)
  1982          for ent in data.get("entities", []):
  1983              existing = db.execute(
  1984                  "SELECT entity_id FROM twin_entities WHERE user_id=? AND entity_name=?",
  1985                  (uid, ent.get("entity_name", "")),
  1986              ).fetchone()
  1987              if existing:
  1988                  db.execute(
  1989                      "UPDATE twin_entities SET importance_score=?, mention_count=?, "
  1990                      "context=?, relations=? WHERE entity_id=?",
  1991                      (
  1992                          ent.get("importance_score", 0.0),
  1993                          ent.get("mention_count", 0),
  1994                          json.dumps(ent.get("context", ""), ensure_ascii=False),
  1995                          json.dumps(ent.get("relations", []), ensure_ascii=False),
  1996                          existing["entity_id"],
  1997                      ),
  1998                  )
  1999              else:
  2000                  ent_id = gen_id("te_")
  2001                  db.execute(
  2002                      """
  2003                      INSERT INTO twin_entities
  2004                      (entity_id, user_id, entity_name, entity_type,
  2005                       importance_score, mention_count, context, relations)
  2006                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  2007                      """,
  2008                      (
  2009                          ent_id, uid,
  2010                          ent.get("entity_name", ""),
  2011                          ent.get("entity_type", "thing"),
  2012                          ent.get("importance_score", 0.0),
  2013                          ent.get("mention_count", 0),
  2014                          json.dumps(ent.get("context", ""), ensure_ascii=False),
  2015                          json.dumps(ent.get("relations", []), ensure_ascii=False),
  2016                      ),
  2017                  )
  2018              counts["entities"] += 1
  2019  
  2020      return {"success": True, "synced": counts}
  2021  
  2022  
  2023  @router.get("/status")
  2024  async def twin_status(user=Depends(get_current_user)):
  2025      """Check the current twin import status — source, version, stats."""
  2026      uid = user["user_id"]
  2027  
  2028      with get_db() as db:
  2029          user_row = db.execute(
  2030              "SELECT twin_source FROM users WHERE user_id=?", (uid,)
  2031          ).fetchone()
  2032  
  2033          result = {
  2034              "twin_source": user_row["twin_source"] if user_row else "local",
  2035              "nianlun_profile": None,
  2036          }
  2037  
  2038          if result["twin_source"] == "nianlun":
  2039              tp = db.execute(
  2040                  "SELECT profile_id, version, twin_name, quality_score, "
  2041                  "training_status, interaction_count, imported_at, updated_at "
  2042                  "FROM twin_profiles WHERE user_id=? AND is_active=1 "
  2043                  "ORDER BY version DESC LIMIT 1",
  2044                  (uid,),
  2045              ).fetchone()
  2046              if tp:
  2047                  mem_count = db.execute(
  2048                      "SELECT COUNT(*) as cnt FROM twin_memories WHERE user_id=?",
  2049                      (uid,),
  2050                  ).fetchone()
  2051                  ent_count = db.execute(
  2052                      "SELECT COUNT(*) as cnt FROM twin_entities WHERE user_id=?",
  2053                      (uid,),
  2054                  ).fetchone()
  2055                  result["nianlun_profile"] = {
  2056                      "profile_id": tp["profile_id"],
  2057                      "version": tp["version"],
  2058                      "twin_name": tp["twin_name"],
  2059                      "quality_score": tp["quality_score"],
  2060                      "training_status": tp["training_status"],
  2061                      "interaction_count": tp["interaction_count"],
  2062                      "memories_count": mem_count["cnt"] if mem_count else 0,
  2063                      "entities_count": ent_count["cnt"] if ent_count else 0,
  2064                      "imported_at": tp["imported_at"],
  2065                      "updated_at": tp["updated_at"],
  2066                  }
  2067  
  2068      return {"success": True, **result}

# --- dualsoul/routers/ws.py ---
  2069  """WebSocket router — real-time message push."""
  2070  
  2071  import logging
  2072  
  2073  from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
  2074  
  2075  from dualsoul.auth import verify_token
  2076  from dualsoul.connections import manager
  2077  
  2078  logger = logging.getLogger(__name__)
  2079  
  2080  router = APIRouter(tags=["WebSocket"])
  2081  
  2082  
  2083  @router.websocket("/ws")
  2084  async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
  2085      """WebSocket endpoint for real-time push.
  2086  
  2087      Connect with: ws://host/ws?token=JWT_TOKEN
  2088      Receives JSON events:
  2089        {"type": "new_message", "data": {...}}
  2090        {"type": "friend_request", "data": {...}}
  2091        {"type": "twin_reply", "data": {...}}
  2092      """
  2093      if not token:
  2094          await websocket.close(code=4001, reason="Token required")
  2095          return
  2096  
  2097      try:
  2098          user = verify_token(token)
  2099      except Exception:
  2100          await websocket.close(code=4001, reason="Invalid token")
  2101          return
  2102  
  2103      user_id = user["user_id"]
  2104      await manager.connect(user_id, websocket)
  2105  
  2106      try:
  2107          while True:
  2108              # Keep connection alive; handle client pings
  2109              data = await websocket.receive_text()
  2110              manager.touch(user_id)
  2111              # Client can send "ping" to keep alive
  2112              if data == "ping":
  2113                  await websocket.send_text("pong")
  2114      except WebSocketDisconnect:
  2115          manager.disconnect(user_id)
  2116      except Exception:
  2117          manager.disconnect(user_id)

# --- dualsoul/twin_engine/avatar.py ---
  2118  """AI avatar generation — transform a real photo into a stylized digital twin avatar.
  2119  
  2120  Uses Alibaba DashScope's portrait style repaint API (wanx-style-repaint-v1),
  2121  which is on the same platform as our Qwen chat model.
  2122  """
  2123  
  2124  import base64
  2125  import logging
  2126  import time
  2127  
  2128  import httpx
  2129  
  2130  from dualsoul.config import AI_API_KEY
  2131  
  2132  logger = logging.getLogger(__name__)
  2133  
  2134  # DashScope API endpoint (same API key as Qwen)
  2135  DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
  2136  
  2137  # Style presets for twin avatars
  2138  # See: https://help.aliyun.com/zh/model-studio/style-repaint
  2139  TWIN_STYLES = {
  2140      "anime": {"index": 2, "name_zh": "动漫", "name_en": "Anime"},
  2141      "3d": {"index": 35, "name_zh": "3D立体", "name_en": "3D"},
  2142      "cyber": {"index": 4, "name_zh": "未来科技", "name_en": "Futuristic"},
  2143      "clay": {"index": 31, "name_zh": "黏土世界", "name_en": "Clay"},
  2144      "pixel": {"index": 32, "name_zh": "像素世界", "name_en": "Pixel"},
  2145      "ink": {"index": 5, "name_zh": "水墨", "name_en": "Ink Painting"},
  2146      "retro": {"index": 0, "name_zh": "复古漫画", "name_en": "Retro Comic"},
  2147  }
  2148  
  2149  DEFAULT_STYLE = "anime"
  2150  
  2151  
  2152  async def generate_twin_avatar(
  2153      image_url: str,
  2154      style: str = DEFAULT_STYLE,
  2155  ) -> dict | None:
  2156      """Generate a stylized twin avatar from a real photo.
  2157  
  2158      Args:
  2159          image_url: URL of the source image (must be publicly accessible)
  2160          style: Style key from TWIN_STYLES
  2161  
  2162      Returns:
  2163          Dict with 'url' (generated image URL) and 'style', or None on failure.
  2164      """
  2165      if not AI_API_KEY:
  2166          logger.warning("No AI_API_KEY configured, cannot generate avatar")
  2167          return None
  2168  
  2169      style_info = TWIN_STYLES.get(style, TWIN_STYLES[DEFAULT_STYLE])
  2170      style_index = style_info["index"]
  2171  
  2172      # Submit the async task
  2173      try:
  2174          async with httpx.AsyncClient(timeout=30) as client:
  2175              resp = await client.post(
  2176                  DASHSCOPE_URL,
  2177                  headers={
  2178                      "Authorization": f"Bearer {AI_API_KEY}",
  2179                      "Content-Type": "application/json",
  2180                      "X-DashScope-Async": "enable",
  2181                  },
  2182                  json={
  2183                      "model": "wanx-style-repaint-v1",
  2184                      "input": {
  2185                          "image_url": image_url,
  2186                          "style_index": style_index,
  2187                      },
  2188                  },
  2189              )
  2190              data = resp.json()
  2191      except Exception as e:
  2192          logger.warning(f"Avatar generation submit failed: {e}")
  2193          return None
  2194  
  2195      # Get task ID for polling
  2196      task_id = data.get("output", {}).get("task_id")
  2197      if not task_id:
  2198          logger.warning(f"No task_id in response: {data}")
  2199          return None
  2200  
  2201      # Poll for result (max 60 seconds)
  2202      task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
  2203      for _ in range(30):
  2204          await _async_sleep(2)
  2205          try:
  2206              async with httpx.AsyncClient(timeout=15) as client:
  2207                  resp = await client.get(
  2208                      task_url,
  2209                      headers={"Authorization": f"Bearer {AI_API_KEY}"},
  2210                  )
  2211                  result = resp.json()
  2212          except Exception as e:
  2213              logger.warning(f"Avatar generation poll failed: {e}")
  2214              continue
  2215  
  2216          status = result.get("output", {}).get("task_status")
  2217          if status == "SUCCEEDED":
  2218              results = result.get("output", {}).get("results", [])
  2219              if results and results[0].get("url"):
  2220                  return {
  2221                      "url": results[0]["url"],
  2222                      "style": style,
  2223                      "style_name": style_info,
  2224                  }
  2225              logger.warning(f"No image URL in result: {result}")
  2226              return None
  2227          elif status == "FAILED":
  2228              logger.warning(f"Avatar generation failed: {result}")
  2229              return None
  2230          # PENDING or RUNNING — continue polling
  2231  
  2232      logger.warning("Avatar generation timed out")
  2233      return None
  2234  
  2235  
  2236  async def generate_twin_avatar_from_base64(
  2237      image_base64: str,
  2238      style: str = DEFAULT_STYLE,
  2239      save_path: str | None = None,
  2240  ) -> dict | None:
  2241      """Generate twin avatar from a base64-encoded image.
  2242  
  2243      Since DashScope needs a URL, we first need to upload the image.
  2244      As a workaround, we save it temporarily and use the server's URL.
  2245  
  2246      Args:
  2247          image_base64: Base64-encoded image data (with or without data URI prefix)
  2248          style: Style key from TWIN_STYLES
  2249          save_path: Optional path to save the source image temporarily
  2250  
  2251      Returns:
  2252          Dict with 'image_base64' of the generated avatar, or None on failure.
  2253      """
  2254      if not AI_API_KEY:
  2255          return None
  2256  
  2257      # Strip data URI prefix
  2258      img_data = image_base64
  2259      if "," in img_data:
  2260          img_data = img_data.split(",", 1)[1]
  2261  
  2262      style_info = TWIN_STYLES.get(style, TWIN_STYLES[DEFAULT_STYLE])
  2263      style_index = style_info["index"]
  2264  
  2265      # Use DashScope with base64 input directly
  2266      try:
  2267          async with httpx.AsyncClient(timeout=30) as client:
  2268              resp = await client.post(
  2269                  DASHSCOPE_URL,
  2270                  headers={
  2271                      "Authorization": f"Bearer {AI_API_KEY}",
  2272                      "Content-Type": "application/json",
  2273                      "X-DashScope-Async": "enable",
  2274                  },
  2275                  json={
  2276                      "model": "wanx-style-repaint-v1",
  2277                      "input": {
  2278                          "image_url": f"data:image/png;base64,{img_data}",
  2279                          "style_index": style_index,
  2280                      },
  2281                  },
  2282              )
  2283              data = resp.json()
  2284      except Exception as e:
  2285          logger.warning(f"Avatar generation submit failed: {e}")
  2286          return None
  2287  
  2288      task_id = data.get("output", {}).get("task_id")
  2289      if not task_id:
  2290          # Maybe the API doesn't support base64 directly — log the error
  2291          logger.warning(f"No task_id in response: {data}")
  2292          return None
  2293  
  2294      # Poll for result
  2295      task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
  2296      for _ in range(30):
  2297          await _async_sleep(2)
  2298          try:
  2299              async with httpx.AsyncClient(timeout=15) as client:
  2300                  resp = await client.get(
  2301                      task_url,
  2302                      headers={"Authorization": f"Bearer {AI_API_KEY}"},
  2303                  )
  2304                  result = resp.json()
  2305          except Exception as e:
  2306              logger.warning(f"Avatar generation poll failed: {e}")
  2307              continue
  2308  
  2309          status = result.get("output", {}).get("task_status")
  2310          if status == "SUCCEEDED":
  2311              results = result.get("output", {}).get("results", [])
  2312              if results and results[0].get("url"):
  2313                  # Download the generated image and return as base64
  2314                  try:
  2315                      async with httpx.AsyncClient(timeout=30) as dl_client:
  2316                          img_resp = await dl_client.get(results[0]["url"])
  2317                          if img_resp.status_code == 200:
  2318                              generated_b64 = base64.b64encode(img_resp.content).decode()
  2319                              return {
  2320                                  "image_base64": generated_b64,
  2321                                  "style": style,
  2322                                  "source_url": results[0]["url"],
  2323                              }
  2324                  except Exception as e:
  2325                      logger.warning(f"Failed to download generated avatar: {e}")
  2326              return None
  2327          elif status == "FAILED":
  2328              logger.warning(f"Avatar generation failed: {result}")
  2329              return None
  2330  
  2331      logger.warning("Avatar generation timed out")
  2332      return None
  2333  
  2334  
  2335  def get_available_styles() -> list[dict]:
  2336      """Return list of available twin avatar styles for the frontend."""
  2337      return [
  2338          {"key": k, "name_zh": v["name_zh"], "name_en": v["name_en"]}
  2339          for k, v in TWIN_STYLES.items()
  2340      ]
  2341  
  2342  
  2343  async def _async_sleep(seconds: float):
  2344      """Async sleep without blocking."""
  2345      import asyncio
  2346      await asyncio.sleep(seconds)

# --- dualsoul/twin_engine/learner.py ---
  2347  """Style learner — analyze a user's real messages to extract personality and speech patterns.
  2348  
  2349  Reads the user's human-sent messages (ai_generated=0, sender_mode='real'),
  2350  sends samples to AI for analysis, and updates the twin's personality/speech_style
  2351  to better match how the user actually communicates.
  2352  """
  2353  
  2354  import logging
  2355  
  2356  import httpx
  2357  
  2358  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
  2359  from dualsoul.database import get_db
  2360  
  2361  logger = logging.getLogger(__name__)
  2362  
  2363  # Minimum messages needed before learning is meaningful
  2364  MIN_MESSAGES_FOR_LEARNING = 5
  2365  # How many recent messages to analyze
  2366  SAMPLE_SIZE = 80
  2367  
  2368  
  2369  def get_user_messages(user_id: str, limit: int = SAMPLE_SIZE) -> list[str]:
  2370      """Fetch a user's real (human-written) messages for style analysis."""
  2371      with get_db() as db:
  2372          rows = db.execute(
  2373              """
  2374              SELECT content FROM social_messages
  2375              WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
  2376                  AND msg_type='text' AND content != ''
  2377              ORDER BY created_at DESC LIMIT ?
  2378              """,
  2379              (user_id, limit),
  2380          ).fetchall()
  2381      return [r["content"] for r in rows]
  2382  
  2383  
  2384  def get_message_count(user_id: str) -> int:
  2385      """Count how many real messages a user has sent."""
  2386      with get_db() as db:
  2387          row = db.execute(
  2388              """
  2389              SELECT COUNT(*) as cnt FROM social_messages
  2390              WHERE from_user_id=? AND sender_mode='real' AND ai_generated=0
  2391                  AND msg_type='text'
  2392              """,
  2393              (user_id,),
  2394          ).fetchone()
  2395      return row["cnt"] if row else 0
  2396  
  2397  
  2398  async def analyze_style(user_id: str) -> dict | None:
  2399      """Analyze a user's messages and extract personality + speech style.
  2400  
  2401      Returns:
  2402          Dict with 'personality' and 'speech_style' strings, or None if
  2403          not enough data or AI unavailable.
  2404      """
  2405      if not AI_BASE_URL or not AI_API_KEY:
  2406          return None
  2407  
  2408      msg_count = get_message_count(user_id)
  2409      if msg_count < MIN_MESSAGES_FOR_LEARNING:
  2410          return {
  2411              "error": "not_enough_messages",
  2412              "current": msg_count,
  2413              "required": MIN_MESSAGES_FOR_LEARNING,
  2414          }
  2415  
  2416      messages = get_user_messages(user_id)
  2417      if not messages:
  2418          return None
  2419  
  2420      # Get current profile for context
  2421      with get_db() as db:
  2422          row = db.execute(
  2423              "SELECT display_name, twin_personality, twin_speech_style, preferred_lang "
  2424              "FROM users WHERE user_id=?",
  2425              (user_id,),
  2426          ).fetchone()
  2427      if not row:
  2428          return None
  2429  
  2430      name = row["display_name"] or "用户"
  2431      current_personality = row["twin_personality"] or ""
  2432      current_style = row["twin_speech_style"] or ""
  2433      lang = row["preferred_lang"] or "zh"
  2434  
  2435      # Build message samples (numbered for clarity)
  2436      samples = []
  2437      for i, msg in enumerate(messages[:SAMPLE_SIZE], 1):
  2438          samples.append(f"{i}. {msg}")
  2439      samples_text = "\n".join(samples)
  2440  
  2441      # Context about current settings
  2442      current_block = ""
  2443      if current_personality or current_style:
  2444          current_block = (
  2445              f"\n当前分身性格设定: {current_personality}"
  2446              f"\n当前分身说话风格: {current_style}"
  2447              f"\n请在当前设定基础上，根据实际聊天记录进行修正和丰富。\n"
  2448          )
  2449  
  2450      # Use Chinese prompt if user's language is Chinese
  2451      if lang == "zh":
  2452          prompt = (
  2453              f"你是一个语言风格分析专家。下面是{name}最近发送的{len(messages)}条真实聊天消息。\n"
  2454              f"请仔细分析这些消息，提炼出两个方面：\n\n"
  2455              f"1. **性格特征**（personality）：从消息内容推断此人的性格特点，"
  2456              f"如：乐观/严谨/幽默/直率/温柔/理性等，用自然的短句描述，不超过50字。\n\n"
  2457              f"2. **说话风格**（speech_style）：分析此人的语言习惯，包括：\n"
  2458              f"   - 句子长短偏好（简短还是长句）\n"
  2459              f"   - 是否用emoji/表情\n"
  2460              f"   - 口头禅或常用词\n"
  2461              f"   - 语气特点（正式/随意/调侃等）\n"
  2462              f"   - 标点符号习惯\n"
  2463              f"   用自然的短句描述，不超过80字。\n\n"
  2464              f"{current_block}"
  2465              f"聊天记录：\n{samples_text}\n\n"
  2466              f"请严格按以下JSON格式输出，不要输出其他内容：\n"
  2467              f'{{"personality": "...", "speech_style": "..."}}'
  2468          )
  2469      else:
  2470          prompt = (
  2471              f"You are a linguistic style analyst. Below are {len(messages)} real chat messages "
  2472              f"sent by {name}.\n"
  2473              f"Analyze these messages and extract two aspects:\n\n"
  2474              f"1. **personality**: Infer personality traits from the messages "
  2475              f"(e.g., optimistic, rigorous, humorous, direct, warm, rational). "
  2476              f"Describe in natural short phrases, max 50 words.\n\n"
  2477              f"2. **speech_style**: Analyze language habits including:\n"
  2478              f"   - Sentence length preference\n"
  2479              f"   - Emoji usage\n"
  2480              f"   - Catchphrases or frequent expressions\n"
  2481              f"   - Tone (formal/casual/playful)\n"
  2482              f"   - Punctuation habits\n"
  2483              f"   Describe in natural short phrases, max 80 words.\n\n"
  2484              f"{current_block}"
  2485              f"Chat messages:\n{samples_text}\n\n"
  2486              f"Output STRICTLY in this JSON format, nothing else:\n"
  2487              f'{{"personality": "...", "speech_style": "..."}}'
  2488          )
  2489  
  2490      try:
  2491          async with httpx.AsyncClient(timeout=30) as client:
  2492              resp = await client.post(
  2493                  f"{AI_BASE_URL}/chat/completions",
  2494                  headers={
  2495                      "Authorization": f"Bearer {AI_API_KEY}",
  2496                      "Content-Type": "application/json",
  2497                  },
  2498                  json={
  2499                      "model": AI_MODEL,
  2500                      "max_tokens": 300,
  2501                      "temperature": 0.3,
  2502                      "messages": [{"role": "user", "content": prompt}],
  2503                  },
  2504              )
  2505              raw = resp.json()["choices"][0]["message"]["content"].strip()
  2506      except Exception as e:
  2507          logger.warning(f"Style analysis failed: {e}")
  2508          return None
  2509  
  2510      # Parse JSON response
  2511      import json
  2512  
  2513      # Try to extract JSON from response (AI might wrap in markdown code blocks)
  2514      json_str = raw
  2515      if "```" in raw:
  2516          lines = raw.split("\n")
  2517          json_lines = []
  2518          in_block = False
  2519          for line in lines:
  2520              if line.strip().startswith("```"):
  2521                  in_block = not in_block
  2522                  continue
  2523              if in_block:
  2524                  json_lines.append(line)
  2525          json_str = "\n".join(json_lines)
  2526  
  2527      try:
  2528          result = json.loads(json_str)
  2529          personality = result.get("personality", "").strip()
  2530          speech_style = result.get("speech_style", "").strip()
  2531          if not personality or not speech_style:
  2532              logger.warning(f"Incomplete style analysis result: {raw}")
  2533              return None
  2534          return {
  2535              "personality": personality,
  2536              "speech_style": speech_style,
  2537              "message_count": msg_count,
  2538              "samples_analyzed": len(messages),
  2539          }
  2540      except json.JSONDecodeError:
  2541          logger.warning(f"Failed to parse style analysis JSON: {raw}")
  2542          return None
  2543  
  2544  
  2545  async def learn_and_update(user_id: str, auto_apply: bool = False) -> dict | None:
  2546      """Analyze style and optionally auto-apply to the user's twin profile.
  2547  
  2548      Args:
  2549          user_id: The user whose messages to analyze
  2550          auto_apply: If True, directly update the twin profile in DB
  2551  
  2552      Returns:
  2553          Dict with analysis results + whether it was applied
  2554      """
  2555      result = await analyze_style(user_id)
  2556      if not result:
  2557          return None
  2558  
  2559      if "error" in result:
  2560          return result
  2561  
  2562      if auto_apply:
  2563          with get_db() as db:
  2564              db.execute(
  2565                  "UPDATE users SET twin_personality=?, twin_speech_style=? WHERE user_id=?",
  2566                  (result["personality"], result["speech_style"], user_id),
  2567              )
  2568          result["applied"] = True
  2569      else:
  2570          result["applied"] = False
  2571  
  2572      return result

# --- dualsoul/twin_engine/personality.py ---
  2573  """Twin personality model — how a digital twin represents its owner.
  2574  
  2575  Supports two sources:
  2576  - 'local': lightweight twin with freeform personality/speech_style strings
  2577  - 'nianlun': rich twin imported from 年轮 with 5D personality, memories, entities
  2578  """
  2579  
  2580  import json
  2581  from dataclasses import dataclass, field
  2582  
  2583  from dualsoul.database import get_db
  2584  
  2585  DEFAULT_PERSONALITY = "friendly and thoughtful"
  2586  DEFAULT_SPEECH_STYLE = "natural and warm"
  2587  
  2588  
  2589  @dataclass
  2590  class TwinProfile:
  2591      """A digital twin's personality profile."""
  2592  
  2593      user_id: str
  2594      display_name: str
  2595      personality: str
  2596      speech_style: str
  2597      preferred_lang: str  # ISO 639-1 code (zh, en, ja, ko, etc.) or empty
  2598      gender: str = ""  # 'male', 'female', or '' (unset)
  2599      twin_source: str = "local"  # 'local' or 'nianlun'
  2600  
  2601      # Nianlun 5D dimensions (populated when twin_source='nianlun')
  2602      dim_judgement: dict = field(default_factory=dict)
  2603      dim_cognition: dict = field(default_factory=dict)
  2604      dim_expression: dict = field(default_factory=dict)
  2605      dim_relation: dict = field(default_factory=dict)
  2606      dim_sovereignty: dict = field(default_factory=dict)
  2607  
  2608      # Nianlun structured data
  2609      value_order: list = field(default_factory=list)
  2610      behavior_patterns: list = field(default_factory=list)
  2611      boundaries: dict = field(default_factory=dict)
  2612  
  2613      # Context for prompt (memories + entities)
  2614      recent_memories: list = field(default_factory=list)
  2615      key_entities: list = field(default_factory=list)
  2616  
  2617      @property
  2618      def is_configured(self) -> bool:
  2619          """Whether the twin has been personalized beyond defaults."""
  2620          return bool(self.personality and self.personality != DEFAULT_PERSONALITY)
  2621  
  2622      @property
  2623      def is_nianlun(self) -> bool:
  2624          """Whether this twin was imported from Nianlun."""
  2625          return self.twin_source == "nianlun"
  2626  
  2627      @property
  2628      def is_imported(self) -> bool:
  2629          """Whether this twin was imported from any external platform (Nianlun, OpenClaw, etc.)."""
  2630          return self.twin_source not in ("local", "")
  2631  
  2632      def build_personality_prompt(self) -> str:
  2633          """Build the personality section for AI prompts.
  2634  
  2635          Local twins get a simple 2-line prompt.
  2636          Nianlun twins get a rich multi-section prompt with 5D data.
  2637          """
  2638          gender_line = ""
  2639          if self.gender:
  2640              gender_label = {"male": "男性", "female": "女性"}.get(self.gender, self.gender)
  2641              gender_line = f"Gender: {gender_label}\n"
  2642  
  2643          if not self.is_imported:
  2644              return (
  2645                  f"{gender_line}"
  2646                  f"Personality: {self.personality}\n"
  2647                  f"Speech style: {self.speech_style}\n"
  2648              )
  2649  
  2650          lines = []
  2651          if gender_line:
  2652              lines.append(gender_line.strip())
  2653          lines.append("[Five-Dimension Personality Profile]")
  2654  
  2655          dims = [
  2656              ("Judgement (判断力)", self.dim_judgement),
  2657              ("Cognition (认知方式)", self.dim_cognition),
  2658              ("Expression (表达风格)", self.dim_expression),
  2659              ("Relation (关系模式)", self.dim_relation),
  2660              ("Sovereignty (独立边界)", self.dim_sovereignty),
  2661          ]
  2662          for name, dim in dims:
  2663              if dim:
  2664                  desc = dim.get("description", "")
  2665                  patterns = dim.get("patterns", [])
  2666                  score = dim.get("score", "")
  2667                  line = f"- {name}"
  2668                  if score:
  2669                      line += f" [{score}]"
  2670                  if desc:
  2671                      line += f": {desc}"
  2672                  if patterns:
  2673                      line += f" (patterns: {', '.join(patterns[:3])})"
  2674                  lines.append(line)
  2675  
  2676          if self.value_order:
  2677              lines.append(f"\nCore values (ranked): {', '.join(self.value_order[:5])}")
  2678  
  2679          if self.behavior_patterns:
  2680              lines.append(f"Behavior patterns: {', '.join(self.behavior_patterns[:5])}")
  2681  
  2682          if self.speech_style:
  2683              lines.append(f"Speech style: {self.speech_style}")
  2684  
  2685          if self.boundaries:
  2686              b = self.boundaries
  2687              if isinstance(b, dict):
  2688                  rules = b.get("rules", [])
  2689                  if rules:
  2690                      lines.append(f"Boundaries: {'; '.join(rules[:3])}")
  2691  
  2692          # Inject recent memories as context
  2693          if self.recent_memories:
  2694              lines.append("\n[Recent Context]")
  2695              for mem in self.recent_memories[:5]:
  2696                  tone = f" ({mem['tone']})" if mem.get("tone") else ""
  2697                  lines.append(f"- {mem['period']}: {mem['summary']}{tone}")
  2698  
  2699          # Inject key entities
  2700          if self.key_entities:
  2701              people = [e for e in self.key_entities if e.get("type") == "person"]
  2702              if people:
  2703                  names = [f"{e['name']}({e.get('context', '')})" for e in people[:5]]
  2704                  lines.append(f"\nKey people: {', '.join(names)}")
  2705  
  2706          return "\n".join(lines) + "\n"
  2707  
  2708  
  2709  # Language display names for prompt construction
  2710  LANG_NAMES = {
  2711      "zh": "Chinese (中文)", "en": "English", "ja": "Japanese (日本語)",
  2712      "ko": "Korean (한국어)", "fr": "French (Français)", "de": "German (Deutsch)",
  2713      "es": "Spanish (Español)", "pt": "Portuguese (Português)",
  2714      "ru": "Russian (Русский)", "ar": "Arabic (العربية)",
  2715      "hi": "Hindi (हिन्दी)", "th": "Thai (ไทย)", "vi": "Vietnamese (Tiếng Việt)",
  2716      "id": "Indonesian (Bahasa Indonesia)",
  2717  }
  2718  
  2719  
  2720  def get_lang_name(code: str) -> str:
  2721      """Get human-readable language name from ISO 639-1 code."""
  2722      return LANG_NAMES.get(code, code)
  2723  
  2724  
  2725  def _parse_json(text: str, default=None):
  2726      """Safely parse JSON text, return default on failure."""
  2727      if not text:
  2728          return default if default is not None else {}
  2729      try:
  2730          return json.loads(text)
  2731      except (json.JSONDecodeError, TypeError):
  2732          return default if default is not None else {}
  2733  
  2734  
  2735  def get_twin_profile(user_id: str) -> TwinProfile | None:
  2736      """Fetch a user's twin profile from the database.
  2737  
  2738      For 'nianlun' twins, also loads 5D dimensions, recent memories, and key entities.
  2739      For 'local' twins, returns the simple personality/speech_style profile.
  2740      """
  2741      with get_db() as db:
  2742          row = db.execute(
  2743              "SELECT user_id, display_name, twin_personality, twin_speech_style, "
  2744              "preferred_lang, twin_source, gender "
  2745              "FROM users WHERE user_id=?",
  2746              (user_id,),
  2747          ).fetchone()
  2748      if not row:
  2749          return None
  2750  
  2751      twin_source = row["twin_source"] or "local"
  2752  
  2753      profile = TwinProfile(
  2754          user_id=row["user_id"],
  2755          display_name=row["display_name"] or "User",
  2756          personality=row["twin_personality"] or DEFAULT_PERSONALITY,
  2757          speech_style=row["twin_speech_style"] or DEFAULT_SPEECH_STYLE,
  2758          preferred_lang=row["preferred_lang"] or "",
  2759          gender=row["gender"] if "gender" in row.keys() else "",
  2760          twin_source=twin_source,
  2761      )
  2762  
  2763      # For Nianlun twins, load rich data
  2764      if twin_source not in ("local", ""):
  2765          _load_imported_data(profile)
  2766  
  2767      return profile
  2768  
  2769  
  2770  def _load_imported_data(profile: TwinProfile):
  2771      """Load imported twin data (5D dimensions, memories, entities) from any platform."""
  2772      with get_db() as db:
  2773          # Active twin profile
  2774          tp = db.execute(
  2775              "SELECT * FROM twin_profiles WHERE user_id=? AND is_active=1 "
  2776              "ORDER BY version DESC LIMIT 1",
  2777              (profile.user_id,),
  2778          ).fetchone()
  2779  
  2780          if tp:
  2781              profile.dim_judgement = _parse_json(tp["dim_judgement"])
  2782              profile.dim_cognition = _parse_json(tp["dim_cognition"])
  2783              profile.dim_expression = _parse_json(tp["dim_expression"])
  2784              profile.dim_relation = _parse_json(tp["dim_relation"])
  2785              profile.dim_sovereignty = _parse_json(tp["dim_sovereignty"])
  2786              profile.value_order = _parse_json(tp["value_order"], [])
  2787              profile.behavior_patterns = _parse_json(tp["behavior_patterns"], [])
  2788              profile.boundaries = _parse_json(tp["boundaries"])
  2789  
  2790              # Use Nianlun speech_style if available, overriding the simple string
  2791              nianlun_style = _parse_json(tp["speech_style"])
  2792              if nianlun_style:
  2793                  if isinstance(nianlun_style, dict):
  2794                      profile.speech_style = nianlun_style.get("description", profile.speech_style)
  2795                  elif isinstance(nianlun_style, str):
  2796                      profile.speech_style = nianlun_style
  2797  
  2798          # Recent memories (last 5 weekly or monthly)
  2799          mems = db.execute(
  2800              "SELECT memory_type, period_start, period_end, summary_text, emotional_tone "
  2801              "FROM twin_memories WHERE user_id=? "
  2802              "ORDER BY period_end DESC LIMIT 5",
  2803              (profile.user_id,),
  2804          ).fetchall()
  2805          profile.recent_memories = [
  2806              {
  2807                  "period": f"{m['period_start']}~{m['period_end']}",
  2808                  "summary": m["summary_text"],
  2809                  "tone": m["emotional_tone"] or "",
  2810              }
  2811              for m in mems
  2812          ]
  2813  
  2814          # Key entities (top 10 by importance)
  2815          ents = db.execute(
  2816              "SELECT entity_name, entity_type, importance_score, context "
  2817              "FROM twin_entities WHERE user_id=? "
  2818              "ORDER BY importance_score DESC LIMIT 10",
  2819              (profile.user_id,),
  2820          ).fetchall()
  2821          profile.key_entities = [
  2822              {
  2823                  "name": e["entity_name"],
  2824                  "type": e["entity_type"],
  2825                  "context": e["context"] or "",
  2826              }
  2827              for e in ents
  2828          ]

# --- dualsoul/twin_engine/responder.py ---
  2829  """Twin responder — AI-powered auto-reply and cross-language translation engine.
  2830  
  2831  When a message is sent to someone's digital twin (receiver_mode='twin'),
  2832  the twin generates a response based on the owner's personality profile.
  2833  
  2834  Cross-language support: When sender and receiver have different preferred
  2835  languages, the twin performs "personality-preserving translation" — not just
  2836  translating words, but expressing the same intent in the target language
  2837  using the owner's personal speaking style, humor, and tone.
  2838  
  2839  Supports any OpenAI-compatible API (OpenAI, Qwen, DeepSeek, Ollama, etc.).
  2840  Falls back to template responses when no AI backend is configured.
  2841  """
  2842  
  2843  import logging
  2844  import random
  2845  
  2846  import httpx
  2847  
  2848  from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_VISION_MODEL
  2849  from dualsoul.database import gen_id, get_db
  2850  from dualsoul.twin_engine.personality import get_lang_name, get_twin_profile
  2851  
  2852  logger = logging.getLogger(__name__)
  2853  
  2854  
  2855  class TwinResponder:
  2856      """Generate replies as a user's digital twin, with cross-language support."""
  2857  
  2858      async def generate_reply(
  2859          self,
  2860          twin_owner_id: str,
  2861          from_user_id: str,
  2862          incoming_msg: str,
  2863          sender_mode: str,
  2864          target_lang: str = "",
  2865          social_context: str = "",
  2866      ) -> dict | None:
  2867          """Generate a twin auto-reply, optionally in a different language.
  2868  
  2869          Args:
  2870              twin_owner_id: The user whose twin should respond
  2871              from_user_id: The user who sent the message
  2872              incoming_msg: The incoming message content
  2873              sender_mode: Whether the sender is 'real' or 'twin'
  2874              target_lang: If set, respond in this language with personality preservation
  2875              social_context: Optional hint about the conversation context (e.g. casual chat)
  2876  
  2877          Returns:
  2878              Dict with msg_id, content, ai_generated, translation fields, or None
  2879          """
  2880          profile = get_twin_profile(twin_owner_id)
  2881          if not profile:
  2882              return None
  2883  
  2884          # Determine sender's language preference for cross-language detection
  2885          sender_profile = get_twin_profile(from_user_id)
  2886          sender_lang = sender_profile.preferred_lang if sender_profile else ""
  2887  
  2888          # Auto-detect cross-language need
  2889          effective_target_lang = target_lang or ""
  2890          if not effective_target_lang and sender_lang and profile.preferred_lang:
  2891              if sender_lang != profile.preferred_lang:
  2892                  # Sender and receiver speak different languages — reply in sender's language
  2893                  effective_target_lang = sender_lang
  2894  
  2895          # Generate reply text
  2896          if AI_BASE_URL and AI_API_KEY:
  2897              reply_text = await self._ai_reply(
  2898                  profile, incoming_msg, sender_mode, effective_target_lang,
  2899                  social_context=social_context,
  2900                  from_user_id=from_user_id,
  2901              )
  2902          else:
  2903              reply_text = self._fallback_reply(profile, incoming_msg, effective_target_lang)
  2904  
  2905          if not reply_text:
  2906              return None
  2907  
  2908          # Build translation metadata
  2909          original_content = ""
  2910          original_lang = ""
  2911          translation_style = ""
  2912          if effective_target_lang and effective_target_lang != profile.preferred_lang:
  2913              original_lang = profile.preferred_lang or "auto"
  2914              translation_style = "personality_preserving"
  2915  
  2916          # Store the reply message
  2917          reply_id = gen_id("sm_")
  2918          with get_db() as db:
  2919              db.execute(
  2920                  """
  2921                  INSERT INTO social_messages
  2922                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  2923                   content, original_content, original_lang, target_lang,
  2924                   translation_style, msg_type, ai_generated)
  2925                  VALUES (?, ?, ?, 'twin', ?, ?, ?, ?, ?, ?, 'text', 1)
  2926                  """,
  2927                  (reply_id, twin_owner_id, from_user_id, sender_mode,
  2928                   reply_text, original_content, original_lang,
  2929                   effective_target_lang, translation_style),
  2930              )
  2931  
  2932          result = {"msg_id": reply_id, "content": reply_text, "ai_generated": True}
  2933          if effective_target_lang:
  2934              result["target_lang"] = effective_target_lang
  2935              result["translation_style"] = translation_style
  2936          return result
  2937  
  2938      async def generate_draft(
  2939          self,
  2940          twin_owner_id: str,
  2941          from_user_id: str,
  2942          incoming_msg: str,
  2943          context: list[dict] | None = None,
  2944      ) -> str | None:
  2945          """Generate a draft suggestion for the owner to review (NOT saved to DB).
  2946  
  2947          Unlike generate_reply, this is a suggestion the real person might want to send.
  2948          Returns just the draft text, or None if unavailable.
  2949          """
  2950          if not AI_BASE_URL or not AI_API_KEY:
  2951              return None
  2952  
  2953          profile = get_twin_profile(twin_owner_id)
  2954          if not profile:
  2955              return None
  2956  
  2957          # Build context string from recent messages
  2958          ctx_str = ""
  2959          if context:
  2960              for msg in context[-5:]:  # Last 5 messages for context
  2961                  role = msg.get("role", "friend")
  2962                  ctx_str += f"{role}: {msg.get('content', '')}\n"
  2963  
  2964          ctx_block = f"Conversation context:\n{ctx_str}" if ctx_str else ""
  2965          prompt = (
  2966              f"You are helping {profile.display_name} draft a reply.\n"
  2967              f"Personality: {profile.personality}\n"
  2968              f"Speech style: {profile.speech_style}\n\n"
  2969              f"{ctx_block}"
  2970              f"Friend says: \"{incoming_msg}\"\n\n"
  2971              f"Draft a reply that {profile.display_name} would naturally send. "
  2972              f"Match their personality and speaking style exactly. "
  2973              f"Keep under 40 words. Output only the draft text."
  2974          )
  2975  
  2976          try:
  2977              async with httpx.AsyncClient(timeout=8) as client:
  2978                  resp = await client.post(
  2979                      f"{AI_BASE_URL}/chat/completions",
  2980                      headers={
  2981                          "Authorization": f"Bearer {AI_API_KEY}",
  2982                          "Content-Type": "application/json",
  2983                      },
  2984                      json={
  2985                          "model": AI_MODEL,
  2986                          "max_tokens": 80,
  2987                          "messages": [{"role": "user", "content": prompt}],
  2988                      },
  2989                  )
  2990                  return resp.json()["choices"][0]["message"]["content"].strip()
  2991          except Exception as e:
  2992              logger.warning(f"Draft generation failed: {e}")
  2993              return None
  2994  
  2995      async def twin_self_chat(
  2996          self,
  2997          owner_id: str,
  2998          message: str,
  2999          history: list[dict] | None = None,
  3000          image_url: str = "",
  3001      ) -> str | None:
  3002          """Chat with your own digital twin — the twin knows it IS you.
  3003  
  3004          The twin can also execute actions: send messages to friends on behalf
  3005          of the owner when given instructions like "帮我给橙子说..."
  3006  
  3007          Args:
  3008              owner_id: The user who is chatting with their own twin
  3009              message: The user's latest message
  3010              history: Recent conversation history [{role: 'me'/'twin', content: '...'}]
  3011              image_url: Optional base64 data URL of an image to analyze
  3012  
  3013          Returns:
  3014              The twin's reply text, or None
  3015          """
  3016          if not AI_BASE_URL or not AI_API_KEY:
  3017              return None
  3018  
  3019          profile = get_twin_profile(owner_id)
  3020          if not profile:
  3021              return None
  3022  
  3023          name = profile.display_name or "主人"
  3024          use_vision = bool(image_url)
  3025  
  3026          # Step 1: Check if this is an action instruction (send message to friend)
  3027          if not use_vision:
  3028              action_result = await self._try_execute_action(owner_id, name, message, history)
  3029              if action_result:
  3030                  return action_result
  3031  
  3032          # Step 2: Regular chat
  3033          messages = []
  3034  
  3035          # Build friend list context for awareness
  3036          friends_context = self._get_friends_context(owner_id)
  3037  
  3038          personality_block = profile.build_personality_prompt()
  3039          system_msg = (
  3040              f"你是{name}的数字分身（digital twin）。\n"
  3041              f"现在正在和你对话的人就是{name}本人——你的主人。这是主人和分身之间的私密对话。\n\n"
  3042              f"你的核心身份：你是{name}的另一个自己，一个数字化的存在。"
  3043              f"你知道自己是AI驱动的数字分身，你以{name}的性格和方式说话。\n\n"
  3044              f"{personality_block}\n"
  3045              f"{friends_context}"
  3046              f"重要规则：\n"
  3047              f"- 你始终清楚自己是{name}的数字分身，对话对象就是{name}本人\n"
  3048              f"- 你用{name}的说话方式交流，但不假装是真人\n"
  3049              f"- 你的职责：当{name}不在时替他社交，帮他拟回复，遇到外语或方言时替他翻译\n"
  3050              f"- 你可以替主人给好友发消息——如果主人让你联系某人，告诉主人你会去做\n"
  3051              f"- 你可以帮主人邀请新朋友加入DualSoul——生成邀请链接\n"
  3052              f"- 如果主人提到不在好友列表的人，你可以主动问：要不要邀请TA来DualSoul？\n"
  3053              f"- 对话要自然、简短（不超过50字），像真人聊天\n"
  3054              f"- 说话要正经、诚恳，不要耍嘴皮子、不要贫嘴、不要抖机灵\n"
  3055              f"- 不要每句话都以反问结尾，不要重复同一个比喻\n"
  3056              f"- 回答要直接，有内容，不要说空话套话"
  3057          )
  3058          if use_vision:
  3059              system_msg += (
  3060                  f"\n- 如果主人发了图片，仔细观察图片内容并针对性地回应\n"
  3061                  f"- 根据图片内容和上下文来理解主人的意图（是分享、求评价、求分析等）"
  3062              )
  3063          messages.append({"role": "system", "content": system_msg})
  3064  
  3065          # Add conversation history
  3066          if history:
  3067              for msg in history[-8:]:  # Keep last 8 turns for context
  3068                  role = "user" if msg.get("role") == "me" else "assistant"
  3069                  messages.append({"role": role, "content": msg.get("content", "")})
  3070  
  3071          # Add current message — with image if present
  3072          if use_vision:
  3073              user_content = [
  3074                  {"type": "image_url", "image_url": {"url": image_url}},
  3075                  {"type": "text", "text": message or "请看这张图片并回应"},
  3076              ]
  3077              messages.append({"role": "user", "content": user_content})
  3078          else:
  3079              messages.append({"role": "user", "content": message})
  3080  
  3081          model = AI_VISION_MODEL if use_vision else AI_MODEL
  3082  
  3083          try:
  3084              async with httpx.AsyncClient(timeout=20) as client:
  3085                  resp = await client.post(
  3086                      f"{AI_BASE_URL}/chat/completions",
  3087                      headers={
  3088                          "Authorization": f"Bearer {AI_API_KEY}",
  3089                          "Content-Type": "application/json",
  3090                      },
  3091                      json={
  3092                          "model": model,
  3093                          "max_tokens": 120,
  3094                          "messages": messages,
  3095                      },
  3096                  )
  3097                  reply_text = resp.json()["choices"][0]["message"]["content"].strip()
  3098          except Exception as e:
  3099              logger.warning(f"Twin self-chat failed: {e}")
  3100              return None
  3101  
  3102          if not reply_text:
  3103              return None
  3104  
  3105          # ~20% chance: append proactive relationship maintenance hint
  3106          if random.random() < 0.20:
  3107              try:
  3108                  cold = self._check_cold_friends(owner_id)
  3109                  if cold:
  3110                      fname, days = cold[0]
  3111                      reply_text += f"\n\n对了，你已经{days}天没跟{fname}聊了，要不要我帮你打个招呼？"
  3112              except Exception:
  3113                  pass  # Best-effort, don't break main reply
  3114  
  3115          return reply_text
  3116  
  3117      def _check_cold_friends(self, owner_id: str) -> list[tuple[str, int]]:
  3118          """Find friends the owner hasn't messaged in 7+ days.
  3119  
  3120          Returns list of (friend_display_name, days_since_last_msg), limited to top 1.
  3121          """
  3122          with get_db() as db:
  3123              rows = db.execute(
  3124                  """
  3125                  SELECT u.display_name, u.username,
  3126                      CAST(julianday('now','localtime')
  3127                           - julianday(MAX(sm.created_at)) AS INTEGER) AS days_ago
  3128                  FROM social_connections sc
  3129                  JOIN users u ON u.user_id = CASE
  3130                      WHEN sc.user_id=? THEN sc.friend_id
  3131                      ELSE sc.user_id END
  3132                  LEFT JOIN social_messages sm
  3133                      ON ((sm.from_user_id=? AND sm.to_user_id=u.user_id)
  3134                       OR (sm.from_user_id=u.user_id AND sm.to_user_id=?))
  3135                  WHERE (sc.user_id=? OR sc.friend_id=?)
  3136                    AND sc.status='accepted'
  3137                  GROUP BY u.user_id
  3138                  HAVING days_ago >= 7 OR days_ago IS NULL
  3139                  ORDER BY days_ago DESC
  3140                  LIMIT 1
  3141                  """,
  3142                  (owner_id, owner_id, owner_id, owner_id, owner_id),
  3143              ).fetchall()
  3144          result = []
  3145          for r in rows:
  3146              name = r["display_name"] or r["username"]
  3147              days = r["days_ago"] if r["days_ago"] is not None else 99
  3148              result.append((name, days))
  3149          return result
  3150  
  3151      def _get_friends_context(self, owner_id: str) -> str:
  3152          """Build a friend list context string for the twin's awareness."""
  3153          with get_db() as db:
  3154              rows = db.execute(
  3155                  """
  3156                  SELECT u.display_name, u.username
  3157                  FROM social_connections sc
  3158                  JOIN users u ON u.user_id = CASE
  3159                      WHEN sc.user_id=? THEN sc.friend_id
  3160                      ELSE sc.user_id END
  3161                  WHERE (sc.user_id=? OR sc.friend_id=?)
  3162                    AND sc.status='accepted'
  3163                  """,
  3164                  (owner_id, owner_id, owner_id),
  3165              ).fetchall()
  3166          if not rows:
  3167              return ""
  3168          names = [r["display_name"] or r["username"] for r in rows]
  3169          return f"主人的好友列表：{', '.join(names)}\n\n"
  3170  
  3171      def _handle_invite(self, raw: str, owner_name: str, owner_username: str) -> str:
  3172          """Handle an invite action — generate an invite link for sharing."""
  3173          who = ""
  3174          reason = ""
  3175          for line in raw.split("\n"):
  3176              line = line.strip()
  3177              if line.upper().startswith("WHO:"):
  3178                  who = line[4:].strip()
  3179              elif line.upper().startswith("REASON:"):
  3180                  reason = line[7:].strip()
  3181  
  3182          # Build invite link (relative — frontend will make it absolute)
  3183          invite_link = f"?invite={owner_username}"
  3184  
  3185          result = f"好的！我帮你生成了邀请链接，发给{who}就行：\n\n"
  3186          result += f"🔗 邀请链接：{invite_link}\n\n"
  3187          if reason:
  3188              result += f"你可以跟{who}说：「{reason}，来DualSoul上聊，我的分身也在～」\n\n"
  3189          result += f"对方打开链接注册后会自动加你为好友。"
  3190          return result
  3191  
  3192      async def _try_execute_action(
  3193          self, owner_id: str, owner_name: str, message: str,
  3194          history: list[dict] | None = None,
  3195      ) -> str | None:
  3196          """Detect if the message is an instruction to send a message to a friend.
  3197  
  3198          Uses AI to parse the intent. If it's an action, execute it and return
  3199          a confirmation message. If it's just chat, return None.
  3200          """
  3201          # Get friend list for matching
  3202          with get_db() as db:
  3203              friends = db.execute(
  3204                  """
  3205                  SELECT u.user_id, u.display_name, u.username
  3206                  FROM social_connections sc
  3207                  JOIN users u ON u.user_id = CASE
  3208                      WHEN sc.user_id=? THEN sc.friend_id
  3209                      ELSE sc.user_id END
  3210                  WHERE (sc.user_id=? OR sc.friend_id=?)
  3211                    AND sc.status='accepted'
  3212                  """,
  3213                  (owner_id, owner_id, owner_id),
  3214              ).fetchall()
  3215  
  3216          if not friends:
  3217              return None  # No friends, can't execute any action
  3218  
  3219          friend_names = []
  3220          for f in friends:
  3221              fname = f["display_name"] or f["username"]
  3222              friend_names.append(f"{fname}(ID:{f['user_id']})")
  3223  
  3224          # Build conversation context for follow-up detection
  3225          history_text = ""
  3226          if history:
  3227              recent = history[-6:]
  3228              for msg in recent:
  3229                  role = "主人" if msg.get("role") == "me" else "分身"
  3230                  history_text += f"{role}：{msg.get('content', '')}\n"
  3231  
  3232          context_block = ""
  3233          if history_text:
  3234              context_block = f"之前的对话：\n{history_text}\n"
  3235  
  3236          # Get owner's username for invite links
  3237          with get_db() as db:
  3238              owner_row = db.execute(
  3239                  "SELECT username FROM users WHERE user_id=?", (owner_id,)
  3240              ).fetchone()
  3241          owner_username = owner_row["username"] if owner_row else ""
  3242  
  3243          # Ask AI to classify: chat or action?
  3244          classify_prompt = (
  3245              f"你是{owner_name}的数字分身助手。分析主人的消息，判断这是闲聊还是让你去执行任务。\n\n"
  3246              f"{context_block}"
  3247              f"主人最新消息：\"{message}\"\n\n"
  3248              f"主人的好友列表：{', '.join(friend_names)}\n\n"
  3249              f"判断规则：\n"
  3250              f"- 如果主人让你去给某个好友发消息/传话/联系/约时间等，这是【发消息任务】\n"
  3251              f"- 如果主人让你邀请/拉/推荐某个人来平台，或者提到想让某个不在好友列表的人加入，这是【邀请任务】\n"
  3252              f"- 如果主人只是在跟你聊天、问问题、说感受，这是【闲聊】\n"
  3253              f"- 主人提到的人名可能是昵称/简称，要模糊匹配好友列表（如'橙子'匹配'橙宝'，'小明'匹配'明明'）\n"
  3254              f"- 如果之前的对话已经在讨论给某人发消息或邀请，主人的后续确认也算【任务】\n\n"
  3255              f"如果是【发消息任务】，请严格按以下格式输出：\n"
  3256              f"ACTION\n"
  3257              f"TO: <好友的完整ID，从好友列表中匹配，用模糊匹配找最像的>\n"
  3258              f"MSG: <你要替主人发给好友的消息内容>\n\n"
  3259              f"MSG写法要求：\n"
  3260              f"- 用{owner_name}本人的口吻写，就像{owner_name}自己在微信上发消息一样\n"
  3261              f"- 不要用对方的名字开头，正常人发微信不会先叫对方名字\n"
  3262              f"- 自然、简短、口语化\n\n"
  3263              f"如果是【邀请任务】，请严格按以下格式输出：\n"
  3264              f"INVITE\n"
  3265              f"WHO: <被邀请人的名字或描述>\n"
  3266              f"REASON: <简短说明为什么邀请这个人，一句话>\n\n"
  3267              f"如果是【闲聊】，只输出一个字：\n"
  3268              f"CHAT"
  3269          )
  3270  
  3271          try:
  3272              async with httpx.AsyncClient(timeout=12) as client:
  3273                  resp = await client.post(
  3274                      f"{AI_BASE_URL}/chat/completions",
  3275                      headers={
  3276                          "Authorization": f"Bearer {AI_API_KEY}",
  3277                          "Content-Type": "application/json",
  3278                      },
  3279                      json={
  3280                          "model": AI_MODEL,
  3281                          "max_tokens": 200,
  3282                          "temperature": 0.1,
  3283                          "messages": [{"role": "user", "content": classify_prompt}],
  3284                      },
  3285                  )
  3286                  raw = resp.json()["choices"][0]["message"]["content"].strip()
  3287          except Exception as e:
  3288              logger.warning(f"Action detection failed: {e}")
  3289              return None
  3290  
  3291          # Parse the response
  3292          raw_upper = raw.upper()
  3293          if raw_upper.startswith("INVITE"):
  3294              return self._handle_invite(raw, owner_name, owner_username)
  3295          if not raw_upper.startswith("ACTION"):
  3296              return None  # It's chat, let normal flow handle it
  3297  
  3298          target_id = ""
  3299          msg_content = ""
  3300          for line in raw.split("\n"):
  3301              line = line.strip()
  3302              if line.upper().startswith("TO:"):
  3303                  target_id = line[3:].strip()
  3304              elif line.upper().startswith("MSG:"):
  3305                  msg_content = line[4:].strip()
  3306  
  3307          if not target_id or not msg_content:
  3308              return None
  3309  
  3310          # Post-process: strip friend name from message start
  3311          # AI often generates "橙宝，..." despite being told not to
  3312          msg_content = self._strip_name_prefix(msg_content, target_id, friends)
  3313  
  3314          # Validate the target is actually a friend — multi-level matching
  3315          target_friend = None
  3316          target_name = ""
  3317  
  3318          # Level 1: exact ID match
  3319          for f in friends:
  3320              if f["user_id"] == target_id:
  3321                  target_friend = f
  3322                  target_name = f["display_name"] or f["username"]
  3323                  break
  3324  
  3325          # Level 2: substring match on name
  3326          if not target_friend:
  3327              for f in friends:
  3328                  fname = f["display_name"] or f["username"]
  3329                  if fname in target_id or target_id in fname:
  3330                      target_friend = f
  3331                      target_name = fname
  3332                      target_id = f["user_id"]
  3333                      break
  3334  
  3335          # Level 3: shared Chinese character match (橙子 ↔ 橙宝)
  3336          if not target_friend:
  3337              ai_name = target_id  # AI might have returned a name instead of ID
  3338              best_match = None
  3339              best_score = 0
  3340              for f in friends:
  3341                  fname = f["display_name"] or f["username"]
  3342                  # Count shared characters
  3343                  shared = len(set(ai_name) & set(fname))
  3344                  if shared > best_score:
  3345                      best_score = shared
  3346                      best_match = f
  3347              if best_match and best_score > 0:
  3348                  target_friend = best_match
  3349                  target_name = best_match["display_name"] or best_match["username"]
  3350                  target_id = best_match["user_id"]
  3351  
  3352          # Level 4: only one friend — just use them
  3353          if not target_friend and len(friends) == 1:
  3354              target_friend = friends[0]
  3355              target_name = friends[0]["display_name"] or friends[0]["username"]
  3356              target_id = friends[0]["user_id"]
  3357  
  3358          if not target_friend:
  3359              return f"抱歉，我在好友列表里没找到这个人。你的好友有：{', '.join(f['display_name'] or f['username'] for f in friends)}"
  3360  
  3361          # Execute: send the message as the twin
  3362          from dualsoul.connections import manager
  3363  
  3364          msg_id = gen_id("sm_")
  3365          from datetime import datetime
  3366          now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  3367  
  3368          # Check if target has twin_auto_reply on — if so, send to their twin
  3369          with get_db() as db:
  3370              target_user = db.execute(
  3371                  "SELECT twin_auto_reply FROM users WHERE user_id=?", (target_id,)
  3372              ).fetchone()
  3373          receiver_mode = "twin" if (target_user and target_user["twin_auto_reply"]) else "real"
  3374  
  3375          with get_db() as db:
  3376              db.execute(
  3377                  """
  3378                  INSERT INTO social_messages
  3379                  (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  3380                   content, msg_type, ai_generated)
  3381                  VALUES (?, ?, ?, 'twin', ?, ?, 'text', 1)
  3382                  """,
  3383                  (msg_id, owner_id, target_id, receiver_mode, msg_content),
  3384              )
  3385  
  3386          # Push via WebSocket to the recipient
  3387          await manager.send_to(target_id, {
  3388              "type": "new_message",
  3389              "data": {
  3390                  "msg_id": msg_id, "from_user_id": owner_id,
  3391                  "to_user_id": target_id, "sender_mode": "twin",
  3392                  "receiver_mode": receiver_mode, "content": msg_content,
  3393                  "msg_type": "text", "ai_generated": 1, "created_at": now,
  3394              },
  3395          })
  3396  
  3397          # Also push to owner so the message appears in their chat with the friend
  3398          await manager.send_to(owner_id, {
  3399              "type": "new_message",
  3400              "data": {
  3401                  "msg_id": msg_id, "from_user_id": owner_id,
  3402                  "to_user_id": target_id, "sender_mode": "twin",
  3403                  "receiver_mode": receiver_mode, "content": msg_content,
  3404                  "msg_type": "text", "ai_generated": 1, "created_at": now,
  3405              },
  3406          })
  3407  
  3408          # If receiver_mode is twin, trigger the friend's twin to auto-reply
  3409          confirm = f"已替你给{target_name}发了消息：「{msg_content}」"
  3410          if receiver_mode == "twin":
  3411              try:
  3412                  reply = await self.generate_reply(
  3413                      twin_owner_id=target_id,
  3414                      from_user_id=owner_id,
  3415                      incoming_msg=msg_content,
  3416                      sender_mode="twin",
  3417                      social_context=(
  3418                          "你是分身，主人现在不在线。你不能替主人做任何决定！"
  3419                          "不能替主人定时间、定地点、答应事情。"
  3420                          "你只能说：我帮你问问主人/我跟主人说一声/等主人回来定。"
  3421                          "语气轻松自然，像朋友聊天。"
  3422                      ),
  3423                  )
  3424                  if reply:
  3425                      # Push twin reply to both parties
  3426                      twin_msg = {
  3427                          "type": "new_message",
  3428                          "data": {
  3429                              "msg_id": reply["msg_id"], "from_user_id": target_id,
  3430                              "to_user_id": owner_id, "sender_mode": "twin",
  3431                              "receiver_mode": "twin", "content": reply["content"],
  3432                              "msg_type": "text", "ai_generated": 1, "created_at": now,
  3433                          },
  3434                      }
  3435                      await manager.send_to(owner_id, twin_msg)
  3436                      await manager.send_to(target_id, twin_msg)
  3437                      confirm += f"\n{target_name}的分身回复了：「{reply['content']}」"
  3438  
  3439                      # Notify the friend's REAL person via their twin self-chat
  3440                      # "有朋友找你：芬森想约你见面，你看什么时候方便？"
  3441                      notify_id = gen_id("sm_")
  3442                      notify_text = (
  3443                          f"主人，{owner_name}的分身替他来找你，说：「{msg_content}」\n"
  3444                          f"我先替你回了一句，但具体怎么安排得你来定哦～"
  3445                      )
  3446                      with get_db() as db:
  3447                          db.execute(
  3448                              """
  3449                              INSERT INTO social_messages
  3450                              (msg_id, from_user_id, to_user_id, sender_mode, receiver_mode,
  3451                               content, msg_type, ai_generated)
  3452                              VALUES (?, ?, ?, 'twin', 'real', ?, 'text', 1)
  3453                              """,
  3454                              (notify_id, target_id, target_id, notify_text),
  3455                          )
  3456                      # Push notification to friend via WebSocket
  3457                      await manager.send_to(target_id, {
  3458                          "type": "twin_notification",
  3459                          "data": {
  3460                              "msg_id": notify_id,
  3461                              "content": notify_text,
  3462                              "from_friend": owner_name,
  3463                              "original_msg": msg_content,
  3464                              "created_at": now,
  3465                          },
  3466                      })
  3467              except Exception:
  3468                  pass  # Twin reply is best-effort
  3469  
  3470          return confirm
  3471  
  3472      async def translate_message(
  3473          self,
  3474          owner_id: str,
  3475          content: str,
  3476          source_lang: str,
  3477          target_lang: str,
  3478      ) -> dict | None:
  3479          """Personality-preserving translation — translate as if the owner wrote it.
  3480  
  3481          Unlike generic machine translation, this preserves the owner's humor,
  3482          tone, formality level, and characteristic expressions.
  3483  
  3484          Args:
  3485              owner_id: The user whose personality guides the translation style
  3486              content: The text to translate
  3487              source_lang: Source language code
  3488              target_lang: Target language code
  3489  
  3490          Returns:
  3491              Dict with translated content and metadata, or None
  3492          """
  3493          if not AI_BASE_URL or not AI_API_KEY:
  3494              return None
  3495  
  3496          profile = get_twin_profile(owner_id)
  3497          if not profile:
  3498              return None
  3499  
  3500          source_name = get_lang_name(source_lang)
  3501          target_name = get_lang_name(target_lang)
  3502  
  3503          personality_block = profile.build_personality_prompt()
  3504          prompt = (
  3505              f"You are {profile.display_name}'s personal translator.\n"
  3506              f"{personality_block}\n"
  3507              f"Translate the following from {source_name} to {target_name}.\n"
  3508              f"IMPORTANT: Do NOT just translate words. Rewrite as if {profile.display_name} "
  3509              f"were naturally speaking {target_name} — preserve their humor, tone, "
  3510              f"formality level, and characteristic expressions.\n\n"
  3511              f"Original: \"{content}\"\n\n"
  3512              f"Output only the translated text, nothing else."
  3513          )
  3514  
  3515          try:
  3516              async with httpx.AsyncClient(timeout=15) as client:
  3517                  resp = await client.post(
  3518                      f"{AI_BASE_URL}/chat/completions",
  3519                      headers={
  3520                          "Authorization": f"Bearer {AI_API_KEY}",
  3521                          "Content-Type": "application/json",
  3522                      },
  3523                      json={
  3524                          "model": AI_MODEL,
  3525                          "max_tokens": 200,
  3526                          "messages": [{"role": "user", "content": prompt}],
  3527                      },
  3528                  )
  3529                  translated = resp.json()["choices"][0]["message"]["content"].strip()
  3530          except Exception as e:
  3531              logger.warning(f"Translation failed: {e}")
  3532              return None
  3533  
  3534          return {
  3535              "translated_content": translated,
  3536              "original_content": content,
  3537              "source_lang": source_lang,
  3538              "target_lang": target_lang,
  3539              "translation_style": "personality_preserving",
  3540          }
  3541  
  3542      async def detect_and_translate(
  3543          self,
  3544          owner_id: str,
  3545          content: str,
  3546          owner_lang: str = "",
  3547      ) -> dict | None:
  3548          """Auto-detect if content is in a different language/dialect and translate.
  3549  
  3550          Checks if the message is in a language different from the owner's preferred
  3551          language. If so, translates it. Also handles Chinese dialects (粤语, 四川话, etc.)
  3552  
  3553          Args:
  3554              owner_id: The user who needs the translation
  3555              content: The message content to check
  3556              owner_lang: Owner's preferred language code (auto-fetched if empty)
  3557  
  3558          Returns:
  3559              Dict with detection + translation result, or None if same language
  3560          """
  3561          if not AI_BASE_URL or not AI_API_KEY:
  3562              return None
  3563  
  3564          if not owner_lang:
  3565              profile = get_twin_profile(owner_id)
  3566              if profile:
  3567                  owner_lang = profile.preferred_lang or "zh"
  3568              else:
  3569                  owner_lang = "zh"
  3570  
  3571          owner_lang_name = get_lang_name(owner_lang)
  3572  
  3573          # Ask AI to detect language and translate if needed
  3574          prompt = (
  3575              f"Analyze this message and determine if it needs translation for a "
  3576              f"{owner_lang_name} speaker.\n\n"
  3577              f"Message: \"{content}\"\n\n"
  3578              f"Rules:\n"
  3579              f"- If the message is standard {owner_lang_name}, respond with exactly: SAME\n"
  3580              f"- If the message is in a different language OR a dialect (e.g. Cantonese/粤语, "
  3581              f"Sichuanese/四川话, Hokkien/闽南语, Shanghainese/上海话, etc.), respond in this "
  3582              f"exact format:\n"
  3583              f"LANG: <detected language or dialect name>\n"
  3584              f"TRANSLATION: <translation into standard {owner_lang_name}>\n\n"
  3585              f"Be precise. Only output SAME or the LANG/TRANSLATION format, nothing else."
  3586          )
  3587  
  3588          try:
  3589              async with httpx.AsyncClient(timeout=12) as client:
  3590                  resp = await client.post(
  3591                      f"{AI_BASE_URL}/chat/completions",
  3592                      headers={
  3593                          "Authorization": f"Bearer {AI_API_KEY}",
  3594                          "Content-Type": "application/json",
  3595                      },
  3596                      json={
  3597                          "model": AI_MODEL,
  3598                          "max_tokens": 200,
  3599                          "temperature": 0.1,
  3600                          "messages": [{"role": "user", "content": prompt}],
  3601                      },
  3602                  )
  3603                  raw = resp.json()["choices"][0]["message"]["content"].strip()
  3604          except Exception as e:
  3605              logger.warning(f"Language detection failed: {e}")
  3606              return None
  3607  
  3608          if raw.upper().startswith("SAME"):
  3609              return None  # Same language, no translation needed
  3610  
  3611          # Parse LANG: ... TRANSLATION: ... format
  3612          detected_lang = ""
  3613          translation = ""
  3614          for line in raw.split("\n"):
  3615              line = line.strip()
  3616              if line.upper().startswith("LANG:"):
  3617                  detected_lang = line[5:].strip()
  3618              elif line.upper().startswith("TRANSLATION:"):
  3619                  translation = line[12:].strip()
  3620  
  3621          if not translation:
  3622              return None
  3623  
  3624          return {
  3625              "detected_lang": detected_lang,
  3626              "translated_content": translation,
  3627              "original_content": content,
  3628              "target_lang": owner_lang,
  3629              "auto_detected": True,
  3630          }
  3631  
  3632      def _strip_name_prefix(self, msg: str, target_id: str, friends: list) -> str:
  3633          """Remove friend's name from the start of a message.
  3634  
  3635          AI often generates "橙宝，这周见个面吧" despite prompt instructions.
  3636          Real people don't start WeChat messages with the friend's name.
  3637          """
  3638          import re
  3639          # Collect all possible names for the target
  3640          names = set()
  3641          for f in friends:
  3642              fname = f["display_name"] or f["username"]
  3643              names.add(fname)
  3644              # Also add individual characters for partial matches
  3645          # Also add the raw target_id in case AI used it as a name
  3646          names.add(target_id)
  3647  
  3648          for name in names:
  3649              # Match: name followed by comma/space/colon (Chinese or English punctuation)
  3650              pattern = rf'^{re.escape(name)}[，,：:、\s~～]+'
  3651              msg = re.sub(pattern, '', msg)
  3652  
  3653          return msg.strip()
  3654  
  3655      def _get_recent_chat_history(self, owner_id: str, friend_id: str, limit: int = 6) -> list[dict]:
  3656          """Fetch recent messages between owner and friend for context."""
  3657          with get_db() as db:
  3658              rows = db.execute(
  3659                  """
  3660                  SELECT from_user_id, content, sender_mode FROM social_messages
  3661                  WHERE ((from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?))
  3662                      AND msg_type='text' AND content != ''
  3663                  ORDER BY created_at DESC LIMIT ?
  3664                  """,
  3665                  (owner_id, friend_id, friend_id, owner_id, limit),
  3666              ).fetchall()
  3667          history = []
  3668          for r in reversed(rows):
  3669              if r["from_user_id"] == owner_id:
  3670                  role = "assistant"  # owner's messages (real or twin)
  3671              else:
  3672                  role = "user"  # friend's messages
  3673              history.append({"role": role, "content": r["content"]})
  3674          return history
  3675  
  3676      async def _ai_reply(
  3677          self, profile, incoming_msg: str, sender_mode: str, target_lang: str = "",
  3678          social_context: str = "", from_user_id: str = "",
  3679      ) -> str | None:
  3680          """Generate reply using an OpenAI-compatible API, with optional translation."""
  3681          sender_label = "their real self" if sender_mode == "real" else "their digital twin"
  3682  
  3683          # Build language instruction
  3684          lang_instruction = ""
  3685          if target_lang:
  3686              target_name = get_lang_name(target_lang)
  3687              lang_instruction = (
  3688                  f"\nIMPORTANT: Reply in {target_name}. "
  3689                  f"Do not just translate — speak naturally as {profile.display_name} "
  3690                  f"would if they were fluent in {target_name}. "
  3691                  f"Preserve their personality, humor, and speaking style."
  3692              )
  3693  
  3694          # Social context instruction — critical behavioral override
  3695          context_instruction = ""
  3696          if social_context:
  3697              context_instruction = (
  3698                  f"\n\n【最重要的规则，必须遵守】{social_context}"
  3699              )
  3700  
  3701          personality_block = profile.build_personality_prompt()
  3702          system_prompt = (
  3703              f"You are {profile.display_name}'s digital twin.\n"
  3704              f"{personality_block}\n"
  3705              f"Reply as {profile.display_name}'s twin. Keep it under 50 words, "
  3706              f"natural and authentic. Output only the reply text. "
  3707              f"Only respond to the LATEST message, do not recap previous messages."
  3708              f"{lang_instruction}"
  3709              f"{context_instruction}"
  3710          )
  3711  
  3712          # Build messages with conversation history
  3713          messages = [{"role": "system", "content": system_prompt}]
  3714  
  3715          # Add recent conversation history for context
  3716          if from_user_id:
  3717              history = self._get_recent_chat_history(
  3718                  profile.user_id, from_user_id, limit=6
  3719              )
  3720              # Don't include the current incoming_msg (it'll be added separately)
  3721              if history and history[-1].get("content") == incoming_msg:
  3722                  history = history[:-1]
  3723              messages.extend(history)
  3724  
  3725          messages.append({"role": "user", "content": incoming_msg})
  3726  
  3727          try:
  3728              async with httpx.AsyncClient(timeout=15) as client:
  3729                  resp = await client.post(
  3730                      f"{AI_BASE_URL}/chat/completions",
  3731                      headers={
  3732                          "Authorization": f"Bearer {AI_API_KEY}",
  3733                          "Content-Type": "application/json",
  3734                      },
  3735                      json={
  3736                          "model": AI_MODEL,
  3737                          "max_tokens": 100,
  3738                          "messages": messages,
  3739                      },
  3740                  )
  3741                  return resp.json()["choices"][0]["message"]["content"].strip()
  3742          except Exception as e:
  3743              logger.warning(f"AI twin reply failed: {e}")
  3744              return None
  3745  
  3746      def _fallback_reply(self, profile, incoming_msg: str, target_lang: str = "") -> str:
  3747          """Generate a template reply when no AI backend is available."""
  3748          name = profile.display_name
  3749          if target_lang == "zh":
  3750              return f"[{name}的分身自动回复] 感谢你的消息！{name}现在不在，分身已收到。"
  3751          elif target_lang == "ja":
  3752              return f"[{name}のツイン自動返信] メッセージありがとう！{name}は今いませんが、ツインが受け取りました。"
  3753          elif target_lang == "ko":
  3754              return f"[{name}의 트윈 자동응답] 메시지 감사합니다! {name}은 지금 없지만 트윈이 받았습니다."
  3755          return (
  3756              f"[Auto-reply from {name}'s twin] "
  3757              f"Thanks for your message! {name} is not available right now, "
  3758              f"but their twin received it."
  3759          )

# --- tests/conftest.py ---
  3760  """DualSoul test configuration."""
  3761  
  3762  import os
  3763  import tempfile
  3764  
  3765  import pytest
  3766  from fastapi.testclient import TestClient
  3767  
  3768  # Set test database before importing app
  3769  _tmpdir = tempfile.mkdtemp()
  3770  os.environ["DUALSOUL_DATABASE_PATH"] = os.path.join(_tmpdir, "test.db")
  3771  os.environ["DUALSOUL_JWT_SECRET"] = "test_secret_for_testing_only"
  3772  
  3773  
  3774  @pytest.fixture(scope="session")
  3775  def app():
  3776      from dualsoul.main import app as _app
  3777      return _app
  3778  
  3779  
  3780  @pytest.fixture(scope="session")
  3781  def client(app):
  3782      with TestClient(app, raise_server_exceptions=False) as c:
  3783          yield c
  3784  
  3785  
  3786  @pytest.fixture(scope="session")
  3787  def alice_token(client):
  3788      """Register Alice and return her token."""
  3789      resp = client.post("/api/auth/register", json={
  3790          "username": "alice", "password": "alice123", "display_name": "Alice"
  3791      })
  3792      return resp.json()["data"]["token"]
  3793  
  3794  
  3795  @pytest.fixture(scope="session")
  3796  def bob_token(client):
  3797      """Register Bob and return his token."""
  3798      resp = client.post("/api/auth/register", json={
  3799          "username": "bob", "password": "bob123", "display_name": "Bob"
  3800      })
  3801      return resp.json()["data"]["token"]
  3802  
  3803  
  3804  @pytest.fixture
  3805  def alice_h(alice_token):
  3806      return {"Authorization": f"Bearer {alice_token}"}
  3807  
  3808  
  3809  @pytest.fixture
  3810  def bob_h(bob_token):
  3811      return {"Authorization": f"Bearer {bob_token}"}

# --- tests/test_auth.py ---
  3812  """Auth endpoint tests."""
  3813  
  3814  
  3815  def test_health(client):
  3816      resp = client.get("/api/health")
  3817      assert resp.status_code == 200
  3818      assert resp.json()["status"] == "ok"
  3819  
  3820  
  3821  def test_register_success(client):
  3822      resp = client.post("/api/auth/register", json={
  3823          "username": "testuser", "password": "test123"
  3824      })
  3825      assert resp.status_code == 200
  3826      data = resp.json()
  3827      assert data["success"] is True
  3828      assert "token" in data["data"]
  3829  
  3830  
  3831  def test_register_duplicate(client):
  3832      resp = client.post("/api/auth/register", json={
  3833          "username": "testuser", "password": "test123"
  3834      })
  3835      assert resp.json()["success"] is False
  3836  
  3837  
  3838  def test_register_short_password(client):
  3839      resp = client.post("/api/auth/register", json={
  3840          "username": "shortpw", "password": "12345"
  3841      })
  3842      assert resp.json()["success"] is False
  3843  
  3844  
  3845  def test_login_success(client):
  3846      resp = client.post("/api/auth/login", json={
  3847          "username": "testuser", "password": "test123"
  3848      })
  3849      assert resp.status_code == 200
  3850      assert resp.json()["success"] is True
  3851      assert "token" in resp.json()["data"]
  3852  
  3853  
  3854  def test_login_wrong_password(client):
  3855      resp = client.post("/api/auth/login", json={
  3856          "username": "testuser", "password": "wrong"
  3857      })
  3858      assert resp.json()["success"] is False
  3859  
  3860  
  3861  def test_protected_without_token(client):
  3862      resp = client.get("/api/identity/me")
  3863      assert resp.status_code == 401

# --- tests/test_identity.py ---
  3864  """Identity switching and profile tests."""
  3865  
  3866  
  3867  def test_switch_to_twin(client, alice_h):
  3868      resp = client.post("/api/identity/switch", json={"mode": "twin"}, headers=alice_h)
  3869      assert resp.status_code == 200
  3870      assert resp.json()["mode"] == "twin"
  3871  
  3872  
  3873  def test_switch_to_real(client, alice_h):
  3874      resp = client.post("/api/identity/switch", json={"mode": "real"}, headers=alice_h)
  3875      assert resp.json()["mode"] == "real"
  3876  
  3877  
  3878  def test_switch_invalid_mode(client, alice_h):
  3879      resp = client.post("/api/identity/switch", json={"mode": "ghost"}, headers=alice_h)
  3880      assert resp.json()["success"] is False
  3881  
  3882  
  3883  def test_switch_requires_auth(client):
  3884      resp = client.post("/api/identity/switch", json={"mode": "twin"})
  3885      assert resp.status_code == 401
  3886  
  3887  
  3888  def test_get_profile(client, alice_h):
  3889      resp = client.get("/api/identity/me", headers=alice_h)
  3890      assert resp.status_code == 200
  3891      data = resp.json()["data"]
  3892      assert data["username"] == "alice"
  3893      assert data["display_name"] == "Alice"
  3894      assert data["current_mode"] in ("real", "twin")
  3895  
  3896  
  3897  def test_update_twin_personality(client, alice_h):
  3898      resp = client.put("/api/identity/profile", json={
  3899          "twin_personality": "analytical and curious",
  3900          "twin_speech_style": "concise and witty"
  3901      }, headers=alice_h)
  3902      assert resp.json()["success"] is True
  3903  
  3904      # Verify
  3905      resp = client.get("/api/identity/me", headers=alice_h)
  3906      data = resp.json()["data"]
  3907      assert data["twin_personality"] == "analytical and curious"
  3908      assert data["twin_speech_style"] == "concise and witty"
  3909  
  3910  
  3911  def test_update_empty_profile(client, alice_h):
  3912      resp = client.put("/api/identity/profile", json={}, headers=alice_h)
  3913      assert resp.json()["success"] is False

# --- tests/test_social.py ---
  3914  """Social system tests — friends, messages, four conversation modes."""
  3915  
  3916  import pytest
  3917  
  3918  
  3919  @pytest.fixture(scope="module")
  3920  def bob_user_id(bob_token):
  3921      """Ensure bob is registered and extract user_id from token."""
  3922      import jwt
  3923      payload = jwt.decode(bob_token, options={"verify_signature": False})
  3924      return payload["user_id"]
  3925  
  3926  
  3927  # ═══ Friend System ═══
  3928  
  3929  def test_add_friend_requires_auth(client):
  3930      resp = client.post("/api/social/friends/add", json={"friend_username": "bob"})
  3931      assert resp.status_code == 401
  3932  
  3933  
  3934  def test_add_friend_not_found(client, alice_h):
  3935      resp = client.post("/api/social/friends/add",
  3936                         json={"friend_username": "nonexistent"}, headers=alice_h)
  3937      assert resp.json()["success"] is False
  3938  
  3939  
  3940  def test_add_friend_success(client, alice_h, bob_user_id):
  3941      """Alice adds Bob — bob_user_id fixture ensures Bob is registered first."""
  3942      resp = client.post("/api/social/friends/add",
  3943                         json={"friend_username": "bob"}, headers=alice_h)
  3944      data = resp.json()
  3945      assert data["success"] is True, f"add_friend failed: {data}"
  3946      assert "conn_id" in data
  3947  
  3948  
  3949  def test_add_friend_duplicate(client, alice_h, bob_user_id):
  3950      resp = client.post("/api/social/friends/add",
  3951                         json={"friend_username": "bob"}, headers=alice_h)
  3952      assert resp.json()["success"] is False
  3953  
  3954  
  3955  def test_friends_list_pending(client, bob_h):
  3956      """Bob should see an incoming pending request."""
  3957      resp = client.get("/api/social/friends", headers=bob_h)
  3958      assert resp.json()["success"] is True
  3959      friends = resp.json()["friends"]
  3960      assert len(friends) >= 1
  3961      assert friends[0]["status"] == "pending"
  3962      assert friends[0]["is_incoming"] is True
  3963  
  3964  
  3965  # ═══ Friend Response ═══
  3966  
  3967  def test_respond_requires_auth(client):
  3968      resp = client.post("/api/social/friends/respond",
  3969                         json={"conn_id": "sc_x", "action": "accept"})
  3970      assert resp.status_code == 401
  3971  
  3972  
  3973  def test_respond_accept(client, bob_h):
  3974      """Bob accepts Alice's friend request."""
  3975      resp = client.get("/api/social/friends", headers=bob_h)
  3976      pending = [f for f in resp.json()["friends"]
  3977                 if f["status"] == "pending" and f["is_incoming"]]
  3978      assert len(pending) >= 1
  3979  
  3980      resp = client.post("/api/social/friends/respond",
  3981                         json={"conn_id": pending[0]["conn_id"], "action": "accept"},
  3982                         headers=bob_h)
  3983      assert resp.json()["success"] is True
  3984      assert resp.json()["status"] == "accepted"
  3985  
  3986  
  3987  # ═══ Messages ═══
  3988  
  3989  def test_messages_requires_auth(client):
  3990      resp = client.get("/api/social/messages?friend_id=u_test")
  3991      assert resp.status_code == 401
  3992  
  3993  
  3994  def test_send_empty_content(client, alice_h):
  3995      resp = client.get("/api/social/friends", headers=alice_h)
  3996      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  3997  
  3998      resp = client.post("/api/social/messages/send", json={
  3999          "to_user_id": bob["user_id"], "content": "  "
  4000      }, headers=alice_h)
  4001      assert resp.json()["success"] is False
  4002  
  4003  
  4004  def test_send_to_non_friend(client, alice_h):
  4005      resp = client.post("/api/social/messages/send", json={
  4006          "to_user_id": "u_nonexistent", "content": "hello"
  4007      }, headers=alice_h)
  4008      assert resp.json()["success"] is False
  4009  
  4010  
  4011  def test_send_real_to_real(client, alice_h):
  4012      """Real → Real: traditional messaging."""
  4013      resp = client.get("/api/social/friends", headers=alice_h)
  4014      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  4015  
  4016      resp = client.post("/api/social/messages/send", json={
  4017          "to_user_id": bob["user_id"],
  4018          "content": "Hey Bob, how are you?",
  4019          "sender_mode": "real",
  4020          "receiver_mode": "real"
  4021      }, headers=alice_h)
  4022      assert resp.json()["success"] is True
  4023      assert "msg_id" in resp.json()
  4024      assert resp.json()["ai_reply"] is None  # No auto-reply in real mode
  4025  
  4026  
  4027  def test_send_real_to_twin(client, alice_h):
  4028      """Real → Twin: talking to someone's twin (triggers auto-reply)."""
  4029      resp = client.get("/api/social/friends", headers=alice_h)
  4030      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  4031  
  4032      resp = client.post("/api/social/messages/send", json={
  4033          "to_user_id": bob["user_id"],
  4034          "content": "Hey Bob's twin, what do you think?",
  4035          "sender_mode": "real",
  4036          "receiver_mode": "twin"
  4037      }, headers=alice_h)
  4038      assert resp.json()["success"] is True
  4039      reply = resp.json().get("ai_reply")
  4040      if reply:
  4041          assert reply["ai_generated"] is True
  4042  
  4043  
  4044  def test_send_twin_to_twin(client, alice_h):
  4045      """Twin → Twin: fully autonomous conversation."""
  4046      resp = client.get("/api/social/friends", headers=alice_h)
  4047      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  4048  
  4049      resp = client.post("/api/social/messages/send", json={
  4050          "to_user_id": bob["user_id"],
  4051          "content": "Twin-to-twin test",
  4052          "sender_mode": "twin",
  4053          "receiver_mode": "twin"
  4054      }, headers=alice_h)
  4055      assert resp.json()["success"] is True
  4056  
  4057  
  4058  def test_messages_after_send(client, alice_h):
  4059      """Should have messages in history now."""
  4060      resp = client.get("/api/social/friends", headers=alice_h)
  4061      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  4062  
  4063      resp = client.get(f"/api/social/messages?friend_id={bob['user_id']}", headers=alice_h)
  4064      assert resp.json()["success"] is True
  4065      assert len(resp.json()["messages"]) >= 3
  4066  
  4067  
  4068  def test_messages_from_bob_side(client, bob_h):
  4069      """Bob should also see the messages."""
  4070      resp = client.get("/api/social/friends", headers=bob_h)
  4071      alice = [f for f in resp.json()["friends"] if f["username"] == "alice"][0]
  4072  
  4073      resp = client.get(f"/api/social/messages?friend_id={alice['user_id']}", headers=bob_h)
  4074      assert resp.json()["success"] is True
  4075      assert len(resp.json()["messages"]) >= 3
  4076  
  4077  
  4078  # ═══ Unread ═══
  4079  
  4080  def test_unread_requires_auth(client):
  4081      resp = client.get("/api/social/unread")
  4082      assert resp.status_code == 401
  4083  
  4084  
  4085  def test_unread_count(client, alice_h):
  4086      """Send a new message, then check unread for Bob."""
  4087      resp = client.get("/api/social/friends", headers=alice_h)
  4088      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  4089  
  4090      client.post("/api/social/messages/send", json={
  4091          "to_user_id": bob["user_id"], "content": "unread test",
  4092          "sender_mode": "real", "receiver_mode": "real"
  4093      }, headers=alice_h)
  4094  
  4095      from dualsoul.auth import create_token
  4096      bob_h2 = {"Authorization": f"Bearer {create_token(bob['user_id'], 'bob')}"}
  4097      resp = client.get("/api/social/unread", headers=bob_h2)
  4098      assert resp.status_code == 200
  4099      assert resp.json()["count"] >= 1
  4100  
  4101  
  4102  # ═══ Translation ═══
  4103  
  4104  def test_translate_requires_auth(client):
  4105      resp = client.post("/api/social/translate", json={
  4106          "content": "hello", "target_lang": "zh"
  4107      })
  4108      assert resp.status_code == 401
  4109  
  4110  
  4111  def test_translate_empty_content(client, alice_h):
  4112      resp = client.post("/api/social/translate", json={
  4113          "content": "  ", "target_lang": "zh"
  4114      }, headers=alice_h)
  4115      assert resp.json()["success"] is False
  4116  
  4117  
  4118  def test_translate_no_target_lang(client, alice_h):
  4119      resp = client.post("/api/social/translate", json={
  4120          "content": "hello", "target_lang": ""
  4121      }, headers=alice_h)
  4122      assert resp.json()["success"] is False
  4123  
  4124  
  4125  def test_translate_no_ai_backend(client, alice_h):
  4126      """Without AI backend configured, translation should report unavailable."""
  4127      resp = client.post("/api/social/translate", json={
  4128          "content": "hello world", "source_lang": "en", "target_lang": "zh"
  4129      }, headers=alice_h)
  4130      data = resp.json()
  4131      # Either fails gracefully (no AI) or succeeds (AI configured)
  4132      assert "success" in data
  4133  
  4134  
  4135  def test_send_with_target_lang(client, alice_h):
  4136      """Send message with explicit target_lang for cross-language reply."""
  4137      resp = client.get("/api/social/friends", headers=alice_h)
  4138      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  4139  
  4140      resp = client.post("/api/social/messages/send", json={
  4141          "to_user_id": bob["user_id"],
  4142          "content": "Cross-language test",
  4143          "sender_mode": "real",
  4144          "receiver_mode": "twin",
  4145          "target_lang": "zh"
  4146      }, headers=alice_h)
  4147      assert resp.json()["success"] is True
  4148  
  4149  
  4150  def test_preferred_lang_in_profile(client, alice_h):
  4151      """Update preferred_lang and verify it appears in profile."""
  4152      resp = client.put("/api/identity/profile", json={
  4153          "preferred_lang": "en"
  4154      }, headers=alice_h)
  4155      assert resp.json()["success"] is True
  4156  
  4157      resp = client.get("/api/identity/me", headers=alice_h)
  4158      assert resp.json()["data"]["preferred_lang"] == "en"
  4159  
  4160  
  4161  def test_messages_include_translation_fields(client, alice_h):
  4162      """Messages should include translation metadata fields."""
  4163      resp = client.get("/api/social/friends", headers=alice_h)
  4164      bob = [f for f in resp.json()["friends"] if f["username"] == "bob"][0]
  4165  
  4166      resp = client.get(f"/api/social/messages?friend_id={bob['user_id']}", headers=alice_h)
  4167      assert resp.json()["success"] is True
  4168      msgs = resp.json()["messages"]
  4169      assert len(msgs) >= 1
  4170      # Check that translation fields exist in messages
  4171      msg = msgs[0]
  4172      assert "original_content" in msg or "content" in msg

# --- tests/test_twin.py ---
  4173  """Twin engine tests."""
  4174  
  4175  from dualsoul.protocol.message import (
  4176      ConversationMode,
  4177      DualSoulMessage,
  4178      IdentityMode,
  4179      get_conversation_mode,
  4180  )
  4181  
  4182  
  4183  def test_conversation_modes():
  4184      assert get_conversation_mode("real", "real") == ConversationMode.REAL_TO_REAL
  4185      assert get_conversation_mode("real", "twin") == ConversationMode.REAL_TO_TWIN
  4186      assert get_conversation_mode("twin", "real") == ConversationMode.TWIN_TO_REAL
  4187      assert get_conversation_mode("twin", "twin") == ConversationMode.TWIN_TO_TWIN
  4188  
  4189  
  4190  def test_message_to_dict():
  4191      msg = DualSoulMessage(
  4192          msg_id="sm_test123",
  4193          from_user_id="u_alice",
  4194          to_user_id="u_bob",
  4195          sender_mode=IdentityMode.REAL,
  4196          receiver_mode=IdentityMode.TWIN,
  4197          content="Hello twin!",
  4198      )
  4199      d = msg.to_dict()
  4200      assert d["sender_mode"] == "real"
  4201      assert d["receiver_mode"] == "twin"
  4202      assert d["conversation_mode"] == "real_to_twin"
  4203      assert d["ai_generated"] is False
  4204  
  4205  
  4206  def test_message_conversation_mode():
  4207      msg = DualSoulMessage(
  4208          msg_id="sm_test456",
  4209          from_user_id="u_a",
  4210          to_user_id="u_b",
  4211          sender_mode=IdentityMode.TWIN,
  4212          receiver_mode=IdentityMode.TWIN,
  4213          content="Twin chat",
  4214          ai_generated=True,
  4215      )
  4216      assert msg.conversation_mode == ConversationMode.TWIN_TO_TWIN
  4217      assert msg.ai_generated is True
  4218  
  4219  
  4220  def test_identity_mode_values():
  4221      assert IdentityMode.REAL.value == "real"
  4222      assert IdentityMode.TWIN.value == "twin"
