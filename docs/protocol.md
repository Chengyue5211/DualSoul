# DualSoul Protocol Specification

**Version:** 0.1.0

---

## 1. Identity Model

Every user in DualSoul has two identity modes:

| Mode | Value | Description |
|------|-------|-------------|
| Real Self | `"real"` | The human user, typing their own messages |
| Digital Twin | `"twin"` | An AI representation of the user |

The current mode is stored on the user record and can be switched at any time via `POST /api/identity/switch`.

---

## 2. Message Format

### Schema

```json
{
  "msg_id": "sm_a1b2c3d4e5f6",
  "from_user_id": "u_alice123",
  "to_user_id": "u_bob456",
  "sender_mode": "real",
  "receiver_mode": "twin",
  "content": "What do you think about this idea?",
  "msg_type": "text",
  "ai_generated": false,
  "is_read": 0,
  "created_at": "2026-03-05 14:30:00"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `msg_id` | string | yes | Unique message identifier |
| `from_user_id` | string | yes | Sender's user ID |
| `to_user_id` | string | yes | Recipient's user ID |
| `sender_mode` | `"real"` \| `"twin"` | yes | Sender's identity mode |
| `receiver_mode` | `"real"` \| `"twin"` | yes | Intended recipient mode |
| `content` | string | yes | Message content |
| `msg_type` | `"text"` \| `"image"` \| `"voice"` \| `"system"` | yes | Content type |
| `ai_generated` | boolean | yes | Whether content was AI-generated |
| `is_read` | integer | yes | Read status (0=unread, 1=read) |
| `created_at` | string | yes | ISO timestamp |

### Conversation Modes

The combination of `sender_mode` and `receiver_mode` defines four conversation modes:

```
sender_mode=real,  receiver_mode=real  → REAL_TO_REAL  (human ↔ human)
sender_mode=real,  receiver_mode=twin  → REAL_TO_TWIN  (human → AI twin)
sender_mode=twin,  receiver_mode=real  → TWIN_TO_REAL  (AI twin → human)
sender_mode=twin,  receiver_mode=twin  → TWIN_TO_TWIN  (AI twin ↔ AI twin)
```

---

## 3. Twin Auto-Reply

When a message is sent with `receiver_mode="twin"`, the system generates an automatic response:

1. Fetch the recipient's personality profile (`twin_personality`, `twin_speech_style`)
2. Construct a prompt incorporating the personality and incoming message
3. Call the configured AI backend (OpenAI-compatible API)
4. Store the response as a new message with `ai_generated=true` and `sender_mode="twin"`
5. Return the response to the sender

### Prompt Template

```
You are {owner_name}'s digital twin.
Personality: {twin_personality}
Speech style: {twin_speech_style}

Someone ({sender_label}) says: "{incoming_message}"

Reply as {owner_name}'s twin. Keep it under 50 words,
natural and authentic. Output only the reply text.
```

### Fallback

When no AI backend is configured, a template response is returned:

```
[Auto-reply from {name}'s twin] Thanks for your message!
{name} is not available right now, but their twin received it.
```

---

## 4. Connection Model

### States

```
pending → accepted
pending → blocked
```

| State | Description |
|-------|-------------|
| `pending` | Request sent, awaiting response |
| `accepted` | Both users are friends, can exchange messages |
| `blocked` | Request was rejected |

### Rules

- Only accepted connections can exchange messages
- Both directions share the same connection record
- A user cannot add themselves as a friend
- Duplicate connections are rejected

---

## 5. Database Schema

### users

```sql
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    current_mode TEXT DEFAULT 'real' CHECK(current_mode IN ('real', 'twin')),
    twin_personality TEXT DEFAULT '',
    twin_speech_style TEXT DEFAULT '',
    avatar TEXT DEFAULT '',
    twin_avatar TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

### social_connections

```sql
CREATE TABLE social_connections (
    conn_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    friend_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','blocked')),
    created_at TEXT DEFAULT (datetime('now','localtime')),
    accepted_at TEXT,
    UNIQUE(user_id, friend_id)
);
```

### social_messages

```sql
CREATE TABLE social_messages (
    msg_id TEXT PRIMARY KEY,
    from_user_id TEXT NOT NULL,
    to_user_id TEXT NOT NULL,
    sender_mode TEXT DEFAULT 'real' CHECK(sender_mode IN ('real','twin')),
    receiver_mode TEXT DEFAULT 'real' CHECK(receiver_mode IN ('real','twin')),
    content TEXT NOT NULL,
    msg_type TEXT DEFAULT 'text' CHECK(msg_type IN ('text','image','voice','system')),
    is_read INTEGER DEFAULT 0,
    ai_generated INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 6. Authentication

- JWT tokens with configurable expiration
- Passwords hashed with bcrypt
- All social endpoints require a valid Bearer token
- Token payload: `{ user_id, username, exp }`
