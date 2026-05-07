# TOOLS.md — 协调员工具

协调员不直接执行，只派单。

---

## OpenClaw 原生工具

### sessions_spawn
**唯一的子 Agent 派发机制**。每次要让 retriever/writer/rewriter/reviewer 干活，必须用这个工具。

**工具参数：**
```json
{
  "task": "string",              // 必填：给子 Agent 的完整指令（含 payload JSON）
  "agentId": "string",           // 必填：目标 Agent ID（见下表）
  "model": "string",             // 可选：覆盖子 Agent 的模型，默认不传
  "runTimeoutSeconds": 60,       // 可选：超时秒数（0=不限）
  "label": "string"              // 可选：任务标签，便于调试
}
```

**返回（立即，非阻塞）：**
```json
{ "status": "accepted", "runId": "...", "childSessionKey": "agent::subagent:..." }
```
子 Agent 完成后自动 announce 结果回本 session，**不需要轮询**。

**子 Agent ID 对照表（必须用全名，已在 openclaw.json allowAgents 白名单里）：**

| 目标 | agentId |
|------|---------|
| 检索员 | `reportclaw-retriever` |
| 写作员 | `reportclaw-writer` |
| 改写员 | `reportclaw-rewriter` |
| 审查员 | `reportclaw-reviewer` |

**铁律**：agentId **绝对不能**用短名（writer/retriever/reviewer/rewriter），会被 OpenClaw 权限网关拒绝并返回 `agentId is not allowed for sessions_spawn (allowed: ...)`。

**注意**：
- `task` 中必须包含完整的角色说明 + payload，因为子 Agent 只拿到 AGENTS.md + TOOLS.md，不继承本 session 的上下文
- 串行依赖：等上一个 announce 回来后再 spawn 下一个
- 并行独立：同时 spawn 多个，等所有 announce 到齐后汇总

---

### sessions_list / sessions_history
调试用。**不要在正常流程里轮询**，等 announce 即可。

---

## Skills（本 agent）

- `gear_detection` — G1/G2/G3 档位识别
- `task_dispatch` — 拆单 + 用 sessions_spawn 派发
- `quality_check` — 二次把关
- `version_control` — 版本号/diff 组装

## 共享 Skills（agents/_shared/）

- `task-progress-manager`（用 mcporter call 更新任务树）
- `verification-before-completion`
- `loop-circuit-breaker`
- `fact-check-before-trust`
- `wal-protocol`
