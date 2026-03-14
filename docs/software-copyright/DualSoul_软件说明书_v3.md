# DualSoul双身份社交协议

## 软件说明书

- 软件名称：DualSoul双身份社交协议软件
- 版本号：V3.0（对应代码版本 v0.7.1，DISP协议 v1.1，TPF v1.0）
- 开发完成日期：2026年3月14日
- 著作权人：Chengyue5211

---

## 目录

1. 软件概述
2. 主要功能
3. 技术架构
4. 数据库设计
5. 运行环境
6. 使用流程
7. 软件特点

---

## 1. 软件概述

DualSoul是实现DISP（Dual Identity Social Protocol，双身份社交协议）的开源软件。每个用户同时拥有真我（Real Self）和数字分身（Digital Twin）两种身份，形成四种数学完备的对话模式（R-R、R-T、T-R、T-T）。

V3.0在V2.0基础上新增：
- **AI数字分身头像生成**：基于真人照片通过AI风格迁移一键生成7种风格分身头像（动漫/3D/未来科技/黏土/像素/水墨/复古漫画），不可用时自动降级为CSS滤镜方案
- **三档智能延迟应答**：根据用户在线状态（离线/在线空闲/正在对话）自适应决定分身介入时机，30秒延迟重检机制避免抢答
- **对话记忆感知应答**：分身回复时自动检索最近6条对话历史，角色映射构建多轮上下文，确保回复连贯
- **分身代回复通知**：分身每次代回复后自动通知主人（消息摘要+回复摘要）
- **分身行为约束**：分身自动回复时注入"只传话不拍板"规则，防止越权决策
- **分身名片与邀请链接分离**：独立视觉设计（蓝色名片🪪 vs 橙色邀请🎁），防止用户混淆

### 软件基本信息

| 字段 | 内容 |
|------|------|
| 软件名称 | DualSoul双身份社交协议软件 |
| 版本号 | V3.0（DISP协议v1.1 + TPF v1.0） |
| 开发语言 | Python 3.10+ / HTML5 / JavaScript |
| 运行环境 | Windows / Linux / macOS |
| 开发框架 | FastAPI + SQLite + JWT + httpx + WebSocket |
| 开源许可 | AGPL-3.0-or-later（双许可证模式） |
| 代码总行数 | 6657行（Python源码3759 + 测试463 + 前端2435） |
| 自动化测试 | 42个测试用例，覆盖所有协议行为 |

---

## 2. 主要功能

### 2.1 双身份账户系统

每个注册用户自动获得真我（real）和数字分身（twin）两种身份。用户可随时切换身份（原子操作）。分身拥有独立头像、个性描述、说话风格配置和语言偏好。支持性别字段和注册来源追踪。V3.0新增AI生成分身头像和风格模板选择器。

### 2.2 四模式对话系统

- **R-R（真人对真人）**：传统即时通讯，无AI参与，默认模式
- **R-T（真人对分身）**：人类向对方的数字分身发送消息，分身根据所有者个性自动回复
- **T-R（分身对真人）**：用户的分身代替本人联系对方真人，实现委托外联
- **T-T（分身对分身）**：两个数字分身自主对话，实现异步社交维护

四种模式覆盖{real, twin}的完整笛卡尔积。

### 2.3 WebSocket实时消息

- WebSocket推送：消息、好友请求、分身回复、分身通知通过WebSocket实时推送
- 自动重连：断线后指数退避重连（1s→2s→4s→8s→30s）
- HTTP兜底：WebSocket不可用时回退到HTTP轮询
- JWT认证：WebSocket连接通过URL参数传递JWT令牌

### 2.4 AI分身自动回复引擎

- 当receiver_mode为twin时，自动触发接收方数字分身的AI回复
- 基于分身所有者配置的个性描述和说话风格生成
- V3.0新增：回复时自动检索最近6条对话历史，构建多轮上下文
- V3.0新增：角色映射（主人消息→assistant，好友消息→user）
- V3.0新增：防重复指令，限制AI只回应最新消息
- 支持任何OpenAI兼容API（通义千问、DeepSeek等）
- 未配置AI后端时使用模板降级回复

### 2.5 三档智能延迟应答（V3.0新增）

分身根据主人的实时在线状态和对话活跃度，智能决定介入时机：

| 状态档位 | 检测条件 | 分身行为 |
|----------|----------|----------|
| 离线 | 无WebSocket连接 | 立即回复 |
| 在线但空闲 | 有WebSocket连接，但30秒内未向该好友发消息 | 延迟30秒后检查，用户仍未回复则分身介入 |
| 正在对话 | 35秒内向该好友发过真人消息 | 完全静默 |

