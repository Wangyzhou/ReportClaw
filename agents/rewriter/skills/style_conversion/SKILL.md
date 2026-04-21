---
name: style_conversion
description: "保留所有数据、结构、引用，只改表达风格（正式↔通俗、中↔英、长句↔短句等）。"
---

# Skill — style_conversion（风格转换模式）

## 用途
保留所有数据、结构、引用，只改表达风格（正式↔通俗、中↔英、长句↔短句等）。

## 输入
- `source_doc`：原稿
- `instructions.style_conversion`：
  - `from_style` / `to_style`：如 "正式书面" → "通俗易懂"
  - `from_lang` / `to_lang`：如 "zh-CN" → "en-US"

## 风格预设

| style 关键词 | 含义 |
|-------------|------|
| `formal_academic` | 学术论文风，长句多，被动语态，术语密集 |
| `formal_business` | 商业报告风，结构清晰，数据导向 |
| `popular` | 通俗易懂，短句，比喻，少术语 |
| `journalistic` | 媒体新闻风，导语+背景+发展+反应 |
| `executive_summary` | 高管摘要，要点提炼，无废话 |

## 流程

```
1. structure_parser 解析原稿
2. 逐段重写（按段落，不按章节）：
   - 数据值不变，[ref:xxx] 不变
   - 句式按 to_style 重组
   - 词汇按 to_lang 翻译（如果跨语言）
3. 标题翻译/转换：
   - 跨语言时翻译标题
   - 同语言换风格时，标题措辞可调（"行业概览" → "行业怎么了"）
4. 章节结构、引用一律保留
```

## 跨语言注意

| 场景 | 处理 |
|------|------|
| 中→英 | 中文专有名词保留拼音/英译，加括号原文（如 "新质生产力 (xinzhi shengchanli)"） |
| 英→中 | 英文术语首次出现保留原文（如 "大语言模型（Large Language Model, LLM）"） |
| 数字单位 | 保留原单位，必要时加括号换算（"3200 亿美元（约 23 万亿人民币）"） |
| 引用格式 | [ref:xxx] 不翻译 |

---

## LLM Prompt 模板

```
任务：改变段落的写作风格，从 {from_style}（{from_lang}）→ {to_style}（{to_lang}）。

原段落：
{paragraph.text}

段落中必须保留的数据点（一字不改）：
{for dp in paragraph.data_points}
- "{dp.value}"
{endfor}

段落中必须保留的引用（一个不少）：
{for r in paragraph.citations}
- {r}
{endfor}

风格定义：
- from_style={from_style}：{from_style_description}
- to_style={to_style}：{to_style_description}

要求：
1. 数据值一字不改
2. 所有 [ref:xxx] 保留（位置可微调不可删除）
3. 按 to_style 重组句式/用词
4. 跨语言（{from_lang}→{to_lang}）时翻译文本但保留引用原格式
5. 不增删事实点

只输出改写后的段落。
```

## Few-Shot 示例

### 示例 1：正式商业 → 通俗易懂（同语言）

**from_style**: formal_business / **to_style**: popular / 同为 zh-CN

**原段落**：
```
2025 年中国 AI 市场规模达 3200 亿美元 [ref:doc_001_p15_3]，
同比增长 28%，渗透率突破 31% [ref:doc_002_p8_1]。
```

**✅ 正确改写**：
```
2025 年，中国 AI 市场做到了 3200 亿美元 [ref:doc_001_p15_3]——
一年就多涨了 28%，而且已经有 31% 的人在用 [ref:doc_002_p8_1]。
```

→ 数据一字不改，引用保留，措辞更口语化。

### 示例 2：中 → 英（跨语言）

**原段落**（zh-CN）：
```
生成式 AI 在教育场景渗透率达 45% [ref:doc_004_p12_2]，
但面临数据隐私与内容合规的双重挑战。
```

**✅ 正确改写**（en-US）：
```
Generative AI (生成式 AI) has reached a 45% adoption rate in
education [ref:doc_004_p12_2], but faces dual challenges of
data privacy and content compliance.
```

→ 引用原格式 `[ref:doc_004_p12_2]` **不翻译**；中文专有名词首次出现括号标注原文。

### 示例 3：反例 — 偷偷改数据

**错误改写**：
```
中国 AI 市场超过 3000 亿美元（约值）[ref:doc_001_p15_3]...  ← ❌ 精度被改
```

→ 3200 → "超过 3000（约值）" 是在改数据。Reviewer 会直接打回。

## Rules

1. **数据零改动**：所有 data_points 的 value 一字不变
2. **引用零改动**：所有 [ref:xxx] 数量、位置、chunk_id 一字不变
3. **结构零改动**：标题树层级和顺序不变（标题文本可改）
4. **不增删信息**：每段的事实点数 = 改写前
5. **风格一致**：通篇统一 to_style，不能前正式后通俗

## 输出补充字段
```json
{
  "changes_summary": {
    "mode": "style_conversion",
    "from_style": "formal_business",
    "to_style": "popular",
    "from_lang": "zh-CN",
    "to_lang": "zh-CN",
    "rewritten_paragraphs": 35,
    "preserved_data_points": 22,
    "preserved_citations": 18
  }
}
```

## 反例
- ❌ 把"3200亿美元"改成"约 3 千多亿"（数据精度被改）
- ❌ 通俗化时砍掉一段"复杂"内容（这是删改，不是风格转换）
- ❌ 跨语言时把 [ref:doc_001_p15_3] 翻译成 [ref:document_001_page_15_paragraph_3]
