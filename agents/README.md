# T5 Agent Team

5 个 Agent 协同完成"知识库驱动报告生成"和"以稿写稿"两大核心能力。

## 目录结构

```
agents/
├── README.md            ← 本文件
├── registry.yaml        ← 部署元数据（Clawith 读取）
├── coordinator/         ← 协调员（指挥官）
│   ├── soul.md
│   └── skills/
│       ├── task_dispatch.md
│       ├── quality_check.md
│       └── version_control.md
├── retriever/           ← 检索员（对接 RAGFlow）
│   ├── soul.md
│   └── skills/
│       ├── hybrid_search.md
│       ├── source_tracking.md
│       └── coverage_analysis.md
├── writer/              ← 写作员
│   ├── soul.md
│   └── skills/
│       ├── outline_generation.md
│       ├── section_writing.md
│       ├── style_mimicking.md
│       └── citation_insertion.md
├── rewriter/            ← 改写员（4 模式）
│   ├── soul.md
│   └── skills/
│       ├── structure_parser.md
│       ├── data_update.md
│       ├── perspective_shift.md
│       ├── content_expansion.md
│       ├── style_conversion.md
│       └── diff_generator.md
└── reviewer/            ← 审查员
    ├── soul.md
    └── skills/
        ├── review_checklist.md
        ├── citation_verification.md
        └── coverage_scoring.md
```

## 设计原则

### 1. 指挥官不执行
Coordinator 只调度，**不**亲自检索/写作/改写/审查。这一原则继承自 MediaClaw 的 workspace-coordinator。

### 2. 一文件一 skill
每个能力独立 markdown 文件，便于：
- LLM 加载时按需引入（context 友好）
- 后续 Hermes 自进化时单 skill 沉淀
- 评分维度与 skill 一一对应，方便演示

### 3. soul.md = 人格 + 规则；skill.md = 具体怎么做
soul 回答 "我是谁、我做什么、我的红线"；skill 回答 "这件事怎么一步步做"。

### 4. 协议唯一
所有 Agent 间消息走 `docs/a2a-message-schema.md` 定义的 envelope，不允许私自加字段。

## 与 T5 评分维度的对应

| 评分项（权重） | 主责 Agent | 关键 skill |
|--------------|-----------|-----------|
| 知识检索准确性 25% | Retriever | hybrid_search + source_tracking |
| 报告生成质量 25% | Writer + Reviewer | section_writing + review_checklist |
| 改写质量 25% | Rewriter | data_update + perspective_shift + content_expansion + style_conversion |
| 对比展示与版本管理 15% | Coordinator + Rewriter | version_control + diff_generator |
| 系统完整性与体验 10% | 全员 + 前端 | — |

## 4/17 之后的 TODO

- [ ] 和王亚洲对齐 `docs/a2a-message-schema.md`，确认字段后冻结
- [ ] 王亚洲：搭 RAGFlow + 把 hybrid_search 接成可调用工具
- [ ] Eddie：每个 skill 加 1-2 个测试用例（输入/期望输出）
- [ ] Clawith 部署：把 registry.yaml + soul.md + skills/ 注册成 Team
- [ ] 4/18：跑通 generate_report 端到端 Demo
- [ ] 4/19：跑通 4 种 rewrite 模式
- [ ] 4/20：前端三栏 UI 对接
