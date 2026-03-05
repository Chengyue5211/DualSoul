"""DualSoul — Dual Identity Social Protocol server."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dualsoul import __version__
from dualsoul.config import CORS_ORIGINS, HOST, PORT
from dualsoul.database import init_db
from dualsoul.routers import auth, identity, social


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"[DualSoul v{__version__}] Database initialized")
    yield


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
app.include_router(identity.router)
app.include_router(social.router)

# Serve demo web client
_web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.isdir(_web_dir):
    app.mount("/static", StaticFiles(directory=_web_dir), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(_web_dir, "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": __version__}


def cli():
    """CLI entry point for `dualsoul` command."""
    import uvicorn

    uvicorn.run("dualsoul.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    cli()
