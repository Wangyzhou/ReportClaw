# RAGFlow Chunk 反查能力调研

> 2026-04-17
> 问题：Reviewer 需要根据 chunk_id 反查 chunk content 做 fact-check，RAGFlow 是否支持？
> 结论：**✅ 原生支持，王亚洲不用新开发接口**

---

## 核心发现

### 1. Retrieval API（Retriever 用）

`POST /api/v1/retrieval`

```json
// 返回
{
  "data": {
    "chunks": [{
      "id": "d78435d142bd5cf6704da62c778795c5",  ← chunk_id
      "content": "...",
      "document_id": "5c5999ec7be811ef9cab0242ac120005",
      "document_keyword": "1.txt",  ← doc_name
      "kb_id": "c7ee74067a2c11efb21c0242ac120006",  ← dataset_id
      "highlight": "<em>ragflow</em> content",
      "similarity": 0.9669,
      "term_similarity": 1.0,
      "vector_similarity": 0.8898,
      "positions": [""],
      "important_keywords": [""]
    }]
  }
}
```

### 2. Chunk 反查 API（Reviewer 用）🎯

`GET /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks?id={chunk_id}`

**这就是我们要的接口**。文档原话：
> `id`(*Filter parameter*), `string`  
> The ID of the chunk to retrieve.

返回：
```json
{
  "data": {
    "chunks": [{
      "id": "b48c170e90f70af998485c1065490726",
      "content": "This is a test content.",   ← 完整原文
      "document_id": "b330ec2e91ec11efbc510242ac120004",
      "docnm_kwd": "1.txt",
      "available": true,
      "positions": [""]
    }]
  }
}
```

✅ 有 `content` 字段，可用于字面比对。

---

## 字段映射表

我们的 schema → RAGFlow 原生字段：

| ReportClaw 字段 | RAGFlow 字段 | 备注 |
|----------------|------------|------|
| `chunk_id` | `id` | 直接映射（RAGFlow 用 32位 hex，不是我们的 `{doc_id}_p{page}_{idx}`） |
| `content` | `content` | 一致 |
| `source.doc_id` | `document_id` | 一致 |
| `source.doc_name` | `docnm_kwd` / `document_keyword` | 一致 |
| `source.dataset_id`（新增）| `kb_id` | **需要加这个字段**，反查必需 |
| `source.page` | — | RAGFlow 默认不提供，需从 `positions[]` 解析（可选） |
| `source.paragraph_id` | — | 用 chunk id 代替 |
| `source.category` | — | 需要 RAGFlow dataset 分类机制（用 dataset_id 映射） |
| `relevance_score` | `similarity` | 一致（或用 vector_similarity） |
| `highlight_spans` | `highlight` 字段（HTML `<em>`） | 需要解析 |

---

## 对 Schema 的影响

### Retriever response 需要加 `source.dataset_id`

```json
{
  "chunk_id": "d78435d142bd5cf6704da62c778795c5",
  "content": "...",
  "source": {
    "doc_id": "5c5999ec7be811ef9cab0242ac120005",
    "doc_name": "2025中国AI行业年度报告.pdf",
    "dataset_id": "c7ee74067a2c11efb21c0242ac120006",  ← 新增字段
    "category": "行业报告"
  },
  "relevance_score": 0.9669
}
```

### Reviewer 的 chunk 反查流程

```python
# 伪代码
def verify_citation(chunk_id: str, dataset_id: str, document_id: str) -> str:
    """反查 chunk content，用于 fact-check"""
    resp = ragflow.get(
        f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
        params={"id": chunk_id}
    )
    chunks = resp["data"]["chunks"]
    if not chunks:
        return None  # chunk 不存在 → 引用错误
    return chunks[0]["content"]

def fact_check_claim(claim: str, chunk_id: str, dataset_id: str, document_id: str):
    chunk_content = verify_citation(chunk_id, dataset_id, document_id)
    if chunk_content is None:
        return {"severity": "HIGH", "type": "citation_error"}
    # 字面比对 claim 里的数字/实体 vs chunk_content
    ...
```

---

## 对齐清单的影响（大幅简化）

| 原 P0-2 | 新状态 |
|---------|-------|
| 需要王亚洲**开发** `GET /chunks/{chunk_id}` 反查接口 | **作废** |
| RAGFlow 原生已有 `List chunks` API 支持按 id 过滤 | ✅ 可用 |
| 王亚洲只需在 Retriever 适配层把 `kb_id` 也传出来 | 10 行代码 |

---

## 剩余注意事项

### 1. 页码 / 段落号
RAGFlow 不直接提供 `page` 和 `paragraph_id`，需要：
- **方案 A**：依赖 `positions[]` 字段（PDF 文档会有 bounding box 信息）
- **方案 B**：放弃 page 精度，用 chunk_id 作为最小溯源单位（前端点击跳转到 chunk 而非具体页）

建议方案 B——对 T5 评分影响不大，用户能看到 doc_name + content 已足够。

### 2. Category 分类
RAGFlow 的 dataset 本身就是一个分类维度（一个 dataset = 一个分类）。建议：
- 把 `政策法规 / 行业报告 / 历史报告 / 媒体资讯` 对应创建 4 个 dataset
- Retriever 检索时按 category 选 dataset_ids 调用即可

### 3. chunk_id 格式
RAGFlow 默认用 32 位 hex（如 `d78435d142bd5cf6704da62c778795c5`），不是人类可读的。这是**可以接受的**——前端展示只需要点击跳转逻辑，用户不直接看 chunk_id。

原方案里设计的 `{doc_id}_p{page}_{idx}` 格式可以废弃，直接用 RAGFlow 原生 id。

---

## 对 Retriever SOUL.md 的更新建议

原来提过"chunk_id 格式统一：`{doc_id}_p{page}_{para_idx}`"，改为：

```markdown
- chunk_id 格式：沿用 RAGFlow 原生 id（32 位 hex），不自造命名规则
```

---

## 推荐的最终决策

✅ **接受 RAGFlow 原生 API 作为反查接口，不新开发**

理由：
1. 功能够用（能按 id 查到 content）
2. 零开发成本（王亚洲不用加代码）
3. 减少 P0-2 风险项
4. 符合"能用现成的就别造轮子"原则

唯一要做的事：
- [x] Retriever 的 response 新增 `source.dataset_id` 字段
- [x] 更新 Retriever 的 `source_tracking.md` skill，说明 chunk_id 用 RAGFlow 原生 id
- [x] 更新 Reviewer 的 `citation_verification.md` skill，调用 RAGFlow 反查 API
- [x] 更新 `alignment-王亚洲.md` 删除 P0-2 的"开发接口"需求

---

## 参考文档

- RAGFlow HTTP API 完整文档：https://github.com/infiniflow/ragflow/blob/main/docs/references/http_api_reference.md
- List chunks: 文档第 2083 行
- Retrieve chunks: 文档第 2577 行
