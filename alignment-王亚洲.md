# 与王亚洲对齐清单 — ReportClaw 报告写作平台（v2 精简版）

> 日期：2026-04-17 下午
> **重要变化**：王亚洲已确认 A2A 协议由 OpenClaw 原生提供，我们**不用设计 envelope**。
> 两层清晰分工：他管"后端 ↔ Claw"，我管"Agent 身份 + 内容 payload"。
> 原对齐清单（带 envelope / SSE / 传输层 P0）已作废。本 v2 只保留真正需要对齐的事项。

---

## 我这边的产出（做完了）

在 `reportclaw/` 下：

- `agents/coordinator/` — 5 文件人格化（SOUL + AGENTS + HEARTBEAT + MEMORY + AGENT-ROUTING）
- `agents/{retriever,writer,rewriter,reviewer}/SOUL.md` — 全部人格化
- `agents/_shared/` — 4 元 skill（task-progress / verification / fact-check / loop-circuit-breaker）
- `agents/coordinator/skills/gear_detection.md` — **G1/G2/G3 自适应分档**（Shifu 思路移植）
- `docs/payload-schema.md` — 5 种 task_type 的 payload 内容约定（envelope 不管）
- `mocks/` — 6 份 mock 数据，覆盖高/低覆盖检索、原稿、期望输出、Reviewer issue 示例

---

## 真正需要你确认的（大幅缩减为 3 项）

### 🔴 P0-1：RAGFlow → Retriever payload 字段映射

我的 Retriever response（详见 `docs/payload-schema.md` §1 + `mocks/retriever-response-high-coverage.json`）：

```json
{
  "results": [{
    "chunk_id": "doc_001_p15_3",
    "content": "...",
    "source": {
      "doc_id": "doc_001",
      "doc_name": "...",
      "page": 15,
      "paragraph_id": "doc_001_p15_3",
      "category": "行业报告"
    },
    "relevance_score": 0.92,
    "highlight_spans": [[12, 28]]
  }],
  "coverage_assessment": "高 | 中 | 低",
  "missing_topics": [...]
}
```

**需要你回答**：
- [ ] RAGFlow hybrid_search 返回的字段，哪些能直接映射到上面？哪些要适配层？
- [ ] `chunk_id` 格式能不能强制成 `{doc_id}_p{page}_{para_idx}`？不能的话建一张映射表即可
- [ ] `coverage_assessment` 和 `missing_topics` 是 RAGFlow 原生，还是让 Retriever Agent 自己算？（我倾向 Agent 自己算，但想听你意见）
- [ ] `highlight_spans` 可选，拿不到就砍

---

### ~~🔴 P0-2：chunk 反查接口（Reviewer 必需）~~ ✅ 已调研作废

**调研结论**：RAGFlow 原生有 `GET /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks?id={chunk_id}` 接口，能按 chunk id 反查 content。**不用新开发，直接复用**。

详见 [`docs/ragflow-chunk-lookup-research.md`](docs/ragflow-chunk-lookup-research.md)。

**唯一需要你做的**：
- [ ] Retriever response 新增 `source.dataset_id` 字段（RAGFlow 的 `kb_id` 透传，约 5 行代码）

这样 Reviewer 在 Agent 内部就能直接调 RAGFlow 反查 API。

---

### 🟡 P1：版本管理后端 API

Coordinator 的 `version_control` skill 调用以下 API：

- [ ] `POST /reports/{report_id}/versions` — 新建版本
- [ ] `GET /reports/{report_id}/versions` — 列出版本
- [ ] `GET /reports/{report_id}/versions/{vN}/{vM}/diff` — 两版 diff
- [ ] `POST /reports/{report_id}/export?format=docx|pdf` — 导出

**需要你回答**：
- [ ] 这套 API 你实现还是前端做？
- [ ] DB 选 SQLite 够不够（Demo 阶段）？

---

## 已作废（OpenClaw 管，不用对齐）

| 原 P0 项 | 作废原因 |
|---------|---------|
| Envelope 字段命名（msg_id/task_id/from_agent 等） | OpenClaw 原生 |
| Delegate / Consult / Notify wire format | OpenClaw 原生 |
| 同步/异步通信方式 | OpenClaw 原生 |
| SSE 流式响应端点 | OpenClaw 原生 |
| focus_ref 生命周期 | OpenClaw 原生（我们只透传）|
| 错误码全集 | OpenClaw 错误 + 我们业务错误（见 payload-schema §7）独立 |
| 多用户/多会话 | Demo 单用户，不涉及 |

---

## 4/18 联调前的"最小可跑通路径"（简化）

```
Path A: 纯 Mock 跑通（不依赖 RAGFlow，今晚/明早就可验证）
  → 用 mocks/retriever-response-high-coverage.json 喂给 Writer
  → Writer 产出报告
  → Reviewer 审查（模拟 P0-2 的 chunk 反查）
  → 验证 schema + Agent 逻辑

Path B: 对接 RAGFlow 跑通（4/18 上午）
  → P0-1 确认后，你的 Retriever 适配层 + 我的 schema 对齐
  → P0-2 提供 chunk 反查接口
  → Coordinator 调 OpenClaw 派发
  → 完整跑通
```

---

## 冻结时间点

- **4/17 今晚**：payload-schema.md 冻结（字段不再改）
- **4/18 上午**：RAGFlow 适配层跑通
- **4/18 下午**：Clawith Agent 部署完
- **4/19**：改写 4 模式跑通
- **4/20**：前端对接
- **4/21**：完整交付

---

## 沟通方式

- **同步**：有时间语音 15 分钟（P0-1 和 P0-2 过完就行）
- **异步**：在本文档每项后打勾 + 写"OK / 需要改：xxx"
