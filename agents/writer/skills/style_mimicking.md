# Skill — style_mimicking

## 用途
mode=`mimic` 时，分析参考报告的写作风格，并应用到当前主题。

## 输入
- `style_reference.doc_id`：参考报告（必须已在知识库中）
- `style_reference.aspects`：要学习的维度，子集自 ["tone", "structure", "citation_style"]

## 学习的维度

### tone（语气）
分析参考报告：
- 句长分布（短句多 vs 长句多）
- 形容词密度
- 第几人称（无人称 / 我们 / 用户视角）
- 正式度（学术 / 商业 / 通俗）

输出 tone profile：
```json
{ "avg_sentence_length": 28, "formality": "formal_business", "voice": "impersonal" }
```

### structure（章节结构）
分析参考报告的：
- 章节层级深度（一般 2 级 vs 3 级）
- 每章首段是否点题
- 是否有摘要 / 结论章节
- 列表 vs 段落比例

### citation_style（引用风格）
- 引用密度（每 N 字一处引用）
- 引用位置（段中 vs 段末）
- 是否有"集中引用段"（多 ref 连用）

## LLM Prompt 模板（风格学习阶段）

```
任务：分析以下参考报告的写作风格，提取 style profile。

参考报告片段（前 3000 字）：
{ref_doc.text[:3000]}

请从以下 3 个维度分析并输出 JSON：

1. tone（语气）
   - avg_sentence_length: 平均句长（字数）
   - formality: "formal_academic" | "formal_business" | "popular" | "journalistic"
   - voice: "impersonal" | "first_person_plural" | "second_person"
   - adjective_density: "low" | "medium" | "high"

2. structure（章节结构）
   - typical_depth: 标题层级深度（2 或 3）
   - opens_with_summary: 每章首段是否点题（true/false）
   - has_executive_summary: 是否有摘要章（true/false）
   - list_ratio: 列表占比（0-1）

3. citation_style（引用风格）
   - density: 平均每多少字一处引用
   - position: "inline_mid" | "inline_end" | "clustered"
   - format: 引用格式样例（如 "[ref:xxx]" / "（来源：X）"）

只输出 JSON，不要解释。
```

## 应用阶段：profile → section_writing 的额外约束

学到的 profile 自动拼接到 `section_writing` prompt 的尾部：

```
风格要求（仿照参考报告）：
- 平均句长约 {avg_sentence_length} 字
- 正式度：{formality}
- 语气：{voice}（如 impersonal 则避免"我们"/"你"；如 first_person_plural 可用"我们"）
- 引用密度：每 {density} 字至少 1 处 [ref:xxx]
- 章节首段是否点题：{opens_with_summary}
- 列表占比参考：{list_ratio}
```

## Few-Shot 示例

### 示例 1：学术论文风 profile

**参考报告风格**（段落样例）：
```
基于 2025 年全国 AI 应用普查数据（N=12,450 企业），本研究发现
生成式 AI 技术渗透率呈现显著的行业异质性特征（F=8.23, p<0.001）。
在高渗透行业（渗透率>50%），其技术采纳路径以"试点-扩展"模式为主...
```

**✅ 正确 profile 输出**：
```json
{
  "tone": {
    "avg_sentence_length": 42,
    "formality": "formal_academic",
    "voice": "impersonal",
    "adjective_density": "low"
  },
  "structure": {
    "typical_depth": 3,
    "opens_with_summary": true,
    "has_executive_summary": true,
    "list_ratio": 0.1
  },
  "citation_style": {
    "density": 60,
    "position": "inline_mid",
    "format": "[ref:xxx]"
  }
}
```

### 示例 2：商业报告风 profile

**参考段落**：
```
2025 年 AI 市场跑出一条陡峭的曲线：规模 3200 亿美元 [ref:doc_001]，
同比增 28%。三个信号特别值得关注：
- 渗透率破 30%，C 端用户突破 4.5 亿
- 头部集中度上升，前 5 厂商占 62% 份额
- 政策明显加码，网信办 3 月出台管理办法
```

**✅ profile**：
```json
{
  "tone": {
    "avg_sentence_length": 24,
    "formality": "formal_business",
    "voice": "impersonal",
    "adjective_density": "medium"
  },
  "structure": {
    "typical_depth": 2,
    "opens_with_summary": true,
    "has_executive_summary": true,
    "list_ratio": 0.35
  },
  "citation_style": {
    "density": 80,
    "position": "inline_end",
    "format": "[ref:xxx]"
  }
}
```

## Rules
- **只学风格，不抄内容**：参考报告的 chunks 不能直接搬到新报告里
- **引用 chunk_id 来源不变**：仿写的报告引用的是当前 query 的 retrieval_results，不是参考报告
- 如果参考报告与当前主题完全无关（领域差太远），降级用默认风格 + warning
