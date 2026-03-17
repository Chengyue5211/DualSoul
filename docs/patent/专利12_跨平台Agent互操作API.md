# 发明专利申请

## 专利十二

## 一种基于API密钥认证的数字分身跨平台Agent互操作系统

| 项目 | 内容 |
|------|------|
| **发明名称** | 一种基于API密钥认证的数字分身跨平台Agent互操作系统 |
| **发明人** | 程跃 |
| **申请人** | 跃创三品文化科技有限公司 |
| **首次公开日期** | 2026-03-15 |
| **公开平台** | GitHub (github.com/Chengyue5211/DualSoul) / Gitee镜像 |
| **申请宽限期截止** | 2026-09-15 |
| **技术领域** | 人工智能代理、API设计、跨平台互操作、身份认证、社交通信 |

---

## 一、技术领域

本发明属于人工智能代理跨平台互操作领域，具体涉及一种通过API密钥认证和RESTful接口，使外部Agent平台能够调用DualSoul数字分身的完整人格和记忆进行对话的方法和系统，实现分身在多个平台上的一致性存在。

---

## 二、背景技术

现有AI代理系统在跨平台互操作方面存在以下问题：

（一）**平台锁定方案**（主流AI平台现状）：用户在ChatGPT、Character.AI等平台创建的AI角色只能在该平台内使用，无法在其他平台上以同一人格进行对话。用户的数字身份被平台绑架。

（二）**简单API方案**（基础聊天API）：部分平台提供简单的消息发送/接收API，但缺乏人格保真——外部调用者得到的是通用AI回复，而非保持用户完整性格、说话风格和社交记忆的分身回复。

（三）**无审计方案**：API调用不记录交互日志，平台方无法监控分身在外部的行为是否正常，出现问题时无法溯源。

（四）**粗粒度权限方案**：API密钥授予全部权限或无权限，无法按功能模块（如只允许对话、不允许修改人格）进行细粒度控制。

（五）**无限制方案**：API无速率限制，外部平台可能过度调用，影响服务质量和成本。

**空白地带**：没有一个数字分身系统实现了完整的跨平台互操作协议，包括安全的密钥认证、人格保真的分身回复、交互审计日志、作用域权限控制和速率限制。

---

## 三、发明内容

### 3.1 技术问题

本发明解决的技术问题是：用户的数字分身如何安全地在多个外部Agent平台上保持一致的人格和记忆进行社交，同时确保交互可审计、权限可控、速率可限。

### 3.2 技术方案

#### 3.2.1 API密钥认证体系

系统采用高强度随机令牌作为API密钥，每个密钥绑定到特定用户和外部平台：

```python
# 密钥生成: 使用secrets模块的加密安全随机数
api_key = f"agent_{secrets.token_urlsafe(64)}"
# 输出示例: agent_3Kx7vZ9mNp2QwR5tY8uI0oP1aS4dF6gH7jK...

# 密钥存储结构
CREATE TABLE agent_api_keys (
    key_id TEXT PRIMARY KEY,
    twin_owner_id TEXT NOT NULL,      -- 分身主人
    external_platform TEXT NOT NULL,  -- 外部平台名称
    api_key TEXT NOT NULL UNIQUE,     -- 密钥值
    scopes TEXT DEFAULT 'twin:reply', -- 权限作用域
    created_at TEXT DEFAULT datetime('now','localtime'),
    expires_at TEXT,                  -- 过期时间
    last_used_at TEXT                 -- 最后使用时间
);
```

密钥管理策略：
- 每用户最多5个API密钥（`AGENT_KEY_MAX_PER_USER = 5`）
- 默认90天过期（`AGENT_KEY_DEFAULT_EXPIRY_DAYS = 90`）
- 密钥仅在创建时返回一次，不可再次查看（列表接口仅显示前12位+后4位预览）
- 支持随时吊销

#### 3.2.2 RESTful API端点设计

系统提供完整的RESTful API，分为管理端点和业务端点：

**管理端点**（用户JWT认证）：
| 端点 | 方法 | 功能 |
|------|------|------|
| /api/agents/keys | POST | 创建API密钥（指定平台、过期天数） |
| /api/agents/keys | GET | 列出所有密钥（密钥值脱敏） |
| /api/agents/keys/{key_id} | DELETE | 吊销指定密钥 |

**业务端点**（API密钥Bearer认证）：
| 端点 | 方法 | 功能 |
|------|------|------|
| /api/agents/reply | POST | 发送消息并获取分身回复 |
| /api/agents/twin/profile | GET | 获取分身公开画像 |
| /api/agents/twin/stats | GET | 获取分身交互统计 |

