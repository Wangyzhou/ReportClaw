# Dogfood 反哺 — ReportClaw 能力 → Shifu 升级

> 2026-04-17
> 立场：ReportClaw 是 Shifu Gear System 在 Agent 场景的第一个"被试品"。
> 反过来，ReportClaw 在落地过程中积累的几个设计模式，也能倒流回 Shifu 补强 Shifu 本身。
> 这是 dogfood 的典型姿态：自己用自己的产品，在用的过程中把产品迭代更好。

---

## 1. 回馈路径总览

```
Shifu（纪律系统）─────────┐
    │ G1/G2/G3 判档           │ 移植
    │ test-first              │ ──→  ReportClaw Coordinator
    │ verification            │          ↓
    │ orchestrate             │      真实 Agent 场景落地
    │                         │          ↓
    └──── Shifu 升级 ←────────┘     反哺 5 个新 Pattern
```

---

## 2. ReportClaw 能倒流给 Shifu 的 5 个设计模式

### (1) fact-check-before-trust（事实核查 skill）

**ReportClaw 场景**：
Reviewer 对报告里每个数字/日期/实体跑一遍"提取 → 置信度打分 → 低置信度回查"协议，防 LLM 虚构数据。

**Shifu 升级**：
当前 `shifu:review` 只做代码 review。可以加一个**通用**的 `shifu:fact-check` skill：
- 适用于任何 Agent 输出涉及具体事实的场景
- 三步：提取 claim → 置信度分档 → 低置信度强制 re-verify
- 特别适合 Shifu 的 G2/G3 档位里的文档/报告类任务

**具体改动**：在 `~/.claude/plugins/marketplaces/shifu-marketplace/plugins/shifu/skills/` 加一个 `fact-check/SKILL.md`，模板可直接从 `reportclaw/agents/_shared/fact-check-before-trust.md` 复用。

---

### (2) loop-circuit-breaker（熔断）

**ReportClaw 场景**：
防 Writer↔Reviewer 打乒乓（Reviewer 说"改"，Writer 改完 Reviewer 又说"还不行"，无限循环）。2 次同签名失败就熔断，升级给用户决定。

**Shifu 升级**：
Shifu 现在遇到失败是 `shifu:debug` 进入 4 阶段根因调查。但**它没有自动熔断机制**——如果 debug 第 2 次还失败，理论上可以无限 debug 下去。

建议加 `shifu:circuit-break` skill：
- 签名归一化（tool_name + args_hash + error_type）
- 同签名累计 ≥ 2 次 → 熔断并升级
- 熔断后自动写入 MEMORY（作为将来的反模式参考）

---

### (3) 人格化 SOUL 模板（核心信念 + 禁止事项）

**ReportClaw 场景**：
5 个 Agent 各自 SOUL.md 都有「核心信念 5 条 + 工作节奏 + 禁止事项 7 条 + 强制语言规则」。LLM 读完角色感极强，输出明显更"像那个角色"。

**Shifu 升级**：
Shifu 的 skills 更偏"操作手册"风格（iron laws + 具体步骤），没有赋予 Agent 人格化身份。可以在 Shifu 加一个：

**新 skill**：`shifu:persona-cast`
- 使用场景：需要多 Agent 分工时（对应 Shifu 的 G3 `orchestrate`）
- 作用：把通用 Agent 转成有明确身份/信念/禁忌的专家 Agent
- 模板：ReportClaw 的 5 个 SOUL.md 抽象成"Soul Builder"

---

### (4) "不要指定工具名 / 不要描述排版"的反直觉铁律

**ReportClaw 场景**：
Coordinator 派任务时禁止说"用 BM25"或"加 H2 标题"。这条规则背后是：**决定 HOW 是子 Agent 的专业权限，Coordinator 只说 WHAT**。

**Shifu 升级**：
Shifu 的 iron laws 目前多是关于"必须做什么"（必须写测试、必须验证）。可以加一条 meta iron law：

**"Orchestrator 不越权"铁律**：
- 向 subagent 派发任务时，只描述"做什么、交付标准"
- 禁止指定 subagent 应该用什么工具、什么格式、什么库
- 工具/格式/库的选择是 subagent 依据自己 skill 自主决定

应该加到 `shifu:orchestrate` 的 iron laws 里。

---

### (5) 任务描述强制模板（派发格式硬约束）

**ReportClaw 场景**：
Coordinator 派发任务必须符合固定模板：主题 / 任务描述 / 交付标准 / 长度语言 / 输出位置。Subagent 汇报也必须固定格式：任务 / 状态 / 成果摘要 / 输出位置 / 问题。

**Shifu 升级**：
Shifu 的 subagent 调用（G3 orchestrate）当前没有强制模板，全靠 LLM 自觉。加一个：

