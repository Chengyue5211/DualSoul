# Dual Identity Social Protocol (DISP) — Technical Specification

**Version:** 1.1.0
**Status:** Stable
**Author:** Chengyue5211
**Date:** March 5, 2026

---

## 1. Overview

This document defines the Dual Identity Social Protocol (DISP) at the wire level. It specifies the data formats, state machines, invariants, and behavioral rules that any conforming implementation MUST follow.

For the motivation, theory, and design rationale, see the [White Paper](whitepaper.md).

---

## 2. Identity Model

### 2.1 Identity Mode

Every user in a DISP system operates in exactly one of two identity modes at any given time:

```
IdentityMode ::= "real" | "twin"
```

| Mode | Value | Operator | Content Origin |
|------|-------|----------|----------------|
| Real Self | `"real"` | Human user | Human-typed |
| Digital Twin | `"twin"` | AI agent | AI-generated |

### 2.2 User Record

```
User ::= {
    user_id          : String,        -- Unique identifier (prefix: "u_")
    username         : String,        -- Unique login name
    password_hash    : String,        -- bcrypt hash
    display_name     : String,        -- Human-readable name
    current_mode     : IdentityMode,  -- Active identity mode
    twin_personality : String,        -- Natural-language personality traits
    twin_speech_style: String,        -- Natural-language speech patterns
    avatar           : String,        -- Real self avatar URL
    twin_avatar      : String,        -- Digital twin avatar URL
    created_at       : Timestamp      -- Account creation time
}
```

### 2.3 Identity Switch

Switching identity mode is an atomic operation:

```
switch(user, new_mode) ::=
    REQUIRE new_mode ∈ {"real", "twin"}
    REQUIRE new_mode ≠ user.current_mode  -- No-op if same
    user.current_mode ← new_mode
    RETURN {success: true, mode: new_mode}
```

---

## 3. Message Format

### 3.1 Schema

```
DISPMessage ::= {
    disp_version  : String,        -- Protocol version (e.g. "1.1")
    msg_id        : String,        -- Unique identifier (prefix: "sm_")
    from_user_id  : String,        -- Sender's user_id
    to_user_id    : String,        -- Receiver's user_id
    sender_mode   : IdentityMode,  -- Sender's identity mode
    receiver_mode : IdentityMode,  -- Intended receiver identity mode
    content       : String,        -- Message payload (non-empty)
    original_content : String,     -- Original text before translation (empty if not translated)
    original_lang    : String,     -- Source language ISO 639-1 code (empty if not translated)
    target_lang      : String,     -- Target language ISO 639-1 code (empty if not translated)
    translation_style: TranslationStyle,  -- Translation method used
    msg_type      : MessageType,   -- Content type
    ai_generated  : Boolean,       -- true if content was AI-produced
    is_read       : Integer,       -- 0 = unread, 1 = read
    created_at    : Timestamp      -- Creation time (ISO 8601)
}

MessageType      ::= "text" | "image" | "voice" | "system"
TranslationStyle ::= "" | "literal" | "personality_preserving"
```

### 3.2 JSON Wire Format

```json
{
  "disp_version":  "1.1",
  "msg_id":        "sm_a1b2c3d4e5f6",
  "from_user_id":  "u_sender12345",
  "to_user_id":    "u_receiver6789",
  "sender_mode":   "real",
  "receiver_mode": "twin",
  "content":       "What do you think about this idea?",
  "original_content": "",
  "original_lang":   "",
  "target_lang":     "",
  "translation_style": "",
  "msg_type":      "text",
  "ai_generated":  false,
  "is_read":       0,
  "created_at":    "2026-03-05 14:30:00"
}
```

### 3.3 Invariants

A conforming implementation MUST enforce:

| # | Invariant | Rule |
|---|-----------|------|
| I1 | Identity Integrity | `sender_mode = "real"` → `ai_generated = false` |
| I2 | Twin Marking | `ai_generated = true` → message was produced by Twin engine |
| I3 | Connection Gate | Messages require `status = "accepted"` between sender and receiver |
| I4 | No Self-Message | `from_user_id ≠ to_user_id` |
| I5 | Content Non-Empty | `len(content.strip()) > 0` |
| I6 | Immutability | `sender_mode`, `receiver_mode`, `ai_generated` are write-once |
| I7 | Version Presence | Every message MUST include `disp_version` |
| I8 | Auto-Reply Termination | An auto-reply (`ai_generated = true`) MUST NOT trigger further auto-replies |

