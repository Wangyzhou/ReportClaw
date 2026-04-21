---
name: hybrid_search
description: "混合检索：向量检索 + 关键词检索 + RRF 融合 + Rerank。"
---

# Skill — hybrid_search

## 用途
混合检索：向量检索 + 关键词检索 + RRF 融合 + Rerank。

## 输入
```json
{
  "query": "用户查询或章节主题",
  "search_scope": {
    "categories": ["..."],
    "doc_ids": ["..."],
    "date_range": ["...", "..."]
  },
  "top_k": 10,
  "rerank": true,
  "min_relevance": 0.6
}
```

## 流程

```
query
  ├─ 向量检索（BGE-M3 embedding → RAGFlow 向量库）
  │   └─ 取 top_k * 3 候选
  ├─ 关键词检索（BM25 / ES / PG FTS）
  │   └─ 取 top_k * 3 候选
  ▼
Reciprocal Rank Fusion
  公式：score = Σ 1 / (k + rank_i)，k=60
  ▼
Rerank（BGE-reranker-v2）
  对 top_k * 2 条做 cross-encoder 重排
  ▼
过滤 min_relevance，取 top_k
  ▼
返回 results
```

## 实现提示
- **直接调用 RAGFlow API**，不要自己搭向量库。RAGFlow 原生支持混合检索
- 如果 RAGFlow 的 hybrid 接口不满足，降级为两次单独调用 + 自己 RRF
- k=60 是 RRF 论文推荐值，不要改
- Rerank 可选开关，性能差时关掉先跑通

## 输出
`results` 数组，字段见 soul.md Output Format。

## 边界
- 知识库为空 → 返回 `results: []` + `coverage_assessment: "低"` + `missing_topics: ["整个知识库为空"]`
- RAGFlow 超时 → 抛 envelope error，error_code=`RETRIEVAL_TIMEOUT`
