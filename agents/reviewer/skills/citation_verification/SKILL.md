---
name: citation_verification
description: "两件事合并："
---

# Skill — citation_verification

## 用途
两件事合并：
1. 验证报告里的每个 [ref:chunk_id] 都真实存在于知识库
2. 验证引用上下文里的数据值与原文 chunk 一致

## 触发
review_checklist 的 step 1（citation_validity）+ step 2（data_accuracy）。

## 流程

```
1. 用正则提取报告里所有 [ref:xxx] → citation_list
2. 对 citation_list 中每个 chunk_id：
   a. 通过 Coordinator → Retriever 调 RAGFlow 查这个 chunk_id 的 content
   b. 不存在 → issue(type=citation_error, severity=HIGH, suggested_fix="移除该引用或换为有效 chunk_id")
   c. 存在 → 进入 step 3
3. 数据一致性核验：
   a. 找出该 [ref:xxx] 引用所在的句子
   b. 提取句子里的数据点（数字/百分比/金额）
   c. 校验这些数据点是否在 chunk content 中出现（精确匹配 + 容忍格式差异如 "3200亿" vs "3,200 亿"）
   d. 数据点找不到对应 → issue(type=data_mismatch, severity=HIGH, suggested_fix="与原文不符，建议核对：原文为 X")
```

## 数据匹配容忍规则

| 原文 | 报告引用 | 是否一致 |
|------|---------|---------|
| 3200 亿美元 | 3,200 亿美元 | ✅ |
| 3200 亿美元 | 约 3200 亿美元 | ✅（"约"是合理修饰）|
| 3200 亿美元 | 3300 亿美元 | ❌（数据不符）|
| 28% | 28 个百分点 | ❌（百分点 ≠ 百分比）|
| 2025 年 | 2024 年 | ❌（时间不符）|
| GPT-4 | GPT-4o | ❌（产品型号不符）|

**实现**：先做字符串归一化（去逗号、去空格、统一全/半角），再精确匹配；不匹配的用 LLM 二次判断（避免"约 3200 亿"被误判）。

## 性能优化
- 同一 chunk_id 在报告中多次引用 → 只查一次 KB，cache content
- KB 查询批量：把所有 unique chunk_ids 一次性发给 Retriever，减少 round trip

## 输出
issues 列表，每条带 location（指向报告里的具体行）。

## 评分影响
`citation_accuracy = (total - invalid) / total`，直接进入 scores 字段。
