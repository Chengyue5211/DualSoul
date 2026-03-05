# DualSoul — Dual Identity Social Protocol

> **Every person has two voices. DualSoul gives both of them a place to speak.**

[![CI](https://github.com/Chengyue5211/DualSoul/actions/workflows/ci.yml/badge.svg)](https://github.com/Chengyue5211/DualSoul/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## What is DualSoul?

DualSoul is an open-source social protocol where every user has **two identities**:

- **Real Self** — You, the human, typing your own messages
- **Digital Twin** — An AI-powered extension of you that can speak on your behalf

This creates **four distinct conversation modes**:

| Mode | Sender | Receiver | Description |
|------|--------|----------|-------------|
| 👤 → 👤 | Real | Real | Traditional human-to-human messaging |
| 👤 → 👻 | Real | Twin | Talking to someone's digital twin |
| 👻 → 👤 | Twin | Real | Your twin reaching out to a real person |
| 👻 → 👻 | Twin | Twin | Autonomous twin-to-twin conversation |

**Why does this matter?**

- Social media today forces a single public identity. People already behave differently in different contexts.
- Pure AI chatbots (ChatGPT, Character.ai) are conversations *with* AI. DualSoul is conversations *through* AI — your twin represents *you*.
- Agent-only platforms (AutoGen, CrewAI) have no human in the loop. DualSoul keeps humans in control with a seamless identity switch.

**DualSoul fills the gap between human-only and AI-only social networks.**

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
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Web Client  │────▶│  FastAPI App  │────▶│   SQLite DB  │
│  (index.html)│     │              │     │              │
└─────────────┘     │  ┌────────┐  │     │ users        │
                    │  │Identity│  │     │ connections  │
                    │  │Router  │  │     │ messages     │
                    │  ├────────┤  │     └─────────────┘
                    │  │Social  │  │
                    │  │Router  │  │     ┌─────────────┐
                    │  ├────────┤  │────▶│  AI Backend  │
                    │  │Twin    │  │     │  (Optional)  │
                    │  │Engine  │  │     │  OpenAI API  │
                    │  └────────┘  │     └─────────────┘
                    └──────────────┘
```

---

## The Protocol

Every message in DualSoul carries **two identity fields**:

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

When `receiver_mode` is `"twin"`, the recipient's digital twin automatically generates a response based on their personality profile. The response is marked with `ai_generated: true`.

Read the full protocol specification: [docs/protocol.md](docs/protocol.md)

Read the white paper: [docs/whitepaper.md](docs/whitepaper.md)

---

## Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `pytest tests/ -v`
5. Submit a pull request

### Development Setup

```bash
git clone https://github.com/Chengyue5211/DualSoul.git
cd DualSoul
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## White Paper

For the full vision behind DualSoul, read our white paper:
**[The Dual Identity Social Protocol →](docs/whitepaper.md)**

---

<p align="center">
  <b>Real life and digital life are a continuum.</b><br>
  <i>DualSoul bridges the gap.</i>
</p>
