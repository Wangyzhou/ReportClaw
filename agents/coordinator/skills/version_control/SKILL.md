---
name: version_control
description: "为每次生成/改写的报告分配版本号，并维护版本树（用于评分项'对比展示与版本管理 15%'）。"
---

# Skill — version_control

## 用途
为每次生成/改写的报告分配版本号，并维护版本树（用于评分项"对比展示与版本管理 15%"）。

## 触发时机
- Writer 出初稿 → 分配 v1
- Reviewer 回环重写 → v1.1, v1.2（小版本）
- Rewriter 改写已有版本 → 在源版本基础上 +1（v2, v3...）

## 版本号规则

| 场景 | 版本号 |
|------|--------|
| 全新生成 | `v1` |
| 同一任务回环修改 | `v1.1`, `v1.2`（小版本） |
| 用户主动改写已有报告 | 源版本 +1 主版本（如 v2 → v3） |
| 用户回滚 | 不改原版本，新建 `vN.rollback_from_vM` |

## 版本元数据（持久化字段）

```json
{
  "version_id": "v3",
  "report_id": "report_xxx",
  "parent_version": "v2",
  "created_by": "rewriter | writer",
  "created_at": "ISO8601",
  "task_id": "...",
  "rewrite_mode": "data_update | null",
  "diff_against_parent": "unified diff",
  "summary": "一句话描述本版本变化"
}
```

## 输出
返回新分配的 `version_id` + 持久化记录到后端版本表。

## Notes
- 版本表的 schema 由王亚洲后端实现，本 skill 只负责调用后端 API
- diff 用 Python `difflib.unified_diff`，前端做渲染
