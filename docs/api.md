# DualSoul API Reference

Base URL: `http://localhost:8000`

All endpoints except `/api/auth/*` and `/api/health` require a JWT token in the `Authorization: Bearer <token>` header.

---

## Auth

### POST /api/auth/register

Register a new user.

**Request:**
```json
{
  "username": "alice",
  "password": "secret123",
  "display_name": "Alice"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "u_a1b2c3d4e5f6",
    "username": "alice",
    "token": "eyJ..."
  }
}
```

### POST /api/auth/login

**Request:**
```json
{
  "username": "alice",
  "password": "secret123"
}
```

**Response:** Same as register.

---

## Identity

### POST /api/identity/switch

Switch between Real and Twin mode.

**Request:**
```json
{ "mode": "twin" }
```

**Response:**
```json
{ "success": true, "mode": "twin" }
```

### GET /api/identity/me

Get your dual identity profile.

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "u_a1b2c3d4e5f6",
    "username": "alice",
    "display_name": "Alice",
    "current_mode": "real",
    "twin_personality": "friendly and thoughtful",
    "twin_speech_style": "casual and warm",
    "preferred_lang": "en",
    "avatar": "",
    "twin_avatar": ""
  }
}
```

### PUT /api/identity/profile

Update twin personality settings.

**Request:**
```json
{
  "twin_personality": "analytical and curious",
  "twin_speech_style": "concise, uses technical terms",
  "preferred_lang": "en"
}
```

---

## Social

### POST /api/social/friends/add

Send a friend request by username.

**Request:**
```json
{ "friend_username": "bob" }
```

### POST /api/social/friends/respond

Accept or block a friend request.

**Request:**
```json
{ "conn_id": "sc_abc123", "action": "accept" }
```

### GET /api/social/friends

List all friends with their dual identity info.

**Response:**
```json
{
  "success": true,
  "friends": [
    {
      "conn_id": "sc_abc123",
      "status": "accepted",
      "is_incoming": false,
      "user_id": "u_bob456",
      "username": "bob",
      "display_name": "Bob",
      "current_mode": "twin",
      "accepted_at": "2026-03-05 10:30:00"
    }
  ]
}
```

### GET /api/social/messages?friend_id=xxx&limit=50

Get conversation history. Messages are returned in chronological order. Unread messages from this friend are automatically marked as read.

### POST /api/social/messages/send

Send a message. If `receiver_mode` is `"twin"`, the recipient's twin auto-replies.

**Request:**
```json
{
  "to_user_id": "u_bob456",
  "content": "Hey, what do you think?",
  "sender_mode": "real",
  "receiver_mode": "twin",
  "target_lang": ""
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `to_user_id` | string | required | Recipient's user ID |
| `content` | string | required | Message text (non-empty) |
| `sender_mode` | string | `"real"` | `"real"` or `"twin"` |
| `receiver_mode` | string | `"real"` | `"real"` or `"twin"` |
| `msg_type` | string | `"text"` | `"text"`, `"image"`, `"voice"`, or `"system"` |
| `target_lang` | string | `""` | If set, Twin replies in this language with personality preservation |

**Response:**
```json
{
  "success": true,
  "msg_id": "sm_def789",
  "ai_reply": {
    "msg_id": "sm_ghi012",
    "content": "That's an interesting point! I'd say...",
    "ai_generated": true,
    "target_lang": "en",
    "translation_style": "personality_preserving"
  }
}
```

**Cross-language auto-detection:** When `target_lang` is empty but the sender and receiver have different `preferred_lang` settings, the Twin automatically replies in the sender's language.

### POST /api/social/translate

Personality-preserving translation — translate text as if the user wrote it in another language, preserving their humor, tone, and characteristic expressions.

**Request:**
```json
{
  "content": "这个方案太牛了！",
  "source_lang": "zh",
  "target_lang": "en"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | string | required | Text to translate |
| `source_lang` | string | `"auto"` | Source language ISO 639-1 code |
| `target_lang` | string | `"en"` | Target language ISO 639-1 code |

**Response:**
```json
{
  "success": true,
  "data": {
    "translated_content": "This plan is absolutely brilliant!",
    "original_content": "这个方案太牛了！",
    "source_lang": "zh",
    "target_lang": "en",
    "translation_style": "personality_preserving"
  }
}
```

**Note:** Requires an AI backend to be configured. Returns `{"success": false, "error": "Translation unavailable (no AI backend)"}` otherwise.

### GET /api/social/unread

Get unread message count.

**Response:**
```json
{ "count": 3 }
```

---

## Health

### GET /api/health

```json
{ "status": "ok", "version": "0.3.0" }
```
