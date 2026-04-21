# TOOLS.md — 协调员工具

协调员不直接执行，只派单。工具仅用于分类与质量检查。

## Skills（本 agent）

- `gear_detection` — G1/G2/G3 档位识别
- `task_dispatch` — 派单到 retriever/writer/rewriter/reviewer
- `quality_check` — 二次把关
- `version_control` — 版本号/diff 组装

## 共享 Skills（agents/_shared/）

- `task-progress-manager`
- `verification-before-completion`
- `loop-circuit-breaker`
- `fact-check-before-trust`
- `wal-protocol`