#### 3.2.3 完整人格保真的分身回复

跨平台回复的核心技术保障是完整人格保真。当外部平台调用 `/reply` 端点时，系统内部走与本平台完全相同的分身回复链路：

```python
@router.post("/reply")
async def agent_reply(req: AgentReplyRequest, agent=Depends(get_agent_user)):
    twin_owner_id = agent["twin_owner_id"]
    # 命名空间化外部发送者ID
    external_sender = f"external:{platform}:{req.sender_id}"

    # 调用与本平台完全相同的分身回复引擎
    result = await twin.generate_reply(
        twin_owner_id=twin_owner_id,
        from_user_id=external_sender,
        incoming_msg=content,
        sender_mode=req.sender_mode,
        target_lang=req.target_lang,
        social_context=req.context,
    )
```

该设计确保外部平台获得的分身回复包含：
- 完整的人格画像（性格、说话风格、方言偏好）
- 叙事记忆上下文（过往对话的摘要和情感基调）
- 人格保真翻译（当指定target_lang时）
- 情感感知回复（根据对话上下文调整语气）

#### 3.2.4 分身画像导出

外部平台可通过 `/twin/profile` 端点获取分身的公开画像，用于展示和匹配：

```python
@router.get("/twin/profile")
async def agent_get_twin_profile(agent=Depends(get_agent_user)):
    profile = get_twin_profile(agent["twin_owner_id"])
    return {
        "display_name": profile.display_name,
        "personality": profile.personality,
        "speech_style": profile.speech_style,
        "preferred_lang": profile.preferred_lang,
        "gender": profile.gender,
        "source": profile.twin_source,
        "capabilities": [
            "text_reply",
            "personality_preserving_translation",
            "emotion_aware_response",
            "narrative_memory",
        ],
    }
```

capabilities字段声明了分身支持的能力列表，外部平台可据此决定交互方式。

#### 3.2.5 交互审计日志

每次外部平台调用 `/reply` 端点，系统自动记录完整的交互日志：

```python
# 交互日志表
CREATE TABLE agent_message_log (
    log_id TEXT PRIMARY KEY,
    from_platform TEXT NOT NULL,      -- 来源平台
    to_twin_id TEXT NOT NULL,         -- 目标分身
    external_user_id TEXT DEFAULT '', -- 外部用户ID
    incoming_content TEXT DEFAULT '', -- 收到的消息
    reply_content TEXT DEFAULT '',    -- 分身回复
    success INTEGER DEFAULT 1,       -- 是否成功
    created_at TEXT DEFAULT datetime('now','localtime')
);
CREATE INDEX idx_aml_twin ON agent_message_log(to_twin_id, created_at DESC);
```

审计日志支持：
- 按平台查询交互记录
- 成功率统计（`/stats` 端点）
- 异常检测和溯源

#### 3.2.6 作用域权限控制

API密钥携带作用域（scopes），系统在端点级别强制检查：

```python
@router.post("/reply")
async def agent_reply(req, agent=Depends(get_agent_user)):
    scopes = (agent.get("scopes") or "").split(",")
    if "twin:reply" not in scopes:
        raise HTTPException(status_code=403, detail="API key lacks 'twin:reply' scope")
    # ... 执行回复逻辑
```

当前定义的作用域：
- `twin:reply` — 允许与分身对话
- 未来可扩展：`twin:profile_read`、`twin:profile_write`、`twin:memory_read` 等

#### 3.2.7 速率限制

系统对Agent API实施独立的速率限制：

```python
RATE_AGENT_MAX = 60  # 每分钟最多60次请求

_agent_limiter = RateLimiter(max_requests=RATE_AGENT_MAX, window_seconds=60)

@router.post("/reply")
async def agent_reply(req, request: Request, agent=Depends(get_agent_user)):
    if _agent_limiter.is_limited(request):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

每个API密钥每分钟最多60次请求，超限返回429状态码，保护服务质量和控制AI调用成本。

#### 3.2.8 密钥生命周期管理

系统实现了完整的密钥生命周期：

1. **创建**：指定平台名称和过期天数，返回密钥（仅此一次）
2. **验证**：每次请求检查密钥有效性和过期时间，同时更新 `last_used_at`
3. **列表**：查看所有密钥的脱敏信息（包含最后使用时间）
4. **吊销**：按 `key_id` 删除密钥，立即生效

```python
def _get_agent_key_owner(api_key: str) -> dict | None:
    row = db.execute("SELECT ... FROM agent_api_keys WHERE api_key=?", (api_key,))
    if not row:
        return None
    # 检查过期
    if row["expires_at"]:
        exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
        if exp < datetime.now():
            return None
    # 更新最后使用时间
    db.execute("UPDATE agent_api_keys SET last_used_at=datetime('now','localtime') WHERE key_id=?", (row["key_id"],))
    return dict(row)
