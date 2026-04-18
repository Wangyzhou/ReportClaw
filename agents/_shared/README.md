# _shared/ — 共享元能力 Skills

所有 Agent 都可以调用的元能力。

| Skill | 谁用 | 作用 |
|-------|------|------|
| `task-progress-manager` | Coordinator（主）+ 所有 Agent（可选） | 任务树可视化到 MCP，前端实时显示 |
| `verification-before-completion` | 所有 Agent | 交付前自检输出 schema 合规 + 事实对齐 |
| `fact-check-before-trust` | Reviewer（主）+ Writer/Rewriter（自查） | 数字/日期/实体的字面比对核查 |
| `loop-circuit-breaker` | Coordinator | 同错误重试 2 次自动熔断 |
| `wal-protocol` | Writer / Rewriter / Coordinator（长任务） | Write-Ahead Log，防 session 崩溃从零重来 |

## 隐式 vs 显式

- **隐式**（`openclaw.always: true`）：后台自动触发，不输出到前端
  - task-progress-manager
  - verification-before-completion
  - loop-circuit-breaker
  - wal-protocol
- **显式**：Agent 主动调用
  - fact-check-before-trust

## 关键约定

1. 所有 `mcporter` 调用前先读对应 SKILL.md
2. `agentId` 参数必须用 `session_status` 返回的 `sessionKey`
3. 隐式 skill 失败不阻塞主流程，但必须写入日志
4. 熔断触发后所有子任务必须标 `failed`，不能留 `running`
