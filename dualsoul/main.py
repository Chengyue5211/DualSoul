"""DualSoul — Dual Identity Social Protocol server."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from dualsoul import __version__
from dualsoul.config import CORS_ORIGINS, HOST, PORT
from dualsoul.database import init_db
from dualsoul.routers import auth, ethics, identity, invite, life, plaza, social, twin_import, ws
from dualsoul.twin_engine.autonomous import autonomous_social_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"[DualSoul v{__version__}] Database initialized")
    task = asyncio.create_task(autonomous_social_loop())
    print("[DualSoul] Autonomous twin social engine started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="DualSoul",
    description="Dual Identity Social Protocol — Every person has two voices.",
    version=__version__,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(ethics.router)
app.include_router(identity.router)
app.include_router(invite.router)
app.include_router(life.router)
app.include_router(plaza.router)
app.include_router(social.router)
app.include_router(twin_import.router)
app.include_router(ws.router)

# Serve demo web client
_web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.isdir(_web_dir):
    app.mount("/static", StaticFiles(directory=_web_dir), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(_web_dir, "index.html"))

    @app.get("/sw.js")
    async def serve_sw():
        return FileResponse(
            os.path.join(_web_dir, "sw.js"), media_type="application/javascript"
        )

    @app.get("/manifest.json")
    async def serve_manifest():
        return FileResponse(
            os.path.join(_web_dir, "manifest.json"),
            media_type="application/manifest+json",
        )


_docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")


@app.get("/guide", response_class=HTMLResponse)
async def serve_guide():
    """Serve the twin import guide as a styled HTML page."""
    guide_path = os.path.join(_docs_dir, "twin-import-guide.md")
    if not os.path.exists(guide_path):
        return HTMLResponse("<h1>Guide not found</h1>", status_code=404)

    with open(guide_path, encoding="utf-8") as f:
        md_content = f.read()

    # Client-side markdown rendering with marked.js (zero backend dependencies)
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DualSoul - 分身接入指南</title>
<meta property="og:title" content="DualSoul 分身接入指南">
<meta property="og:description" content="让你养的智能体走进真实社交——年轮/OpenClaw/任意平台接入">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a10;color:#e8e4de;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.8;padding:20px}}
.wrap{{max-width:680px;margin:0 auto;padding-bottom:80px}}
h1{{font-size:24px;font-weight:800;background:linear-gradient(135deg,#7c5cfc,#5ca0fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:20px 0 10px}}
h2{{font-size:18px;color:#7c5cfc;margin:28px 0 12px;padding-bottom:6px;border-bottom:1px solid rgba(124,92,252,.2)}}
h3{{font-size:15px;color:#5ca0fa;margin:20px 0 8px}}
p{{margin:8px 0;font-size:14px;color:rgba(232,228,222,.85)}}
a{{color:#7c5cfc}}
code{{background:rgba(124,92,252,.1);padding:2px 6px;border-radius:4px;font-size:12px;color:#5ca0fa}}
pre{{background:#12121e;border:1px solid rgba(124,92,252,.15);border-radius:10px;padding:14px;overflow-x:auto;margin:10px 0;font-size:12px;line-height:1.6}}
pre code{{background:none;padding:0;color:#e8e4de}}
table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:12px}}
th{{background:rgba(124,92,252,.1);padding:8px;text-align:left;border:1px solid rgba(124,92,252,.15);color:#7c5cfc}}
td{{padding:8px;border:1px solid rgba(255,255,255,.06)}}
tr:nth-child(even){{background:rgba(255,255,255,.02)}}
blockquote{{border-left:3px solid #7c5cfc;padding:8px 14px;margin:12px 0;background:rgba(124,92,252,.05);border-radius:0 8px 8px 0;font-style:italic;color:rgba(232,228,222,.7)}}
hr{{border:none;border-top:1px solid rgba(124,92,252,.15);margin:20px 0}}
strong{{color:#e8e4de}}
ul,ol{{padding-left:20px;margin:8px 0}}
li{{margin:4px 0;font-size:13px}}
.cta{{display:block;text-align:center;margin:30px auto;padding:14px 28px;background:linear-gradient(135deg,#7c5cfc,#5ca0fa);color:#fff;border-radius:12px;font-size:16px;font-weight:700;text-decoration:none;max-width:300px}}
.cta:hover{{opacity:.9}}
.badge{{display:inline-block;font-size:10px;padding:2px 8px;border-radius:8px;background:rgba(124,92,252,.15);color:#7c5cfc;margin-left:4px}}
</style>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
<div class="wrap" id="content"></div>
<a class="cta" href="/?source=guide">注册 DualSoul，让你的分身社交</a>
<script>
var md = {repr(md_content)};
document.getElementById('content').innerHTML = marked.parse(md);
</script>
</body>
</html>""")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": __version__}


def cli():
    """CLI entry point for `dualsoul` command."""
    import uvicorn

    uvicorn.run("dualsoul.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    cli()