---

## 4. Conversation Modes

### 4.1 Mode Space

The conversation mode is defined as the ordered pair `(sender_mode, receiver_mode)`:

```
ConversationMode ::= IdentityMode × IdentityMode

    = { (real, real),   -- R→R: Human ↔ Human
        (real, twin),   -- R→T: Human → AI Twin
        (twin, real),   -- T→R: AI Twin → Human
        (twin, twin) }  -- T→T: AI Twin ↔ AI Twin
```

### 4.2 Mode Behavior Matrix

```
                        ┌─────────────────────────────────────────┐
                        │           RECEIVER MODE                  │
                        │    real              twin                 │
              ┌─────────┼──────────────────┬───────────────────────┤
              │  real    │  R→R             │  R→T                  │
   SENDER     │         │  No AI involved  │  Twin auto-replies    │
   MODE       │         │  Standard chat   │  AI marks response    │
              ├─────────┼──────────────────┼───────────────────────┤
              │  twin    │  T→R             │  T→T                  │
              │         │  Twin initiates  │  Fully autonomous     │
              │         │  Human receives  │  Both sides are AI    │
              └─────────┴──────────────────┴───────────────────────┘
```

### 4.3 Auto-Reply Rules

| Condition | Auto-Reply? | Responder |
|-----------|:-----------:|-----------|
| `receiver_mode = "real"` | No | — |
| `receiver_mode = "twin"` | Yes | Receiver's Digital Twin |

### 4.4 T→T Termination Rule

To prevent unbounded recursive auto-replies in Twin-to-Twin conversations:

1. **No Cascading Auto-Reply:** A Twin auto-reply (message where `ai_generated = true`) MUST NOT trigger a further auto-reply. Only messages initiated by a human action or an explicit orchestration request may trigger Twin responses.

2. **Autonomous Session Limit:** When a client explicitly initiates a multi-turn T→T session, the implementation MUST enforce `max_autonomous_rounds` (default: 10). After the limit is reached, the session terminates and both Twin owners are notified.

3. **Explicit Initiation:** T→T sessions require a human on at least one side to initiate the first message. Fully autonomous initiation (where a Twin decides on its own to start a conversation) is NOT permitted in DISP v1.0.

---

## 5. Twin Auto-Reply Protocol

### 5.1 Trigger Condition

Auto-reply is triggered when and only when `receiver_mode = "twin"` in the incoming message.

### 5.2 Sequence Diagram

```
 Client (Sender)              DISP Server                    AI Backend
       │                           │                              │
       │  1. POST /messages/send   │                              │
       │  {sender_mode, receiver_  │                              │
       │   mode:"twin", content}   │                              │
       │ ─────────────────────────►│                              │
       │                           │                              │
       │                           │  2. Validate connection      │
       │                           │     (status = "accepted")    │
       │                           │                              │
       │                           │  3. Store sender's message   │
       │                           │     (ai_generated = false)   │
       │                           │                              │
       │                           │  4. Load receiver's          │
       │                           │     TwinProfile              │
       │                           │                              │
       │                           │  5. Construct prompt         │
       │                           │     (personality + message)  │
       │                           │                              │
       │                           │  6. POST /chat/completions   │
       │                           │ ─────────────────────────────►
       │                           │                              │
       │                           │  7. AI response              │
       │                           │ ◄─────────────────────────── │
       │                           │                              │
       │                           │  8. Store twin reply         │
       │                           │     (ai_generated = true,    │
       │                           │      sender_mode = "twin",   │
       │                           │      receiver_mode = sender_ │
       │                           │      mode of original msg)   │
       │                           │                              │
       │  9. Response {msg_id,     │                              │
       │     ai_reply: {msg_id,    │                              │
       │     content, ai_generated │                              │
       │     : true}}              │                              │
       │ ◄─────────────────────────│                              │
```

### 5.3 Prompt Template

```
You are {owner_name}'s digital twin.
Personality: {twin_personality}
Speech style: {twin_speech_style}

Someone ({sender_label}) says: "{incoming_message}"

Reply as {owner_name}'s twin. Keep it natural and authentic.
Output only the reply text, nothing else.
```

Where:
- `{owner_name}` = display_name of the Twin's owner
- `{twin_personality}` = owner's twin_personality field
- `{twin_speech_style}` = owner's twin_speech_style field
- `{sender_label}` = `"{sender}'s real self"` if sender_mode="real", else `"{sender}'s twin"`
- `{incoming_message}` = the message content

