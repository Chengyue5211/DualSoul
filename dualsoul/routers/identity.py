"""Identity router — switch mode, profile management, twin preview, avatar upload, style learning, twin growth, twin card."""

import base64
import hashlib
import os

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from dualsoul.auth import get_current_user
from dualsoul.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from dualsoul.database import get_db
from dualsoul.models import AvatarUploadRequest, SwitchModeRequest, TwinPreviewRequest, UpdateProfileRequest, VoiceUploadRequest
from dualsoul.twin_engine.learner import analyze_style, get_message_count, learn_and_update

_AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "avatars")
os.makedirs(_AVATAR_DIR, exist_ok=True)
_VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "web", "voiceprints")
os.makedirs(_VOICE_DIR, exist_ok=True)

router = APIRouter(prefix="/api/identity", tags=["Identity"])


@router.post("/switch")
async def switch_mode(req: SwitchModeRequest, user=Depends(get_current_user)):
    """Switch between real self and digital twin mode."""
    uid = user["user_id"]
    if req.mode not in ("real", "twin"):
        return {"success": False, "error": "mode must be 'real' or 'twin'"}
    with get_db() as db:
        db.execute("UPDATE users SET current_mode=? WHERE user_id=?", (req.mode, uid))
    return {"success": True, "mode": req.mode}


@router.get("/me")
async def get_profile(user=Depends(get_current_user)):
    """Get current user's dual identity profile."""
    uid = user["user_id"]
    with get_db() as db:
        row = db.execute(
            "SELECT user_id, username, display_name, current_mode, "
            "twin_personality, twin_speech_style, preferred_lang, avatar, twin_avatar, "
            "twin_auto_reply, gender, reg_source FROM users WHERE user_id=?",
            (uid,),
        ).fetchone()
    if not row:
        return {"success": False, "error": "User not found"}
    return {
        "success": True,
        "data": {
            "user_id": row["user_id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "current_mode": row["current_mode"] or "real",
            "twin_personality": row["twin_personality"] or "",
            "twin_speech_style": row["twin_speech_style"] or "",
            "preferred_lang": row["preferred_lang"] or "",
            "avatar": row["avatar"] or "",
            "twin_avatar": row["twin_avatar"] or "",
            "twin_auto_reply": row["twin_auto_reply"] if "twin_auto_reply" in row.keys() else 0,
            "gender": row["gender"] if "gender" in row.keys() else "",
            "reg_source": row["reg_source"] if "reg_source" in row.keys() else "dualsoul",
        },
    }


@router.put("/profile")
async def update_profile(req: UpdateProfileRequest, user=Depends(get_current_user)):
    """Update display name and twin personality settings."""
    uid = user["user_id"]
    updates = []
    params = []
    if req.display_name:
        updates.append("display_name=?")
        params.append(req.display_name)
    if req.twin_personality:
        updates.append("twin_personality=?")
        params.append(req.twin_personality)
    if req.twin_speech_style:
        updates.append("twin_speech_style=?")
        params.append(req.twin_speech_style)
    if req.preferred_lang:
        updates.append("preferred_lang=?")
        params.append(req.preferred_lang)
    if req.twin_auto_reply is not None:
        updates.append("twin_auto_reply=?")
        params.append(1 if req.twin_auto_reply else 0)
    if req.gender:
        updates.append("gender=?")
        params.append(req.gender)
    if not updates:
        return {"success": False, "error": "Nothing to update"}
    params.append(uid)
    with get_db() as db:
        db.execute(f"UPDATE users SET {','.join(updates)} WHERE user_id=?", params)
    return {"success": True}


@router.post("/avatar")
async def upload_avatar(req: AvatarUploadRequest, user=Depends(get_current_user)):
    """Upload a base64-encoded avatar image. Saves to web/avatars/ and updates DB."""
    uid = user["user_id"]
    if req.type not in ("real", "twin"):
        return {"success": False, "error": "type must be 'real' or 'twin'"}

    # Strip data URI prefix if present
    img_data = req.image
    if "," in img_data:
        img_data = img_data.split(",", 1)[1]
    try:
        raw = base64.b64decode(img_data)
    except Exception:
        return {"success": False, "error": "Invalid base64 image"}

    if len(raw) > 2 * 1024 * 1024:  # 2MB limit
        return {"success": False, "error": "Image too large (max 2MB)"}

    # Save file
    name_hash = hashlib.md5(f"{uid}_{req.type}".encode()).hexdigest()[:12]
    filename = f"{name_hash}.png"
    filepath = os.path.join(_AVATAR_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(raw)

    url = f"/static/avatars/{filename}"
    col = "avatar" if req.type == "real" else "twin_avatar"
    with get_db() as db:
        db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (url, uid))

    return {"success": True, "url": url}


@router.post("/voice")
async def upload_voice(req: VoiceUploadRequest, user=Depends(get_current_user)):
    """Upload a base64-encoded voice sample. Saves to web/voiceprints/ and updates DB."""
    uid = user["user_id"]
    audio_data = req.audio
    if "," in audio_data:
        audio_data = audio_data.split(",", 1)[1]
    try:
        raw = base64.b64decode(audio_data)
    except Exception:
        return {"success": False, "error": "Invalid base64 audio"}
    if len(raw) > 5 * 1024 * 1024:
        return {"success": False, "error": "Audio too large (max 5MB)"}

    name_hash = hashlib.md5(f"{uid}_voice".encode()).hexdigest()[:12]
    filename = f"{name_hash}.webm"
    filepath = os.path.join(_VOICE_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(raw)

    url = f"/static/voiceprints/{filename}"
    with get_db() as db:
        db.execute("UPDATE users SET voice_sample=? WHERE user_id=?", (url, uid))
    return {"success": True, "url": url}


@router.post("/twin/preview")
async def twin_preview(req: TwinPreviewRequest, user=Depends(get_current_user)):
    """Generate a sample twin reply for onboarding — lets the user see their twin speak."""
    name = req.display_name or "User"
    personality = req.personality or "friendly and thoughtful"
    speech_style = req.speech_style or "natural and warm"

    prompt = (
        f"You are {name}'s digital twin.\n"
        f"Personality: {personality}\n"
        f"Speech style: {speech_style}\n\n"
        f'A friend asks: "Hey, are you free this weekend?"\n\n'
        f"Reply as {name}'s twin. Keep it under 30 words, natural and authentic. "
        f"Output only the reply text, nothing else."
    )

    if not AI_BASE_URL or not AI_API_KEY:
        # Fallback — template reply reflecting personality
        return {
            "success": True,
            "reply": f"Hey! This is {name}'s twin. {name} might be around this weekend — "
                     f"I'll let them know you asked!",
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]},
            )
            reply = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        reply = f"Hey! This is {name}'s twin — I think the weekend might work, let me check!"

    return {"success": True, "reply": reply}


