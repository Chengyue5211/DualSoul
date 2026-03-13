# DualSoul — 开发指南

## 项目定位
DualSoul是"第四种社交"——人+AI融合社交协议(DISP)。每个用户拥有真人身份+数字分身身份，四模式对话(R-R/R-T/T-R/T-T)，跨语言人格保真翻译。

## 当前状态 (2026-03-13)
- **版本**: v0.4.0 / DISP v1.1
- **许可证**: AGPL-3.0-or-later
- **测试**: 42个全通过 (`python -m pytest tests/ -v`)
- **代码**: Python后端 + 单文件SPA前端
- **新增功能**: WebSocket实时消息、分身引导流程、PWA、离线分身自动回复

## 技术栈
- 后端: FastAPI + SQLite + JWT + httpx + bcrypt
- Twin引擎: dualsoul/twin_engine/ (AI回复+跨语言翻译)
- AI: 通义千问 (OpenAI兼容API, 通过环境变量配置)
- 前端: web/index.html (单文件SPA)
- 小程序: miniprogram/ (已完成,不再作为主力方向)

## 关键文件
- `dualsoul/twin_engine/responder.py` — 核心翻译引擎
- `dualsoul/twin_engine/personality.py` — 人格画像+语言映射
- `dualsoul/routers/social.py` — 消息/好友/翻译路由
- `dualsoul/database.py` — 数据库schema(3表)
- `docs/whitepaper.md` — 白皮书v1.1(13章)
- `docs/protocol.md` — 协议规范v1.1(10章)

## 部署
- 服务器: 47.93.149.187 (SSH别名: nianlun)
- 路径: /root/yuechuang_nianlun/ (与年轮共享服务器)
- AI配置: AI_BASE_URL / AI_API_KEY / AI_MODEL 环境变量

## 当前开发方向：P0任务
用户已决定将DualSoul做成独立产品(PWA)，和年轮项目分开：
1. WebSocket实时消息（替换HTTP轮询）
2. PWA化（manifest + Service Worker）
3. Twin后台自主回复（用户离线Twin仍能回复）
4. Twin性格引导流程（新用户首次体验）
5. 部署上线

## 用户工作偏好
- 每次修改完成后自动执行：commit → push
- 以做自己产品的精神主动推进
- 追求世界级品质
- 不懂技术细节，需要通俗解释

## 知识产权
- 4项专利交底书: docs/PATENT_DISCLOSURE.md (截止2026-09)
- 确权声明: docs/IP_CONFIRMATION_v1.1.md
- 软著材料: 桌面/DualSoul双身份社交协议/软著申请材料/ (v1.1全套)
- 策略报告: 桌面/DualSoul双身份社交协议/09_产品策略深度分析报告.docx
