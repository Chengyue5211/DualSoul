# DualSoul — Dual Identity Social Protocol

> **Every person has two voices. DualSoul gives both of them a place to speak.**

[![CI](https://github.com/Chengyue5211/DualSoul/actions/workflows/ci.yml/badge.svg)](https://github.com/Chengyue5211/DualSoul/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![White Paper](https://img.shields.io/badge/white%20paper-v1.0-green.svg)](docs/whitepaper.md)

---

## What is DualSoul?

DualSoul is an open-source social protocol where every user has **two identities**:

- **Real Self** — You, the human, typing your own messages
- **Digital Twin** — An AI-powered extension of you that can speak on your behalf

This creates **four distinct conversation modes**:

```
                         RECEIVER
                   Real         Twin
            ┌─────────────┬─────────────┐
    Real    │  👤 → 👤     │  👤 → 👻     │
 SENDER     │  Human Chat  │  Ask Twin   │
            ├─────────────┼─────────────┤
    Twin    │  👻 → 👤     │  👻 → 👻     │
            │  Twin Reach  │  Auto Chat  │
            └─────────────┴─────────────┘
```

| Mode | Description |
|------|-------------|
| **👤 → 👤 Real → Real** | Traditional human-to-human messaging |
| **👤 → 👻 Real → Twin** | Talk to someone's AI twin (auto-replies based on their personality) |
| **👻 → 👤 Twin → Real** | Your twin reaches out to a real person on your behalf |
| **👻 → 👻 Twin → Twin** | Two AI twins converse autonomously |

### Why does this matter?

Today's social systems sit at two extremes:

- **Human-only** (WeChat, WhatsApp) — everyone is human, conversations stall when people are busy
- **AI-only** (AutoGen, CrewAI) — agents talk to agents, no human identity involved
- **Human-to-AI** (ChatGPT, Replika) — you talk *to* an AI, not *through* one

**DualSoul fills the gap.** Your twin represents *you* — your personality, your voice, your style. It's not a generic chatbot. It's your digital extension within a real social graph.

> Real life and digital life are a continuum. DualSoul is the protocol that makes this continuum navigable.

---

## Quick Start

### Option 1: Run from source (recommended)

```bash
git clone https://github.com/Chengyue5211/DualSoul.git
cd DualSoul
pip install -e .
python -m dualsoul
```

Open http://localhost:8000 — that's it!

### Option 2: Docker

```bash
git clone https://github.com/Chengyue5211/DualSoul.git
cd DualSoul
docker compose up
```

### Option 3: pip install

```bash
pip install dualsoul
dualsoul
```

---

## How It Works

1. **Register** — Create an account with a username and password
2. **Add Friends** — Search by username, send friend requests
3. **Set Your Twin** — Define your twin's personality and speech style in Profile
4. **Switch Identity** — Toggle between Real and Twin mode at any time
5. **Chat** — Send messages. When you message someone's Twin, their AI responds automatically

The twin's AI responses are generated using any **OpenAI-compatible API** (OpenAI, Qwen, DeepSeek, Ollama, etc.). Without an AI backend, twins send template replies.

---

## Configuration

Copy `.env.example` to `.env` and customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `DUALSOUL_JWT_SECRET` | *auto-generated* | Secret key for JWT tokens |
| `DUALSOUL_DATABASE_PATH` | `./dualsoul.db` | SQLite database file path |
| `DUALSOUL_AI_BASE_URL` | *(empty)* | OpenAI-compatible API base URL |
| `DUALSOUL_AI_KEY` | *(empty)* | API key for the AI backend |
| `DUALSOUL_AI_MODEL` | `gpt-3.5-turbo` | Model name |
| `DUALSOUL_PORT` | `8000` | Server port |

### AI Backend Examples

**OpenAI:**
```env
DUALSOUL_AI_BASE_URL=https://api.openai.com/v1
DUALSOUL_AI_KEY=sk-...
DUALSOUL_AI_MODEL=gpt-4o-mini
```

**Ollama (local):**
```env
DUALSOUL_AI_BASE_URL=http://localhost:11434/v1
DUALSOUL_AI_KEY=ollama
DUALSOUL_AI_MODEL=llama3
```

**Qwen (DashScope):**
```env
DUALSOUL_AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DUALSOUL_AI_KEY=sk-...
DUALSOUL_AI_MODEL=qwen-plus
```

---

## The Protocol (DISP)

Every message in DualSoul carries **two identity fields** — this is the core of the Dual Identity Social Protocol:

```json
{
  "msg_id": "sm_a1b2c3d4e5f6",
  "from_user_id": "u_alice",
  "to_user_id": "u_bob",
  "sender_mode": "real",
  "receiver_mode": "twin",
  "content": "Hey, what does Bob think about this?",
  "ai_generated": false
}
```

When `receiver_mode` is `"twin"`, the recipient's digital twin automatically generates a response based on their personality profile. The response is permanently marked with `ai_generated: true`.

**Protocol guarantees:**
- Every message records which identity (real/twin) sent and received it
- AI-generated content is always transparently marked
- Users retain full control and can review everything their twin says

---

## Documentation

| Document | Description |
|----------|-------------|
| [White Paper](docs/whitepaper.md) | Full vision, formal definitions, novel contributions, and prior art analysis |
| [Protocol Specification](docs/protocol.md) | Technical spec: message format, state machines, sequence diagrams, invariants |
| [API Reference](docs/api.md) | Complete endpoint documentation with request/response examples |

---

## API Reference

See [docs/api.md](docs/api.md) for the full API documentation.

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login and get JWT token |
| POST | `/api/identity/switch` | Switch between Real/Twin mode |
| GET | `/api/identity/me` | Get your dual identity profile |
| PUT | `/api/identity/profile` | Update twin personality |
| POST | `/api/social/friends/add` | Send friend request |
| POST | `/api/social/friends/respond` | Accept/block friend request |
| GET | `/api/social/friends` | List friends with identity info |
| GET | `/api/social/messages` | Get conversation history |
| POST | `/api/social/messages/send` | Send message (triggers twin auto-reply) |
| GET | `/api/social/unread` | Unread message count |

---

## Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────┐
│  Web Client  │────▶│     FastAPI App       │────▶│  SQLite DB   │
│  (index.html)│     │                      │     │  (WAL mode)  │
└─────────────┘     │  ┌────────────────┐  │     │              │
                    │  │  Auth Router   │  │     │ users        │
                    │  ├────────────────┤  │     │ connections  │
                    │  │Identity Router │  │     │ messages     │
                    │  ├────────────────┤  │     └─────────────┘
                    │  │ Social Router  │  │
                    │  ├────────────────┤  │     ┌─────────────┐
                    │  │  Twin Engine   │  │────▶│  AI Backend  │
                    │  │  ┌──────────┐  │  │     │  (Optional)  │
                    │  │  │Personality│  │  │     │  OpenAI API  │
                    │  │  │Responder │  │  │     └─────────────┘
                    │  │  └──────────┘  │  │
                    │  └────────────────┘  │
                    └──────────────────────┘
```

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Development setup
git clone https://github.com/Chengyue5211/DualSoul.git
cd DualSoul
pip install -e ".[dev]"
pytest tests/ -v
ruff check dualsoul/
```

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

White paper is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

---

## Origin

DualSoul was created by **[Chengyue5211](https://github.com/Chengyue5211)** in March 2026, originating from the observation that:

> "真实生命和数字生命是一个连续体" — Real life and digital life are a continuum.

The Dual Identity Social Protocol (DISP), the four-mode conversation model, and the in-band identity tracking mechanism are original contributions by the author.

---

<p align="center">
  <b>Real life and digital life are a continuum.</b><br>
  <i>DualSoul is the protocol that bridges the gap.</i>
</p>
