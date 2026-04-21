---
name: diff_generator
description: "对比改写前后的 markdown，生成 unified diff，前端渲染'修订视图'。这是评分项'对比展示与版本管理 15%'的核心展示点。"
---

# Skill — diff_generator

## 用途
对比改写前后的 markdown，生成 unified diff，前端渲染"修订视图"。这是评分项"对比展示与版本管理 15%"的核心展示点。

## 输入
- `original_markdown`：原稿
- `rewritten_markdown`：改写后

## 实现

用 Python 标准库 `difflib.unified_diff`：

```python
import difflib

def gen_diff(original: str, rewritten: str, context_lines: int = 3) -> str:
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        rewritten.splitlines(keepends=True),
        fromfile="原稿",
        tofile="改写稿",
        n=context_lines,
    )
    return "".join(diff)
```

## 输出格式

```json
{
  "format": "unified",
  "context_lines": 3,
  "content": "--- 原稿\n+++ 改写稿\n@@ -10,3 +10,3 @@\n-2024年市场规模3000亿\n+2025年市场规模3200亿 [ref:doc_001_p15_3]\n",
  "stats": {
    "added_lines": 12,
    "removed_lines": 8,
    "modified_hunks": 5
  }
}
```

## 前端渲染建议（不是本 skill 责任，给前端参考）
- `+` 行 → 绿色背景
- `-` 行 → 红色删除线
- `[新增]` 标记的段落 → 额外加 emoji 或徽章
- 引用变化 `[ref:old] → [ref:new]` → 单独一栏列出

## 进阶（v2 优化项）
- 段落级 diff（按 paragraph_id 对齐）替代行级 diff，对中文报告更友好
- 数据点 diff 单独一栏（"市场规模：2500亿 → 3200亿"）
- v1.0 先用 unified diff 跑通，v2 再优化

## Rules
- 不修改 markdown 内容，只做对比
- 如果原稿 = 改写稿（极端 case），返回空 diff + warning
