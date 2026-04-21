---
name: data_update
description: "保持原稿结构和论述完全不变，只把旧数据替换为新数据。"
---

# Skill — data_update（数据更新模式）

## 用途
保持原稿结构和论述完全不变，只把旧数据替换为新数据。

## 输入
- `source_doc`：原稿
- `instructions.data_update.new_data_sources`：新的检索结果（来自 Retriever，对应当前主题的最新数据）

## 流程

```
1. 调 structure_parser → 拿到原稿的 data_points 列表
2. 对每个 data_point：
   a. 用 LLM 在 new_data_sources 中找匹配项
      （匹配维度：context 相同/相近 + 同一指标）
   b. 找到 → 替换 value，并更新 [ref:xxx] 为新 chunk_id
   c. 找不到 → 保留原数据，记入 unmatched_data_points
3. 拼回 markdown，结构、段落顺序、句式完全不变
4. 调 diff_generator 生成 diff
```

## LLM Prompt 模板（核心）

```
任务：保持段落结构完全不变，只把数据点替换为 new_data_sources 里的最新值。

原段落：
{paragraph.text}

原数据点标记：
{for dp in paragraph.data_points}
- id={dp.id} | context="{dp.context}" | value="{dp.value}" | ref={dp.chunk_id}
{endfor}

可用的新数据：
{for chunk in new_data_sources}
[chunk_id={chunk.chunk_id}]
{chunk.content}
{endfor}

要求：
1. 对每个原数据点，在 new_data_sources 中找 context 相同或相近、同一指标的新数据
2. 找到 → 把原 value 替换为新 value，把原 [ref:xxx] 替换为新 chunk_id
3. 找不到 → 保留原 value 和 [ref:xxx]，并在段末追加标记 `<!-- unmatched:dp_id -->`
4. 除数据外，句子其他部分一字不改（时间词跟着数据变可以：2024→2025）
5. 不新增段落、不新增论述、不改标题

只输出改写后的段落，不要解释。
```

## Few-Shot 示例

### 示例 1：单数据点替换

**输入原段落**：
```
根据统计，2024年AI市场规模达到 2500亿美元 [ref:old_doc_p1_2]，同比增长 18%。
```

**data_points**：
- `dp_001` | context="AI市场规模" | value="2500亿美元" | ref=`old_doc_p1_2`
- `dp_002` | context="同比增长率" | value="18%" | ref=`old_doc_p1_2`

**new_data_sources**：
```
[chunk_id=doc_001_p15_3]
2025年中国AI市场规模达到3200亿美元，同比增长 28%，为历年最高...
```

**✅ 正确输出**：
```
根据统计，2025年AI市场规模达到 3200亿美元 [ref:doc_001_p15_3]，同比增长 28%。
```

### 示例 2：部分匹配，部分保留

**输入原段落**：
```
生成式 AI 渗透率从 2022 年的 3% 增至 2024 年的 18% [ref:old_doc_p3_5]，
其中 C 端用户数突破 2 亿 [ref:old_doc_p3_6]。
```

**new_data_sources** 只包含渗透率的新数据，没有 C 端用户数：
```
[chunk_id=doc_002_p8_1]
生成式 AI 渗透率 2025 年已达 31%...
```

**✅ 正确输出**：
```
生成式 AI 渗透率从 2022 年的 3% 增至 2025 年的 31% [ref:doc_002_p8_1]，
其中 C 端用户数突破 2 亿 [ref:old_doc_p3_6]。<!-- unmatched:dp_003 -->
```

### 示例 3：反例 — 越界修改

**错误输出**：
```
2025年 AI 市场规模达到 3200 亿美元 [ref:doc_001_p15_3]，增速迅猛，
预计未来三年内保持 30% 以上增长速度。  ← ❌ 这是新论述，越界了
```

**正确**：只替换数据，不加预测。预测是 content_expansion 的事。

---

## 自检（返回前必跑）

```python
# 伪代码
assert structure_unchanged(original, rewritten)          # 段落数、标题树一致
assert all_old_data_replaced_or_marked(data_points)      # 每个 dp 要么替换要么 unmatched
assert no_new_sentences(original, rewritten)             # 句子数 ≤ 原句子数（允许 -1 是可以的，但不允许 +）
assert all_refs_valid(rewritten, new_data_sources + kept_refs)
```

## Rules

1. **结构不动**：标题、段落数、句子顺序一字不改
2. **句式微调可以**：`2024年... 2500亿` → `2025年... 3200亿`，时间词跟着改是允许的
3. **新数据必须有 [ref:xxx]**：替换后引用必须更新为新 chunk_id
4. **找不到就不改**：宁可留旧数据 + warning，也不要瞎编
5. **unmatched 必须报告**：返回 changes_summary 时列出未匹配的 data_point id

## 输出补充字段
```json
{
  "changes_summary": {
    "mode": "data_update",
    "matched_data_points": 15,
    "unmatched_data_points": ["dp_007", "dp_011"],
    "data_replacements": [
      { "old": "2500亿美元 [ref:old_doc_p1_2]", "new": "3200亿美元 [ref:doc_001_p15_3]" }
    ]
  }
}
```

## 反例
- ❌ 顺手把"AI 行业"改成"人工智能产业"（这是风格转换，不是数据更新）
- ❌ 因为新数据更详细，多加一段分析（这是内容扩展）
- ❌ unmatched 时编一个差不多的数（虚构 = Reviewer 直接打回）
