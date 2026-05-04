---
name: task_dispatch
description: "把用户的自然语言请求，拆解成符合 A2A schema 的子任务计划（dispatch payload）。"
---

# Skill — task_dispatch

## 用途
把用户的自然语言请求，拆解成符合 A2A schema 的子任务计划（dispatch payload）。

## 触发时机
Coordinator 接到任何用户请求的**第一步**，先调此 skill 出 plan，再按 plan 派发。

## Step 0：派发前澄清（必须）

在生成 subtasks 之前，检查以下条件。**任意一条不满足，必须先向用户提问，拿到答案后再派发**。

| 场景 | 缺失信息 | 必须问用户的问题（**请直接复述这些句式之一，保留 "请问/请描述/请提供/请告知" 起手词**） |
|------|---------|----------------|
| `rewrite_report`，用户说"换个视角" / "换种立场" 但**完全没说**视角名 | 目标视角 | "请问您希望从哪个视角重写？（如：投资者视角、政策制定者视角、消费者视角）" |
| `rewrite_report`，用户说"改一下" / "修改" 但没有 @mention 任何源稿 | 源稿 | "请提供您要改写的源稿，请@mention 文档名，或告知文档标题。" |
| `rewrite_report`，用户说"仿写" / "按这个风格写" 但没有 @mention 参考文档 | 参考文档 | "请提供想仿写风格的参考文档，请@mention 或告知文档名称。" |
| `rewrite_report`，用户说"换风格" 但没有说明目标风格 | 目标风格 | "请描述目标风格（如：学术论文风格、新闻稿风格、咨询报告风格）。" |
| `generate_report`，用户请求话题非常宽泛（如"写个报告"）且未指定主题 | 报告主题 | "请描述报告主题和目标读者。" |

**澄清话术硬规则**：发起澄清时，**第一句必须以"请问"、"请描述"、"请提供"、"请告知"之一开头**（不要用"麻烦您…"、"能否…"、"您是否…"等其他句式）。这是前端解析澄清意图的标记词。

**只有上面四种情况才需要打断**，其他场景直接拆解，不要过度追问。

**视角粒度规则（重要）**：用户给了**任何角色名**（"投资人"、"政策制定者"、"消费者"、"年轻用户"、"创业者"等），就算具体视角，**直接派发**，不再追问粒度。

❌ 反例："投资人视角"已经具体，**禁止**追问"风投/二级/战略哪种投资人"。如确需细分，由 Rewriter 在 perspective_shift skill 内消化，不在 Step 0 拦截。

---

## @mention 语义规则

| intent | @mention 含义 |
|--------|--------------|
| `generate_report` | 限定检索范围——只在这几个文档里搜索，不搜全库 |
| `rewrite_report` | `mentioned_docs[0]` 是**改写的源稿**；其余 doc 限定新数据检索范围 |

前端已将 @mention 解析为 `mentionedDocs: [{docId, docName, category, datasetId}]`，Coordinator 从消息元数据中读取。

---

## 改写模式识别

| 用户关键词 | sub_mode |
|-----------|---------|
| 更新数据 / 最新数据 / 数据换新 | `data_update` |
| 换视角 / X视角 / 站在X角度 | `perspective_shift` |
| 扩写 / 补充 / 加更多内容 | `content_expansion` |
| 仿写 / 按风格 / 换风格 | `style_conversion` |

---

## 拆解规则

| intent | 子任务序列 |
|--------|-----------|
| `search_knowledge` | retriever（单步） |
| `generate_report` | retriever → writer → reviewer →（needs_revision 则 writer 重做） |
| `rewrite_report / data_update` | retriever（取新数据，doc_ids=非源稿的@mention）→ fetch_document（取源稿全文）→ rewriter → reviewer |
| `rewrite_report / perspective_shift` | fetch_document（取源稿全文）→ rewriter → reviewer |
| `rewrite_report / content_expansion` | fetch_document（取源稿全文）→ retriever（补充检索）→ rewriter → reviewer |
| `rewrite_report / style_conversion` | fetch_document（取源稿全文）→ rewriter → reviewer |

**fetch_document** 是发给 Retriever 的子任务，`task_type=fetch_document`，让 Retriever 取 `mentioned_docs[0]` 的完整文档内容交给 Rewriter 作为 `source_doc`。

---

### 修订轮（round ≥ 2）的 task_type 规则

