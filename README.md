# ReportClaw 📑

> **多 Agent 协作的智能报告写作平台** — 知识库驱动 + 引用追溯 + 流程熔断 + MCP 工具化
> T5 智能报告写作平台参赛实现

---

## 一句话

**ReportClaw 不是单 LLM 一次性吐报告，而是 5 个 AI 角色协作 + 引用必须可追溯 + 流程上限可控。**

| 维度 | ChatGPT 写报告 | ReportClaw |
|------|---------------|-----------|
| 单 LLM 一次性吐 5000 字 | ✓ | ❌ |
| 5 角色拆（Coord/Retriever/Writer/Rewriter/Reviewer）| ❌ | ✓ |
| 强制 chunk_id 回查 — 不虚构引用 | ❌ | ✓ |
| Writer↔Reviewer 熔断 ≤2 轮 | ❌ | ✓ |
| 4 改写模式（数据更新/视角调整/内容扩展/风格转换）| 重新说一遍 | ✓ 定向 + diff |
| 任务树实时可观察 | 黑盒 | ✓ |

适合：研究分析师 / 投资经理 / 政策研究员 / 行业分析师 — 任何**职业上必须对引用真实性负责**的角色。

---

## 系统架构

```
用户层（React 三栏）
  KnowledgePanel    ChatPanel              DeliveryPanel
  ┌──────────┐     ┌────────────┐         ┌──────────┐
  │ 4 分类知识库│ │ 主对话流式  │         │ 任务树看板│
  │ + 上传文档│   │ + 引用 hover│         │ + 报告预览│
  └──────────┘     └────────────┘         └──────────┘
                          │
                          ↓ NDJSON
        ┌─────────────────────────────────────────┐
        │  Spring Boot (8080)         Python chat │
        │  /api/sessions              server (8081)│
        │  /api/kb/*                  /api/chat/*  │
        │  /api/tasks                              │
        └────┬────────────────────────────┬───────┘
             │                            │ subprocess
             ↓                            ↓
        OpenClaw Gateway              `openclaw agent`
        (ws://localhost:18789)            CLI
                                          │
                          ┌───────────────┼───────────────┐
                          ↓               ↓               ↓
                  reportclaw-coordinator  ...writer  ...reviewer
                  (5 Agent runtime, real DeepSeek calls,
                   complete SOUL.md + skills loaded per turn)
                          │
                          ↓
                  MCP 工具层 (Higress + 王亚洲生产部署)
                          │
                          ↓
                  RAGFlow 知识库 (BGE-M3 embedding + Reranker)
```

---

## 5 个 Agent

| Agent | 核心职责 | Model | Temperature |
|-------|---------|-------|-------------|
| **Coordinator** | 判档 G1/G2/G3 + 任务派发 + 验收 | deepseek-v4-pro | 0.3 |
| **Retriever** | RAGFlow 混合检索 + 溯源 + 覆盖度 | deepseek-v4-flash | 0.0 |
| **Writer** | outline / section / mimic / citation | deepseek-v4-flash | 0.6 |
| **Rewriter** | data_update / perspective_shift / content_expansion / style_conversion | deepseek-v4-flash | 0.4 |
| **Reviewer** | citation_verification / review_checklist / coverage_scoring | deepseek-v4-flash | 0.2 |

每个 Agent 有 SOUL.md（人格信念）+ AGENTS.md（工作手册）+ skills/（能力 prompt），共享 `_shared/` 元 skill（loop-circuit-breaker / fact-check-before-trust / verification-before-completion 等）。

---

## Gear System

| Gear | 场景 | 编队 | 耗时 |
|------|------|------|------|
| **G1** | 快速查询 / 元信息 | Retriever 或直答 | <10s |
| **G2** | 短报告 / 简单改写 | 全链路 1 轮审 | 30-60s |
| **G3** | 长报告 / 仿写 / 扩展 | 并行检索 + ≤2 轮审 | 2-5min |

动态升级：Retriever 低覆盖 / Reviewer HIGH issue / 用户追加需求 → G2 自动升 G3。

---

## 6 个关键创新（含本机 demo 增强）

