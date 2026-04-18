# Payload Schema — T5 Agent 内容协议

> 版本：v0.2（2026-04-17）
> **注意**：envelope 字段（msg_id/task_id/from/to/msg_type 等）由 OpenClaw CollaborationService 原生提供，本文档不管。
> 本文档**只管 payload 内容** — 每个 task_type 的请求/响应数据结构。

---

## 为什么需要这个 schema

OpenClaw 原生 envelope 解决了"消息怎么传"的问题。但"payload 里放什么"是 Agent 之间自己的约定。5 个 Agent 要协作，就需要对 payload 格式达成一致。

本文档是 T5 内部约定，不涉及 OpenClaw 底层。

---

## 5 种 task_type

| task_type | from → to | 场景 |
|-----------|-----------|------|
| `retrieve` | Coordinator → Retriever | 检索知识库 |
| `write` | Coordinator → Writer | 生成报告（from_outline / mimic / continue） |
| `rewrite` | Coordinator → Rewriter | 4 模式改写 |
| `review` | Coordinator → Reviewer | 审查报告 |
| `dispatch` | Coordinator 内部 | 任务树规划（不发给其他 Agent） |

---

## 1. `retrieve` — Coordinator → Retriever

### Request payload

```json
{
  "query": "用户原始问题或章节主题",
  "search_scope": {
    "categories": ["政策法规", "行业报告", "历史报告", "媒体资讯"],
    "doc_ids": ["doc_001", "doc_007"],
    "date_range": ["2024-01-01", "2026-04-17"]
  },
  "top_k": 10,
  "rerank": true,
  "min_relevance": 0.6
}
```

### Response payload

```json
{
  "query": "原查询回显",
  "results": [
    {
      "chunk_id": "doc_001_p15_3",
      "content": "检索到的文本片段（原文，不改写）",
      "source": {
        "doc_id": "doc_001",
        "doc_name": "2025中国AI行业年度报告.pdf",
        "page": 15,
        "paragraph_id": "doc_001_p15_3",
        "category": "行业报告"
      },
      "relevance_score": 0.92,
      "highlight_spans": [[12, 28]]
    }
  ],
  "coverage_assessment": "高 | 中 | 低",
  "missing_topics": ["可能缺失的子主题列表"],
  "total_hits": 47
}
```

**实例见** `mocks/retriever-response-high-coverage.json` + `mocks/retriever-response-low-coverage.json`。

---

## 2. `write` — Coordinator → Writer

### Request payload

```json
{
  "mode": "from_outline | mimic | continue",
  "topic": "报告主题",
  "outline": [
    { "level": 1, "title": "一、行业概览", "guidance": "可选写作提示", "supporting_chunks": ["doc_001_p15_3"] },
    { "level": 2, "title": "1.1 市场规模" }
  ],
  "retrieval_results": [ /* 来自 Retriever 的 results 数组 */ ],
  "style_reference": {
    "doc_id": "ref_doc_003",
    "aspects": ["tone", "structure", "citation_style"]
  },
  "constraints": {
    "max_length": 5000,
    "language": "zh-CN",
    "must_cite": true,
    "no_fabrication": true
  }
}
```

### Response payload

```json
{
  "report_markdown": "# 标题\n\n根据统计，2025年AI市场规模达到3200亿美元 [ref:doc_001_p15_3]...",
  "sections": [
    {
      "title": "一、行业概览",
      "content": "...",
      "citations": ["doc_001_p15_3", "doc_007_p2_1"]
    }
  ],
  "citation_index": {
    "doc_001_p15_3": { "used_count": 3, "first_section": "1.1", "all_sections": ["1.1", "1.2"] }
  },
  "stats": {
    "word_count": 4200,
    "citation_count": 18,
    "uncited_paragraphs": 0
  }
}
```

**实例见** `mocks/writer-expected-output.md`。

---

## 3. `rewrite` — Coordinator → Rewriter

### Request payload

```json
{
  "mode": "data_update | perspective_shift | content_expansion | style_conversion",
  "source_doc": {
    "doc_id": "user_uploaded_xxx",
    "markdown": "原稿全文 markdown"
  },
  "instructions": {
    "data_update": {
      "new_data_sources": [ /* Retriever 给的新数据 chunks */ ]
    },
    "perspective_shift": {
      "from": "投资人视角",
      "to": "监管者视角",
      "audience": "政府部门"
    },
    "content_expansion": {
      "expand_sections": ["第二章", "第四章"],
      "new_topics": ["碳中和影响", "出海策略"],
      "new_data_sources": [ /* 可选，新话题需要新料 */ ]
    },
    "style_conversion": {
      "from_style": "formal_business",
      "to_style": "popular",
      "from_lang": "zh-CN",
      "to_lang": "zh-CN"
    }
  },
  "preserve": {
    "structure": true,
    "headings": true,
    "citations": true
  }
}
```

### Response payload