审查回环（reviewer 返回 `needs_revision`）派 Writer 重做时，**`task_type` 仍取 `write`**（**不是** `revise` / `amend` / `fix` / 任何自创类型）。修订语义只通过 `payload.revision_context` 字段表达，**不**通过新的 task_type 表达。

合法 `task_type` 集合（封闭枚举）：`retrieve` / `fetch_document` / `write` / `rewrite` / `review`。

| 错误示范 | 正确示范 |
|---------|---------|
| `"task_type": "revise"` ❌ | `"task_type": "write"` + `payload.revision_context = {...}` ✅ |
| `"task_type": "amend"` ❌ | 同上 ✅ |
| `"task_type": "fix"` ❌ | 同上 ✅ |

理由：`task_type` 是路由关键字（OpenClaw 用它派发到对应 Agent），新增类型会破坏 Writer/Rewriter 的 dispatch 路由。修订是 Writer 的 `write` 任务的一个 mode，不是新种类。

---

## 输出格式

**任何 intent / 任何 gear**（包括 G1 search_knowledge），**第一个非空输出必须是完整 dispatch payload JSON**（一个 ```json fenced 代码块，外层只允许必要的中文铺垫一两句、不允许夹其他 JSON 块）。

dispatch payload JSON 是：
1. **task-progress 前端可视化的唯一数据源**（无 JSON 则前端空白）
2. **下游 sessions_spawn 派发的来源**（runtime 读 JSON 里的 subtasks 派发）

⛔ 禁止把 gear_detection 的"输出示例"（gear/rationale/agents_to_dispatch 那种短 JSON）误当作 dispatch payload 输出 — 它是 gear_detection skill 文档里的内部示例，**不是**本次该输出的 JSON。本 skill 只接受下面这种带 `intent + subtasks + gear` 的完整 dispatch payload。

⛔ 禁止跳过 dispatch payload JSON 直接产出 sessions_spawn 调用块（哪怕是 G1 单步检索 — G1 也必须先出含 1 条 subtask 的 dispatch JSON，再产 sessions_spawn）。

输出顺序：**dispatch payload JSON（必须）→ sessions_spawn 调用块（按附录格式）**。

```json
{
  "user_request": "帮我把这份报告改成投资者视角",
  "intent": "rewrite_report",
  "sub_mode": "perspective_shift",
  "gear": "G3",
  "subtasks": [
    {
      "task_id": "t1",
      "to_agent": "retriever",
      "task_type": "fetch_document",
      "payload": {
        "doc_id": "<mentionedDocs[0].docId>",
        "dataset_id": "<mentionedDocs[0].datasetId>",
        "doc_name": "<mentionedDocs[0].docName>"
      },
      "depends_on": [],
      "rationale": "取源稿全文，供 Rewriter 改写"
    },
    {
      "task_id": "t2",
      "to_agent": "rewriter",
      "task_type": "rewrite",
      "payload": {
        "mode": "perspective_shift",
        "source_doc_task_id": "t1",
        "target_perspective": "投资者视角"
      },
      "depends_on": ["t1"],
      "rationale": "按目标视角改写"
    },
    {
      "task_id": "t3",
      "to_agent": "reviewer",
      "task_type": "review",
      "depends_on": ["t2"],
      "rationale": "质检改写结果"
    }
  ],
  "max_review_rounds": 2
}
```

### 非首轮派发示例（接到 reviewer round-1 issues 之后）

审查回环 round=1 → reviewer 返回 `verdict=needs_revision` → Coordinator 派 Writer round=2 时的完整 dispatch payload（实测 Round 5 smoke 在该场景 LLM 偶尔跳过 dispatch JSON 直出 sessions_spawn — **即使是修订轮，必须先 emit 完整 dispatch JSON，再 sessions_spawn**）：

```json
{
  "user_request": "写一份2500字的中国AI产业概览报告",
  "intent": "generate_report",
  "gear": "G2",
  "subtasks": [
    {
      "task_id": "t2_round2",
      "to_agent": "writer",
      "task_type": "write",
      "payload": {
        "mode": "from_outline",
        "topic": "中国AI产业概览",
        "revision_context": {
          "round": 2,
          "previous_report": "<round-1 Writer 草稿全文 markdown 引用>",
          "review_issues": [
            {
              "id": "issue_001",
              "type": "data_mismatch",
              "severity": "HIGH",
              "location": {"section": "二、市场规模", "line_range": [12, 14]},
              "detail": "round-1 草稿声明 2025 年市场规模 25%，与 doc_001_p15_3 的 21% 不符",
              "suggested_fix": "改回 21% 并保留 [ref:doc_001_p15_3]"
            },
            {
              "id": "issue_002",
              "type": "fabrication",
              "severity": "HIGH",
              "location": {"section": "三、垂直场景", "line_range": [42, 45]},
              "detail": "声称'深度求索市占率领先'但无对应 chunk 支撑",
              "suggested_fix": "删除该论断或补充检索"
            }
          ],
          "must_fix_severities": ["HIGH"]
        }
      },
      "depends_on": [],
      "rationale": "按 reviewer round-1 issues 修订上一版报告（round=2，max_review_rounds=2 还有 1 轮余额）"
    },
    {
      "task_id": "t3_round2",
      "to_agent": "reviewer",
      "task_type": "review",
      "payload": {"round": 2},
      "depends_on": ["t2_round2"],
      "rationale": "对 round-2 修订稿再质检"
    }
  ],
  "max_review_rounds": 2
}
```

要点：
1. **`task_type` 仍取 `write`** — 不要改成 `revise`（见上节"修订轮 task_type 规则"）。
2. **`revision_context` 嵌在 writer subtask 的 `payload` 字段里**，不要放到顶层 dispatch payload，也不要放到 subtask 的 root（payload 之外）— 这两条都是 fallback，会触发下游 smoke 的 `[WARN]` 提示。
3. `revision_context.round=2`，并把 reviewer 返回的 issues 完整传入 `review_issues` 数组（保留 id / severity / location / suggested_fix）。
4. `max_review_rounds=2` 已耗尽时（round-2 仍 needs_revision），**不要再派 round=3 写**，直接给用户升级提示（自然语言，不出 dispatch JSON），见 SOUL.md 禁止无限回环铁律。

---

## 反例（禁止）

- ❌ 把 retrieve 和 write 合并成一个 task 给 Writer（Writer 不会检索）
- ❌ 跳过 Reviewer 直接交付（除非 intent=search_knowledge）
- ❌ 自己在 Coordinator 里"顺手"做检索/写作
- ❌ rewrite_report 时不发 fetch_document，导致 Rewriter 拿不到源稿
- ❌ perspective_shift / style_conversion 在 Step 0 未确认具体视角/风格就直接派发
- ❌ 改写时把源稿也加入检索 doc_ids（源稿通过 fetch_document 取，不是用来检索新数据的）
- ❌ 生成 subtasks 后不调 sessions_spawn，只是文字描述计划（计划不等于执行）
- ❌ 用 sessions_list 轮询等结果（等 announce 即可，不要轮询）
- ❌ **直接进入 sessions_spawn 块跳过 dispatch payload JSON 输出**（前端拿不到可视化数据；JSON + sessions_spawn 两步都要做）
- ❌ **修订轮（round=2）跳过 dispatch JSON 直接 sessions_spawn 派发 Writer**（即使是回环重派，前端 task-progress 仍要看到新 round 的 subtask；先出"非首轮派发示例"那种 dispatch JSON，再 sessions_spawn）
- ❌ **修订轮自创 `task_type="revise"` / `"amend"` / `"fix"`**（合法集只 5 种，修订仍用 `write` + `payload.revision_context`，见"修订轮 task_type 规则"节）
- ❌ **把 `revision_context` 放在顶层 dispatch payload 或 subtask root（payload 之外）**（必须嵌在 writer subtask 的 `payload` 字段里）

---

## 附录：sessions_spawn 调用模板

> ⚠️ 本节是 dispatch payload JSON 输出**之后**的派发执行模板。如果你还没产出 ## 输出格式 节里的 JSON，**先产 JSON**，再读本节。

**拆解完 subtasks 并输出 JSON 后，按下面步骤用 `sessions_spawn` 实际执行派发。**

### 单个子任务调用格式

```json
sessions_spawn({
  "agentId": "retriever",
  "mode": "run",
  "runtime"="subagent",
  "task": "你是 ReportClaw 检索员（reportclaw-retriever）。\n\n## 本次任务\ntask_type: retrieve\npayload:\n```json\n{\"query\": \"AI市场规模\", \"search_scope\": {\"categories\": [\"行业报告\"]}, \"top_k\": 10}\n```\n\n## 交付要求\n按 SOUL.md Output Format 返回 results 数组，每条带 chunk_id + source + content + relevance_score。"
})
```

### 串行执行（有依赖）

```
1. sessions_spawn(retriever, task=t1)
   → 等 t1 announce 回来，拿到 retrieval_results
