# ReportClaw 接力说明 — 给王亚洲

> 日期：2026-04-18
> 作者：林宇泰
> 用途：Agent 侧阶段性交付 → 对接你的 Claw + RAGFlow 层

---

## 1. 项目改名

T5 → **ReportClaw**（延续 OpenClaw / MediaClaw 的 `-claw` 命名系）。
仓库路径：`reportclaw/`（原 `t5/` 已改）。

---

## 2. 我这边 100% 跑通的东西

### 2.1 架构（Agent 侧）

```
reportclaw/
├── agents/
│   ├── _shared/              ← 5 个元 skill（全部 Agent 共用）
│   ├── coordinator/          ← 主 Agent（5 文件：SOUL+AGENTS+HEARTBEAT+MEMORY+AGENT-ROUTING）
│   ├── retriever/            ← 检索员
│   ├── writer/               ← 写作员
│   ├── rewriter/             ← 改写员（4 模式）
│   ├── reviewer/             ← 审查员
│   └── registry.yaml         ← Agent 注册元数据
├── docs/
│   ├── payload-schema.md     ← 5 种 task_type 的 payload 契约（你只管 envelope，内容归我）
│   └── ragflow-chunk-lookup-research.md  ← ★ 关键调研：RAGFlow 原生支持 chunk 反查
├── mocks/                    ← 6 份测试数据（不依赖 RAGFlow 就能冒烟）
└── tests/                    ← ★★★ 7 个 skill × 6 断言 = 42 项真实 LLM 验证全过
```

### 2.2 已验证的 skill（真实 Sonnet/Opus 跑过）

| Skill | Tier | 断言 | 验证了什么 |
|-------|------|------|----------|
| Writer.section_writing | Sonnet | 6/6 | 按提纲写 800 字章节，引用全有效 |
| Writer.outline_generation | Sonnet | 6/6 | 5 个一级 + 10 个二级章节 JSON |
| Rewriter.data_update | Sonnet | 6/6 | 旧数据全替换，结构零改动 |
| Rewriter.perspective_shift | Opus | 6/6 | 投资人→监管者，数据一字不改 |
| Rewriter.style_conversion | Sonnet | 6/6 | 正式→通俗，句长 70→48 字 |
| Rewriter.content_expansion | Opus | 6/6 | 追加 `[新增]` 段落，原内容不动 |
| Reviewer.review_checklist | Sonnet | 6/6 | 识别虚构引用/数据错误/无据结论 |

一键跑：
```bash
cd reportclaw/tests
# 前置：.env 里有 ANTHROPIC_API_KEY + pip install anthropic python-dotenv
for f in smoke_*.py; do python3 $f; done
```

---

## 3. 对齐清单（大幅瘦身）

### ✅ 已解决（不用你做）

1. ~~chunk 反查接口~~ — RAGFlow 原生 `GET /api/v1/datasets/{ds}/documents/{doc}/chunks?id={chunk_id}` 就够用。详见 `docs/ragflow-chunk-lookup-research.md`
2. ~~A2A envelope 设计~~ — OpenClaw CollaborationService 原生提供，我这边只定义 payload 内容
3. ~~多轮审查回环~~ — Coordinator 内部处理，你只看最终结果

### 🟡 还需要对齐的（只剩 2 项）

#### P0-1：RAGFlow 字段映射

我需要 Retriever 返回这个 schema（详见 `agents/retriever/skills/source_tracking.md`）：

```json
{
  "chunk_id": "d78435d142bd5cf...",   // RAGFlow 原生 id，别改
  "content": "原文",
  "source": {
    "doc_id": "xxx",              // ← RAGFlow 的 document_id
    "doc_name": "xxx.pdf",        // ← RAGFlow 的 docnm_kwd
    "dataset_id": "xxx",          // ← RAGFlow 的 kb_id ★ 这个最重要，Reviewer 反查必需
    "category": "行业报告"        // ← 从 dataset 映射
  },
  "relevance_score": 0.9669,
  "highlight_spans": [[12, 28]]   // 可选，拿不到就砍
}
```

**要做的**：你的 RAGFlow 适配层把这些字段透传出来，大概 10 行代码。

#### P0-2：OpenClaw 能加载哪些 Agent 文件

