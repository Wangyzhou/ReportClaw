---
name: wal-protocol
description: Write-Ahead Logging for long-running tasks — 防 Writer 写 5000 字中途崩溃导致从零重来。所有长任务 Agent 必用。
metadata: {"openclaw": {"always": true}}
---

# wal-protocol（写前日志协议）

> 借鉴 mediaclaw 的 proactive-agent-skill WAL 模式。
> **核心场景**：Writer 生成 5000 字报告需要 30-60 秒，中途 session 崩/被 kill/OOM → 没有 WAL 就从零重来。

---

## 三文件结构

每个 Agent 工作时在自己的 workspace 维护三个文件：

```
workspace/{agent_name}/
├── SESSION-STATE.md       # 当前任务的活跃快照（每次关键动作更新）
├── working-buffer.md      # 实时 log（每次 LLM 调用前后 append）
└── MEMORY.md              # 长期记忆（已存在，不动）
```

---

## SESSION-STATE.md 模板

**每次关键动作更新**（接任务、切 stage、子任务完成、遇错）。

```markdown
# SESSION-STATE

## Current Task
- task_id: {uuid}
- started_at: {ISO8601}
- intent: {generate_report | rewrite | retrieve | ...}
- stage: {planning | dispatching | writing | reviewing | done | failed}
- gear: {G1 | G2 | G3}
- tier: {T1 | T2 | T3}

## Input snapshot
- topic: ...
- outline: ... (or null)
- constraints: { max_length, language, ... }
- retrieval_results_count: {n}

## Progress
- Sections completed: [sec_1, sec_2]
- Sections pending: [sec_3, sec_4]
- Last checkpoint at: {ISO8601}

## Next Step
{一句话说明"恢复后从哪一步继续"}

## Partial output location
{file path where in-progress output is being appended}
```

**关键字段**：`Next Step` 是恢复的入口，Agent 重启只读这一行就知道该做什么。

---

## working-buffer.md 协议

**每次 LLM 调用前后各写一行**。append-only，不编辑。

```markdown
[2026-04-18T00:15:32] PRE  section=1.1 tier=T2 prompt_chars=1840
[2026-04-18T00:15:58] POST section=1.1 output_chars=1120 citations=3
[2026-04-18T00:16:00] CHECKPOINT state.yaml updated
[2026-04-18T00:16:02] PRE  section=1.2 tier=T2 prompt_chars=1920
[2026-04-18T00:16:28] POST section=1.2 output_chars=1245 citations=4
[2026-04-18T00:16:30] ERROR section=1.3 LLM_RATE_LIMIT retry_in=30s
[2026-04-18T00:17:00] PRE  section=1.3 tier=T2 prompt_chars=1880 (retry 1)
```

**格式**：`[时间] 动作 字段=值`，一行一事件。

---

## 4 步循环

### Step 1 — Capture（进任务）
Agent 接到任务后第一动作：
1. 创建/覆写 `SESSION-STATE.md`（current task + input snapshot）
2. Append `[TIME] TASK_START task_id=X intent=Y gear=Z` 到 working-buffer

### Step 2 — Compact（干活中）
每次 LLM 调用：
1. **调用前** append `PRE` 行到 working-buffer
2. 调 LLM
3. **调用后** append `POST` 行，并更新 SESSION-STATE 的 Progress 字段

### Step 3 — Curate（阶段完成）
Stage 切换（如 planning→writing）时：
1. 把 SESSION-STATE 的 stage 字段更新
2. 如有值得长期保留的 learning，append 到 MEMORY.md
3. working-buffer 保持 append-only 不清空

### Step 4 — Recover（session 重启后）
Agent 启动时先查：
1. 读 SESSION-STATE.md — 是否有 stage ≠ done 的未完成任务？
2. 读 working-buffer.md 末尾 20 行 — 最后一步做到哪了？
3. 根据 SESSION-STATE 的 `Next Step` 字段**从断点继续**，不从头再来

---

## 并发 & 原子性

- SESSION-STATE.md 写入必须**原子替换**（临时文件 + rename）防部分写入
- working-buffer.md 是 append-only，用 `O_APPEND` 打开，不 truncate
- 不同 Agent 各自 workspace 独立 WAL，不共享文件

---

## Writer 的特殊要求

Writer 写 5000 字报告时，**每完成一节就 checkpoint**：
1. 把该节 markdown 写入 `partial_output.md`
2. 更新 SESSION-STATE 的 `Sections completed`
3. Append POST + CHECKPOINT 到 working-buffer

崩溃恢复时 Writer 读 partial_output.md → 知道已完成哪些 → 从下一节开始。**不重写已完成的节**。

---

## Rewriter 的特殊要求

Rewriter 改 4 模式时：
- `structure_parser` 解析结果单独保存到 `parsed_structure.json`
- 每改一段就写 WAL（段级 checkpoint）
- diff 增量计算（不要整篇重算）

---

## 性能

- WAL 本身的 IO 开销：< 10ms per checkpoint（可忽略）
- 磁盘占用：working-buffer 典型 < 100KB / task
- **收益**：5000 字报告中途崩溃时恢复成本从 60s 降到 5s（只需重跑最后一节）

---

## 不启用 WAL 的例外

- G1 任务（简单修改）— 本来就快，崩了重来也不亏
- Retriever 单次检索（纯读，无中间状态）
- Reviewer 60 秒以内完成的审查

**启用 WAL 的场景**（必须）：
- Writer 任何 section_writing 或 outline_generation
- Rewriter 任何模式（特别是 content_expansion）
- Coordinator 的 G3 全链路

---

## 谁用

**所有 Agent 在长任务场景都要用**。实现路径：
- 启动时调用 `wal.start(task_id)`
- 关键动作前后调用 `wal.pre()` / `wal.post()`
- stage 切换调用 `wal.checkpoint()`
- 异常退出时依赖 finally 块写 ERROR 行

运行时 utility 代码由王亚洲的 Claw 层提供，Agent 只负责"按协议写"。