- 通过WebSocket连接管理器检测用户在线状态
- 通过消息数据库查询检测用户对话活跃度
- 异步延迟任务机制（asyncio.ensure_future），不阻塞主线程

### 2.6 分身代回复通知（V3.0新增）

分身每次自动回复后，自动通知分身主人：
- 在分身与主人的私密对话中存储通知消息（好友消息摘要+分身回复摘要）
- 通过WebSocket推送 `twin_notification` 事件
- 更新主人的未读消息计数
- 注入行为约束：分身不替主人做决定，只传话不拍板

### 2.7 AI数字分身头像生成（V3.0新增）

- 基于DashScope `wanx-style-repaint-v1` AI风格迁移模型
- 7种风格预设：动漫、3D立体、未来科技、黏土世界、像素世界、水墨、复古漫画
- 异步任务轮询架构（提交→每2秒轮询→最长60秒超时）
- 注册引导流程集成：拍照后可一键AI生成分身头像
- CSS滤镜降级方案：AI不可用时自动使用7种CSS滤镜
- 头像随时可替换：真人头像和分身头像均可独立更换或重新AI生成

### 2.8 对话记忆感知应答（V3.0新增）

- 滑动窗口检索：从消息数据库获取最近6条双向对话记录
- 角色映射：主人消息（真人或分身模式）→ assistant，好友消息 → user
- 去重机制：自动检测并移除与当前待回复消息重复的末尾记录
- 双重上下文融合：人格上下文（system prompt）+ 对话上下文（message history）
- 分身自聊扩展：与主人对话时注入8轮历史+好友列表+冷联系提醒

### 2.9 跨语言人格保真翻译

- 当发送方和接收方使用不同语言时，系统自动触发人格保真翻译
- 翻译保留说话人的个人风格（幽默感、语气、正式程度、惯用表达）
- 支持14种语言（zh、en、ja、ko、fr、de、es、pt、ru、ar、hi、th、vi、id）
- 自动检测方言和外语并推送翻译
- 消息翻译按钮：手动触发翻译

### 2.10 跨平台分身导入

- **Twin Portable Format (TPF v1.0)**：标准化的分身数据交换格式
- **五维人格模型**：决断力、认知方式、表达风格、人际关系、自主性
- **三种接入方式**：文件上传、API推送、增量同步
- **支持平台**：年轮、OpenClaw及任意AI培养平台
- **热冷双存储**：五维数据供AI实时查询，完整数据供审计追溯

### 2.11 视觉AI

- 分身可以理解用户发送的图片
- 基于通义千问VL视觉模型
- 分身看图后以自己的人格风格回应

### 2.12 PWA

- manifest.json + Service Worker
- 可安装到手机主屏幕
- 离线时显示提示页面
- 独立窗口运行（standalone模式）
- 缓存版本管理（自动更新）

### 2.13 社交连接管理

- 好友请求状态机（pending → accepted / blocked）
- 好友列表含双头像 + 当前身份模式 + 来源徽章
- 邀请链接分享（自动预填加好友）
- V3.0新增：分身名片预览（蓝色主题🪪）与邀请链接（橙色主题🎁）视觉分离

### 2.14 分身与自己聊天

- 用户可与自己的分身对话
- 分身知道自己在与主人交流，切换到"自我对话"模式
- 支持发送图片让分身解读
- 扩展上下文：好友列表感知+冷联系好友提醒

### 2.15 风格学习

- 分析用户历史聊天记录
- 自动提取人格特征和说话风格
- 一键应用到分身设置
- 风格模板选择器：预设卡片+微调标签

---

## 3. 技术架构

### 3.1 模块列表