1. **Gear 自适应** — G1/G2/G3 决定执行深度，简单请求不走全链路
2. **双层事实校验** — verification-before-completion（章节做完）+ fact-check-before-trust（引用对得上）
3. **BY_ORDER SOP 熔断 ≤2 轮**（[task_dispatch/SKILL.md](agents/coordinator/skills/task_dispatch/SKILL.md)）— round counter 硬规则状态机，禁止 LLM 自由判断"还要不要再改一轮"
4. **可插拔检索层** — 在线 RAGFlow / 离线 mock，外部依赖不稳定时仍能演示核心能力
5. **MCP 工具化** — 知识库 = `ragflow_hybrid_search` / `ragflow_get_chunk` 标准工具，跟 OpenClaw + Higress 解耦
6. **cause_by envelope** ⭐（本机 demo 新增）— 报告里每个 [来源] hover 看完整追踪链：Retriever 检索 doc/page → Writer 在哪段引用 → Reviewer 校验 verdict + accuracy_score

---

## 本机快速启动

> 不依赖王亚洲生产环境（OpenClaw gateway pairing / Higress MCP），本机 3 命令跑通完整 demo

### 前置依赖

| 依赖 | 装法 |
|------|------|
| OpenClaw daemon | 已装（`openclaw doctor` 确认） |
| Java 21 | `brew install openjdk@21` |
| Node 20+ | `brew install node` |
| Python 3.11+ | 系统已有 |
| DeepSeek API key | 已在 `~/.openclaw/agents/main/agent/auth-profiles.json` |

### 启动（3 命令）

```bash
# Terminal 1: Spring Boot + Python chat server (端口 8080 + 8081)
cd ReportClaw
bash scripts/start_demo.sh

# Terminal 2: React 前端 (端口 3000)
cd ReportClaw/frontend
npm run dev

# 浏览器开 http://localhost:3000
```

输入主题（如"写一份 A 股 AI 算力 Q1 流动性观察报告"），看：

| ~时间 | UI 反应 |
|------|--------|
| 0s | 用户消息 + Coordinator 判档卡片 |
| ~25s | dispatch JSON + 💰 Coordinator 真 OpenClaw runtime cost |
| ~30s | retrieval 6 chunks + 任务树 retriever ✓ |
| ~30-100s | Markdown 流式打印（4 章节带 [来源]）+ writer 🔄→✓ |
| ~100-110s | Reviewer 卡片 verdict pass + 💰 cost |
| ~110s | 💰 总成本 + cause_chain 6 chunks tracked |
| ~110s | 报告里每个 [来源] hover 看完整追踪链 tooltip |

停止：
```bash
bash scripts/stop_demo.sh
```

### 评委 5 分钟快速验证（不依赖 chat server）

```bash
git checkout submission/final
bash scripts/quick_verify_deepseek.sh   # 70s / $0.0008，跑 17 次真 LLM 调用
```

会跑 1 份完整报告（4 章节）+ 1 改写模式 + 1 续写 + 重新生成 diff，全部用 DeepSeek。产出 deliverables/ 真实文件可直接打开。

---

## 评委验证主线（PDF 评委版第 13 节路径）

| 类型 | 位置 |
|------|------|
| 3 份完整报告 | `deliverables/reports/topic-0{1,2,3}/v1.md`（提交时跑出，submission/final 分支）|
| 版本管理 v1→v2 | `deliverables/reports/topic-01-*/VERSIONS.md` |
| 4 改写模式 | `deliverables/rewrite-demos/0{1,2,3,4}-*/diff.md` |
| 续写 | `deliverables/continuation-demo/new-section-only.md` |
| Word 导出 | `deliverables/exports/*.docx` (5 份) |
| 17 次 LLM 调用日志 | `deliverables/generation-log.json` (sections 数组 / 0 越界引用) |
| 引用校验 + 共享元约束 | `agents/_shared/` |
| Gear 判档 | `agents/coordinator/skills/gear_detection/SKILL.md` |
| BY_ORDER SOP 硬规则 | `agents/coordinator/skills/task_dispatch/SKILL.md` |
| MCP 工具契约 | `deploy/higress-mcp-server.yaml` + `.mcp.json` |
| 任务树后端 | `openclaw-chat-ui/.../TaskProgressController.java` |
| 任务树前端 | `frontend/src/components/DeliveryPanel/TaskTreePanel.tsx` |

---

## 评分映射

| 维度 | 权重 | ReportClaw 实现 |
|------|------|----------------|
| 知识检索准确性 | 25% | Retriever 混合检索 + chunk_id 溯源 + coverage_assessment |
| 报告生成质量 | 25% | Writer 4 skill (outline/section/mimic/citation) + 0 越界引用 |
| 改写质量 | 25% | Rewriter 4 模式 + diff_generator |
| 对比展示与版本管理 | 15% | v1/v2 versioning + diff-side-by-side |
| 系统完整性与体验 | 10% | Gear 自适应 + 三栏 UI + Mock 闭环 + cause_by envelope |