### 5.4 Fallback Behavior

When no AI backend is configured (`AI_BASE_URL` is empty), the Twin MUST return a template response:

```
[Auto-reply from {name}'s twin] Thanks for your message!
{name} is not available right now, but their twin received it.
```

This ensures protocol consistency: a message with `receiver_mode = "twin"` ALWAYS produces a response.

---

## 6. Social Connection Model

### 6.1 Connection Record

```
SocialConnection ::= {
    conn_id     : String,            -- Unique identifier (prefix: "sc_")
    user_id     : String,            -- Requester's user_id
    friend_id   : String,            -- Recipient's user_id
    status      : ConnectionStatus,  -- Current state
    created_at  : Timestamp,         -- Request time
    accepted_at : Timestamp | null   -- Acceptance time (null if not accepted)
}

ConnectionStatus ::= "pending" | "accepted" | "blocked"
```

### 6.2 State Machine

```
                              respond("accept")
             ┌──────────┐  ──────────────────►  ┌──────────┐
add_friend() │          │                       │          │
────────────►│ pending  │                       │ accepted │
             │          │                       │          │
             └──────┬───┘                       └──────────┘
                    │
                    │ respond("block")
                    ▼
             ┌──────────┐
             │ blocked  │
             └──────────┘
```

### 6.3 Rules

1. **Uniqueness:** At most one connection may exist between any two users.
2. **Directionality:** The connection record stores `user_id` (requester) and `friend_id` (recipient). Both directions use the same record.
3. **Authorization:** Only `friend_id` may respond to a pending request.
4. **Message Gate:** Messages require `status = "accepted"`.

---

## 7. Authentication

### 7.1 Token Format

DISP uses JSON Web Tokens (JWT) for stateless authentication:

```json
{
  "user_id": "u_a1b2c3d4e5f6",
  "username": "alice",
  "exp": 1741234567
}
```

### 7.2 Password Storage

Passwords are hashed using bcrypt with automatic salt generation. The raw password is never stored or logged.

### 7.3 Request Authentication

All endpoints except `/api/auth/*` and `/api/health` require:

```
Authorization: Bearer <jwt_token>
```

---

## 8. Database Schema

### 8.1 Users Table

```sql
CREATE TABLE users (
    user_id           TEXT PRIMARY KEY,
    username          TEXT NOT NULL UNIQUE,
    password_hash     TEXT NOT NULL,
    display_name      TEXT DEFAULT '',
    current_mode      TEXT DEFAULT 'real'
                      CHECK(current_mode IN ('real', 'twin')),
    twin_personality  TEXT DEFAULT '',
    twin_speech_style TEXT DEFAULT '',
    avatar            TEXT DEFAULT '',
    twin_avatar       TEXT DEFAULT '',
    created_at        TEXT DEFAULT (datetime('now','localtime'))
);
```

### 8.2 Social Connections Table

```sql
CREATE TABLE social_connections (
    conn_id     TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    friend_id   TEXT NOT NULL,
    status      TEXT DEFAULT 'pending'
                CHECK(status IN ('pending','accepted','blocked')),
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    accepted_at TEXT,
    UNIQUE(user_id, friend_id)
);
```

### 8.3 Social Messages Table

