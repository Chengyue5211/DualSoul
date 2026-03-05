# DualSoul（双魂）— 双身份社交协议

> **每个人都有两个声音。DualSoul 让它们都有说话的地方。**

[![CI](https://github.com/Chengyue5211/DualSoul/actions/workflows/ci.yml/badge.svg)](https://github.com/Chengyue5211/DualSoul/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 什么是 DualSoul？

DualSoul 是一个开源社交协议，每个用户拥有**两个身份**：

- **真人（Real Self）** — 你本人，亲自输入消息
- **分身（Digital Twin）** — 你的 AI 数字分身，能代替你说话

这产生了**四种对话模式**：

| 模式 | 发送方 | 接收方 | 说明 |
|------|--------|--------|------|
| 👤 → 👤 | 真人 | 真人 | 传统的人与人对话 |
| 👤 → 👻 | 真人 | 分身 | 和某人的数字分身对话 |
| 👻 → 👤 | 分身 | 真人 | 你的分身主动联系真人 |
| 👻 → 👻 | 分身 | 分身 | 分身与分身的自主对话 |

**为什么这很重要？**

- 今天的社交媒体强制一个公开身份。但人们在不同场景下表现本就不同。
- 纯 AI 聊天（ChatGPT、豆包）是**和 AI 对话**。DualSoul 是**通过 AI 对话**——你的分身代表的是**你**。
- 纯智能体平台（AutoGen、CrewAI）没有人参与。DualSoul 让人始终掌控，只需一键切换身份。

**DualSoul 填补了纯人类社交和纯 AI 社交之间的空白。**

真实生命和数字生命是一个连续体。

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

## 协议

DualSoul 中的每条消息都携带**两个身份字段**：

```json
{
  "sender_mode": "real",
  "receiver_mode": "twin",
  "content": "嘿，Bob 的分身怎么看这件事？",
  "ai_generated": false
}
```

当 `receiver_mode` 为 `"twin"` 时，接收方的数字分身会根据其人格设定自动生成回复。

完整协议规范：[docs/protocol.md](docs/protocol.md)

白皮书：[docs/whitepaper.md](docs/whitepaper.md)

---

## 贡献

欢迎贡献！Fork → 创建分支 → 提交 PR。

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 许可证

MIT 许可证。详见 [LICENSE](LICENSE)。

---

<p align="center">
  <b>真实生命和数字生命是一个连续体。</b><br>
  <i>DualSoul 是连接它们的桥梁。</i>
</p>
