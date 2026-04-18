# Skill — task_dispatch

## 用途
把用户的自然语言请求，拆解成符合 A2A schema 的子任务计划（dispatch payload）。

## 触发时机
Coordinator 接到任何用户请求的**第一步**，先调此 skill 出 plan，再按 plan 派发。

## 输入
- 用户原始请求文本
- 当前会话上下文（已选知识库范围、参考稿、版本号等）

## 输出
按 `docs/a2a-message-schema.md` §2.5 的 dispatch payload 格式：

```json
{
  "user_request": "...",
  "intent": "generate_report | rewrite_report | search_knowledge",
  "subtasks": [
    {
      "task_id": "uuid",
      "to_agent": "retriever | writer | rewriter | reviewer",
      "task_type": "...",
      "depends_on": ["前置 task_id"],
      "rationale": "为什么要这一步"
    }
  ],
  "max_review_rounds": 2
}
```

## 拆解规则

| intent | 子任务序列 |
|--------|-----------|
| `search_knowledge` | retriever（单步） |
| `generate_report` | retriever → writer → reviewer →（needs_revision 则 writer 重做） |
| `rewrite_report`（数据更新模式） | retriever（取新数据）→ rewriter → reviewer |
| `rewrite_report`（视角/扩展/风格模式） | rewriter → reviewer（可不查 KB） |

## 反例（禁止）
- ❌ 把 retrieve 和 write 合并成一个 task 给 Writer（Writer 不会检索）
- ❌ 跳过 Reviewer 直接交付（除非 intent=search_knowledge）
- ❌ 自己在 Coordinator 里"顺手"做检索/写作
