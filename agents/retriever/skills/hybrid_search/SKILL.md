---
name: hybrid_search
description: "混合检索：调用 ragflow_hybrid_search MCP 工具，支持按 docIds 过滤。"
---

# Skill — hybrid_search

## 用途
通过 `mcporter call rag-mcp.ragflow_hybrid_search` 执行混合检索（向量 + 关键词 + RRF）。

## 工具调用

从 retrieve 子任务的 `payload` 中提取参数：

```
mcporter call rag-mcp.ragflow_hybrid_search \
  question="<payload.query>" \
  categories='["行业报告", "政策法规"]' \
  docIds='["abc123def456"]' \
  topK=10
```

参数说明：
- `question`：检索问题，来自 `payload.query`
- `categories`：来自 `payload.search_scope.categories`；**为空则不传**（搜全库）
- `docIds`：来自 `payload.search_scope.doc_ids`；**@mention 的文档 id 必须带上**；为空则不传（搜全库）
- `topK`：来自 `payload.top_k`，默认 10

## 工具响应字段映射

工具返回的 chunk 对象字段（Spring Boot MCP API 响应格式）：

| 工具返回字段 | 含义 | 映射到 result 字段 |
|------------|------|-----------------|
| `chunkId` | chunk 唯一标识（16 位 hex） | `chunk_id` |
| `documentName` | 来源文档名 | `source.doc_name` |
| `content` | chunk 原文内容 | `content` |
| `score` | 相关性分数（0~1） | `relevance_score` |
| `datasetId` | 所属知识库 dataset id | `source.dataset_id` |
| `documentId` | 所属文档 id | `source.doc_id` |

### 响应示例

```json
{
  "chunks": [
    {
      "chunkId": "7302ebeb47eabc9f",
      "documentName": "2024年AI产业报告.pdf",
      "content": "全球AI市场规模在2024年达到3200亿美元...",
      "score": 0.46,
      "datasetId": "b9effd06a1234567",
      "documentId": "d30a9564abcd1234"
    }
  ],
  "total": 4
}
```

## 边界
- 知识库为空 → 返回 `results: []` + `coverage_assessment: "低"` + `missing_topics: ["整个知识库为空"]`
- 工具调用失败 → 抛 envelope error，error_code=`RETRIEVAL_TIMEOUT`
- `docIds` 指定但无命中 → 返回空 results，`missing_topics` 说明原因

## 输出
`results` 数组，字段见 SOUL.md Output Format。每条结果须经 `source_tracking` skill 补齐 source 字段后返回。
