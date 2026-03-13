# DualSoul — 开发指南

## 项目定位
DualSoul是"第四种社交"——人+AI融合社交协议(DISP)。每个用户拥有真人身份+数字分身身份，四模式对话(R-R/R-T/T-R/T-T)，跨语言人格保真翻译。

## 当前状态 (2026-03-13)
- **版本**: v0.6.1 / DISP v1.1
- **许可证**: AGPL-3.0-or-later
- **测试**: 42个全通过 (`python -m pytest tests/ -v`)
- **代码**: Python后端 + 单文件SPA前端
- **已完成功能**: WebSocket实时消息、分身引导流程、PWA、离线分身自动回复、
  分身自聊（无需好友即可体验）、双头像赛博风视觉、消息翻译按钮、
  从聊天记录自动学习说话风格、分身身份意识+对话记忆

## 技术栈
- 后端: FastAPI + SQLite + JWT + httpx + bcrypt
- Twin引擎: dualsoul/twin_engine/ (AI回复+跨语言翻译)
- AI: 通义千问 (OpenAI兼容API, 通过环境变量配置)
- 前端: web/index.html (单文件SPA)
- 小程序: miniprogram/ (已完成,不再作为主力方向)

## 关键文件
- `dualsoul/twin_engine/responder.py` — 核心: AI回复+翻译+分身自聊
- `dualsoul/twin_engine/personality.py` — 人格画像+语言映射
- `dualsoul/twin_engine/learner.py` — 从聊天记录自动学习说话风格
- `dualsoul/routers/social.py` — 消息/好友/翻译/分身聊天路由
- `dualsoul/routers/identity.py` — 身份/头像/风格学习路由
- `dualsoul/database.py` — 数据库schema(3表)
- `docs/whitepaper.md` — 白皮书v1.1(13章)
- `docs/protocol.md` — 协议规范v1.1(10章)

## 部署
- 服务器: 47.93.149.187 (SSH别名: nianlun)
- DualSoul路径: /root/DualSoul/
- 访问地址: http://47.93.149.187/ds/ (域名 dualsoul.cn 待ICP备案)
- Nginx: 通过 /ds/ 路径前缀代理到 uvicorn (port 8000)
- AI配置: AI_BASE_URL / AI_API_KEY / AI_MODEL 环境变量
- 部署方式: 本地编辑 → commit → scp 到服务器 → systemctl restart dualsoul

## 当前开发方向
已完成 P0 任务(WebSocket/PWA/离线分身/引导流程/部署)，进入 P1 迭代：
- [x] 分身自聊（无需好友体验产品）
- [x] 双头像视觉升级（赛博风分身 vs 真人风）
- [x] 消息翻译按钮（手动触发，支持方言）
- [x] 从聊天记录自动学习说话风格
- [x] 分身身份意识+多轮对话记忆
- [x] 方言自动检测+翻译
- [x] 首页新用户引导简化（直接进分身对话）
- [x] 域名 + HTTPS（dualsoul.cn，Let's Encrypt）
- [x] 风格模板选择器（预设卡片+微调标签）
- [x] 分身头像风格选择器（7种CSS滤镜：赛博/霓虹/素描/波普/梦幻/冰蓝）
- [x] Service Worker缓存问题修复 + applyLang初始化顺序修复
- [ ] ICP备案完成后启用 dualsoul.cn 域名
- [ ] HTTPS 443端口连通性排查（安全组已开但外部不通）

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
