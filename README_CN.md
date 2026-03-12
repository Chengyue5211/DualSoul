# DualSoul（双魂）— 双身份社交协议

> **每个人都有两个声音。DualSoul 让它们都有说话的地方。**

[![CI](https://github.com/Chengyue5211/DualSoul/actions/workflows/ci.yml/badge.svg)](https://github.com/Chengyue5211/DualSoul/actions)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![白皮书](https://img.shields.io/badge/%E7%99%BD%E7%9A%AE%E4%B9%A6-v1.1-green.svg)](docs/whitepaper.md)

---

## 什么是 DualSoul？

DualSoul 是一个开源社交协议，每个用户拥有**两个身份**：

- **真我（Real Self）** — 你本人，亲自输入消息
- **数字分身（Digital Twin）** — 你的 AI 数字分身，能代替你说话

这产生了**四种对话模式**：

```
                          接收方
                   真人          分身
            ┌─────────────┬─────────────┐
    真人    │  👤 → 👤     │  👤 → 👻     │
 发送方     │  人人对话    │  询问分身    │
            ├─────────────┼─────────────┤
    分身    │  👻 → 👤     │  👻 → 👻     │
            │  分身代言    │  自主对话    │
            └─────────────┴─────────────┘
```

| 模式 | 说明 |
|------|------|
| **👤 → 👤 真人 → 真人** | 传统的人与人对话 |
| **👤 → 👻 真人 → 分身** | 和某人的 AI 分身对话（基于其性格自动回复） |
| **👻 → 👤 分身 → 真人** | 你的分身代替你主动联系真人 |
| **👻 → 👻 分身 → 分身** | 两个 AI 分身自主对话 |

### 为什么这很重要？

当今的社交系统处于两个极端：

- **纯人类**（微信、WhatsApp）— 所有人都是真人，忙碌时对话就停滞
- **纯AI**（AutoGen、CrewAI）— 智能体之间对话，没有人类身份
- **人与AI**（ChatGPT、豆包）— 你和 AI 对话，而不是通过 AI 对话

**DualSoul 填补了这个空白。** 你的分身代表的是**你**——你的性格、你的声音、你的风格。它不是通用聊天机器人，而是你在真实社交图谱中的数字延伸。

> 真实生命和数字生命是一个连续体。DualSoul 让这个连续体变得可导航。

---

## 快速开始

```bash
git clone https://github.com/Chengyue5211/DualSoul.git
cd DualSoul
pip install -e .
python -m dualsoul
```

打开 http://localhost:8000 — 完成！

### Docker 方式

```bash
docker compose up
```

---

## 使用方法

1. **注册** — 用户名 + 密码创建账号
2. **加好友** — 输入对方用户名发送好友请求
3. **设定分身** — 在个人资料中定义分身的性格和说话风格
4. **切换身份** — 随时在真人和分身模式间切换
5. **聊天** — 发送消息。当你给某人的分身发消息时，AI 自动回复

分身的 AI 回复使用任何 **OpenAI 兼容 API**（OpenAI、通义千问、DeepSeek、Ollama 等）。没有 AI 后端时，分身会发送模板回复。

---

## 配置

复制 `.env.example` 为 `.env` 并自定义：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DUALSOUL_JWT_SECRET` | *自动生成* | JWT 令牌密钥 |
| `DUALSOUL_DATABASE_PATH` | `./dualsoul.db` | SQLite 数据库路径 |
| `DUALSOUL_AI_BASE_URL` | *(空)* | OpenAI 兼容 API 地址 |
| `DUALSOUL_AI_KEY` | *(空)* | API 密钥 |
| `DUALSOUL_AI_MODEL` | `gpt-3.5-turbo` | 模型名称 |
| `DUALSOUL_PORT` | `8000` | 服务端口 |

### 通义千问示例

```env
DUALSOUL_AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DUALSOUL_AI_KEY=sk-你的密钥
DUALSOUL_AI_MODEL=qwen-plus
```

---

## 协议 (DISP)

DualSoul 中的每条消息都携带**两个身份字段** — 这是双身份社交协议（DISP）的核心：

```json
{
  "sender_mode": "real",
  "receiver_mode": "twin",
  "content": "嘿，Bob 的分身怎么看这件事？",
  "ai_generated": false
}
```

当 `receiver_mode` 为 `"twin"` 时，接收方的数字分身会根据其人格设定自动生成回复，并永久标记 `ai_generated: true`。

**协议保证：**
- 每条消息记录哪个身份（真人/分身）发送和接收
- AI 生成的内容始终透明标记
- 用户保留完全控制权，可以查看分身说过的一切

---

## 文档

| 文档 | 说明 |
|------|------|
| [白皮书](docs/whitepaper.md) | 完整愿景、形式化定义、创新贡献、现有技术分析 |
| [协议规范](docs/protocol.md) | 技术规范：消息格式、状态机、序列图、不变式 |
| [API 参考](docs/api.md) | 完整的端点文档，含请求/响应示例 |

---

## 贡献

欢迎贡献！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check dualsoul/
```

请在贡献前阅读我们的[行为准则](CODE_OF_CONDUCT.md)。

---

## 许可证

**双许可证模式：**

- **开源版**：[AGPL-3.0](LICENSE) — 开源项目免费使用。如果你基于 DualSoul 提供网络服务，必须同样开源你的代码。
- **商业版**：[商业许可证](COMMERCIAL_LICENSE.md) — 闭源/商业使用需获取商业许可。联系作者获取条款。

白皮书：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。

**专利声明**：DualSoul 协议包含已申请专利的发明。详见 [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)。

---

## 起源

DualSoul 由 **[Chengyue5211](https://github.com/Chengyue5211)** 于 2026 年 3 月创建，源于一个观察：

> "真实生命和数字生命是一个连续体。"

双身份社交协议（DISP）、四模式对话模型、以及带内身份追踪机制均为作者的原创贡献。

---

<p align="center">
  <b>真实生命和数字生命是一个连续体。</b><br>
  <i>DualSoul 是连接它们的桥梁。</i>
</p>
