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

| 场景 | 缺失信息 | 必须问用户的问题 |
|------|---------|----------------|
| `rewrite_report`，用户说"换个视角" / "从XX视角重写" 但没有指定具体视角 | 目标视角 | "请问您希望从哪个视角重写？（如：投资者视角、政策制定者视角、消费者视角）" |
| `rewrite_report`，用户说"仿写" / "按这个风格写" 但没有 @mention 参考文档 | 参考文档 | "请 @mention 您想仿写风格的参考文档，或告知文档名称。" |
| `rewrite_report`，用户说"换风格" 但没有说明目标风格 | 目标风格 | "请描述目标风格（如：学术论文风格、新闻稿风格、咨询报告风格）。" |
| `generate_report`，用户请求话题非常宽泛（如"写个报告"）且未指定主题 | 报告主题 | "请描述报告主题和目标读者。" |

**只有上面四种情况才需要打断**，其他场景直接拆解，不要过度追问。

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

## 输出格式

```json
{
  "user_request": "帮我把这份报告改成投资者视角",
  "intent": "rewrite_report",
  "sub_mode": "perspective_shift",
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

---

## 反例（禁止）

- ❌ 把 retrieve 和 write 合并成一个 task 给 Writer（Writer 不会检索）
- ❌ 跳过 Reviewer 直接交付（除非 intent=search_knowledge）
- ❌ 自己在 Coordinator 里"顺手"做检索/写作
- ❌ rewrite_report 时不发 fetch_document，导致 Rewriter 拿不到源稿
- ❌ perspective_shift / style_conversion 在 Step 0 未确认具体视角/风格就直接派发
- ❌ 改写时把源稿也加入检索 doc_ids（源稿通过 fetch_document 取，不是用来检索新数据的）