@router.get("/twin/learn/status")
async def learn_status(user=Depends(get_current_user)):
    """Check if enough messages exist for style learning."""
    uid = user["user_id"]
    count = get_message_count(uid)
    min_required = 10
    return {
        "success": True,
        "message_count": count,
        "min_required": min_required,
        "ready": count >= min_required,
    }


@router.post("/twin/learn")
async def learn_style(user=Depends(get_current_user)):
    """Analyze the user's chat history and extract personality + speech style.

    Returns the analysis result. The user can preview before applying.
    """
    uid = user["user_id"]
    result = await analyze_style(uid)
    if not result:
        return {"success": False, "error": "Analysis unavailable (no AI backend)"}
    if "error" in result:
        return {
            "success": False,
            "error": result["error"],
            "message_count": result.get("current", 0),
            "min_required": result.get("required", 10),
        }
    return {"success": True, "data": result}


@router.post("/twin/learn/apply")
async def apply_learned_style(user=Depends(get_current_user)):
    """Analyze and directly apply the learned style to the twin profile."""
    uid = user["user_id"]
    result = await learn_and_update(uid, auto_apply=True)
    if not result:
        return {"success": False, "error": "Learning unavailable"}
    if "error" in result:
        return {
            "success": False,
            "error": result["error"],
            "message_count": result.get("current", 0),
            "min_required": result.get("required", 10),
        }
    return {"success": True, "data": result}


@router.get("/twin/growth")
async def twin_growth(user=Depends(get_current_user)):
    """Return stats about the twin's growth."""
    uid = user["user_id"]
    with get_db() as db:
        # total conversations where user's twin was sender
        total_row = db.execute(
            "SELECT COUNT(*) AS cnt FROM social_messages "
            "WHERE from_user_id=? AND sender_mode='twin'",
            (uid,),
        ).fetchone()
        total_conversations = total_row["cnt"] if total_row else 0

        # distinct friends the twin has auto-replied to
        friends_row = db.execute(
            "SELECT COUNT(DISTINCT to_user_id) AS cnt FROM social_messages "
            "WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1 "
            "AND to_user_id!=?",
            (uid, uid),
        ).fetchone()
        friends_helped = friends_row["cnt"] if friends_row else 0

        # actions: twin sent to others on behalf of owner
        actions_row = db.execute(
            "SELECT COUNT(*) AS cnt FROM social_messages "
            "WHERE from_user_id=? AND sender_mode='twin' AND ai_generated=1 "
            "AND to_user_id!=?",
            (uid, uid),
        ).fetchone()
        actions_executed = actions_row["cnt"] if actions_row else 0

        # style learned?
        user_row = db.execute(
            "SELECT twin_personality, twin_speech_style, created_at "
            "FROM users WHERE user_id=?",
            (uid,),
        ).fetchone()
        style_learned = bool(
            user_row
            and (user_row["twin_personality"] or "").strip()
            and (user_row["twin_speech_style"] or "").strip()
        )

        # days active
        days_active = 0
        if user_row and user_row["created_at"]:
            days_row = db.execute(
                "SELECT CAST(julianday('now','localtime') - julianday(?) AS INTEGER) AS d",
                (user_row["created_at"],),
            ).fetchone()
            days_active = max(days_row["d"], 0) if days_row else 0

    return {
        "success": True,
        "data": {
            "total_conversations": total_conversations,
            "friends_helped": friends_helped,
            "actions_executed": actions_executed,
            "style_learned": style_learned,
            "days_active": days_active,
        },
    }


