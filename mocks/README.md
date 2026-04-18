# Mocks — ReportClaw Agent 验证数据

> ⚠️ **架构演示用数据 — 非真实数据**
>
> 所有具体数字（如"2025 年中国 AI 市场 3200 亿美元"、"OpenAI 估值 3000 亿美元"、
> 公司名、报告名、chunk_id 等）都是**手工构造**的 schema 演示数据，
> **未经 fact-check**，**不可作为真实信息引用**。
>
> 用途限定在：
> 1. 验证 Agent skill 的 schema 兼容性（不依赖 RAGFlow，纯本地跑）
> 2. Demo/答辩时展示流程（配合免责声明使用）
> 3. 给王亚洲参考 response 格式
>
> 真实跑起来后，所有数据必须来自 RAGFlow 真实知识库，由 Retriever 实际检索返回。

---

## 文件清单

| 文件 | 用途 |
|------|------|
| `retriever-response-high-coverage.json` | **高覆盖** Retriever response：用户查 2025 年中国生成式 AI，6 条高相关 chunks |
| `retriever-response-low-coverage.json` | **低覆盖** Retriever response：查东南亚 AI 监管，只有 1 条，coverage=低，触发 G2→G3 升级 |
| `user-source-draft.md` | 用户上传的 2024 年原稿，用于演示 Rewriter 4 模式 |
| `writer-expected-output.md` | Writer 基于 high-coverage 应产出的 2025 年新报告 |
| `rewriter-data-update-expected.md` | Rewriter `data_update` 模式期望输出（原稿 + 新数据 → 2025 版保持原结构） |
| `reviewer-sample-issues.json` | Reviewer 审查一份带错报告的典型 response（2 HIGH + 1 LOW） |

---

## 怎么用

### 验证 Writer
```python
# 伪代码
mock_retrieval = load_json("retriever-response-high-coverage.json")
writer_output = writer.section_writing(
    outline=auto_gen_outline(mock_retrieval),
    retrieval_results=mock_retrieval["results"],
    constraints={"max_length": 2500, "language": "zh-CN"}
)
# 对比 writer-expected-output.md
diff(writer_output, expected)
```

### 验证 Rewriter (data_update)
```python
source = load_md("user-source-draft.md")
new_data = load_json("retriever-response-high-coverage.json")
rewritten = rewriter.data_update(source, new_data["results"])
# 对比 rewriter-data-update-expected.md
```

### 验证 Reviewer 的回环
```python
# 给 Reviewer 一份故意带错的报告
broken_report = introduce_errors(writer_expected_output)
issues = reviewer.review(broken_report, retrieval_results)
assert issues["verdict"] == "needs_revision"
assert len([i for i in issues["issues"] if i["severity"] == "HIGH"]) >= 2
# 对比 reviewer-sample-issues.json 的结构
```

### 验证 Coordinator 的 G2→G3 升级
```python
# 喂低覆盖 retriever response，Coordinator 应该自动升级 G3
mock_low = load_json("retriever-response-low-coverage.json")
assert mock_low["coverage_assessment"] == "低"
# 触发 coordinator.gear_detection 重新判档
new_gear = coordinator.re_evaluate_gear(current="G2", trigger=mock_low)
assert new_gear == "G3"
```

---

## 为什么值得维护这套 mock

1. **跑通闭环不等 RAGFlow** — 王亚洲搭 RAGFlow 期间，我们可以先用 mock 把 Agent 跑通
2. **回归测试** — 以后改 skill，跑一遍 mock 验证没有打破期望行为
3. **答辩材料** — 固定输入 → 固定输出，演示现场不会翻车

---

## Mock 数据的真实性

所有数据**均为手工编造**，用于架构演示。真实上线时：
- Retriever 返回的 chunks 来自 RAGFlow（或晴天 MCP）的实际检索结果
- `doc_*` 的 doc_id 由王亚洲的入库管线分配
- `coverage_assessment` 由 Retriever Agent 基于实际 top_k 命中率计算