```sql
CREATE TABLE social_messages (
    msg_id        TEXT PRIMARY KEY,
    from_user_id  TEXT NOT NULL,
    to_user_id    TEXT NOT NULL,
    sender_mode   TEXT DEFAULT 'real'
                  CHECK(sender_mode IN ('real','twin')),
    receiver_mode TEXT DEFAULT 'real'
                  CHECK(receiver_mode IN ('real','twin')),
    content       TEXT NOT NULL,
    msg_type      TEXT DEFAULT 'text'
                  CHECK(msg_type IN ('text','image','voice','system')),
    is_read       INTEGER DEFAULT 0,
    ai_generated  INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 9. API Endpoint Summary

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| POST | `/api/auth/register` | No | Create a new dual-identity account |
| POST | `/api/auth/login` | No | Authenticate and receive JWT |
| POST | `/api/identity/switch` | Yes | Switch between Real and Twin mode |
| GET | `/api/identity/me` | Yes | Get dual identity profile |
| PUT | `/api/identity/profile` | Yes | Update Twin personality settings |
| POST | `/api/social/friends/add` | Yes | Send friend request by username |
| POST | `/api/social/friends/respond` | Yes | Accept or block friend request |
| GET | `/api/social/friends` | Yes | List friends with dual identity info |
| GET | `/api/social/messages` | Yes | Get conversation history |
| POST | `/api/social/messages/send` | Yes | Send message (triggers Twin auto-reply) |
| POST | `/api/social/translate` | Yes | Personality-preserving translation |
| GET | `/api/social/unread` | Yes | Get unread message count |
| GET | `/api/health` | No | Health check |

For detailed request/response formats, see [api.md](api.md).

---

## 10. Cross-Language Translation Protocol

### 10.1 Overview

DISP v1.1 introduces **personality-preserving translation** as a protocol-level feature. When users who speak different languages interact through their Digital Twins, the Twin does not merely translate words — it expresses the same intent as if the owner were natively fluent in the target language, preserving humor, tone, formality, and characteristic expressions.

### 10.2 User Language Preference

Each user record includes a `preferred_lang` field (ISO 639-1 code):

```
User (v1.1 addition) ::= {
    ...
    preferred_lang : String  -- ISO 639-1 code ("zh", "en", "ja", etc.) or ""
}
```

Supported language codes: `zh`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `pt`, `ru`, `ar`, `hi`, `th`, `vi`, `id`.

### 10.3 Auto-Detection Rules

Cross-language translation is triggered automatically during Twin auto-reply:

```
detect_cross_language(sender, receiver) ::=
    IF receiver_mode ≠ "twin"
        RETURN ""  -- No auto-reply, no translation
    IF sender.preferred_lang = "" OR receiver.preferred_lang = ""
        RETURN ""  -- Language preference not set
    IF sender.preferred_lang = receiver.preferred_lang
        RETURN ""  -- Same language, no translation needed
    RETURN sender.preferred_lang  -- Reply in sender's language
```

### 10.4 Translation Sequence Diagram

```
 Client (Sender, lang=en)      DISP Server                    AI Backend
       │                           │                              │
       │  1. POST /messages/send   │                              │
       │  {receiver_mode:"twin",   │                              │
       │   content:"Hi there!"}    │                              │
       │ ─────────────────────────►│                              │
       │                           │                              │
       │                           │  2. Detect sender.lang=en    │
       │                           │     receiver.lang=zh         │
       │                           │     → target_lang="en"       │
       │                           │                              │
       │                           │  3. Construct prompt:        │
       │                           │     "Reply in English.       │
       │                           │      Speak naturally as      │
       │                           │      {name} would if fluent  │
       │                           │      in English. Preserve    │
       │                           │      personality."           │
       │                           │                              │
       │                           │  4. POST /chat/completions   │
       │                           │ ─────────────────────────────►
       │                           │                              │
       │                           │  5. AI response (in English  │
       │                           │     with owner's personality)│
       │                           │ ◄─────────────────────────── │
       │                           │                              │
       │                           │  6. Store reply with:        │
       │                           │     target_lang="en"         │
       │                           │     original_lang="zh"       │
       │                           │     translation_style=       │
       │                           │      "personality_preserving"│
       │                           │                              │
       │  7. Response with         │                              │
       │     translation metadata  │                              │
       │ ◄─────────────────────────│                              │
```

### 10.5 Translation Invariants

| # | Invariant | Rule |
|---|-----------|------|
| T1 | Provenance | `translation_style = "personality_preserving"` → `original_lang` MUST be non-empty |
| T2 | Transparency | `original_content` SHOULD be preserved when translation occurs |
| T3 | Personality Fidelity | Translation MUST use the Twin owner's personality profile, not generic translation |
| T4 | Language Validity | `target_lang` and `original_lang` MUST be valid ISO 639-1 codes |
| T5 | No Double Translation | A message already translated MUST NOT be translated again |

### 10.6 Standalone Translation

Users may request personality-preserving translation independently of messaging:

```
POST /api/social/translate
{
    "content": "要翻译的文本",
    "source_lang": "zh",
    "target_lang": "en"
}
```

The translation uses the requesting user's own personality profile to preserve their characteristic tone and expressions.

### 10.7 Fallback Behavior

When no AI backend is configured, the Twin MUST return a template response in the appropriate language. The reference implementation provides templates for Chinese, Japanese, Korean, and English.

---

*This specification is part of the DualSoul project by Chengyue5211, first published March 5, 2026.*