**`shifu:dispatch-template`**
- 派发方用这个模板拼消息
- 汇报方用这个模板返回
- 前端可以可视化任务树（借鉴 mediaclaw 的 task-progress-manager MCP）

---

## 3. 共同升级：Shifu → ReportClaw 的双向优化

除了反哺，还有些 Shifu 已有能力能进一步强化 ReportClaw：

### (a) shifu:think-first → ReportClaw 的 create-plan

ReportClaw Coordinator 现在用了 create-plan 模板（借鉴 mediaclaw）。但 Shifu 的 `shifu:think-first` 做得更细致（设计阶段 + 规划阶段分层）。可以把 ReportClaw 的 create-plan skill 重构为调用 `shifu:think-first`。

### (b) shifu:test-first → ReportClaw 的 mocks

ReportClaw 已经造了 6 份 mock 数据。下一步应该把每个 skill 的 Few-Shot 示例转成**可执行的测试**（pytest + 断言输出），完全贴合 shifu:test-first 的 TDD 理念。

---

## 4. 具体 Action Items

| # | 动作 | 目标仓库 | 谁做 |
|---|------|---------|------|
| 1 | 把 fact-check-before-trust 移植为 Shifu 通用 skill | `shifu/skills/fact-check/` | 后续（本周内） |
| 2 | 在 `shifu:debug` 加熔断机制 | `shifu/skills/debug/` | 后续 |
| 3 | 写 `shifu:persona-cast` skill | `shifu/skills/persona-cast/` | 后续 |
| 4 | 加"Orchestrator 不越权" meta iron law | `shifu/skills/orchestrate/` | 立刻可做 |
| 5 | 加 `shifu:dispatch-template` | `shifu/skills/dispatch-template/` | 后续 |
| 6 | 把 ReportClaw mock 改成 pytest（对齐 shifu:test-first） | `reportclaw/tests/` | 4/18 可做 |
| ✅ 7 | **已完成**：新增 `shifu:delegate`（model tier 路由）+ engage.md 引用 + 修 conflict resolution 矛盾 + 版本号对齐 | `shifu/skills/delegate/` | **2026-04-18 完成** |
| ✅ 8 | **已完成**：ReportClaw `AGENT-ROUTING.md` 加 Tier 映射表（5 Agent × 所有 skill 的默认档位 + 升降档条件） | `reportclaw/agents/coordinator/AGENT-ROUTING.md` | **2026-04-18 完成** |

---

## 5. 为什么这个反哺有意义

### 立场一：对 Shifu 是打磨

Shifu 做出来就是给"通用 Claude Code 任务"用的。ReportClaw 是一个**真实、复杂、有交付压力**的项目，是检验 Shifu 在重度场景下是否好用的"极限测试"。ReportClaw 跑通并提出改进，比 Shifu 自己做单元测试有价值 10 倍。

### 立场二：对 ReportClaw 是加速

反过来，Shifu 已有的 test-first / orchestrate / debug 等方法论可以直接套用到 ReportClaw 的后续迭代，省掉重新发明的时间。

### 立场三：对答辩是亮点

"我的 T5 项目不是孤立的——它使用了我自己做的 Shifu 系统，并且在过程中反哺升级了 Shifu。这是一个完整的 AI-native 工作流闭环。"——这是能写进答辩 PPT 的故事线。

---

## 6. 不能移植的部分（划清边界）

有些 ReportClaw 的设计是**领域特定**的，不该塞进通用 Shifu：

| ReportClaw 特性 | 为什么不该移植到 Shifu |
|----------------|--------------------- |
| `gear_detection` 的 G1/G2/G3 用报告长度做判据 | Shifu 的 gear 用代码复杂度判据，判据不同 |
| `source_tracking` 的 `[ref:xxx]` 引用格式 | 只对报告/文档场景有意义，代码/通用任务用不上 |
| `data_update` / `perspective_shift` 等 Rewriter 模式 | 报告改写独有 |
| Retriever 的 coverage_assessment | 依赖有向量知识库，Shifu 通用场景不一定有 |

划清边界很重要——Shifu 是骨架，ReportClaw 是血肉。不能把血肉塞回骨架里。

---

## 7. 下次做 Shifu 升级时的清单

等 T5 答辩完（4/21 后），可以启动"Shifu v2"迭代，清单：

- [ ] 创建 `fact-check` skill（从 ReportClaw 移植）
- [ ] `shifu:debug` 加熔断
- [ ] 创建 `persona-cast` skill
- [ ] `shifu:orchestrate` 加"不越权" iron law
- [ ] 创建 `dispatch-template` skill
- [ ] 给 Shifu 写一篇 "Lessons from ReportClaw" 的 blog post（作为 dogfood 故事）

这才是 dogfood 的完整闭环——用自己的工具做真实项目，工具在过程中被真实磨砺，最后工具和项目互相成就。
