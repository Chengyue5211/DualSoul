"""DualSoul configuration — all settings from environment variables."""

import logging
import os
import secrets

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Database
DATABASE_PATH = os.getenv("DUALSOUL_DATABASE_PATH", "./dualsoul.db")

# JWT — persist secret across restarts even if env var not set
JWT_SECRET = os.getenv("DUALSOUL_JWT_SECRET", "")
if not JWT_SECRET:
    _secret_file = os.path.join(os.path.dirname(DATABASE_PATH), ".jwt_secret")
    try:
        if os.path.exists(_secret_file):
            with open(_secret_file) as _f:
                JWT_SECRET = _f.read().strip()
        if not JWT_SECRET:
            JWT_SECRET = secrets.token_hex(32)
            with open(_secret_file, "w") as _f:
                _f.write(JWT_SECRET)
            logger.info("Generated persistent JWT secret saved to .jwt_secret")
    except OSError:
        JWT_SECRET = secrets.token_hex(32)
        logger.warning("Could not persist JWT secret. Tokens will expire on restart.")

JWT_EXPIRE_HOURS = int(os.getenv("DUALSOUL_JWT_EXPIRE_HOURS", "72"))

# AI Backend (OpenAI-compatible API)
AI_BASE_URL = os.getenv("DUALSOUL_AI_BASE_URL", "")
AI_API_KEY = os.getenv("DUALSOUL_AI_KEY", "")
AI_MODEL = os.getenv("DUALSOUL_AI_MODEL", "gpt-3.5-turbo")
AI_VISION_MODEL = os.getenv("DUALSOUL_AI_VISION_MODEL", "qwen-vl-plus")

# Server
HOST = os.getenv("DUALSOUL_HOST", "0.0.0.0")
PORT = int(os.getenv("DUALSOUL_PORT", "8000"))

# CORS
CORS_ORIGINS = os.getenv("DUALSOUL_CORS_ORIGINS", "*").split(",")
