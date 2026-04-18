# mediaclaw 深度洞察笔记 v2

> 在 v1 digest 基础上的二次深挖。本文专门记录"第一轮漏掉/没展开"的部分。
> 扫描时间：2026-04-17 第二轮
> 覆盖：15 个剩余元 skill + 4 个子 Agent 的 AGENTS.md + shared 文件约定 + 反模式合集

---

## 1. Skill 调用链模式（第一次提到）

mediaclaw 里 skill 之间有明确的**组合套路**，不是孤立使用：

| 组合链 | 触发时机 |
|--------|---------|
| `brainstorming` → `writing-plans` → `subagent-driven-development` → `verification-before-completion` → `daily-review` | 新功能/新报告开发 |
| `create-plan` → `writing-plans` → `task-progress-manager` | 用户直接要 plan 时 |
| `fact-check-before-trust` → `verification-before-completion` | 事实报告审查 |
| `task-handoff` → `proactive-agent`（WAL 恢复） | 长任务中断 |
| `context-window-management` → `persistent-memory-hygiene` → `memory-graph-builder --digest` | context 膨胀 |

**关键原则**：skill 在 `## When to Use` 里**显式指向下一步该调哪个 skill**，例如 brainstorming 结尾写"Then move to writing-plans"。T5 应该照抄这个习惯。

**来源**：`workspace-coordinator/skills/brainstorming/SKILL.md`（最后一句：*"Then move to writing-plans"*）

---

## 2. create-plan 的标准模板（T5 Coordinator dispatch 可直接用）

**来源**：`workspace-coordinator/skills/create-plan/SKILL.md`

```markdown
# Plan

<1–3 sentences: what, why, high-level approach.>

## Scope
- In:
- Out:

## Action items
[ ] <Step 1>  ← verb-first：Add/Refactor/Verify/Ship
[ ] <Step 2>  ← 6-10 个 atomic 步骤
...

## Open questions
- <最多3个>
```

**硬规则**：
- 只读模式（不改文件）
- 最多问1-2个 blocking 问题
- 不要前言后语，直接输出 plan
- 每项 action 都要可验证
- 必须包含 tests/validation 和 edge cases

**T5 直接用途**：Coordinator 接到用户需求时，走 create-plan 产出这个结构，作为 `dispatch` payload 给用户确认。

---

## 3. 前端交互约定（完整清单，超越 %%选项%%）

**任务命名规范**（来自 workspace-coordinator/HEARTBEAT.md）：
```
主任务：📋 [类型]-主题
子任务：🔍 搜集 / ✍️ 撰写 / ✅ 审查 / 🎉 完成
```

**汇报固定格式**（强制）：
```
# 完成汇报
## 任务 / 状态 / 成果摘要 / 输出位置 / 问题
```

**派发模板**（强制）：
```
# [任务类型]任务
## 主题 / 任务描述 / 交付标准 / 输出位置
请完成后通知我。
```

**T5 可抄**：三栏UI中间区直接用这些emoji+格式，无需重新设计。

---

## 4. Coordinator 的"任务描述铁律"（极反直觉但有教训支撑）

**来源**：`workspace-coordinator/MEMORY.md`

| 铁律 | 原因 | T5 怎么用 |
|------|------|----------|
| **禁止在任务描述中写排版/样式细节** | 外行指令覆盖 agent 的专业 skill 规范 | Coordinator 派 Writer 时只说"写一份行业报告"，不说"用H2标题+带表格" |
| **禁止指定工具名** | 工具由 agent 自己的 skill 决定 | 不说"用 BM25 检索"，只说"从知识库找相关内容" |
| **禁止子agent直接传任务** | 必须经 Coordinator 中转 | Retriever→Writer 的数据必须回到 Coordinator 再转发 |
| **禁止在验收上妥协** | 将就就是失职 | Reviewer 返回 needs_revision 必须走回环 |

---

## 5. WAL Protocol（长任务防崩溃的救命技术）

**来源**：`workspace-coordinator/skills/proactive-agent-skill/SKILL.md`

```
workspace/
├── SESSION-STATE.md       # 当前任务的活跃工作内存
├── working-buffer.md      # "危险区"实时 log（每次 exchange 记录）
├── MEMORY.md              # 长期记忆
└── memory/YYYY-MM-DD.md   # 日志
```

**4步循环**：
1. **Capture**：每次关键 exchange 写入 working-buffer
2. **Compact**：定期review提炼
3. **Curate**：重要信息移入 MEMORY.md
4. **Recover**：重启后从 log 恢复

**T5 必抄**：Writer 写 5000 字报告中途如果 session 崩了，没这个就从零重来。实现成本低（就是追加log），收益巨大。

---

## 6. 记忆三件套（reviewer 专属，mediaclaw 最精致的设计）

### (a) memory-graph-builder
**来源**：`workspace-reviewer/skills/memory-graph-builder/SKILL.md`
- 把扁平 MEMORY.md 建成知识图谱（node + edge）
- 4种关系：`related_to / contradicts / supersedes / depends_on`
- 生成 `memory-digest.md` 带 token budget
- 输出带 `[CONFLICT]` 标记
- 命令：`python3 graph.py --digest --max-tokens 1500`

