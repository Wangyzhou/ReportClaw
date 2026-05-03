---
name: gear_detection
description: 任务复杂度自动判档。G1/G2/G3 三档决定 Coordinator 走多深的流程。灵感来自 Shifu Gear System。
---

# Skill — gear_detection

> **核心理念**：不是所有请求都该走 5-Agent 完整流水线。小请求走重流程 = 浪费；大请求走轻流程 = 掉质量。
> 自动判档 + 用户 override，兼顾速度和质量。

---

## Gear 定义

| Gear | 场景 | Agent 编队 | 审查 | 典型耗时 |
|------|------|------------|------|---------|
| **G1** 轻档 | 快速问答 / 元信息查询 / 版本查看 / 知识检索 | Coordinator 直答 或 Retriever 单独 | ❌ | < 10s |
| **G2** 中档 | 短报告生成（<3000字）/ 简单改写（数据更新 / 风格转换）/ 单轮续写 | Retriever → Writer/Rewriter → Reviewer | ✅ 1 轮 | 30-60s |
| **G3** 重档 | 长报告（>3000字）/ 仿写 / 内容扩展 / 视角调整 / 多章节 | 并行 Retriever → Writer/Rewriter → Reviewer | ✅ 最多 2 轮 | 2-5min |

---

## 自动判档规则

### 先看"意图关键词"

| 关键词 | 判为 | 说明 |
|-------|------|------|
| "查一下"、"有没有"、"是否"、"元数据" | G1 | 纯查询 |
| "帮我改数据"、"换成最新数据"、"翻成英文"、"改成通俗" | G2 | 已知模式的简单改写 |
| "写一份报告"、"仿写"、"扩写"、"基于参考稿"、"多视角" | G3 | 创作或复杂改写 |

### 再看"长度/复杂度信号"

| 信号 | 影响 |
|------|------|
| 用户指定 < 3000 字 | 倾向 G2 |
| 用户指定 > 3000 字 | 倾向 G3 |
| 未指定长度 | 默认 G2 |
| 涉及多个知识库分类 | +1 级 |
| 涉及仿写参考稿（`style_conversion` / 仿写） | 强制 G3 |
| 涉及内容扩展（`content_expansion` / 扩写） | 强制 G3 |
| 涉及视角调整（`perspective_shift` / 换视角） | 强制 G3 |

### 最终档位 = max(意图档, 长度档, 强制升档)

**🔒 硬规则优先级**（从高到低）：

1. **强制 G3 类型**（`style_conversion` / `content_expansion` / `perspective_shift`）→ **直接 G3**，**任何字数都不降级**（这三种 sub_mode 的复杂度内禀，跟字数无关）。
2. **明确字数 hard cap/floor**（仅当不命中规则 1 时生效）：
   - 用户**明确说出小于 3000 字的字数**（如"2500 字"、"1500 字"、"2000 字左右"）→ **强制 gear = G2**，**不允许关键词把它推到 G3**。
   - 用户**明确说出大于等于 3000 字的字数**（如"5000 字"、"8000 字"、"3000 字左右"）→ **强制 gear ≥ G3**。
3. **默认规则**（无字数 + 不命中强制 G3 类型）：max(意图档, 长度档默认G2, +1级 升档)。

**判档伪代码**（按此顺序短路）：

```
if intent == rewrite_report and sub_mode in {perspective_shift, content_expansion, style_conversion}:
    return G3     # 终结，无视字数和其他信号
if 用户明确字数 < 3000:
    return G2     # 终结，关键词不再升档
if 用户明确字数 >= 3000:
    return max(G3, 强制升档)
return max(意图档, 长度档默认G2, +1级 升档)
```

**举例**：
- "写一份 2500 字的中国 AI 产业概览报告" → 不是 rewrite，命中字数 hard cap → **G2**
- "把这份报告改成投资人视角"（未指定字数）→ rewrite_report / perspective_shift → **G3**（不被字数缺失影响）
- "写一份深度 AI 产业报告"（未指定字数）→ 默认 G2 + 关键词"深度" + "报告" → G3
- "写一份 8000 字 AI 行业研究" → hard floor → G3
- "帮我改个数据"（未指定字数 + 关键词"改数据" / `data_update`）→ G2（不在强制 G3 三种 sub_mode 内）

