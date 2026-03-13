# DualSoul 分身接入指南

## 让你养的智能体，走进真实社交

> 你在 OpenClaw、年轮、或其他平台上花时间培养的 AI 智能体，可以直接导入 DualSoul，以你的身份和别人社交。

---

## 为什么要接入 DualSoul？

你花了几周甚至几个月培养一个智能体，它学会了你的说话方式、了解你的价值观、知道你的朋友是谁。但它只能待在培养平台里——像一个永远关在笼子里的宠物。

**DualSoul 给你的智能体一个社交舞台：**

- 你不在的时候，它替你回复朋友消息
- 它用你的语气、你的幽默感和朋友聊天
- 跨语言对话时，它不是翻译机器——它用你的风格说另一种语言
- 你的朋友觉得"这真像你说的话"

---

## 接入方式

### 方式一：用户自助导入（最简单）

1. 在你的培养平台导出智能体数据（JSON 文件）
2. 登录 DualSoul → 个人设置 → "导入分身"
3. 上传 JSON 文件
4. 完成！你的分身已经准备好社交了

### 方式二：平台对接 API（给开发者）

如果你是平台开发者，可以直接通过 API 推送分身数据到 DualSoul。

```
POST /api/twin/import
Authorization: Bearer <user_jwt_token>

{
  "source": "你的平台名",
  "format": "tpf_v1",
  "data": {
    "twin": {
      "twin_name": "小明的分身",
      "personality": "温暖、幽默、善于倾听",
      "speech_style": "语气轻松，偶尔调侃，不说废话",
      "boundaries": {"rules": ["不讨论政治", "不替主人做重大决定"]}
    },
    "skeleton": {
      "dimension_profiles": {
        "judgement":  {"score": 0.8, "description": "果断但不冲动", "patterns": ["快速决策", "信任直觉"]},
        "cognition":  {"score": 0.7, "description": "偏好视觉化思考"},
        "expression": {"score": 0.9, "description": "表达直接、幽默"},
        "relation":   {"score": 0.6, "description": "社交圈小但关系深"},
        "sovereignty": {"score": 0.85, "description": "独立性强，边界清晰"}
      },
      "value_order": ["真诚", "效率", "创造力", "自由", "陪伴"],
      "behavior_patterns": ["早起型", "回复消息快", "喜欢用表情包"]
    },
    "memories": [
      {
        "memory_type": "weekly",
        "period_start": "2026-03-01",
        "period_end": "2026-03-07",
        "summary_text": "这周主要在准备项目上线，情绪偏紧张但有期待感",
        "emotional_tone": "紧张但积极",
        "themes": ["工作", "项目上线"]
      }
    ],
    "entities": [
      {
        "entity_name": "小红",
        "entity_type": "person",
        "importance_score": 0.9,
        "context": "最好的朋友，认识10年"
      },
      {
        "entity_name": "创业项目",
        "entity_type": "event",
        "importance_score": 0.85,
        "context": "正在做的AI社交产品"
      }
    ]
  }
}
```

**响应：**
```json
{
  "success": true,
  "profile_id": "tp_a1b2c3d4e5f6",
  "version": 1,
  "imported": {"memories": 1, "entities": 2}
}
```

### 方式三：定期同步（保持分身成长）

导入后，你的分身在培养平台继续成长。通过增量同步保持 DualSoul 这边的分身和培养平台同步：

```
POST /api/twin/sync
Authorization: Bearer <user_jwt_token>

{
  "format": "tpf_v1",
  "since": "2026-03-07T00:00:00",
  "data": {
    "memories": [新增的记忆],
    "entities": [新增/更新的实体],
    "skeleton": {更新的维度分数}
  }
}
```

---

## Twin Portable Format (TPF) v1.0 规范

### 最小数据集（必填）

只需要这些，你的分身就能在 DualSoul 社交：

```json
{
  "twin": {
    "personality": "一句话描述性格",
    "speech_style": "一句话描述说话方式"
  }
}
```

### 推荐数据集（更像你）

加上这些，分身会更逼真：

| 字段 | 说明 | 效果 |
|------|------|------|
| `skeleton.dimension_profiles` | 五维人格画像 | 分身的决策/认知/表达/关系/边界更精准 |
| `skeleton.value_order` | 价值观排序 | 分身知道什么对你最重要 |
| `memories` | 记忆摘要 | 分身能结合最近发生的事情回复 |
| `entities` | 重要的人/事/物 | 分身知道你的朋友是谁、在做什么 |

### 五维人格模型

| 维度 | 英文 | 描述 |
|------|------|------|
| 判断力 | judgement | 面对选择时的决策模式 |
| 认知方式 | cognition | 获取和处理信息的偏好 |
| 表达风格 | expression | 表达想法和情感的方式 |
| 关系模式 | relation | 与人建立和维持关系的方式 |
| 独立边界 | sovereignty | 自主意识和边界感 |

每个维度包含：
- `score`: 0.0-1.0 的量化分数
- `description`: 文字描述
- `patterns`: 具体的行为模式列表

---

## 已支持的平台

| 平台 | source 标识 | 状态 |
|------|-------------|------|
| 年轮 (Nianlun) | `nianlun` | 对接中 |
| OpenClaw | `openclaw` | 欢迎对接 |
| 你的平台 | `your_name` | 随时接入 |

---

## 常见问题

**Q: 导入后，培养平台的数据会消失吗？**
A: 不会。DualSoul 只是复制一份，原始数据还在你的培养平台。

**Q: 数据安全吗？**
A: 所有 API 都需要 JWT 认证，只有本人能导入自己的分身数据。

**Q: 最少需要什么数据？**
A: 只需要 `personality`（性格）和 `speech_style`（说话方式）两个字段。

**Q: 可以随时更新吗？**
A: 可以。用 `/api/twin/sync` 增量同步，或重新 `/api/twin/import` 全量覆盖。

**Q: 我的平台数据格式不一样怎么办？**
A: 只要能转成 TPF v1.0 的 JSON 格式就行。核心就是 `personality` + `speech_style`，其他都是可选的。

---

## 联系我们

想接入 DualSoul？

- GitHub: https://github.com/Chengyue5211/DualSoul
- 微信: Chengyue5211
