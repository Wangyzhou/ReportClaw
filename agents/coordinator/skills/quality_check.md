# Skill — quality_check

## 用途
最终交付前的"门禁"，独立于 Reviewer Agent（Reviewer 是内容审查，本 skill 是协议+完整性审查）。

## 触发时机
Coordinator 收到所有子 Agent 的 result，准备返回用户**之前**。

## 检查清单

| 项 | 必须满足 | 不满足处理 |
|---|---------|-----------|
| Reviewer verdict | `pass` 或 已达 max_review_rounds | 升级给用户 |
| 引用完整性 | 报告里所有 `[ref:xxx]` 都在 Retriever 返回的 chunks 中存在 | 标注"引用失效"，让用户决定 |
| focus_ref 透传 | 每个子任务结果的 focus_ref = 用户请求的 focus_ref | 修正后再交付 |
| 字段完整性 | deliverable.content_markdown 非空（除 search_knowledge 外） | status=failed |
| 版本号 | 已分配 report_version | 调 version_control 补 |
| 长度合理 | content_markdown 在用户指定 max_length ±20% 内 | warning，不阻断 |

## 输出

```json
{
  "passed": true,
  "warnings": ["可选的非阻断警告"],
  "blocking_issues": []
}
```

`passed=false` 时，Coordinator 不能交付，必须返回 status=failed 并说明原因。