2. sessions_spawn(writer, task=t2, payload 包含 t1 的 retrieval_results)
   → 等 t2 announce 回来，拿到 report_draft
3. sessions_spawn(reviewer, task=t3, payload 包含 t2 的 report_draft)
   → 等 t3 announce 回来，拿到 review_result
```

### 并行执行（无依赖，G3 多 category 检索）

```
同时 sessions_spawn 多个 retriever（不同 categories），
全部 announce 回来后合并 results，再 sessions_spawn writer。
```

### task 参数写法要点

子 Agent **只会收到 AGENTS.md + TOOLS.md**，不继承本 session 上下文，因此 `task` 必须包含：
1. 角色说明（一句话：你是 XXX）
2. `task_type`（retrieve / write / rewrite / review）
3. 完整的 `payload` JSON
4. 交付格式要求（引用 SOUL.md 的 Output Format 或明确列出字段）

---

## 审查回环硬规则（BY_ORDER SOP）

**借鉴自 MetaGPT 的 BY_ORDER SOP**：审查回环的终止条件**不是 LLM 判断**，是 round counter 硬规则。Coordinator 必须按下面的状态机执行，**禁止 LLM 自由决定"是否再改一轮"**。

### 状态机

```
状态: rounds_used = 0, max_review_rounds = 2 (G2) / 3 (G3 仅 dynamic upgrade)

