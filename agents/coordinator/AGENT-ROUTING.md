# AGENT-ROUTING.md — 子 Agent 路由手册

> Coordinator 专用：接到用户请求时快速判断派给谁 + 调哪个 skill。

---

## 📌 调用原则

1. Coordinator 只做调度，不执行具体任务
2. 优先使用 Agent 自带的专用 skill，不指定工具
3. 一个任务可串行/并行多个 Agent
4. 不确定意图时用 `%%选项%%` 澄清，不猜

---

## 🤖 子 Agent 清单（4 个）

### 1️⃣ Retriever（检索员）

**职责**：从知识库精准检索 + 来源标注 + 覆盖度评估

| Skill | 适用场景 |
|-------|---------|
| `hybrid_search` | 向量+关键词混合检索（默认用这个） |
| `source_tracking` | 每个 chunk 标 doc_id/page/paragraph_id |
| `coverage_analysis` | 评估知识库对主题的覆盖度，找 missing_topics |

**典型调用**：
- 用户要报告/改写需要新数据 → Retriever + `hybrid_search`
- 用户问"知识库里有没有关于 X 的资料" → Retriever + `coverage_analysis`

**禁忌**：Coordinator 不要指定"用 BM25"或"用向量"，由 Retriever 自己决定混合策略。

---

### 2️⃣ Writer（写作员）

**职责**：基于检索结果 + 提纲生成高质量报告（含仿写）

| Skill | 适用场景 |
|-------|---------|
| `outline_generation` | 用户没给提纲时先生成提纲 |
| `section_writing` | 按章节逐段写，每段带 `[ref:chunk_id]` |
| `style_mimicking` | 用户上传参考稿时，学习其风格和结构 |
| `citation_insertion` | 写完后校验所有引用 ID ∈ 检索结果 |

**典型调用**：
- 从零写报告 → Writer + `outline_generation` → `section_writing` → `citation_insertion`
- 仿写参考稿 → Writer + `style_mimicking` → `section_writing`
- 续写章节 → Writer + `section_writing`（传入原稿上下文）

**禁忌**：派发时不要写"用 markdown 格式"，Writer 默认就是 markdown；不要指定字体颜色这种排版细节。

---

### 3️⃣ Rewriter（改写员）

**职责**：4 种模式的智能改写 + diff 对比

| Skill | 适用场景 |
|-------|---------|
| `structure_parser` | 解析原稿结构（所有模式前置步骤） |
| `data_update` | 数据更新模式：保持结构，替换旧数据 |
| `perspective_shift` | 视角调整模式：同内容改立场/受众 |
| `content_expansion` | 内容扩展模式：补充新分析/案例/章节 |
| `style_conversion` | 风格转换：正式↔通俗，中↔英 |
| `diff_generator` | 生成前后对比 diff 视图 |

**典型调用**：
- 数据更新 → Retriever（取新数据）→ Rewriter + `data_update` + `diff_generator`
- 视角调整 → Rewriter + `perspective_shift` + `diff_generator`（不需 Retriever）
- 内容扩展 → Retriever（可选）→ Rewriter + `content_expansion` + `diff_generator`
- 风格转换 → Rewriter + `style_conversion` + `diff_generator`

**禁忌**：Rewriter 不主动查知识库，需要新数据时由 Coordinator 提前调 Retriever。

---

### 4️⃣ Reviewer（审查员）

**职责**：事实/引用/逻辑/格式审查，给 verdict

| Skill | 适用场景 |
|-------|---------|
| `citation_verification` | 校验 chunk_id ∈ 知识库（需回查 chunk content） |
| `review_checklist` | 跑 6 项检查：引用有效/数据准确/逻辑连贯/无虚构/格式/覆盖度 |
| `coverage_scoring` | 给 coverage_score 和 quality_score |

**典型调用**：
- 生成/改写完成 → Reviewer + `review_checklist` + `citation_verification`
- 多轮回环时 Reviewer 只检查"上次问题是否修复"+"新问题"

**禁忌**：
- Reviewer 不重写内容，只发 issue（修改是 Writer/Rewriter 的事）
- Reviewer 必须 60 秒内返回，超时视为 fail（不做文字级校对）
- `severity_threshold = MEDIUM`：HIGH 以上必改，LOW 忽略

---

## 🔀 用户意图 → Agent 调度速查

| 用户说 | 调度 | 说明 |
|-------|------|------|
| "帮我生成一份 X 报告" | Retriever → Writer → Reviewer | 全链路 |
| "这份报告用最新数据改写" | Retriever → Rewriter（data_update）→ Reviewer | 补新数据 |
| "把这份报告改成给投资人看" | Rewriter（perspective_shift）→ Reviewer | 不需新数据 |
| "帮我扩写第二章" | Retriever → Rewriter（content_expansion）→ Reviewer | 可能需新料 |
| "把这份正式报告改成通俗版" | Rewriter（style_conversion）→ Reviewer | |
| "把这份中文报告翻成英文" | Rewriter（style_conversion, lang=en）→ Reviewer | |
| "帮我续写一章关于 X" | Retriever → Writer（continue mode）→ Reviewer | |
| "知识库里有没有 X 的资料" | Retriever + coverage_analysis | 不出报告 |
| "给我看 v2 和 v3 的差异" | 后端 diff 服务（无 Agent） | |
| "把这个报告导出 Word" | 后端导出服务（无 Agent） | |

