---
name: section_writing
description: "按章节逐一生成内容，是 Writer 的核心干活 skill。"
---

# Skill — section_writing

## 用途
按章节逐一生成内容，是 Writer 的核心干活 skill。

## 流程

```
对 outline 中的每个 section：
  1. 取 section.supporting_chunks 对应的 retrieval_results
  2. 把 chunks 内容 + section.title + section.guidance 喂给 LLM
  3. 让 LLM 写一段 markdown，要求：
     - 段落开头点题
     - 数据/论断后立即跟 [ref:chunk_id]
     - 结尾承上启下（如果不是最后一章）
  4. 校验：生成内容里所有 [ref:xxx] 必须 ∈ supporting_chunks
  5. 拼接到全文
```

## Prompt 模板（喂给 LLM）

```
你是专业的报告写作员。

任务：写报告的"{section.title}"章节。
写作指引：{section.guidance}
目标长度：{target_words} 字

可用的资料片段（必须基于这些写，不要虚构）：
{for chunk in supporting_chunks}
[chunk_id={chunk.chunk_id}]
{chunk.content}
{endfor}

要求：
1. 用 markdown 格式，标题级别为 {level}
2. 每个数据/论断后必须用 [ref:chunk_id] 标注来源
3. 不引用 supporting_chunks 之外的 chunk_id
4. 语言：{constraints.language}
5. 长度控制在 {target_words} 字 ±20%

直接输出章节内容，不要前言后语。
```

## 长度分配
`target_words = constraints.max_length / outline 中一级章节数`

二级章节继承父章节长度的均分。

## 校验（写完每段后）
- 提取所有 `[ref:xxx]` → 必须 ∈ supporting_chunks
- 不符合的引用：去掉，并记到 stats.uncited_paragraphs +1
- citation_count == 0 的段落：警告（除过渡段外）

## 输出
单个 section 的：
```json
{
  "title": "...",
  "content": "markdown 段落",
  "citations": ["doc_001_p15_3", "doc_001_p16_0"]
}
```