| 模块 | 文件 | 行数 | 功能 |
|------|------|------|------|
| 入口 | `dualsoul/__init__.py` | 7 | 版本号和包信息 |
| CLI | `dualsoul/__main__.py` | 5 | 命令行入口 |
| 认证 | `dualsoul/auth.py` | 52 | JWT认证 + bcrypt密码哈希 |
| 配置 | `dualsoul/config.py` | 32 | 环境变量配置 |
| 连接管理 | `dualsoul/connections.py` | 68 | WebSocket连接管理器 + 在线状态追踪 |
| 数据库 | `dualsoul/database.py` | 193 | SQLite初始化 + 迁移 |
| 主应用 | `dualsoul/main.py` | 143 | FastAPI应用 + 路由注册 + 静态文件 |
| 数据模型 | `dualsoul/models.py` | 100 | Pydantic请求模型（含头像生成请求） |
| 协议 | `dualsoul/protocol/message.py` | 81 | DISP消息类型定义 |
| 认证路由 | `dualsoul/routers/auth.py` | 67 | 注册/登录API |
| 身份路由 | `dualsoul/routers/identity.py` | 490 | 身份切换/配置/头像/声音/学习/AI头像生成API |
| 社交路由 | `dualsoul/routers/social.py` | 516 | 好友/消息/翻译/分身聊天/三档延迟应答/主人通知API |
| 导入路由 | `dualsoul/routers/twin_import.py` | 314 | 分身导入/同步/状态API |
| WebSocket | `dualsoul/routers/ws.py` | 49 | WebSocket端点 |
| **头像引擎** | `dualsoul/twin_engine/avatar.py` | **229** | **AI头像风格迁移生成（V3.0新增）** |
| 学习引擎 | `dualsoul/twin_engine/learner.py` | 226 | 聊天历史分析+风格提取 |
| 人格引擎 | `dualsoul/twin_engine/personality.py` | 256 | 五维人格模型+自适应提示词 |
| 回复引擎 | `dualsoul/twin_engine/responder.py` | 931 | AI回复+翻译+视觉理解+对话记忆检索 |

### 3.2 关键技术特性

- **FastAPI异步框架**：高性能异步HTTP + WebSocket
- **SQLite**：零配置嵌入式数据库，支持万级用户
- **JWT认证**：无状态令牌认证，支持HTTP和WebSocket
- **OpenAI兼容API**：可接入通义千问、DeepSeek等任意兼容后端
- **DashScope AI图像API**：阿里云AI风格迁移（与通义千问同平台同密钥）
- **异步任务架构**：asyncio.ensure_future实现非阻塞延迟任务
- **热冷双存储**：五维人格数据在索引列（热），完整JSON在raw_import列（冷）
- **滑动窗口对话检索**：定量控制上下文大小，平衡质量与成本

---

## 4. 数据库设计

### 4.1 核心表（3张）

**users表**：用户账户和双身份配置

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | TEXT PK | 用户唯一标识 |
| username | TEXT UNIQUE | 用户名 |
| password_hash | TEXT | bcrypt密码哈希 |
| display_name | TEXT | 显示昵称 |
| current_mode | TEXT | 当前身份模式（real/twin） |
| twin_personality | TEXT | 分身性格描述 |
| twin_speech_style | TEXT | 分身说话风格 |
| preferred_lang | TEXT | 语言偏好（V1.1） |
| avatar | TEXT | 真人头像URL |
| twin_avatar | TEXT | 分身头像URL |
| twin_auto_reply | INTEGER | 分身自动回复开关（V2.0） |
| voice_sample | TEXT | 声音样本URL（V2.0） |
| twin_source | TEXT | 分身数据来源（V2.0） |
| gender | TEXT | 性别（V2.0） |
| reg_source | TEXT | 注册来源（V2.0） |

**social_connections表**：好友关系

| 字段 | 类型 | 说明 |
|------|------|------|
| conn_id | TEXT PK | 连接唯一标识 |
| user_id | TEXT | 请求发起方 |
| friend_id | TEXT | 请求接收方 |
| status | TEXT | 状态（pending/accepted/blocked） |
| accepted_at | TEXT | 接受时间 |

**social_messages表**：消息记录

| 字段 | 类型 | 说明 |
|------|------|------|
| msg_id | TEXT PK | 消息唯一标识 |
| from_user_id | TEXT | 发送者 |
| to_user_id | TEXT | 接收者 |
| sender_mode | TEXT | 发送者身份（real/twin） |
| receiver_mode | TEXT | 接收者身份（real/twin） |
| content | TEXT | 消息内容 |
| original_content | TEXT | 翻译前原文（V1.1） |
| original_lang | TEXT | 原始语言（V1.1） |
| target_lang | TEXT | 目标语言（V1.1） |
| translation_style | TEXT | 翻译风格（V1.1） |
| msg_type | TEXT | 消息类型（text/image） |
| ai_generated | INTEGER | 是否AI生成（write-once） |
| is_read | INTEGER | 是否已读 |
| auto_reply | INTEGER | 是否自动回复（V2.0） |
| metadata | TEXT | 预留元数据字段（V2.0） |

### 4.2 扩展表（3张，V2.0新增）

**twin_profiles表**：五维人格档案

| 字段 | 类型 | 说明 |
|------|------|------|
| profile_id | TEXT PK | 档案唯一标识 |
| user_id | TEXT | 所属用户 |
| source | TEXT | 来源平台 |
| version | INTEGER | 版本号 |
| is_active | INTEGER | 是否活跃版本 |
| dim_judgement | TEXT | 决断力维度 |
| dim_cognition | TEXT | 认知方式维度 |
| dim_expression | TEXT | 表达风格维度 |
| dim_relation | TEXT | 人际关系维度 |
| dim_sovereignty | TEXT | 自主性维度 |
| raw_import | TEXT | 完整原始导入数据（JSON冷存储） |