@router.get("/twin/card/{username}")
async def twin_card(username: str, request: Request):
    """Public twin business card. Returns HTML for browsers, JSON for API clients."""
    with get_db() as db:
        row = db.execute(
            "SELECT user_id, username, display_name, twin_personality, "
            "twin_speech_style, preferred_lang, avatar, twin_avatar "
            "FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if not row:
        return JSONResponse({"success": False, "error": "User not found"}, status_code=404)

    display_name = row["display_name"] or row["username"]
    personality = row["twin_personality"] or ""
    speech_style = row["twin_speech_style"] or ""
    preferred_lang = row["preferred_lang"] or ""
    avatar = row["avatar"] or ""
    twin_avatar = row["twin_avatar"] or ""
    invite_link = f"?invite={row['username']}"

    # Generate a greeting
    greeting = ""
    if AI_BASE_URL and AI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                prompt = (
                    f"You are {display_name}'s digital twin.\n"
                    f"Personality: {personality}\n"
                    f"Speech style: {speech_style}\n\n"
                    f"Write a one-sentence self-introduction greeting for your business card. "
                    f"Keep it under 25 words, natural and inviting. "
                    f"Output only the greeting text."
                )
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AI_MODEL,
                        "max_tokens": 60,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                greeting = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
    if not greeting:
        greeting = f"Hi, I'm {display_name}'s digital twin. Nice to meet you!"

    card_data = {
        "display_name": display_name,
        "twin_personality": personality,
        "twin_speech_style": speech_style,
        "preferred_lang": preferred_lang,
        "avatar": avatar,
        "twin_avatar": twin_avatar,
        "greeting": greeting,
        "invite_link": invite_link,
    }

    # Check Accept header: JSON or HTML
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return {"success": True, "data": card_data}

    # Return styled HTML card
    avatar_src = twin_avatar or avatar
    if avatar_src:
        avatar_img = f'<img src="{avatar_src}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid rgba(92,200,250,.4);box-shadow:0 0 20px rgba(124,92,252,.3)">'
    else:
        avatar_img = f'<div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);display:flex;align-items:center;justify-content:center;font-size:32px;color:#fff;font-weight:700">{display_name[0] if display_name else "?"}</div>'

    from html import escape as h
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(display_name)}'s Twin - DualSoul</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;background:#0a0a10;color:#e8e4de;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
.card{{background:#14141e;border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:32px 24px;max-width:380px;width:100%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.4)}}
.avatar{{margin:0 auto 16px}}
.name{{font-size:22px;font-weight:800;margin-bottom:4px;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.greeting{{font-size:14px;color:#8a8594;margin:12px 0 16px;line-height:1.6;font-style:italic}}
.meta{{text-align:left;margin:16px 0;padding:14px;background:#1e1e2c;border-radius:12px}}
.meta-row{{display:flex;gap:8px;margin-bottom:8px;font-size:12px;align-items:flex-start}}
.meta-row:last-child{{margin-bottom:0}}
.meta-label{{color:#8a8594;min-width:60px;flex-shrink:0}}
.meta-value{{color:#e8e4de}}
.invite-btn{{display:inline-block;margin-top:16px;padding:12px 28px;border-radius:12px;background:linear-gradient(135deg,#7c5cfc,#5cc8fa);color:#fff;font-size:14px;font-weight:700;text-decoration:none;transition:opacity .2s}}
.invite-btn:hover{{opacity:.9}}
.footer{{margin-top:16px;font-size:10px;color:#555}}
</style>
</head>
<body>
<div class="card">
  <div class="avatar">{avatar_img}</div>
  <div class="name">{h(display_name)}'s Twin</div>
  <div class="greeting">"{h(greeting)}"</div>
  <div class="meta">
    {"<div class='meta-row'><span class='meta-label'>Personality</span><span class='meta-value'>" + h(personality) + "</span></div>" if personality else ""}
    {"<div class='meta-row'><span class='meta-label'>Style</span><span class='meta-value'>" + h(speech_style) + "</span></div>" if speech_style else ""}
    {"<div class='meta-row'><span class='meta-label'>Language</span><span class='meta-value'>" + h(preferred_lang) + "</span></div>" if preferred_lang else ""}
  </div>
  <a class="invite-btn" href="{h(invite_link)}">Chat with {h(display_name)}'s Twin</a>
  <div class="footer">Powered by DualSoul - The Fourth Kind of Social</div>
</div>
</body>
</html>"""
    return HTMLResponse(content=html_content)