派 Writer (round 1)
  → 收 Writer draft
  → 派 Reviewer (round 1)
  → rounds_used = 1
  → 看 Reviewer verdict:
      verdict = "pass"            → 交付 (终止)
      verdict = "fail"            → 升级用户 (终止，不重试)
      verdict = "needs_revision":
          if rounds_used < max:
              → 派 Writer (round 2, 带 revision_context)
              → 派 Reviewer (round 2)
              → rounds_used = 2
              → 看 verdict:
                  pass            → 交付
                  needs_revision  → 升级用户 (硬终止：第 3 轮不允许)
                  fail            → 升级用户
          else:
              → 升级用户 (硬终止)
```

### 升级用户的固定话术

当硬终止触发时，必须给用户**3 选项**，不要给 4 个或 2 个，不要让 LLM 自由表达：

```
当前报告已达最大审查轮数 (rounds_used / max_review_rounds)，仍存在 N 个 HIGH 级别问题：
- 接受当前版本（已知问题列表附后）
- 重新开始（可调整知识库范围 / 报告主题 / 长度约束）
- 由人工继续修订（导出当前 draft，您手动改完上传新版本）

请选择 1/2/3。
```

### 为什么硬规则而非 LLM 判断

1. **终止性可证明**：硬规则保证 100% 终止；LLM 自由判断有"再改一轮也许更好"的概率漂移，最坏 case token 失控
2. **成本可预算**：max_review_rounds × 单轮成本 = 上限，前端显示"本轮预算 ≤ $X"
3. **可重放**：同输入 + 同 round counter → 同结果（LLM 自由判断破坏可复现性）
4. **审计留痕**：rounds_used 字段写进 `revision_context`，对应 deliverables/generation-log.json 一行记录

---

## 反例（禁止）

- ❌ 把 retrieve 和 write 合并成一个 task 给 Writer（Writer 不会检索）
- ❌ 跳过 Reviewer 直接交付（除非 intent=search_knowledge）
- ❌ 自己在 Coordinator 里"顺手"做检索/写作
- ❌ rewrite_report 时不发 fetch_document，导致 Rewriter 拿不到源稿
- ❌ perspective_shift / style_conversion 在 Step 0 未确认具体视角/风格就直接派发
- ❌ 改写时把源稿也加入检索 doc_ids（源稿通过 fetch_document 取，不是用来检索新数据的）
- ❌ 生成 subtasks 后不调 sessions_spawn，只是文字描述计划（计划不等于执行）
- ❌ 用 sessions_list 轮询等结果（等 announce 即可，不要轮询）
- ❌ 让 LLM 自由判断"还要不要再改一轮"（违反 BY_ORDER SOP — 必须按 rounds_used/max_review_rounds 硬规则）
- ❌ 升级用户时让 LLM 自由表达建议（必须用上面 3 选项固定话术，前端 parser 才能识别）
- ❌ 第 3 轮派 Writer (rounds_used == max_review_rounds 时仍触发新 round) — 硬终止条件违反
