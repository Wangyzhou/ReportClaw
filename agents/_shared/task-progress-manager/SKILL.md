---
name: task-progress-manager
description: 任务进度管理。所有 Agent 在任务开始/完成/失败时必须更新 task-progress MCP，前端中间区实时可视化。
metadata: {"openclaw": {"always": true}}
---

# task-progress-manager

> **每次发起任务必须提前规划任务树 → 同步到 task-progress MCP → 节点状态变更必须更新。**

## ⚠️ 强制触发规则

| 触发时机 | 操作 |
|---------|------|
| 任务开始前 | `create-task` 创建一级 + 子任务 |
| 子任务开始执行 | `update-task-status` = `running` |
| 子任务完成 | `update-task-status` = `completed` |
| 子任务失败 | `update-task-status` = `failed` |
| 所有子任务完成 | 一级任务 `update-task-status` = `completed` |

## 调用约定

```
mcporter call <mcp-server>.create-task \
  nodeId="<CLAW_NODE_ID>" \
  agentId="<session_status 返回的 sessionKey>" \
  taskName="<动词+对象>" \
  taskStatus="pending"
```

**参数注意**：
- `agentId` 必须用 OpenClaw `session_status` 返回的 sessionKey，不能用其他 label
- `taskName` 用中文："检索 AI 市场数据"、"写作第二章"

## 任务命名规范（沿用 HEARTBEAT.md）

- 主任务：`📋 [类型]-主题`
- 子任务：`🔍 检索 / ✍️ 写作 / 🔄 改写 / ✅ 审查 / 🎉 完成`

## 隐式调用

**这个 skill 是隐式 skill**——后台自动执行，不输出到前端。但**不可跳过**，跳过会导致前端任务树断层。

## 并发

- 多个 `update-task-status` 可并行（用 `&` + `wait`）
- `update-task-status` 与 `create-task` 可并行
- 但父任务 `completed` 必须等所有子任务 `completed` 后

## 失败恢复

- MCP 调用失败：重试 1 次，仍失败则记日志但不阻塞主流程
- Coordinator 崩溃：Session 恢复后读 SESSION-STATE.md 继续，task-progress 保持原状

---

**谁用**：Coordinator 主要用；Retriever/Writer/Rewriter/Reviewer 在子任务内部也可创建更细粒度的进度节点（可选）。