**直接呼应 Eddie 提的"低模型消化"思路**——这就是成熟的 digest pipeline。

### (b) memory-integrity-checker
**来源**：`workspace-reviewer/skills/memory-integrity-checker/SKILL.md`
8 种 DAG 结构检查：
- ORPHAN_NODE / CIRCULAR_REF / TOKEN_INFLATION / BROKEN_LINEAGE / STALE_ACTIVE / EMPTY_NODE / DUPLICATE_EDGE / DEPTH_MISMATCH

**灵感**：`lossless-claw` 项目。每周日 3am cron 自动修复。

### (c) persistent-memory-hygiene
**来源**：`workspace-coordinator/skills/persistent-memory-hygiene/SKILL.md`
- 双层：`memory/YYYY-MM-DD.md`（daily raw）+ `MEMORY.md`（curated <500行）
- daily 文件 append-only，不改旧条目
- 23:00 cron 自动 Session Closing Routine

**T5 用法**：写进"未来迭代"PPT，对应"自进化"故事线。

---

## 7. cron-hygiene 的血泪教训（T5 做定时报告必读）

**来源**：`workspace-coordinator/skills/cron-hygiene/SKILL.md`

> "A cron running every 5 minutes in main session mode can turn a $10/month setup into $80+ (issue #20092)"

**硬规则**：
- cron 必须 `sessionMode: isolated`（不继承历史）
- output < 500 tokens
- 频率 ≥ 10 分钟
- 7 天无 state update 的 cron 自动标记 dead

**T5 用法**：4/21 交付后要做"每周自动报告"时，一定查这个。不然客户钱包会被 token 吃掉。

---

## 8. task-handoff（session 重启的交接模板）

**来源**：`workspace-coordinator/skills/task-handoff/SKILL.md`

```markdown
# Handoff: [task name]
Written: YYYY-MM-DD HH:MM
Reason: [why stopping]

## Current State  [1-3句话]
## What's Done
## What's Next  [具体指令]
## Important Context  [code里看不出的决策]
## Files Modified
## Tests  [Last run / Status]
## Blockers
```

**T5 用法**：我们的"接力说明.md"可以升级成这个模板。

---

## 9. dangerous-action-guard 的"5分钟确认过期"

**来源**：`workspace-coordinator/skills/dangerous-action-guard/SKILL.md`

- 只接受明确词："yes/go ahead/confirmed/do it/proceed"
- 拒绝："maybe/I think so/sure I guess"
- approval 5 分钟过期，超时重新确认
- batch 操作必须先展示 scope
- >10 项只显示前 5 + 总数

**T5 用法**：导出 Word/PDF、删除版本、发布报告 都应该走这个。

---

## 10. skill-creator 的黄金原则（T5 自创 skill 时必读）

**来源**：`workspace-coordinator/skills/skill-creator/SKILL.md`

1. **"Concise is Key"** — context 是公共资源
2. **"Default assumption: Claude is already very smart"** — 不解释已知
3. **三档自由度**：
   - 高自由度：纯文本指令（多方案都行）
   - 中自由度：伪代码/带参脚本（有偏好模式）
   - 低自由度：specific script（操作脆弱）

4. **SKILL.md 结构**：frontmatter (name+description) + Markdown body
5. **配套目录**：scripts/（deterministic代码）/ references/（按需加载文档）/ assets/（输出用的模板/图标）

---

## 11. skill-vetting（有意思但 T5 用不上）

**来源**：`workspace-coordinator/skills/skill-vetting/SKILL.md`

> "~17% of ClawHub skills are malicious."

Red flags 清单：unknown network calls / credential harvesting / filesystem writes outside / obfuscated code / excessive permissions / unverifiable author。

**T5 不用**，但这个数字值得知道——如果未来用户装第三方 skill 得过这关。

---

## 12. subagent-driven-development 的真·并行

**来源**：`workspace-coordinator/skills/subagent-driven-development/SKILL.md`

```bash
exec command:"claude --permission-mode bypassPermissions --print '[spec A]'" background:true
exec command:"claude --permission-mode bypassPermissions --print '[spec B]'" background:true
```

不是顺序调用，是**真正起独立 claude 进程**。

**T5 用法**：Retriever 并行查 5 个 category；Rewriter 的 4 种模式可同时跑让用户选最好的。

---

## 13. `~/.openclaw/shared/` 文件约定（团队协作的基础）

| 路径 | 内容 | 生命周期 |
|------|------|---------|
| `tasks/active/{task_id}.md` | 活动任务卡片 | 任务完成移出 |
| `logs/execution.log` | 执行日志 | append-only |
| `reports/review/daily/{YYYYMMDD}.md` | 日复盘 | 按日期归档 |
| `reports/review/weekly/week{周数}.md` | 周报 | 每周一生成 |
| `team-memory.md` | 团队共享记忆 | 长期维护 |

