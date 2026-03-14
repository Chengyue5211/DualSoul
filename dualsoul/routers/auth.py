"""Auth router — register, login, and account management."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dualsoul.auth import create_token, get_current_user, hash_password, verify_password
from dualsoul.database import gen_id, get_db
from dualsoul.models import LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


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
        inviter_username = (req.invited_by or "").strip()
        db.execute(
            "INSERT INTO users (user_id, username, password_hash, display_name, reg_source, invited_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, hash_password(req.password), req.display_name or username,
             req.reg_source or "dualsoul", inviter_username),
        )
        # Increment inviter's invite_count (only if inviter actually exists)
        if inviter_username:
            inviter = db.execute(
                "SELECT user_id FROM users WHERE username=?", (inviter_username,)
            ).fetchone()
            if inviter:
                db.execute(
                    "UPDATE users SET invite_count = invite_count + 1 WHERE username=?",
                    (inviter_username,),
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


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user=Depends(get_current_user)):
    """Change password for the logged-in user."""
    uid = user["user_id"]
    if len(req.new_password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    with get_db() as db:
        row = db.execute(
            "SELECT password_hash FROM users WHERE user_id=?", (uid,)
        ).fetchone()
        if not row or not verify_password(req.old_password, row["password_hash"]):
            return {"success": False, "error": "Current password is incorrect"}
        db.execute(
            "UPDATE users SET password_hash=? WHERE user_id=?",
            (hash_password(req.new_password), uid),
        )
    return {"success": True}
