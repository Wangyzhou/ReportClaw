# Skill — content_expansion（内容扩展模式）

## 用途
保留原稿框架，在指定章节内或章节之间补充新分析/案例/数据/章节。

## 输入
- `source_doc`：原稿
- `instructions.content_expansion`：
  - `expand_sections`：要扩写的章节标题列表（如 ["第二章"]）
  - `new_topics`：要新增的主题（如 ["碳中和影响", "出海策略"]）
- 通常需要先有 Retriever 给的新资料（new_data_sources）

## 流程

```
1. structure_parser 解析原稿，得到 title_tree
2. 对 expand_sections 中的每章：
   a. 在该章末尾追加新段落
   b. 新段落必须用新 retrieval_results 支撑（带 [ref:xxx]）
   c. 新段落第一行加标记 `> [新增]`
3. 对 new_topics 中的每个主题：
   a. 决定插入位置：
      - 同主题已有相关章节 → 该章末尾追加子节
      - 完全新主题 → 在最相关的一级章节后追加新章节
   b. 用 LLM 根据 new_data_sources 写新章节
   c. 章节标题层级与上下文一致
4. 原有内容一字不改
5. 调 diff_generator 生成 diff
```

## 新增内容标注

每个新段落（含新章节标题下的所有段落）开头加：

```markdown
> [新增]
2026 年起，AI 数据中心的电力消耗占比迅速攀升 [ref:doc_009_p3_1]...
```

新章节标题：

```markdown
## 1.3 [新增] 碳中和影响
```

前端解析 `[新增]` 标记 → 在 diff 视图中用绿色高亮区分。

---

## LLM Prompt 模板（扩写章节末尾）

```
任务：在原章节末尾追加新段落，不改原有内容。

原章节标题：{section.title}（level={section.level}）
原章节最后一段：
{section.last_paragraph}

要追加的主题：{expand_topic}

可用的新资料：
{for chunk in retrieval_results}
[chunk_id={chunk.chunk_id}]
{chunk.content}
{endfor}

要求：
1. 在原章节结尾追加 1-3 段（视资料量而定）
2. 每段开头必须加 `> [新增]` 标记
3. 每段至少 1 个 [ref:xxx]，引用来自上述 retrieval_results
4. 与原章节最后一段承接自然（"此外"、"值得关注的是"等过渡词）
5. 不改写原章节任何内容
6. 不引入 retrieval_results 之外的信息

输出格式：
> [新增]
{新段落1}

> [新增]
{新段落2}（如有）
```

## LLM Prompt 模板（新增整章）

```
任务：在报告中新增一章，讨论 {new_topic}。

报告现有章节：
{for s in existing_sections}
- {s.title} (level={s.level})
{endfor}

建议插入位置：{suggested_position}（由 structure_parser 判断）
新章节标题：{new_topic} （带 [新增] 标记）
目标长度：{target_words} 字

可用的资料：
{for chunk in retrieval_results}
[chunk_id={chunk.chunk_id}]
{chunk.content}
{endfor}

要求：
1. 章节标题：`## X.Y [新增] {new_topic}`（level 与同级章节一致）
2. 章节开头一段点题
3. 每段都必须带 `> [新增]` 前缀
4. 每段至少 1 个 [ref:xxx]
5. 与前后章节在逻辑上能自然衔接（如果后面还有章节）
6. 长度 {target_words} ± 20%
```

## Few-Shot 示例

### 示例 1：章节末追加

**原章节** "1.2 市场规模" 最后一段：
```
2025 年中国 AI 市场规模达 3200 亿美元 [ref:doc_001_p15_3]，较 2023 年翻倍。
```

**expand_topic**：`碳中和影响`
**retrieval_results**：
```
[chunk_id=doc_009_p3_1]
AI 数据中心 2025 年全国电力消耗占比达 3.8%，较 2023 年的 1.5% 翻倍...
```

**✅ 正确输出**：
```
2025 年中国 AI 市场规模达 3200 亿美元 [ref:doc_001_p15_3]，较 2023 年翻倍。

> [新增]
规模扩张的背后是电力消耗的同步攀升。2025 年 AI 数据中心全国电力消耗占比达 3.8% [ref:doc_009_p3_1]，较 2023 年的 1.5% 翻倍，碳排放成为行业不得不面对的议题。
```

### 示例 2：反例 — 改动原内容

**错误输出**（越界）：
```
2025 年中国 AI 市场规模达 3200 亿美元 [ref:doc_001_p15_3]，较 2023 年**爆发式增长**翻倍。  ← ❌ 改了原文

> [新增]
...
```

→ 只能追加，不能改动一个字的原内容。

## Rules

1. **不改原内容**：原有段落、标题、引用一字不动
2. **新内容必带引用**：每个新增段落至少 1 个 [ref:xxx]，引用来自 new_data_sources
3. **标记必须显式**：所有新增内容都加 `[新增]`，否则 diff 视图分不出
4. **新增章节层级合理**：新增的子章节层级 = 父章节 + 1，不要跳级
5. **不要全文铺新内容**：扩展是局部行为，整篇都改 = 应该用 from_outline 重写

## 输出补充字段
```json
{
  "changes_summary": {
    "mode": "content_expansion",
    "expanded_sections": ["1.3", "2.4"],
    "new_sections": ["3.5 出海策略"],
    "new_paragraphs_count": 8,
    "new_words": 1200,
    "new_content_marked": true
  }
}
```

## 反例
- ❌ 扩展时顺手修改了原稿一段措辞（越界，应该用 perspective_shift）
- ❌ 新增内容不加 [新增] 标记
- ❌ 扩展导致原章节顺序变化（如把"3.5 出海策略"插到了"3.1"之前但没在用户确认下）
