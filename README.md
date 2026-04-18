# ReportClaw 📑

> **智能报告写作的 Agent 团队**——知识库驱动生成 × 以稿写稿。
> T5 题目的参赛实现。

---

## 名字由来

`ReportClaw` 延续 OpenClaw / MediaClaw 的 `-claw` 命名系，意思是"把报告写作的 Agent 能力爪下来"。中文可叫 **报告爪**。

原名 T5 保留在 git 历史里（`feat/t5-agent-architecture` / `feat/t5-agent-v3-gear` 分支）。

---

## 架构一图

```
用户请求
  ↓
┌──────────────────────────────────────────┐
│ Coordinator（指挥官）                      │
│  1. gear_detection: 判档 G1/G2/G3         │
│  2. 用 create-plan 规划子任务              │
│  3. 按 Gear 派发 Agent                    │
│  4. 聚合 + Reviewer 验收                  │
└────┬──────┬──────┬──────┬────────────────┘
     │      │      │      │
  ┌──▼─┐ ┌─▼──┐ ┌─▼──┐ ┌─▼───┐
  │检索│ │写作│ │改写│ │审查 │
  └────┘ └────┘ └────┘ └─────┘
  Retriever Writer Rewriter Reviewer
     ↓
  RAGFlow + 晴天 MCP + 知识 digest
```

---

## 目录结构

```
reportclaw/
├── README.md              ← 本文
├── 方案-v1.md              ← 原始技术方案
├── 接力说明.md              ← 换设备接力
├── alignment-王亚洲.md     ← 对齐清单 v2（已从 8 项缩为 2 项）
│
├── agents/                ← Agent Team（5 个）
│   ├── _shared/           ← 元 skill（4 个通用能力）
│   ├── coordinator/       ← 指挥官（SOUL + AGENTS + HEARTBEAT + MEMORY + AGENT-ROUTING + skills）
│   ├── retriever/         ← 检索员
│   ├── writer/            ← 写作员
│   ├── rewriter/          ← 改写员
│   ├── reviewer/          ← 审查员
│   └── registry.yaml      ← 部署元数据
│
├── docs/                  ← 设计文档
│   ├── payload-schema.md  ← 5 种 task_type payload 契约（OpenClaw 管 envelope，我们管内容）
│   ├── mediaclaw-digest.md
│   └── mediaclaw-digest-v2.md
│
└── mocks/                 ← 不依赖 RAGFlow 的测试数据
    ├── retriever-response-high-coverage.json
    ├── retriever-response-low-coverage.json
    ├── user-source-draft.md
    ├── writer-expected-output.md
    ├── rewriter-data-update-expected.md
    └── reviewer-sample-issues.json
```

---

## 5 个 Agent 速览

| Agent | 核心职责 | 核心 skill |
|-------|---------|-----------|
| **Coordinator** | 指挥官：判档/派发/验收 | gear_detection / task_dispatch / quality_check |
| **Retriever** | 知识库守门员 | hybrid_search / source_tracking / coverage_analysis |
| **Writer** | 产出担当 | outline_generation / section_writing / style_mimicking / citation_insertion |
| **Rewriter** | 以稿写稿核心 | structure_parser / data_update / perspective_shift / content_expansion / style_conversion / diff_generator |
| **Reviewer** | 质量守门人 | citation_verification / review_checklist / coverage_scoring |

---

## 5 个关键创新

1. **Gear System（借鉴 Shifu）** — G1/G2/G3 自适应分档，简单请求不走全链
2. **双层事实防线** — verification-before-completion（任务做了）+ fact-check-before-trust（事实对了）
3. **熔断保护** — loop-circuit-breaker 防 Writer↔Reviewer 死循环
4. **强制人格化** — 每个 Agent 有核心信念 + 禁止事项 + 强制语言规则（中文、不指定工具、不描述排版）
5. **Mock 闭环** — 不依赖 RAGFlow 就能冒烟，答辩现场不翻车

---

## Gear System

| Gear | 场景 | Agent 编队 | 耗时 |
|------|------|-----------|------|
| **G1** 轻 | 快速查询 / 元信息 | Retriever 或直答 | <10s |
| **G2** 中 | 短报告 / 简单改写 | 全链路 1 轮审 | 30-60s |
| **G3** 重 | 长报告 / 仿写 / 扩展 | 并行检索 + ≤2 轮审 | 2-5min |

动态升级：Retriever 低覆盖 / Reviewer 有 HIGH issue / 用户追加需求 → G2 自动升 G3。

---

## 评分映射

| 维度 | 权重 | ReportClaw 对应能力 |
|------|------|-------------------|
| 知识检索准确性 | 25% | Retriever 的混合检索 + 溯源 + 覆盖度评估 |
| 报告生成质量 | 25% | Writer 的 outline/section/mimic/citation 4 skill |
| 改写质量 | 25% | Rewriter 4 模式 + diff |
| 对比展示与版本管理 | 15% | diff_generator + 后端版本 API（王亚洲） |
| 系统完整性与体验 | 10% | Gear 自适应 + 前端三栏 + Mock 闭环 |

---

## 分工

- **林宇泰**：Agent 身份 + Skill + Coordinator 调度 + 前端（本目录内容）
- **王亚洲**：RAGFlow 搭建 + Claw 后端集成 + 通信层

对齐剩 2 项：RAGFlow 字段映射 + chunk 反查接口（见 `alignment-王亚洲.md`）。

---

## 交付时间表

| 日期 | 里程碑 |
|------|-------|
| 4/17 | Agent Team + Skill Prompt + Mock 闭环 ✅ |
| 4/18 | RAGFlow 联调 + v1.0 跑通 |
| 4/19 | 改写 4 模式 + diff + 版本管理 |
| 4/20 | 前端三栏对接 |
| 4/21 | **完整交付** + 3 份 Demo 报告 + 设计文档 |
