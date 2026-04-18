# Skill — coverage_analysis

## 用途
评估检索结果对原 query 的覆盖度，让 Coordinator 知道是否需要扩搜或提示用户补料。

## 触发时机
`hybrid_search` 返回结果后，对结果做整体评估。

## 评估方法

### Step 1：query 子主题拆解
用 LLM 把 query 拆成 3-5 个子主题。
> 示例：
> query = "2025 年中国 AI 行业的市场规模、政策环境和主要玩家"
> 子主题 = ["市场规模", "政策环境", "主要玩家"]

### Step 2：每个子主题命中度判断
对每个子主题，检查 results 里是否有 relevance_score ≥ 0.7 的片段覆盖。

### Step 3：评级

| 命中子主题数 / 总数 | coverage_assessment |
|--------------------|---------------------|
| ≥ 80% | 高 |
| 50% – 80% | 中 |
| < 50% | 低 |

### Step 4：列出 missing_topics
未命中的子主题写入 `missing_topics`，让 Coordinator 决策：
- "中" → 可继续，但在前端提示用户
- "低" → 强烈建议扩大 search_scope 或上传更多文档

## 输出
合并到 hybrid_search 的 response payload：

```json
{
  "results": [...],
  "coverage_assessment": "中",
  "missing_topics": ["主要玩家"]
}
```

## 性能考虑
子主题拆解是一次额外 LLM call，对延迟敏感场景（如实时检索）可降级为关键词覆盖法（不调 LLM，看 query 中的名词短语在 results 里出现频次）。
