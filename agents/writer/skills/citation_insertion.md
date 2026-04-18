# Skill — citation_insertion

## 用途
统一所有引用标注格式 `[ref:chunk_id]`，并维护 citation_index。

## 引用格式

```
正文：根据统计，2025年中国AI市场规模达到3200亿美元 [ref:doc_001_p15_3]，同比增长 28% [ref:doc_001_p15_4]。
```

**规范**：
- 紧跟在被引用的事实/数据之后
- 在标点符号之前（中文逗号/句号前）
- 多源支撑同一论断时连写：`...达到3200亿美元 [ref:doc_001_p15_3] [ref:doc_007_p2_1]`

## 引用位置规则

| 内容类型 | 引用位置 |
|---------|---------|
| 数据点（数字、百分比、金额） | 数据后立即引用 |
| 政策条文 | 条文表述后引用 |
| 专家观点 | 观点结尾引用 |
| 转述段落 | 段末统一引用 |
| 过渡段、总结句 | 不引用 |

## citation_index 维护

每次插入引用，更新：
```json
{
  "doc_001_p15_3": {
    "used_count": 3,
    "first_section": "1.1",
    "all_sections": ["1.1", "1.2", "3.1"]
  }
}
```

## 校验（必须跑，返回前）

```python
# 伪代码，section_writing 完成后自动跑
import re

def validate_citations(report_markdown: str, retrieval_results: list) -> dict:
    """
    返回 {valid, invalid_refs, orphan_paragraphs, citation_index}
    """
    allowed_chunk_ids = {r["chunk_id"] for r in retrieval_results}
    refs = re.findall(r'\[ref:([a-zA-Z0-9_]+)\]', report_markdown)

    invalid = [r for r in refs if r not in allowed_chunk_ids]

    # 检查 orphan paragraph（含具体数据但无引用）
    paragraphs = report_markdown.split("\n\n")
    orphan = []
    for i, p in enumerate(paragraphs):
        has_number = bool(re.search(r'\d+(\.\d+)?\s*(%|亿|万|美元)', p))
        has_ref = '[ref:' in p
        # 过渡段/标题除外
        is_transition = len(p) < 40 or p.startswith('#')
        if has_number and not has_ref and not is_transition:
            orphan.append(i)

    return {
        "valid": len(invalid) == 0 and len(orphan) == 0,
        "invalid_refs": invalid,
        "orphan_paragraphs": orphan,
        "citation_index": build_index(refs),
    }
```

**校验失败处理**：
- `invalid_refs` 非空 → 返回给 Coordinator，由 Coordinator 决定：删掉该段 or 回环让 Writer 重写
- `orphan_paragraphs` 非空 → 视为 uncited，stats.uncited_paragraphs 记录

## Few-Shot 示例

### 示例 1：正确引用位置

```
✅ 根据统计，2025 年中国 AI 市场规模达到 3200 亿美元 [ref:doc_001_p15_3]，
同比增长 28% [ref:doc_001_p15_4]，渗透率达 31% [ref:doc_002_p8_1]。
```

### 示例 2：多源支撑同一论断

```
✅ 市场规模突破 3200 亿美元 [ref:doc_001_p15_3] [ref:doc_007_p2_1]。
```

### 示例 3：反例合集

```
❌ 2025 年市场规模 [ref:doc_001_p15_3] 达到 3200 亿美元。
   ← 引用不该放在数据前

❌ 根据统计，2025 年 AI 市场规模达到 3200 亿美元。[ref:doc_001_p15_3]
   ← 引用放在句号后（应在句号前）

❌ [ref:doc_001_p15_3] 根据统计，2025 年市场规模 3200 亿美元。
   ← 引用放在段首

❌ [来源：doc_001 第15页] 市场规模 3200 亿美元。
   ← 格式错误，前端无法解析

❌ 市场规模 3200 亿美元 [ref:doc_001]。
   ← 缺 page/paragraph

❌ 市场规模 3200 亿美元 [ref:doc_001_p15_3] [ref:doc_001_p15_3] [ref:doc_001_p15_3]
   ← 同 chunk 堆砌
```

## 反例（规则总结）

- ❌ `[来源：doc_001 第15页]`（前端无法解析）
- ❌ `[ref:doc_001]`（缺 page 和 paragraph）
- ❌ 引用放在段首（语义不清）
- ❌ 同一个 chunk_id 在同一段内重复 5+ 次（堆砌）
- ❌ 引用放在中文句号/逗号后（应在标点前）
