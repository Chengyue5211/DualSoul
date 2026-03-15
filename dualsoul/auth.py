"""DualSoul authentication — JWT + bcrypt."""

import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dualsoul.config import DATABASE_PATH, JWT_SECRET, JWT_EXPIRE_HOURS

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, username: str, token_gen: int = 0) -> str:
    """Create a JWT token with generation counter for invalidation."""
    payload = {
        "user_id": user_id,
        "username": username,
        "gen": token_gen,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency — extract and verify the current user from JWT."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = verify_token(credentials.credentials)
        # Verify token generation counter (password change invalidates old tokens)
        token_gen = payload.get("gen", 0)
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT token_gen FROM users WHERE user_id=?", (payload["user_id"],)
        ).fetchone()
        conn.close()
        if row:
            db_gen = row["token_gen"] if "token_gen" in row.keys() else 0
            if token_gen != db_gen:
                raise HTTPException(status_code=401, detail="Token invalidated — please login again")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