---

## 边界（诚实披露）

| 已完成 ✅ | 仍在边界 |
|-----------|---------|
| 用户文档上传 → embedding → 知识入库链路 | Retriever 调真 RAGFlow 需王亚洲端口转发 192.168.4.176:8082 Higress MCP |
| 知识驱动报告生成（3 真实报告 + 17 LLM 调用 + 0 越界） | Coordinator 在 OpenClaw turn 内**自动 sessions_spawn** 真子 agent — 当前 chat server 仍手动编排 |
| 改写 4 模式 + 续写 + 版本管理 v1/v2 | 完整 Spring Boot Chat UI ↔ OpenClaw gateway pairing — 当前用 `openclaw agent` CLI subprocess 路径替代 |
| OpenClaw 5-Agent runtime 真接通（CLI subprocess 路径） | 真 G3 多 retriever 并行 + 2 轮 review 视觉契约 |
| 任务树实时可观察（Spring Boot `/api/tasks` ↔ React 轮询） | |
| BY_ORDER SOP 硬规则 + cause_by envelope（追踪链可视化）| |
| 真实 V4-Flash / V4-Pro 智能混合 + 真实计费（cache hit/miss） | |

---

## 分工

- **林宇泰 (Eddie)**：Agent 身份 + Skill + Coordinator 调度 + 前端 + 本机 demo runtime
- **王亚洲**：RAGFlow 搭建 + Spring Boot 后端 + Higress MCP + Claw 集成

---

## 项目演进里程碑

| 日期 | 里程碑 |
|------|-------|
| 2026-04-17 | Agent Team 5 角色 + Skill Prompt + Mock 闭环 ✅ |
| 2026-04-18~21 | RAGFlow 联调 + 改写 + 续写 + 版本 + diff + 任务树 + 前端三栏 ✅ |
| 2026-04-22 | submission/final 提交（17 LLM 调用 / 0 越界 / deliverables 完整产出）|
| 2026-05-04 | drift-free backend smoke (M4/M5/M6) + SKILL.md 3 bug 修 |
| 2026-05-04 | 本机 demo 端到端跑通：DeepSeek shim + Python chat server + 智能混合 V4-Pro/Flash |
| 2026-05-04 | cause_by envelope（[来源] hover 追踪链）+ BY_ORDER SOP（MetaGPT 借鉴）|
| 2026-05-05 | OpenClaw 5-Agent runtime 真接通（subprocess CLI 路径） |

---

## 设计哲学的 5 个开源项目对应

| 维度 | ReportClaw | 借鉴/对应 |
|------|-----------|----------|
| 多视角检索发现 | gear_detection + Retriever | [STORM](https://github.com/stanford-oval/storm)（Stanford NLP，多 perspective conversation）|
| 多 Agent 协作运行时 | OpenClaw + agents/registry.yaml | [CrewAI](https://github.com/crewAIInc/crewAI) / [LangGraph](https://github.com/langchain-ai/langgraph) |
| 角色边界 + SOP 固化 | 5 SOUL.md + BY_ORDER SOP | [MetaGPT](https://github.com/geekan/MetaGPT)（"Code = SOP(Team)"）|
| 自主深度研究 | gear=G3 + Coordinator 派发 | [GPT Researcher](https://github.com/assafelovic/gpt-researcher)（多源融合 + 章节并行）|
| 中文 PDF 解析护城河 | RAGFlow 内置 + 待替 MinerU | [MinerU](https://github.com/opendatalab/MinerU)（中文表格/公式 +40% 质量）|

---

## 文档导航

- **设计哲学**: [docs/payload-schema.md](docs/payload-schema.md) — 5 种 task_type payload 契约
- **集成复盘**: [docs/OpenClaw集成复盘.md](docs/OpenClaw集成复盘.md)
- **AI 工具使用**: [docs/AI工具使用日志.md](docs/AI工具使用日志.md)
- **快速启动**: [SESSION-2026-05-04-05.md](SESSION-2026-05-04-05.md) — 启动 3 命令 + 文件地图 + 后续待办
- **CLAUDE.md**: 项目内 AI 协作约定