```json
{
  "rewritten_markdown": "改写后全文",
  "diff": {
    "format": "unified",
    "content": "@@ -10,3 +10,3 @@\n-2024年市场规模3000亿\n+2025年市场规模3200亿 [ref:doc_001_p15_3]"
  },
  "changes_summary": {
    "mode": "data_update",
    "added_lines": 12,
    "removed_lines": 8,
    "modified_sections": ["1.2", "2.1"],
    "matched_data_points": 8,
    "unmatched_data_points": ["dp_007"],
    "new_content_marked": true
  },
  "preserved_citations": ["doc_002_p7_2"],
  "new_citations": ["doc_001_p15_3"]
}
```

**实例见** `mocks/rewriter-data-update-expected.md`。

---

## 4. `review` — Coordinator → Reviewer

### Request payload

```json
{
  "report_markdown": "待审查的报告全文",
  "knowledge_base_snapshot_id": "kb_v_2026_04_17",
  "retrieval_results_ref": [ /* Writer 用过的 chunks，用于 citation_verification 反查 */ ],
  "checks": [
    "citation_validity",
    "data_accuracy",
    "logic_coherence",
    "no_fabrication",
    "format_compliance",
    "coverage"
  ],
  "severity_threshold": "MEDIUM",
  "round": 1
}
```

### Response payload

```json
{
  "verdict": "pass | needs_revision | fail",
  "issues": [
    {
      "id": "issue_001",
      "type": "citation_error | data_mismatch | logic_break | fabrication | format | coverage",
      "location": {
        "section": "第3章第2段",
        "line_range": [142, 148],
        "citation_id": "doc_001_p15_3"
      },
      "detail": "引用的 chunk 在知识库中不存在",
      "severity": "HIGH | MEDIUM | LOW",
      "suggested_fix": "建议改引 doc_001_p15_4"
    }
  ],
  "scores": {
    "coverage_score": 0.85,
    "quality_score": 0.78,
    "citation_accuracy": 0.95
  },
  "retry_recommended": true,
  "rounds_used": 1
}
```

**实例见** `mocks/reviewer-sample-issues.json`。

---

## 5. `dispatch` — Coordinator 内部任务规划

Coordinator 拆解用户请求时产生的任务计划。不发给其他 Agent，但写入 task-progress MCP 用于前端展示：

```json
{
  "user_request": "原始用户输入",
  "intent": "generate_report | rewrite_report | retrieve_knowledge",
  "gear": "G1 | G2 | G3",
  "gear_rationale": "为什么选这个 gear",
  "subtasks": [
    {
      "task_id": "...",
      "to_agent": "retriever",
      "task_type": "retrieve",
      "depends_on": [],
      "rationale": "为什么派这个任务"
    },
    {
      "task_id": "...",
      "to_agent": "writer",
      "task_type": "write",
      "depends_on": ["上一个 task_id"]
    }
  ],
  "max_review_rounds": 2,
  "allow_upgrade_to_g3": true
}
```

---

## 6. 审查回环协议

```
1. Coordinator → Writer: write (round=1)
2. Writer → Coordinator: result
3. Coordinator → Reviewer: review (round=1)
4. Reviewer → Coordinator: result(verdict=needs_revision, issues=[...])
5. Coordinator → Writer: write (round=2, payload.revision_context = issues)
6. ... 最多 max_review_rounds=2 轮，超过升级给用户
```

第 5 步的 payload 扩展字段：

```json
{
  "revision_context": {
    "round": 2,
    "previous_report": "上一版全文",
    "review_issues": [ /* Reviewer 返回的 issues 数组 */ ],
    "must_fix_severities": ["HIGH"]
  }
}
```

---

## 7. 错误 payload

任何 Agent 出错时 payload 格式：

```json
{
  "error_code": "RETRIEVAL_TIMEOUT | LLM_RATE_LIMIT | INVALID_INPUT | KB_UNAVAILABLE | KB_NO_MATCH | INTERNAL",
  "error_message": "人类可读的错误描述",
  "retryable": true,
  "retry_after_seconds": 30,
  "context": { /* 任意调试上下文 */ }
}
```

熔断规则：见 `agents/_shared/loop-circuit-breaker.md`。

---

## 8. 与 OpenClaw 的分工

| 层 | 谁管 |
|----|------|
| envelope（msg_id / task_id / from_agent / to_agent / msg_type / stream） | OpenClaw 原生 |
| 传输（HTTP / SSE / WebSocket） | OpenClaw 原生 |
| task_type 分类 | OpenClaw + T5 共同约定 |
| **各 task_type 的 payload 字段** | **T5（本文档）** |
| 审查回环 | **T5（本文档 §6）** |
| 错误分类 | **T5（本文档 §7）** |
| 任务进度可视化 | `agents/_shared/task-progress-manager.md` + MCP |

---

## 变更历史

- **v0.2** (2026-04-17): 瘦身
  - 删除 envelope 字段定义（OpenClaw 管）
  - 删除 SSE 流式协议（Claw 管）
  - 删除"给王亚洲的对接清单"（分层后不需要）
  - 合并错误格式到独立章节
  - 加入 gear 字段到 dispatch payload
  - 加入 revision_context 细节
  - 与 `mocks/` 目录下实例文件交叉引用

- **v0.1** (2026-04-17): 初稿（含 envelope，已过时）