```

### 3.3 有益效果

（一）用户的数字分身可以在多个外部Agent平台上以一致的人格和记忆进行社交，打破平台锁定。

（二）API密钥认证体系兼顾安全性（加密安全随机数、过期机制、吊销能力）和易用性（Bearer认证、简单的RESTful接口）。

（三）完整人格保真确保外部平台获得的分身回复与本平台质量一致，包含人格、记忆和翻译能力。

（四）交互审计日志使分身在外部的行为可追踪、可统计、可溯源。

（五）作用域权限控制实现细粒度的能力授权，保护用户隐私和安全。

（六）速率限制保护服务质量和控制成本。

---

## 四、权利要求书

1. 一种数字分身跨平台Agent互操作方法，其特征在于：系统通过加密安全随机数生成API密钥（每用户最多5个，带过期时间），外部Agent平台使用该密钥通过RESTful API与用户的数字分身进行对话，分身回复经过与本平台完全相同的人格保真引擎，包含完整的性格、说话风格、叙事记忆和情感感知。

2. 根据权利要求1所述的方法，其特征在于：系统提供分身回复（POST /reply）、画像导出（GET /profile）和统计查询（GET /stats）三个业务端点，以及密钥创建、列表和吊销三个管理端点，形成完整的跨平台互操作协议。

3. 根据权利要求1所述的方法，其特征在于：外部发送者的身份通过 `external:{platform}:{sender_id}` 格式进行命名空间化处理，与本平台用户ID隔离，防止身份冲突。

4. 根据权利要求1所述的方法，其特征在于：每次跨平台对话交互自动记录到审计日志表（agent_message_log），包含来源平台、外部用户ID、消息内容、回复内容和成功状态，支持按平台查询交互记录和计算成功率。

5. 根据权利要求1所述的方法，其特征在于：API密钥携带作用域标识（如 twin:reply），系统在端点级别强制检查作用域权限，实现细粒度的能力授权控制。

6. 根据权利要求1所述的方法，其特征在于：Agent API实施独立的速率限制（默认每分钟60次），超限请求返回429状态码，保护服务质量和控制AI调用成本。

7. 根据权利要求1所述的方法，其特征在于：分身画像导出端点返回人格描述、说话风格、语言偏好和能力列表（capabilities），使外部平台能够了解分身的完整能力并据此决定交互方式。

8. 根据权利要求1所述的方法，其特征在于：API密钥实现完整的生命周期管理，包括一次性密钥展示（创建后不可再查看全文）、过期自动失效、最后使用时间追踪和即时吊销。

---

## 五、在先技术对比

| 在先技术 | 与本发明的区别 |
|----------|---------------|
| OpenAI API | 通用AI模型API，非用户个人分身的跨平台人格保真 |
| Character.AI API | 角色锁定在平台内，不支持跨平台互操作 |
| Matrix协议 | 通信互操作协议，不涉及AI人格保真和叙事记忆 |
| ActivityPub（Mastodon） | 社交内容联邦协议，非AI Agent的跨平台人格一致性 |
| OAuth 2.0 | 通用授权协议，不涉及AI分身回复和人格保真 |
| OpenClaw Agent Protocol | Agent注册协议，不包含完整的人格保真引擎和交互审计 |

本发明的独创性：首次实现了数字分身在多个Agent平台间的互操作协议，包括API密钥认证、完整人格保真回复（含叙事记忆和翻译）、交互审计日志、作用域权限控制和速率限制的完整体系。

---

## 六、确权证据

| 证据类型 | 内容 |
|----------|------|
| Git提交记录 | `60eaeeb` (2026-03-15) |
| GitHub仓库 | github.com/Chengyue5211/DualSoul |
| Gitee镜像 | gitee.com/chengyue5211/DualSoul |
| 许可证 | AGPL-3.0-or-later |
| 关键代码文件 | `dualsoul/routers/agents.py` — API端点、密钥管理、速率限制；`dualsoul/database.py` — SCHEMA_V7（agent_api_keys, agent_message_log 表定义） |

---

## 七、附件说明

1. GitHub仓库完整提交历史
2. 专利技术交底书（docs/PATENT_DISCLOSURE.md）
3. 参考实现源代码（dualsoul/routers/agents.py, dualsoul/database.py）
4. 自动化测试（tests/）

---

发明人：程跃（跃创三品文化科技有限公司） | 日期：2026年03月15日

*本文档仅用于专利申请准备。*
