---
name: fact-check-before-trust
description: 事实核查。verification 查"任务做了"，本 skill 查"事实对了"——防止数字/日期/实体虚构。
---

# fact-check-before-trust

> Reviewer 的金牌 skill。对应 T5 评分里"事实性错误检测"核心能力。

## 何时触发

Reviewer 审查任何报告都必跑。其他 Agent 在返回带"具体事实陈述"的输出时也应跑。

## 检查范围

遇到以下内容必须核查：

- **数字/金额**：价格、规模、百分比、统计数据
- **日期/时间**：发布日期、截止日期、事件时间
- **命名实体**：人名、公司名、产品名、法规名
- **因果/超级称**："X 导致 Y"、"最大的"、"唯一的"、"首次"

**跳过**：纯论述段落、过渡句、概括性陈述。

## 三步协议

### 第一步：提取所有 claim

逐一列出报告里的事实主张：
```
claim_1: 2025 年 AI 市场规模达 3200 亿美元
claim_2: 根据工信部 2024 年 3 月发布的《AI 发展规划》...
claim_3: 生成式 AI 渗透率从 2022 年 3% 增至 2024 年 31%
```

### 第二步：给每个 claim 打置信度

| 置信度 | 条件 |
|-------|------|
| **高** | 段落后面直接跟 `[ref:chunk_id]`，且 claim 在 chunk content 里能字面找到 |
| **中** | 段落有 `[ref:chunk_id]`，但需要推理才能对应 |
| **低** | 没有 `[ref:]` 标注，或引用的 chunk 里找不到该 claim |

### 第三步：低/中 置信度必须逐个回查

对低/中置信度 claim：
1. 取其 `[ref:chunk_id]`（如果有）
2. 用 Retriever 的 chunk 反查接口取 chunk content
3. 字面比对：claim 描述 vs chunk 原文
4. 不符 → 生成 HIGH 级 issue

## 输出格式

```json
{
  "fact_check_results": [
    {
      "claim": "2025 年 AI 市场规模达 3200 亿美元",
      "confidence": "高",
      "verified": true,
      "evidence_chunk_id": "doc_001_p15_3"
    },
    {
      "claim": "生成式 AI 渗透率从 2022 年 3% 增至 2024 年 31%",
      "confidence": "低",
      "verified": false,
      "reason": "chunk doc_001_p22_4 原文为 '从 3% 增至 18%'，与报告陈述的 31% 不符",
      "severity": "HIGH",
      "suggested_fix": "改为 18%，或删除此条陈述"
    }
  ]
}
```

## 为什么重要

T5 评分里"事实性错误检测"是 Reviewer 25% 权重的关键。一个明显的数据虚构错误（例如把 ¥716 写成 ¥70000）能在 verification 里通过（任务做完了），但 fact-check 能抓住。

## 谁用

**Reviewer 必用**。Writer/Rewriter 在返回前也应该用一遍自查（避免把错送到 Reviewer 再被打回，走冤枉路）。