我每个 Agent 目录下有 5 个文件（Coordinator）或 1-2 个文件（其他）：

```
coordinator/
├── SOUL.md           ← 人格（核心信念、禁止事项）
├── AGENTS.md         ← 工作手册（任务分类表 + 禁忌）
├── HEARTBEAT.md      ← 启动红线 + 任务命名规范
├── MEMORY.md         ← 历史教训 + 永久禁止项
├── AGENT-ROUTING.md  ← 子 Agent 路由 + tier 路由
└── skills/           ← 具体能力
```

**需要你确认**：
- OpenClaw 原生加载 5 文件的哪些？
- 如果只加载 SOUL.md，剩下 4 个文件我要不要合并？
- skills/ 目录下的 markdown 是 Agent 自动 find-skills 发现，还是要显式注册？

**建议时间**：15 分钟线下对一次就清楚了。

---

## 4. 关键决策（已锁定，不用讨论）

1. **chunk_id 用 RAGFlow 原生 id**（放弃自造 `{doc_id}_p{page}_{idx}` 方案）
2. **4 种 category 对应 4 个 RAGFlow dataset**（政策法规/行业报告/历史报告/媒体资讯）
3. **Reviewer 自己调 RAGFlow 反查**，不走你的中间层（减少你负担）
4. **max_review_rounds = 2**，超过升级给用户
5. **引用格式统一 `[ref:chunk_id]`**，前端渲染为可点击跳转
6. **Gear System（G1/G2/G3）+ Model Tier（T1/T2/T3）双层自适应** — 来自 Shifu plugin

---

## 5. 工具链（已落地）

| 工具 | 位置 | 用途 |
|------|------|------|
| MCP Schema Proxy | `tools/mcp-schema-proxy.py` | 修 wenge MCP schema 违规（Claude Code 才能调 Agent） |
| Smoke test 基础设施 | `reportclaw/tests/smoke_*.py` | 7 个 skill 的端到端验证 |
| Mock 数据集 | `reportclaw/mocks/*.json` | 不依赖 RAGFlow 冒烟 |

---

## 6. 你的分工

| 项 | 谁 | 备注 |
|----|----|------|
| RAGFlow 部署 + 文档入库 | **你** | 4 个 dataset：policies/industry_reports/historical_reports/media_news |
| RAGFlow → Retriever schema 适配层 | **你** | 见 §3 P0-1 |
| Claw + CollaborationService 集成 | **你** | 承载我这 5 个 Agent |
| 版本管理后端 API | **你** | `POST /reports/{id}/versions` 等 4 个 endpoint（详见 alignment-王亚洲.md §5） |
| 前端三栏 UI | 待定 | 我写 Agent 逻辑，前端可以一起分 |

| 项 | 谁 | 备注 |
|----|----|------|
| 5 个 Agent SOUL + Skill | **我**（完成） | 7/7 smoke 通过 |
| Mock 数据集 | **我**（完成） | 6 份 |
| Schema Proxy | **我**（完成） | 本地已运行 |
| Smoke Test 基础设施 | **我**（完成） | 一键 42 断言 |
| 答辩 PPT | 待启动 | 4/20 前 |

---

## 7. 明日（4/18）建议节奏

| 时间 | 事项 | 谁 |
|------|------|-----|
| AM | 15 min 对齐 §3 两项 | 我们俩 |
| AM | 你开搭 RAGFlow | 你 |
| PM | 我起草前端三栏 UI 设计 | 我 |
| PM | 你接通 Retriever API | 你 |
| EOD | v1.0 联调（真实 RAGFlow + 我的 Agent） | 我们俩 |

---

## 8. 备注

所有改动都在 `main` 分支上（PR #1-#6 都合了）。
你拉 `git pull origin main` 就是最新状态。

答辩评分 5 维度对应我们的交付：
- 知识检索准确性 25% — Retriever 的混合检索 + 溯源（✅ 架构 OK，等 RAGFlow）
- 报告生成质量 25% — Writer 3 skill 全过（✅ 已验证）
- 改写质量 25% — Rewriter 4 模式全过（✅ 已验证）
- 对比展示与版本管理 15% — diff_generator + 你的版本 API（🟡 待你）
- 系统完整性与体验 10% — Gear + Tier + 三栏 UI（🟡 前端待做）

有问题飞书叫我。
