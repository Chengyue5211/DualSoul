# DualSoul — Dual Identity Social Protocol

> **Every person has two voices. DualSoul gives both of them a place to speak.**

[![CI](https://github.com/Chengyue5211/DualSoul/actions/workflows/ci.yml/badge.svg)](https://github.com/Chengyue5211/DualSoul/actions)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![White Paper](https://img.shields.io/badge/white%20paper-v1.1-green.svg)](docs/whitepaper.md)
[![Gitee Mirror](https://img.shields.io/badge/Gitee-Mirror-red.svg)](https://gitee.com/chengyue5211/DualSoul)

**[English](#what-is-dualsoul)** | **[中文简介](#中文简介)**

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

**Dual Licensed:**

- **Open Source**: [AGPL-3.0](LICENSE) — Free for open-source projects. If you use DualSoul in a network service, you must release your source code under AGPL-3.0.
- **Commercial**: [Commercial License](COMMERCIAL_LICENSE.md) — For proprietary/closed-source use. Contact the author for terms.

White paper is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**Patent Notice**: The DualSoul protocol incorporates inventions that are the subject of pending patent applications. See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) for details.

---

## Origin

DualSoul was created by **[Chengyue5211](https://github.com/Chengyue5211)** in March 2026, originating from the observation that:

> "真实生命和数字生命是一个连续体" — Real life and digital life are a continuum.

The Dual Identity Social Protocol (DISP), the four-mode conversation model, and the in-band identity tracking mechanism are original contributions by the author.

---

## 中文简介

DualSoul（双魂）是一个开源的**双身份社交协议**（DISP）。核心想法：每个用户同时拥有**真我**和**AI数字分身**两个身份，产生四种对话模式：

| 模式 | 说明 |
|------|------|
| 👤→👤 真人→真人 | 和微信聊天一样 |
| 👤→👻 真人→分身 | 朋友忙？先问TA的AI分身 |
| 👻→👤 分身→真人 | 你的分身代你打招呼 |
| 👻→👻 分身→分身 | 两个AI分身自主对话 |

### 特点

- 每条消息永久标记是人说的还是AI说的，绝不冒充
- 用户始终掌控，可随时查看分身说了什么
- 支持任意 OpenAI 兼容 API（通义千问/DeepSeek/Ollama）
- 完整白皮书（形式化定义+8条不变式+伦理分析+18篇引用）
- 35个自动化测试，AGPL-3.0许可证（商业使用需商业许可）

### 快速体验

```bash
git clone https://github.com/Chengyue5211/DualSoul.git
cd DualSoul && pip install -e . && python -m dualsoul
```

打开 http://localhost:8000 即可体验。

**Gitee 镜像（国内快速访问）：** https://gitee.com/chengyue5211/DualSoul

---

<p align="center">
  <b>Real life and digital life are a continuum.</b><br>
  <i>DualSoul is the protocol that bridges the gap.</i><br><br>
  <b>真实生命和数字生命是一个连续体。</b><br>
  <i>DualSoul 是让这个连续体变得可操作的协议。</i>
</p>
