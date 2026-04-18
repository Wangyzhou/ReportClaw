---
name: loop-circuit-breaker
description: 防死循环。同一错误重试 2 次自动熔断，防 Writer↔Reviewer 回环失控。
metadata: {"openclaw": {"always": true}}
---

# loop-circuit-breaker

> OpenClaw 默认遇错就重试。但对"确定性错误"（参数缺失、类型错、知识库里没这个主题）重试也不会成功，只会烧 token。本 skill 自动识别并熔断。

## 熔断算法

每次子 Agent 返回 error 或 Reviewer 返回 needs_revision 时，Coordinator 执行：

1. 归一化签名：`(agent_name, task_type, error_type)`
2. 查历史：本轮任务内该签名出现过几次
3. 累计 ≥ 2 次 → **熔断**：不再重试，升级给用户

## 错误分类

| 类型 | 是否熔断 |
|------|---------|
| **确定性错误**（INVALID_INPUT / MISSING_FIELD / KB_NO_MATCH） | 立即熔断（1 次就停） |
| **瞬时错误**（LLM_RATE_LIMIT / TIMEOUT / NETWORK） | 重试 2 次后熔断 |
| **审查回环**（needs_revision → write → needs_revision） | 2 轮后熔断（= max_review_rounds） |

## 熔断后的动作

1. 停止当前任务树的所有派发
2. `task-progress` 所有未完成子任务标 `failed`
3. 返回给用户：
   ```
   ⚠️ 任务遇到反复失败，已熔断
   - 失败签名：Retriever × KB_NO_MATCH × 2
   - 可能原因：{分类原因}
   - 建议操作：%%换个主题%% %%扩大知识库范围%% %%改用其他模式%%
   ```
4. 写入 MEMORY.md 历史教训表（自我进化）

## 为什么重要

- 防 $10/月烧到 $80+（cron-hygiene 的教训）
- 防 Writer↔Reviewer 打乒乓
- 防 Retriever 查不到还硬扩大 scope 查

## 谁用

**Coordinator 必用**。每次收到子 Agent 返回时都检查一次签名历史。

## 与 max_review_rounds 的关系

`max_review_rounds = 2` 是专门针对审查回环的熔断。loop-circuit-breaker 是通用熔断，两者配合。

| 场景 | 熔断依据 |
|------|---------|
| Reviewer 连续 2 轮 needs_revision | max_review_rounds |
| Retriever 3 次 KB_NO_MATCH | loop-circuit-breaker |
| Writer 2 次超时 | loop-circuit-breaker |
