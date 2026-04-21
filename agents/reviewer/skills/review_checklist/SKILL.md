---
name: review_checklist
description: "Reviewer 的总指挥 skill，按顺序跑 6 项检查并汇总结果。"
---

# Skill — review_checklist

## 用途
Reviewer 的总指挥 skill，按顺序跑 6 项检查并汇总结果。

## 流程

```
对 payload.checks 中每一项（按下表顺序）：
  执行对应检查 → 收集 issues
  
汇总 issues + 计算 scores → 给 verdict → 返回
```

## 6 项检查执行细节

### 1. citation_validity（引用真实性）
- 提取报告中所有 `[ref:xxx]` chunk_id
- 通过 Coordinator → Retriever 反查每个 chunk_id 是否在 KB 中存在
- 不存在 → 一个 HIGH issue（type=citation_error）
- 详见 `citation_verification.md`

### 2. data_accuracy（数据一致性）
- 用 structure_parser 提取报告中所有数据点（数字/百分比/金额）
- 对每个数据点，取其引用的 chunk content，校验数据值是否与原文一致
- 不一致 → HIGH issue（type=data_mismatch）
- 详见 `citation_verification.md`

### 3. logic_coherence（逻辑连贯性）
- 章节间过渡：检查每章首段是否承接上一章结尾
- 内部矛盾：用 LLM 扫全文，找前后不一致的论断
- 找到 → MEDIUM issue（type=logic_break）

### 4. no_fabrication（无虚构）
- 找出所有非过渡段（type ≠ transition）且无 [ref:xxx] 的段落
- 每个 → HIGH issue（type=fabrication，severity 视段落重要性）
- 例外：纯总结性段落（章节末"综上所述"开头）可豁免

### 5. format_compliance（格式规范）
- 标题层级是否乱跳（# → ### 跳级）
- `[ref:xxx]` 格式是否合法：chunk_id 必须是 **32 位十六进制字符串**（正则 `^[0-9a-f]{32}$`），如 `d78435d142bd5cf6704da62c778795c5`；旧格式 `doc_*_p*_*` 视为非法
- markdown 是否能正常渲染
- 不合规 → LOW issue（type=format）

### 6. coverage（覆盖度）
- 详见 `coverage_scoring.md`
- 覆盖度 < 0.7 → MEDIUM issue（type=coverage）

## scores 计算

```python
quality_score = 1.0 - (HIGH_count * 0.15 + MEDIUM_count * 0.05 + LOW_count * 0.01)
quality_score = max(0.0, min(1.0, quality_score))

citation_accuracy = (total_citations - invalid_citations) / total_citations

coverage_score = covered_outline_items / total_outline_items
```

## 输出
按 soul.md Output Format 返回。issues 按 severity 倒序排列（HIGH 在前）。
