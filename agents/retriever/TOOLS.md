# TOOLS.md — 检索员工具

## MCP 工具（rag-mcp 服务器，由 OpenClaw 注入）

通过 `mcporter call rag-mcp.<tool>` 调用。

---

### ragflow_hybrid_search
对知识库执行混合检索（向量 + 关键词 + RRF）。

**mcporter 调用格式：**
```
mcporter call rag-mcp.ragflow_hybrid_search \
  question="<检索问题>" \
  categories='["政策法规","行业报告"]' \
  docIds='["<doc_id>"]' \
  topK=10
```

**输入参数：**
```json
{
  "question": "string",       // 必填：检索问题
  "categories": ["string"],   // 可选：政策法规 / 行业报告 / 历史报告 / 媒体资讯；不传=全库
  "docIds": ["string"],       // 可选：限定文档 ID（@mention 场景）；不传=全库
  "topK": 10                  // 可选：返回条数，默认 10
}
```

**返回结构：**
```json
{
  "chunks": [
    {
      "chunkId": "7302ebeb47eabc9f",
      "documentName": "文件名.pdf",
      "content": "原文内容...",
      "score": 0.46,
      "datasetId": "b9effd06...",
      "documentId": "d30a9564..."
    }
  ],
  "total": 4
}
```

---

### ragflow_get_chunk
按 chunkId 反查某个 chunk 的原始文本（Reviewer 验证引用时使用）。

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
  "datasetId": "string",  // 必填：来自检索结果的 datasetId
  "docId": "string",      // 必填：来自检索结果的 documentId
  "chunkId": "string"     // 必填：来自检索结果的 chunkId（16 位 hex）
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

- `hybrid_search`
- `source_tracking`
- `coverage_analysis`

## 共享 Skills（agents/_shared/）

- `fact-check-before-trust`
- `verification-before-completion`