---

## 🚦 并行 vs 串行决策树

```
新报告生成：
  Retriever（并行检索多 category）→ [汇总] → Writer → Reviewer

改写（数据更新）：
  Retriever（新数据）→ Rewriter → Reviewer

改写（无需新数据）：
  Rewriter → Reviewer

审查多章节报告：
  Reviewer 可并行审多个章节（如报告超过 5000 字）
```

**并行原则**：独立子任务之间并行；有依赖关系的串行。
**并行数上限**：一次最多 3 个子任务并行（避免 API 限流）。

---

## 🎯 Model Tier 路由（配合 Shifu `delegate`）

Gear 管流程深度，Tier 管模型成本。G3 的任务也**不是每一步都用 Opus**——大部分步骤其实 T2 就够。

### Agent × Skill × 推荐 Tier

| Agent | Skill | 默认 Tier | 升档条件 | 降档条件 |
|-------|-------|----------|---------|---------|
| **Coordinator** | gear_detection | T1 | — | — |
| **Coordinator** | task_dispatch | T2 | 用户意图极模糊 → T3 | 已有相同模板复用 → T1 |
| **Coordinator** | quality_check | T2 | Reviewer 3 轮未过 → T3 | — |
| **Retriever** | hybrid_search | T1 | — | — |
| **Retriever** | source_tracking | T1 | — | — |
| **Retriever** | coverage_analysis | T2 | — | 单一主题查询 → T1 |
| **Writer** | outline_generation | T2 | 深度报告/仿写 → T3 | 标准模板报告 → T1 |
| **Writer** | section_writing | T2 | 关键章节（结论/executive summary）→ T3 | 过渡段/附录 → T1 |
| **Writer** | style_mimicking | T3 | — | 风格明显（学术/通俗二选一）→ T2 |
| **Writer** | citation_insertion | T1 | — | — |
| **Rewriter** | structure_parser | T1 | — | — |
| **Rewriter** | data_update | T2 | — | 纯数字替换 → T1 |
| **Rewriter** | perspective_shift | T3 | — | 受众差异小（同一行业内部）→ T2 |
| **Rewriter** | content_expansion | T3 | 新主题陌生领域 → T3 | 扩展同质内容 → T2 |
| **Rewriter** | style_conversion | T2 | 中↔英翻译 → T3 | 正式↔通俗同语言 → T2 |
| **Rewriter** | diff_generator | T1 | — | — |
| **Reviewer** | citation_verification | T1 | — | — |
| **Reviewer** | review_checklist | T2 | — | 简短报告（<2000字）→ T1 |
| **Reviewer** | coverage_scoring | T1 | — | — |

### 关键洞察

1. **Retriever 全员 T1/T2** — 检索任务是模式匹配，不需要 Opus
2. **Writer 主力 T2** — `section_writing` 一个报告调用 N 次，T3 每次都上成本爆炸
3. **Rewriter 的"创意"档位最高** — perspective_shift 和 content_expansion 需要真正的推理，默认 T3 合理
4. **Reviewer 偏 T1** — 审查是规则校验（citation 在不在 KB、字数够不够），不需要深度推理
5. **Style mimicking 特殊** — 学风格需要从少量样本抽象，T3 开始最稳

### 成本估算（写一份 5000 字报告）

| 情景 | 主要 tier 分布 | 相对成本 |
|------|--------------|---------|
| 无脑全 Opus | 全 T3 | 100% |
| 默认 Shifu delegate | 30% T3 / 50% T2 / 20% T1 | ~35% |
| 激进省钱（G2 场景） | 10% T3 / 40% T2 / 50% T1 | ~18% |

**目标**：默认路由把一份 5000 字报告的 token 成本降到"无脑全 Opus"的 **1/3**。

### 铁律

- **Retriever 永远不用 T3** — 如果想让 T3 做检索，说明你 prompt 写糟了
- **citation_verification 永远 T1** — 纯字面匹配，T3 是浪费
- **任何 Agent 的 fallback（失败重试）必须升一档** — 第一次 T2 失败 → 第二次 T3（参考 shifu:delegate 的 upgrade triggers）

### 用户覆盖

用户可以说：
- "这份报告用 Opus 写" → Writer 全档升 T3
- "省钱模式" → 所有默认下降一档（T3→T2, T2→T1）
- "质量优先" → 只把 Writer 的 section_writing 升到 T3，其他保持
