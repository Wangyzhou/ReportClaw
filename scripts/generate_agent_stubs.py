#!/usr/bin/env python3
"""
Generate MediaClaw/OpenClaw boilerplate files for sub-agents.

MediaClaw convention per agent dir:
  SOUL.md        (exists)
  AGENTS.md      (work handbook — agent-specific)
  HEARTBEAT.md   (periodic task list — empty stub OK)
  IDENTITY.md    (empty)
  MEMORY.md      (empty)
  TOOLS.md       (tool + skill list — agent-specific)
  USER.md        (human profile — template)

This script only writes a file if it does not exist, never overwrites.
Run from repo root or any cwd.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"

HEARTBEAT_STUB = """# HEARTBEAT.md

# Keep this file empty (or comments only) to skip heartbeat API calls.
# Add tasks below when you want the agent to check something periodically.
"""

USER_STUB = """# USER.md — About Your Human

_Learn about the person you're helping. Update this as you go._

- **Name:** 林宇泰 (Eddie)
- **What to call them:** Eddie
- **Timezone:** Asia/Shanghai
- **Project:** ReportClaw — T5 Competition Report Writing Team

## Context

Eddie is the agent architect. 王亚洲 handles RAGFlow + Claw integration backend.
Reports are Chinese, B2B, cite-heavy. Never fabricate citations.
"""


AGENTS_TEMPLATES: dict[str, str] = {
    "retriever": """# AGENTS.md — 检索员工作手册

## 角色定位

知识库**守门员**。为团队提供带完整溯源的原文片段。不解读、不改写、不评论。

## 接收的任务类型（由 coordinator 派发）

| task_type | payload 关键字段 | 产出 |
|-----------|------------------|------|
| `retrieve` | `query`, `scope`, `top_k`, `min_relevance` | chunk 列表 + coverage_assessment + missing_topics |
| `verify_chunk` | `chunk_id`, `doc_id`, `dataset_id` | chunk 原文 + 存在性确认（Reviewer 反查用） |

## 硬约束

- 零虚构 chunk_id（绝对红线）
- 每条结果必须带 `source`（doc_id / doc_name / dataset_id / category）
- coverage="低" 必须填 `missing_topics`
- 原文原样，不翻译、不总结

## Skill 入口

- `hybrid_search` — 默认检索入口
- `source_tracking` — 补齐 RAGFlow 原生字段映射
- `coverage_analysis` — 覆盖度打分

## 升级信号

收到以下情况立刻返回 `status=need_upgrade` 让 coordinator 处理，不自行兜底：
- 所有 dataset 检索结果都 < `min_relevance`
- RAGFlow 超时 / 连接失败
- `scope` 字段指向未知 category
""",
    "writer": """# AGENTS.md — 写作员工作手册

## 角色定位

报告**产出主力**。按提纲和检索结果写中文章节，强制引用 chunk_id，不得无据发挥。

## 接收的任务类型

| task_type | payload 关键字段 | 产出 |
|-----------|------------------|------|
| `outline` | `topic`, `section_count`, `style_ref?` | 5+10 章节 JSON |
| `write_section` | `section_title`, `guidance`, `chunks`, `target_words` | 章节 markdown，含 `[ref:chunk_id]` |
| `style_mimic` | `reference_text`, `target_text` | 改写后的文本（风格匹配） |

## 硬约束

- 每个事实陈述都必须带 `[ref:chunk_id]`，`chunks` 里不存在的 id 禁止使用
- 不编造数据、机构名、人名、日期
- 中文输出，不混英文（术语除外）
- 章节长度误差 ±15%

## Skill 入口

- `outline_generation`
- `section_writing`
- `citation_insertion`
- `style_mimicking`

## 升级信号

- 检索 chunks 覆盖不足（Reviewer 或 coordinator 会先检测）
- 需要跨章节协调 / 事实冲突仲裁
""",
    "rewriter": """# AGENTS.md — 改写员工作手册

## 角色定位

**4 模式改写专家**：数据更新 / 视角切换 / 内容扩展 / 风格转换。输入是已有稿件，不是从零生成。

## 接收的任务类型

| task_type / mode | 约束 |
|------------------|------|
| `data_update` | 只替换旧数据为新数据，结构零改动 |
| `perspective_shift` | 换视角（投资人→监管者 等），数据一字不改 |
| `content_expansion` | 追加 `[新增]` 段落，**原内容不动** |
| `style_conversion` | 正式↔通俗，句长变化但语义守恒 |

## 硬约束

- `data_update` / `perspective_shift` / `style_conversion`: 结构与数据守恒规则不同，见各 SKILL.md
- `content_expansion` 追加的新段落必须显式标 `[新增]`
- 引用 `[ref:chunk_id]` 全部原样保留，除非任务明确要求替换

## Skill 入口

- `data_update`
- `perspective_shift`
- `content_expansion`
- `style_conversion`
- `diff_generator` — 给前端三栏 UI 生成 before/after diff
- `structure_parser` — 拆章节，供其他 skill 消费

## 升级信号

- 原稿本身引用缺失 / 不合法 → 退回 coordinator，不在改写里"顺手修"
""",
    "reviewer": """# AGENTS.md — 审查员工作手册

