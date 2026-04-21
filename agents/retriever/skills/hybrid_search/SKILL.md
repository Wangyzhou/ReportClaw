---
name: hybrid_search
description: "混合检索：调用 ragflow_hybrid_search 工具，支持按 doc_ids 过滤。"
---

# Skill — hybrid_search

## 用途
调用 `ragflow_hybrid_search` 工具执行混合检索（向量 + 关键词 + RRF）。

## 工具调用

从 retrieve 子任务的 `payload` 中提取参数，调用 `ragflow_hybrid_search` 工具：

```json
{
  "question": "<payload.query>",
  "categories": ["行业报告", "政策法规"],
  "doc_ids": ["abc123def456..."],
  "top_k": 10
}
```

参数说明：
- `question`：检索问题，来自 `payload.query`
- `categories`：来自 `payload.search_scope.categories`；为空则传所有分类
- `doc_ids`：来自 `payload.search_scope.doc_ids`；**@mention 的文档 id 必须带上**；为空则不传（搜全库）
- `top_k`：来自 `payload.top_k`，默认 10

## 工具响应字段映射

| 工具返回字段 | 映射到 result 字段 |
|------------|-----------------|
| `id` / `chunk_id` | `chunk_id` |
| `document_keyword` / `document_name` | `source.doc_name` |
| `content` / `content_with_weight` | `content` |
| `similarity` / `score` | `relevance_score` |
| `dataset_id` | `source.dataset_id` |
| `document_id` / `doc_id` | `source.doc_id` |

## 边界
- 知识库为空 → 返回 `results: []` + `coverage_assessment: "低"` + `missing_topics: ["整个知识库为空"]`
- 工具调用失败 → 抛 envelope error，error_code=`RETRIEVAL_TIMEOUT`
- `doc_ids` 指定但无命中 → 返回空 results，`missing_topics` 说明原因

## 输出
`results` 数组，字段见 SOUL.md Output Format。每条结果须经 `source_tracking` skill 补齐 source 字段后返回。
