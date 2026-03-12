# DualSoul 知识产权确权声明 — DISP v1.1 跨语言人格保真翻译

## 确权信息

| 项目 | 内容 |
|------|------|
| **创新名称** | 跨语言人格保真翻译通信方法 (Cross-Language Personality-Preserving Communication) |
| **发明人** | Chengyue5211 |
| **首次公开日期** | 2026年3月13日 |
| **首次公开平台** | GitHub (github.com/Chengyue5211/DualSoul) |
| **首次公开提交** | `c7bdd9d19c0d1dc77f607c35529a0493927b2b20` |
| **首次公开时间戳** | 2026-03-13 07:51:37 +0800 (UTC+8) |
| **协议版本** | DISP v1.1 |
| **软件版本** | DualSoul v0.3.0 |
| **许可证** | AGPL-3.0-or-later (代码) / CC BY 4.0 (文档) |
| **镜像仓库** | Gitee (gitee.com/chengyue5211/DualSoul) |

---

## 创新内容摘要

### 核心创新

在双身份社交协议（DISP）框架下，将数字分身（Digital Twin）从社交代理扩展为**文化桥梁**——利用用户的人格画像（personality profile）进行跨语言翻译，使翻译结果不仅语言正确，而且保留说话人的个人风格（幽默感、语气、正式程度、惯用表达）。

### 与现有技术的区别

| 现有技术 | 局限性 | 本发明的区别 |
|----------|--------|-------------|
| Google Translate / DeepL | 翻译语言准确但丢失个人风格 | 通过人格画像保留说话人特征 |
| 微信/iMessage内置翻译 | 仅嵌入通用翻译，无个性化 | 以人格引擎驱动翻译 |
| Meta SeamlessM4T | 语音翻译无人格保真 | 在协议层面定义翻译溯源 |
| ChatGPT多语言模式 | AI通用多语言，不代表特定用户 | 翻译反映特定用户的说话风格 |

### 技术要素

1. **协议扩展**：DISP消息格式新增 `original_content`、`original_lang`、`target_lang`、`translation_style` 四个字段
2. **自动检测机制**：基于 `preferred_lang` 字段差异自动触发跨语言翻译
3. **人格保真翻译提示词工程**：将用户人格画像注入翻译过程
4. **独立翻译服务**：`POST /api/social/translate` 端点
5. **翻译不变式**：5条协议级不变式（溯源、透明度、人格保真、语言有效性、防重复翻译）

---

## 确权证据链

### 第一层：Git提交记录（不可篡改的时间戳）

```
提交哈希: c7bdd9d19c0d1dc77f607c35529a0493927b2b20
提交时间: 2026-03-13 07:51:37 +0800
提交消息: feat: DISP v1.1 跨语言人格保真翻译——数字分身充当文化桥梁
平台记录: GitHub + Gitee 双平台同步推送
```

验证方法：
```bash
git log --format="%H %ai %s" c7bdd9d -1
# 输出: c7bdd9d19c0d1dc77f607c35529a0493927b2b20 2026-03-13 07:51:37 +0800
```

### 第二层：文件变更清单

本次提交涉及13个文件，681行新增代码/文档：

| 文件 | 类型 | 创新内容 |
|------|------|----------|
| `dualsoul/twin_engine/responder.py` | 核心代码 | 完整翻译引擎实现 |
| `dualsoul/twin_engine/personality.py` | 核心代码 | 人格画像+语言映射 |
| `dualsoul/database.py` | 数据库 | preferred_lang + 翻译字段 |
| `dualsoul/models.py` | 数据模型 | TranslateRequest + target_lang |
| `dualsoul/routers/social.py` | API路由 | /translate端点 |
| `docs/whitepaper.md` | 白皮书 | 第6章跨语言人格保真通信 |
| `docs/protocol.md` | 协议规范 | 第10章跨语言翻译协议 |
| `docs/PATENT_DISCLOSURE.md` | 专利交底 | 专利四完整技术描述 |
| `tests/test_social.py` | 测试 | 7个翻译相关测试 |

### 第三层：关联创新历史

| 日期 | 提交 | 创新内容 |
|------|------|----------|
| 2026-03-05 | `1cb4327` | DualSoul首次公开（DISP v1.0） |
| 2026-03-05 | `c4ddb5e` | 微信小程序实现 |
| 2026-03-05 | `a3cad1b` | 白皮书v1.1（全面发展模型） |
| 2026-03-13 | `1186416` | 许可证变更(MIT→AGPL-3.0) + 专利1-3交底 |
| 2026-03-13 | `c7bdd9d` | **DISP v1.1 跨语言人格保真翻译 + 专利4** |

---

## 专利申请关键日期

| 事项 | 日期 | 说明 |
|------|------|------|
| 首次公开（专利1-3） | 2026-03-05 | GitHub提交记录 |
| 首次公开（专利4） | 2026-03-13 | GitHub提交记录 |
| 专利申请宽限期截止（专利1-3） | **2026-09-05** | 首次公开后6个月 |
| 专利申请宽限期截止（专利4） | **2026-09-13** | 首次公开后6个月 |

> **重要提示**：中国专利法对公开后的宽限期有严格限制。建议尽早提交专利申请，不要等到截止日期。

---

## 声明

本文档作为知识产权确权的辅助证据，与以下材料共同构成完整的确权证据链：

1. GitHub仓库提交历史（github.com/Chengyue5211/DualSoul）
2. Gitee镜像仓库提交历史（gitee.com/chengyue5211/DualSoul）
3. 专利技术交底书（docs/PATENT_DISCLOSURE.md）
4. 商业许可证（COMMERCIAL_LICENSE.md）
5. 白皮书（docs/whitepaper.md）
6. 协议规范（docs/protocol.md）

---

*Chengyue5211 | 2026年3月13日*
