# TOOLS.md — 审查员工具

## MCP 工具（rag-mcp 服务器，由 OpenClaw 注入）

通过 `mcporter call rag-mcp.<tool>` 调用。

---

### ragflow_get_chunk
按 chunkId 反查某个 chunk 的原始文本，用于验证报告中引用的真实性和数据一致性。

**mcporter 调用格式：**
```
mcporter call rag-mcp.ragflow_get_chunk \
  datasetId="<dataset_id>" \
  docId="<document_id>" \
  chunkId="<16位hex>"
```

**输入参数：**
```json
{
  "datasetId": "string",  // 必填：来自 citation_index 或 retrieval_results 的 datasetId
  "docId": "string",      // 必填：来自 citation_index 或 retrieval_results 的 documentId
  "chunkId": "string"     // 必填：报告中 [ref:xxx] 的 chunk id（16 位 hex）
}
```

**返回结构：**
```json
{
  "chunkId": "7302ebeb47eabc9f",
  "documentName": "文件名.pdf",
  "content": "原文内容...",
  "score": 0.0,
  "datasetId": "b9effd06...",
  "documentId": "d30a9564..."
}
```

---

## Skills（本 agent）

- `review_checklist`
- `citation_verification`
- `coverage_scoring`

## 共享 Skills（agents/_shared/）

- `fact-check-before-trust`
- `verification-before-completion`
