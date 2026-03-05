"""DualSoul configuration — all settings from environment variables."""

import os
import secrets

from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_PATH = os.getenv("DUALSOUL_DATABASE_PATH", "./dualsoul.db")

# JWT
JWT_SECRET = os.getenv("DUALSOUL_JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    print("[DualSoul] WARNING: No JWT_SECRET set. Using random secret (tokens won't persist across restarts).")

JWT_EXPIRE_HOURS = int(os.getenv("DUALSOUL_JWT_EXPIRE_HOURS", "72"))

# AI Backend (OpenAI-compatible API)
AI_BASE_URL = os.getenv("DUALSOUL_AI_BASE_URL", "")
AI_API_KEY = os.getenv("DUALSOUL_AI_KEY", "")
AI_MODEL = os.getenv("DUALSOUL_AI_MODEL", "gpt-3.5-turbo")

# Server
HOST = os.getenv("DUALSOUL_HOST", "0.0.0.0")
PORT = int(os.getenv("DUALSOUL_PORT", "8000"))

# CORS
CORS_ORIGINS = os.getenv("DUALSOUL_CORS_ORIGINS", "*").split(",")
