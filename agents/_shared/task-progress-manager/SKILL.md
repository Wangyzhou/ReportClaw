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

---

## MCP 工具

通过 `mcporter call task-progress-mcp.<tool>` 调用。

### create-task

**mcporter 调用格式：**
```
mcporter call task-progress-mcp.create-task \
  nodeId="<唯一节点ID>" \
  agentId="<session_status 返回的 sessionKey>" \
  taskName="<动词+对象>" \
  taskStatus="pending" \
  parentId="<父节点ID>"
```

**参数说明：**
- `nodeId`：全局唯一，建议格式 `<session_prefix>-<序号>`，如 `coord-1`、`ret-2`
- `agentId`：必须用 OpenClaw `session_status` 返回的 sessionKey
- `taskName`：中文，动词+对象，如 `检索 AI 市场数据`、`写作第二章`
- `taskStatus`：初始固定传 `pending`
- `parentId`：可选，父节点的 `nodeId`；Coordinator 创建主任务时不传，子 Agent 创建子任务时传入主任务的 nodeId

**返回结构：**
```json
{
  "nodeId": "coord-1",
  "agentId": "agent::main:main",
  "taskName": "检索 AI 市场数据",
  "taskStatus": "pending",
  "createdAt": 1713700000000,
  "updatedAt": 1713700000000
}
```

---

### update-task-status

**mcporter 调用格式：**
```
mcporter call task-progress-mcp.update-task-status \
  nodeId="<唯一节点ID>" \
  agentId="<sessionKey>" \
  taskStatus="running|completed|failed"
```

**参数说明：**
- `nodeId`：必须与 `create-task` 时一致
- `taskStatus`：`running` / `completed` / `failed`

**返回结构：**
```json
{
  "nodeId": "coord-1",
  "agentId": "agent::main:main",
  "taskName": "检索 AI 市场数据",
  "taskStatus": "completed",
  "createdAt": 1713700000000,
  "updatedAt": 1713700030000
}
```

---

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