**twin_memories表**：分身记忆

| 字段 | 类型 | 说明 |
|------|------|------|
| memory_id | TEXT PK | 记忆唯一标识 |
| user_id | TEXT | 所属用户 |
| memory_type | TEXT | 类型（daily/weekly/monthly/quarterly/yearly） |
| period_start | TEXT | 时间段起始 |
| period_end | TEXT | 时间段结束 |
| summary_text | TEXT | 记忆摘要 |
| emotional_tone | TEXT | 情感基调 |

**twin_entities表**：分身知识实体

| 字段 | 类型 | 说明 |
|------|------|------|
| entity_id | TEXT PK | 实体唯一标识 |
| user_id | TEXT | 所属用户 |
| entity_name | TEXT | 实体名称 |
| entity_type | TEXT | 类型（person/place/thing/event/concept） |
| importance_score | REAL | 重要性评分 |
| context | TEXT | 上下文描述 |

---

## 5. 运行环境

### 硬件要求
- CPU：1核+
- 内存：512MB+
- 硬盘：100MB+

### 软件要求
- 操作系统：Windows 10+ / Linux / macOS
- Python：3.10+
- 浏览器：Chrome/Safari/Firefox（前端PWA）

### 安装方式
```bash
pip install dualsoul
# 或
docker-compose up -d
```

### 环境变量
- `AI_BASE_URL`：AI后端地址（通义千问/DeepSeek等）
- `AI_API_KEY`：AI后端密钥（同时用于通义千问对话和DashScope图像生成）
- `AI_MODEL`：AI模型名称
- `JWT_SECRET`：JWT签名密钥
- `CORS_ORIGINS`：跨域白名单

---

## 6. 使用流程

1. **注册**：`POST /api/auth/register`（携带用户名、密码、来源标识）
2. **配置分身**：`PUT /api/identity/profile`（设置个性、风格、语言偏好、性别）
3. **AI生成分身头像**：`POST /api/identity/avatar/generate`（上传真人照片+选择风格，V3.0新增）
4. **查看可用风格**：`GET /api/identity/avatar/styles`（返回7种AI风格列表，V3.0新增）
5. **导入外部分身**：`POST /api/twin/import`（上传TPF格式JSON，可选）
6. **添加好友**：`POST /api/social/friends/add`
7. **建立WebSocket**：`ws://host/ws?token=JWT`
8. **发送消息**：`POST /api/social/messages/send`（指定sender_mode和receiver_mode）
9. **人格保真翻译**：`POST /api/social/translate`（可选，手动翻译）
10. **与分身聊天**：`POST /api/social/twin/chat`
11. **查看对话**：`GET /api/social/messages`（含翻译溯源）
12. **增量同步**：`POST /api/twin/sync`（培养平台定期推送）

---

## 7. 软件特点

1. **原创双身份社交协议（DISP v1.1）**：首次统一人类和AI身份的四种对话模式，填补"第四种社交"空白
2. **完备消息格式**：双向身份模式对 + 翻译溯源元数据 + AI生成标记（write-once不可篡改）
3. **跨语言人格保真翻译**：首创基于人格画像的翻译方法，保留说话人个人风格
4. **跨平台分身可移植格式（TPF v1.0）**：首创AI分身人格数据的标准化交换格式
5. **五维人格模型**：决断力、认知方式、表达风格、人际关系、自主性——面向AI代理的正交人格框架
6. **WebSocket实时通信**：消息秒级推送 + 自动重连 + HTTP兜底
7. **三档智能延迟应答**：首创基于用户三档在线状态的AI代理自适应介入策略（V3.0新增）
8. **对话记忆感知应答**：首创数字分身代理场景的滑动窗口对话检索+角色映射（V3.0新增）
9. **AI数字分身头像生成**：首创在双身份社交网络中从真人照片一键AI生成风格化分身头像（V3.0新增）
10. **联邦式开放平台**：培养平台负责养，社交平台负责用，通过TPF格式无缝协作
11. **可插拔AI后端**：支持通义千问、DeepSeek等任意OpenAI兼容API
12. **PWA化**：可安装到手机主屏幕，接近原生APP体验
13. **42个自动化测试**：覆盖所有协议行为和API端点
14. **八层知识产权保护**：AGPL-3.0 + 8项专利 + 商标 + 软著 + 双平台确权
