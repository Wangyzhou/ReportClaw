---
name: verification-before-completion
description: 所有 Agent 交付前必须自检输出合规。分两层：任务完成 + 事实正确。
metadata: {"openclaw": {"always": true}}
---

# verification-before-completion

> 每个 Agent 返回结果给 Coordinator 前，必须自查一遍。不合格宁可延迟返回，不交"看起来完成了"的污染产出。

## 两层检查

### 第一层：任务做了（输出 schema 合规）

| Agent | 必查项 |
|-------|-------|
| Retriever | `results[].chunk_id` 存在 / `source` 字段完整 / `coverage_assessment` ∈ {高,中,低} |
| Writer | `report_markdown` 非空 / `citations` 数组非空 / 所有 `[ref:xxx]` ∈ `retrieval_results` / word_count 在约束范围 ±20% |
| Rewriter | `rewritten_markdown` 非空 / `diff.content` 非空 / `changes_summary.mode` 匹配请求 / preserved_citations 有值 |
| Reviewer | `verdict` ∈ {pass, needs_revision, fail} / 每个 issue 带 severity / scores 都是 0-1 浮点 |

### 第二层：事实对了（仅 Writer / Rewriter / Reviewer）

- 有数字/日期/人名/机构名的段落，必须能在 retrieval_results 中找到出处
- 如果找不到 → 视为虚构，立即删掉或标记 `[需补料]`
- 这条规则比"引用完整"严一层：不光要有 `[ref:]`，引用的 chunk 里真的要包含这个数据

## 失败处理

- 第一层不通过 → **不能返回给 Coordinator**，必须修好再返回
- 第二层不通过且无法修复 → 返回时 status="partial"，issues 里列出无法验证的点

## 耗时控制

- 自检必须 < 5 秒
- 如果自检本身超时，视为第一层不通过

## 谁用

**所有 Agent 返回前都要用**。Coordinator 在汇总回包前也要用（查 envelope 字段完整性）。
