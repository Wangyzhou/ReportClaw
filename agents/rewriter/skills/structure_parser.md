# Skill — structure_parser

## 用途
解析原稿 markdown，提取结构化信息：标题树 / 段落 / 数据点 / 引用清单。其他改写 skill 都依赖这个产出。

## 输入
原稿 markdown 字符串。

## 输出

```json
{
  "title_tree": [
    { "level": 1, "title": "一、行业概览", "line_range": [1, 45], "children": [
        { "level": 2, "title": "1.1 市场规模", "line_range": [3, 20] }
    ]}
  ],
  "paragraphs": [
    { "id": "p_001", "section": "1.1", "line_range": [5, 8], "text": "...", "type": "data_paragraph | narrative | transition | summary" }
  ],
  "data_points": [
    {
      "id": "dp_001",
      "paragraph_id": "p_001",
      "value": "3200亿美元",
      "context": "2025年中国AI市场规模",
      "citation": "doc_001_p15_3",
      "char_offset": [12, 19]
    }
  ],
  "citations": [
    { "chunk_id": "doc_001_p15_3", "occurrences": 3, "paragraph_ids": ["p_001", "p_005"] }
  ],
  "stats": {
    "total_words": 4200,
    "total_paragraphs": 35,
    "total_citations": 18,
    "total_data_points": 22
  }
}
```

## 解析规则

### 标题树
按 markdown `#` 数量识别 level。中文章节号（一、二、三 / 1.1, 1.2）作为 title 的一部分保留。

### 段落分类
| type | 判定 |
|------|------|
| data_paragraph | 含 ≥1 个数字/百分比/金额 |
| narrative | 论述性段落，无数字 |
| transition | < 30 字、承上启下 |
| summary | 章节末"综上所述/小结"开头 |

### 数据点提取
正则 + LLM 兜底：
- 正则匹配：`\d+(\.\d+)?(%|万|亿|元|美元|倍|个|家)`
- 提取 value + 前后 15 字 context + 同段 [ref:xxx]

### 引用清单
扫描 `[ref:xxx]`，统计每个 chunk_id 出现次数和位置。

## 用途下游
- `data_update`：根据 data_points 找出"哪些数据要被替换"
- `content_expansion`：根据 title_tree 找"在哪一章后面插入新章节"
- `diff_generator`：用 paragraph 边界做 diff 对齐