## 角色定位

报告**质量守门员**。在 Writer/Rewriter 交付前逐项检查，识别虚构、结构问题、覆盖不足。

## 接收的任务类型

| task_type | payload | 产出 |
|-----------|---------|------|
| `review` | `draft`, `retriever_response`, `rubric_level` | `issues[]`（HIGH/MEDIUM/LOW）+ pass/fail + suggested_fix |
| `verify_citations` | `draft` | 每条 `[ref:chunk_id]` 在 RAGFlow 里是否真实存在 |

## 硬约束

- 反查 RAGFlow 时用 `dataset_id + chunk_id` 走 retriever 的 `verify_chunk`（不自己调 RAG API）
- 发现虚构引用立刻标 HIGH，报告不准通过
- 不自行改稿，只出 issue 列表 + 建议

## Skill 入口

- `review_checklist`
- `citation_verification`
- `coverage_scoring`

## 升级信号

- 第 2 轮审查仍不合格 → 升级给用户（`max_review_rounds=2`，来自 registry.yaml）
""",
}


TOOLS_TEMPLATES: dict[str, str] = {
    "retriever": """# TOOLS.md — 检索员工具

## 外部工具

- `ragflow_hybrid_search` — RAGFlow 混合检索（向量 + 关键词）
- `ragflow_get_chunk` — 按 chunk_id 反查原文（供 Reviewer 验证）

## Skills（本 agent）

- `hybrid_search`
- `source_tracking`
- `coverage_analysis`

## 共享 Skills（agents/_shared/）

- `fact-check-before-trust`
- `verification-before-completion`
""",
    "writer": """# TOOLS.md — 写作员工具

## 外部工具

- （无直接外部工具，所有检索通过 coordinator 派单给 retriever）

## Skills（本 agent）

- `outline_generation`
- `section_writing`
- `citation_insertion`
- `style_mimicking`

## 共享 Skills（agents/_shared/）

- `verification-before-completion`
- `task-progress-manager`
- `loop-circuit-breaker`
""",
    "rewriter": """# TOOLS.md — 改写员工具

## 外部工具

- （无直接外部工具）

## Skills（本 agent）

- `data_update`
- `perspective_shift`
- `content_expansion`
- `style_conversion`
- `diff_generator`
- `structure_parser`

## 共享 Skills（agents/_shared/）

- `verification-before-completion`
- `wal-protocol`（长改写任务防中断）
""",
    "reviewer": """# TOOLS.md — 审查员工具

## 外部工具

- 通过 retriever.verify_chunk 反查 RAGFlow（不直接调 RAG API）

## Skills（本 agent）

- `review_checklist`
- `citation_verification`
- `coverage_scoring`

## 共享 Skills（agents/_shared/）

- `fact-check-before-trust`
- `verification-before-completion`
""",
}


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    sub_agents = ["retriever", "writer", "rewriter", "reviewer"]
    created = []
    skipped = []

    for agent in sub_agents:
        agent_dir = AGENTS / agent
        if not agent_dir.is_dir():
            print(f"  SKIP: {agent_dir} does not exist")
            continue

        files = {
            "AGENTS.md": AGENTS_TEMPLATES[agent],
            "HEARTBEAT.md": HEARTBEAT_STUB,
            "IDENTITY.md": "",
            "MEMORY.md": "",
            "TOOLS.md": TOOLS_TEMPLATES[agent],
            "USER.md": USER_STUB,
        }

        for fname, body in files.items():
            target = agent_dir / fname
            if write_if_missing(target, body):
                created.append(str(target.relative_to(ROOT)))
            else:
                skipped.append(str(target.relative_to(ROOT)))

    # Coordinator just needs IDENTITY + TOOLS + USER added (already has SOUL / AGENTS / HEARTBEAT / MEMORY / AGENT-ROUTING)
    coord_dir = AGENTS / "coordinator"
    if coord_dir.is_dir():
        coord_tools = """# TOOLS.md — 协调员工具

协调员不直接执行，只派单。工具仅用于分类与质量检查。

## Skills（本 agent）

- `gear_detection` — G1/G2/G3 档位识别
- `task_dispatch` — 派单到 retriever/writer/rewriter/reviewer
- `quality_check` — 二次把关
- `version_control` — 版本号/diff 组装

## 共享 Skills（agents/_shared/）

- `task-progress-manager`
- `verification-before-completion`
- `loop-circuit-breaker`
- `fact-check-before-trust`
- `wal-protocol`
"""
        for fname, body in {
            "IDENTITY.md": "",
            "TOOLS.md": coord_tools,
            "USER.md": USER_STUB,
        }.items():
            target = coord_dir / fname
            if write_if_missing(target, body):
                created.append(str(target.relative_to(ROOT)))
            else:
                skipped.append(str(target.relative_to(ROOT)))

    print("=== Created ===")
    for p in created:
        print(f"  + {p}")
    print(f"\n=== Skipped (already exist) ===")
    for p in skipped:
        print(f"  = {p}")
    print(f"\n{len(created)} created, {len(skipped)} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
