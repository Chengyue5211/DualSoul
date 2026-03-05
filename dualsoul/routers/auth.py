"""Auth router — register and login."""

from fastapi import APIRouter

from dualsoul.auth import create_token, hash_password, verify_password
from dualsoul.database import gen_id, get_db
from dualsoul.models import LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register")
async def register(req: RegisterRequest):
    """Register a new user."""
    username = req.username.strip()
    if not username or len(username) < 2:
        return {"success": False, "error": "Username must be at least 2 characters"}
    if len(req.password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    with get_db() as db:
        exists = db.execute(
            "SELECT user_id FROM users WHERE username=?", (username,)
        ).fetchone()
        if exists:
            return {"success": False, "error": "Username already taken"}

        user_id = gen_id("u_")
        db.execute(
            "INSERT INTO users (user_id, username, password_hash, display_name) "
            "VALUES (?, ?, ?, ?)",
            (user_id, username, hash_password(req.password), req.display_name or username),
        )

    token = create_token(user_id, username)
    return {
        "success": True,
        "data": {
            "user_id": user_id,
            "username": username,
            "token": token,
        },
    }


@router.post("/login")
async def login(req: LoginRequest):
    """Login and get a JWT token."""
    with get_db() as db:
        user = db.execute(
            "SELECT user_id, username, password_hash FROM users WHERE username=?",
            (req.username.strip(),),
        ).fetchone()

    if not user or not verify_password(req.password, user["password_hash"]):
        return {"success": False, "error": "Invalid username or password"}

    token = create_token(user["user_id"], user["username"])
    return {
        "success": True,
        "data": {
            "user_id": user["user_id"],
            "username": user["username"],
            "token": token,
        },
    }