**T5 可抄**：这套目录结构做"报告历史版本库"非常合适。

---

## 14. 反模式合集（踩坑教训汇总）

从 MEMORY.md 里挖出的 13 条真实事故：

| 事故 | 根因 | 教训 |
|------|------|------|
| web_search 越权调用 | Coordinator 自己搜 | 搜索一律委托 subagent |
| 排版简陋 | 任务描述写"基本排版" | 不描述怎么做，只说做什么 |
| 英文输出 | 约束放得太靠后 | 关键约束放任务描述第一行 |
| reviewer 超时4分钟 | 把审查当成写文档 | reviewer 只做快速验证，1分钟内 |
| steer 重启浪费时间 | 派发前没想清楚 | 想清楚再派发，一次到位 |
| 隐式技能遗漏 | 依赖记忆执行 | 强制检查点清单 |
| MCP 格式错误 | 凭猜测调用 | 先读 SKILL.md 再调 |
| agentId 错误 | 用 label 当 agentId | 用 session_status 取 sessionKey |
| 配图未确认 | 默认就配 | 必须事先用 %%选项%% 问 |
| 搜图拆成独立节点 | 误以为要拆 | 配图是 media-editor 内部的事 |
| 跳过渠道获取直接发布 | 省步骤 | 必须先 get-all-accounts |
| 遗漏 add-file-record | 规则只写"文件产生时" | 绑定到具体流程节点 |

**T5 对应**：每条都对应 T5 一个潜在坑。比如"reviewer 超时"直接告诉我们 Reviewer 的 checklist 要短、不做文字级校对。

---

## 15. 子 Agent 的 AGENTS.md 特色（v1 没展开）

### analyst
- 核心skill：`fact-check-before-trust` + `content-writer`
- 标准输出：`# {主题}调研报告` 带"核心发现"带可信度列
- **可信度**用星级标（`⭐⭐⭐ / ⭐⭐ / ⭐`）

### researcher
- 核心指令：**搜索必须并行**（用 `&` + `wait`）
- 工具优先级表（3星→1星）
- 最多 2 轮搜索（防无限搜）

### media-editor
- **HTML 排版硬规则**：禁用 `<style>` 标签 / 禁用 class 选择器 / 必须行内样式 / 必须相对路径
- 5个平台差异化字数表（微信 1500-3000 / 小红书 500-1000 / 微博 300-500 / 知乎 1000-2000 / 头条 800-1500）

### reviewer
- **5种产出固定模板**：问题记录表 / 用户画像 / 日复盘 / 周报 / 团队记忆更新
- 问题记录表列：`# / 描述 / 任务 / 影响 / 根因 / 方案 / 状态`

---

## 16. 最让人眼前一亮的 3 个发现

### 🥇 WAL Protocol（第5节）
Writer 写 5000 字中途崩溃=救星。实现成本极低（追加 log），应该进 T5 v1.0。

### 🥈 Memory Graph Builder 的 --digest 管线
和 Eddie 提的"低模型消化"思路完全重合。mediaclaw 已经把这个做成了成熟 skill：
- 去重/去冲突/去陈旧
- token budget 控制
- 替换原 MEMORY.md 注入 system prompt
- 省 30-60% token

T5 的知识库本质就是个大 MEMORY.md。**这个 skill 可以直接 port 过来治理历史报告**。

### 🥉 "禁止指定工具名" + "不描述怎么做"
这两条反直觉铁律背后是一个深刻洞察：**Coordinator 是业务指挥官，不是技术架构师**。它说做什么，子Agent 靠自己的 skill 决定怎么做。这样 skill 更新时不会被 Coordinator 的硬编码拖累。

T5 Coordinator 的 dispatch 模板必须严格遵守——这是整个架构能长期演化的关键。

---

## 17. 更新 ROI 排序（合并 v1 + v2）

| 优先级 | 动作 | 新加入 |
|-------|------|--------|
| 🔴 P0 | 5个SOUL.md 升级（v1） | |
| 🔴 P0 | 5个Agent 加 AGENTS.md（v1，用上面子Agent的格式） | |
| 🔴 P0 | Coordinator 加 AGENT-ROUTING + HEARTBEAT + MEMORY（v1） | |
| 🔴 P0 | `_shared/` 4个元skill（v1） | |
| 🔴 P0 | **Coordinator 的 dispatch 用 create-plan 模板** | ✅ 新 |
| 🔴 P0 | **WAL Protocol 基础版**（SESSION-STATE + working-buffer） | ✅ 新 |
| 🟡 P1 | self-improving + brainstorming（v1） | |
| 🟡 P1 | **task-handoff 模板升级现有"接力说明.md"** | ✅ 新 |
| 🟡 P1 | **前端 UI 中间区用 emoji+汇报格式硬编码** | ✅ 新 |
| 🟢 P2 | memory-graph-builder（v1） | |
| 🟢 P2 | **cron-hygiene / dangerous-action-guard / memory-integrity-checker** | ✅ 新 |