---

## 用户 override

用户可以用显式指令强制档位：
- "快速回答就行" → 强制 G1
- "简单处理" → 强制 G2
- "深度做"、"仔细分析"、"高质量" → 强制 G3

---

## 内部判档结果（仅供 task_dispatch 读取，不要单独输出给用户/runtime）

> ⚠️ **本节示例仅说明判档结果的字段含义**。Coordinator 的实际输出**只有 task_dispatch SKILL.md 里的 dispatch payload JSON**，judge 结果会作为 `gear` 字段**嵌入** dispatch payload（不要单独输出 yaml/json gear-only 块）。

判档心算结构（不要直接写到对外输出）：

```
gear: G2
rationale: 用户要求生成 2500 字短报告 + 简单数据更新，单主题单分类
allow_upgrade: true   # 如果 Retriever coverage=低，可升级到 G3 扩搜
```

---

## Gear → 工作流映射

### G1 流程
```
用户请求
  → Coordinator 判断（30ms）
  → Retriever（或直答）
  → 返回用户
  不经过 Reviewer
```

### G2 流程
```
用户请求
  → Coordinator 判断 + task-progress create-task
  → Retriever（单 category，top_k=10）
  → Writer/Rewriter
  → Reviewer 1 轮
  → 通过就交付；不通过给用户选"重试还是收货"
```

### G3 流程
```
用户请求
  → Coordinator create-plan（用户确认）
  → 并行 Retriever（多 category，top_k=20）
  → Writer（style_mimicking 如果需要）
  → Reviewer 第 1 轮
  → (if needs_revision) Writer 修订
  → Reviewer 第 2 轮
  → 通过交付 或 升级给用户
```

---

## 动态升级规则

某些情况下 G2 任务需要即时升级到 G3：

| 触发 | 升级动作 |
|------|---------|
| Retriever 返回 coverage=低 且 missing_topics 非空 | G2 → G3（扩大 scope 再搜） |
| Reviewer 第 1 轮 verdict=needs_revision 且 issues 包含 HIGH | G2 → G3（允许第 2 轮） |
| 用户追加需求（"再加一章 X"） | G2 → G3 |

升级时必须告诉用户：「检测到任务复杂度超出预期，从 G2 升级到 G3，预计多花 2 分钟」

---

## 反例（不要这样判档）

- ❌ 用户"帮我改个数据"就判 G3（浪费，明明是简单 data_update，G2 够）
- ❌ 用户"写份深度报告"判 G1（掉质量）
- ❌ 不问长度就默认 G2（5000 字应该是 G3）
- ❌ 发现 coverage 低还坚持 G2（应该升档）

---

## 判档心算结构示例（不是对外输出 — 仅供推理时心算字段含义）

⛔ **此示例不要复制到对话输出**。Coordinator 对外的唯一 JSON 是 task_dispatch 的 dispatch payload（`{"intent": ..., "gear": ..., "subtasks": [...]}`），其中 `gear` 字段就是这里 judge 出来的结果。

下面字段是判档时**内心要明确的项**（不要单独输出一个 gear-only JSON 块，否则会和 dispatch payload JSON 重复，前端解析失败）：

- `gear`: G1/G2/G3 之一
- `rationale`: 一句话解释（嵌入 dispatch payload 时可省略）
- `agents_to_dispatch`: 派往哪几个 agent（这个映射到 dispatch payload.subtasks 里的 to_agent）
- `review_rounds_cap`: 1 或 2（嵌入 dispatch payload.max_review_rounds）
- `parallel_retrieval`: bool（是否并行检索）
- `allow_upgrade_to_g3`: bool（是否允许动态升级）
- `upgrade_triggers`: 升级触发条件数组
