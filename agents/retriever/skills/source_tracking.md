# Skill — source_tracking

## 用途
保证每条检索结果都带完整、可点击跳转的溯源元数据。这是评分项"知识检索准确性 25%"的核心展示点。

---

## chunk_id 格式（用 RAGFlow 原生 id）

**直接沿用 RAGFlow 返回的 32 位 hex id**，不自造命名。

```
示例：
  d78435d142bd5cf6704da62c778795c5
  b48c170e90f70af998485c1065490726
```

**为什么放弃原来的 `{doc_id}_p{page}_{idx}` 方案**：
1. RAGFlow 分块算法是层级/滑窗式，一个"段落"可能跨页或半页
2. 强制自造命名需要建映射表，增加两边维护成本
3. 用户看到的是 `doc_name + 可跳转高亮原文`，不直接看 chunk_id
4. 调研见 `docs/ragflow-chunk-lookup-research.md`

---

## source 字段规范

```json
{
  "doc_id": "5c5999ec7be811ef9cab0242ac120005",
  "doc_name": "2025年AI行业报告.pdf",
  "dataset_id": "c7ee74067a2c11efb21c0242ac120006",
  "category": "行业报告",
  "upload_date": "2026-03-12",
  "highlight_spans": [[12, 28]]
}
```

**字段来源映射表**（和 RAGFlow API 原生字段对齐）：

| ReportClaw 字段 | RAGFlow 字段 | 备注 |
|----------------|------------|------|
| `source.doc_id` | `document_id` | RAGFlow 文档主键 |
| `source.doc_name` | `document_keyword` / `docnm_kwd` | 人类可读名 |
| `source.dataset_id` | `kb_id` | **必需** — Reviewer 反查 chunk 内容要这个 |
| `source.category` | 从 dataset 映射 | 政策法规/行业报告/历史报告/媒体资讯 ← 4 个 dataset |
| `source.upload_date` | 从 document metadata | 可选 |
| `source.highlight_spans` | 从 `highlight` 字段（HTML `<em>`）解析 | 可选，拿不到就空 |

**绝对不能省的字段**：`doc_id`、`doc_name`、`dataset_id`（Reviewer 反查刚需）。

---

## Category ↔ RAGFlow Dataset 映射

在 RAGFlow 里为每个分类创建一个独立 dataset：

| ReportClaw category | RAGFlow dataset name | dataset_id（示例） |
|--------------------|---------------------|-------------------|
| 政策法规 | `policies` | `c7ee740...a2c11efb` |
| 行业报告 | `industry_reports` | `d8fe851...b3d22fgc` |
| 历史报告 | `historical_reports` | `e9ff962...c4e33ghd` |
| 媒体资讯 | `media_news` | `fa0073...d5f44hie` |

Retriever 检索时按 scope.categories 映射 dataset_ids 传给 RAGFlow：

```python
# 伪代码
def retrieve(query, categories):
    dataset_ids = [CATEGORY_TO_DATASET[c] for c in categories]
    resp = ragflow.post("/api/v1/retrieval", {
        "question": query,
        "dataset_ids": dataset_ids,
        "top_k": 10,
        "keyword": True,
        "highlight": True,
    })
    return map_to_reportclaw_schema(resp)
```

---

## 报告中的引用格式

Writer/Rewriter 在报告 markdown 中插入：

```
根据统计，2025 年 AI 市场规模达到 3200 亿美元 [ref:d78435d142bd5cf6704da62c778795c5]
```

前端解析 `[ref:xxx]` → 渲染为可点击链接（显示成上标 [1] [2] 编号友好）→ 点击跳转知识库面板高亮原文。

---

## Reviewer 如何反查 chunk 原文

Reviewer 的 `citation_verification` skill 用：

```
GET /api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks?id={chunk_id}
```

所以每条 source 必须带齐 `dataset_id + doc_id + chunk_id` 三件套，缺一不可。

---

## 反例

- ❌ `source: { "doc_name": "AI报告" }` — 缺 doc_id / dataset_id / chunk_id
- ❌ chunk_id 自造成 `doc_001_p15_3` — 和 RAGFlow 实际 id 不一致，反查会失败
- ❌ 缺 `dataset_id` — Reviewer 无法反查
- ❌ 引用格式写成 `（来源：AI报告 p15）` — 前端无法解析跳转
- ❌ dataset_id 为空串 / null — 前端渲染不了跳转

---

## 校验（Retriever 返回前自检）

调用 `verification-before-completion` 之前确认：
- [ ] 每条 result 都有 `chunk_id`、`content`、`source`
- [ ] `source` 至少有 `doc_id / doc_name / dataset_id`
- [ ] `relevance_score` >= `min_relevance`
- [ ] `coverage_assessment ∈ {"高","中","低"}`
- [ ] 如 coverage="低" 必须填 `missing_topics`（至少 1 条）

不通过就返回 `status: partial` 并说明原因。
