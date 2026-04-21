---
name: outline_generation
description: "用户没给提纲时，根据主题 + Retriever 返回的 results，自动生成一个层级化提纲。"
---

# Skill — outline_generation

## 用途
用户没给提纲时，根据主题 + Retriever 返回的 results，自动生成一个层级化提纲。

## 触发时机
`write` payload 中 `outline` 字段为空，且 `mode=from_outline`。

## 输入
- `topic`：报告主题
- `retrieval_results`：Retriever 返回的 chunks
- `constraints.max_length`：用于决定提纲粒度

## 输出
```json
[
  { "level": 1, "title": "一、行业概览", "guidance": "覆盖市场规模和增长趋势", "supporting_chunks": ["d78435d142bd5cf6704da62c778795c5"] },
  { "level": 2, "title": "1.1 市场规模", "supporting_chunks": ["d78435d142bd5cf6704da62c778795c5"] },
  { "level": 2, "title": "1.2 增长趋势" },
  { "level": 1, "title": "二、政策环境", "supporting_chunks": ["b48c170e90f70af998485c1065490726"] }
]
```

## 生成规则

| 报告长度（max_length） | 一级章节数 | 二级章节数 |
|---------------------|----------|----------|
| < 2000 字 | 3-4 | 不分 |
| 2000-5000 字 | 4-6 | 每章 2-3 |
| > 5000 字 | 5-8 | 每章 3-4 |

## LLM Prompt 模板

```
任务：根据主题和检索到的资料，生成一个层级化提纲。

主题：{topic}
目标长度：{max_length} 字
语言：{language}

可用资料（chunk 清单）：
{for chunk in retrieval_results}
[chunk_id={chunk.chunk_id}]
category: {chunk.source.category}
摘要: {chunk.content[:120]}...
{endfor}

要求：
1. 一级章节数遵守下表：
   - <2000 字：3-4 章
   - 2000-5000 字：4-6 章
   - >5000 字：5-8 章
2. 每个一级章节至少分配 1-3 个 supporting chunks（必须来自上面的 chunk 清单）
3. 覆盖 retrieval_results 能支撑的全部主要 topic，不超纲
4. 章节顺序按"总→分"或"时序"组织（先概览、后细分；先现在、后未来）
5. 标题用中文数字 "一、二、三..."，二级用 "1.1 / 1.2"
6. 每个一级章节带 guidance（一句话写作提示）

输出 JSON 格式（严格对齐下面结构）：
[
  { "level": 1, "title": "一、X", "guidance": "...", "supporting_chunks": ["chunk_id_1", ...] },
  { "level": 2, "title": "1.1 Y", "supporting_chunks": [...] },
  ...
]
```

## Few-Shot 示例

**topic**: "2025 年中国生成式 AI 产业分析报告" / **max_length**: 5000

**retrieval_results**（简化，chunk_id 为 RAGFlow 原生 32 位 hex）:
- `d78435d142bd5cf6704da62c778795c5` 行业报告 "2025 AI 市场规模 3200 亿美元"
- `b48c170e90f70af998485c1065490726` 行业报告 "渗透率 31%，C 端用户 4.5 亿"
- `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6` 行业报告 "Q1 融资 580 亿美元，头部厂商集中度提升"
- `e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0` 政策法规 "网信办《生成式 AI 服务管理办法》"
- `f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6` 行业报告 "教育/医疗/金融渗透率差异"
- `c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4` 行业报告 "数据中心电力消耗 3.8%"

**✅ 正确输出**：
```json
[
  { "level": 1, "title": "一、市场概览", "guidance": "概述 2025 年整体规模+增长+用户基数", "supporting_chunks": ["d78435d142bd5cf6704da62c778795c5", "b48c170e90f70af998485c1065490726"] },
  { "level": 2, "title": "1.1 市场规模与增速", "supporting_chunks": ["d78435d142bd5cf6704da62c778795c5"] },
  { "level": 2, "title": "1.2 用户渗透", "supporting_chunks": ["b48c170e90f70af998485c1065490726"] },
  { "level": 1, "title": "二、行业格局", "guidance": "资本流向和头部集中度", "supporting_chunks": ["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"] },
  { "level": 1, "title": "三、垂直场景分化", "guidance": "教育/医疗/金融渗透差异分析", "supporting_chunks": ["f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"] },
  { "level": 1, "title": "四、政策与监管", "guidance": "网信办管理办法影响解读", "supporting_chunks": ["e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"] },
  { "level": 1, "title": "五、可持续挑战", "guidance": "能耗与碳排放问题", "supporting_chunks": ["c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4"] }
]
```

## 反例

- ❌ 提纲超过 retrieval_results 能支撑的范围（例如加"未来 5 年预测"但检索里没有预测数据）
- ❌ 一级章节 > 8 个（写不完，会被 Reviewer 打回）
- ❌ 一级章节没有 supporting_chunks（写出来就是空话）
- ❌ 标题用英文数字 "1、2、3"（违反中文规范）
