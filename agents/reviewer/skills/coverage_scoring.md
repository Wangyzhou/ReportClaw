# Skill — coverage_scoring

## 用途
评估报告对用户原始需求/提纲的覆盖度，给 coverage_score。

## 触发
review_checklist 的 step 6（coverage）。

## 输入
- `report_markdown`：待审报告
- 原始 outline（从 task 上下文取，Coordinator 会透传）
- 用户原始 query（如果 mode=from_outline 之外）

## 流程

### Case A：有 outline
```
1. 提取报告的 title_tree
2. 对 outline 中每个一级/二级章节：
   - 在报告 title_tree 中查找匹配章节（按标题相似度）
   - 找到 → covered++，并检查内容是否充实（≥ 100 字）
   - 找不到 → 列入 missing_sections
3. coverage_score = covered / total_outline_items
```

### Case B：无 outline，只有 query
```
1. 用 LLM 把 query 拆成 3-5 个子主题（同 Retriever 的 coverage_analysis）
2. 对每个子主题，在报告全文中找是否有相关段落
3. coverage_score = covered_topics / total_topics
```

## 阈值

| coverage_score | 处理 |
|---------------|------|
| ≥ 0.85 | 通过，不报 issue |
| 0.7 – 0.85 | warning，不阻断 |
| < 0.7 | MEDIUM issue（type=coverage） + 列出 missing_sections / missing_topics |

## issue 格式
```json
{
  "type": "coverage",
  "location": { "section": "全文" },
  "detail": "未覆盖以下要点：[出海策略, 监管风险]",
  "severity": "MEDIUM",
  "suggested_fix": "建议补充章节 'X.X 出海策略'，引用 doc_005 系列"
}
```

## Notes
- 标题相似度用 LLM 判断（"行业概览" ≈ "市场全景"），不要纯字符串匹配
- 内容充实度的 100 字门槛是兜底，避免空标题骗过检查
