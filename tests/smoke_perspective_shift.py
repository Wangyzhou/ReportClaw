#!/usr/bin/env python3
"""
Smoke test — Rewriter.perspective_shift

验证"视角调整"模式：内容/数据/引用全保留，只改表达立场。
输入：投资人视角原稿 → 输出：监管者视角改写稿
"""
import os
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


OLD_DRAFT = """## 二、行业格局

2025 年 Q1 生成式 AI 行业融资总额达 580 亿美元 [ref:doc_003_p2_1]，
龙头 OpenAI 估值突破 3000 亿美元 [ref:doc_003_p2_1]，资本热度创历史新高，
给行业带来前所未有的机会窗口。

头部 5 家厂商合计市场份额 62% [ref:doc_003_p2_1]，行业集中度较 2024 年
上升 15 个百分点，马太效应显著，利好头部玩家，投资回报率预期持续走高。"""


def build_prompt(old_draft: str, from_view: str, to_view: str, audience: str) -> str:
    return f"""任务：视角调整——把以下段落从「{from_view}」视角改为「{to_view}」视角，目标受众是「{audience}」。

原稿：
{old_draft}

## 硬约束

1. **数据一字不改**：所有数字、百分比、金额、年份保持原样
2. **引用一个不少**：所有 [ref:xxx] 保留，位置可微调但不可删除
3. **结构零改动**：标题、段落数保留
4. **论述角度从 {from_view} 改为 {to_view}**：
   - 重点关注的问题跟着变
   - 用词的价值判断跟着变（如"机会"→"风险"）
5. **不引入新事实**：不能加入原稿没有的数据或主张

直接输出改写后的 markdown，不要前言后语。
"""


def call_llm(prompt: str, tier: str = "T3") -> str:
    """perspective_shift 默认 T3（真推理），但先用 T2 验证够不够。"""
    from anthropic import Anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT.parent / ".env", override=True)
    MODEL_MAP = {
        "T1": "claude-haiku-4-5-20251001",
        "T2": "claude-sonnet-4-6",
        "T3": "claude-opus-4-7",
    }
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model=MODEL_MAP[tier], max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def extract_numbers(text: str) -> set:
    """提取关键数据点（数字+单位）"""
    pattern = r"(\d+(?:\.\d+)?\s*(?:亿美元|亿|万|%|百分点))"
    return set(re.findall(pattern, text))


def run_assertions(output: str, old_draft: str) -> list:
    results = []

    # 1) 非空
    results.append((bool(output.strip()), "有非空输出"))

    # 2) 所有数据点保留
    old_data = extract_numbers(old_draft)
    new_data = extract_numbers(output)
    missing = old_data - new_data
    results.append((len(missing) == 0, f"数据点全部保留（缺失 {missing}）"))

    # 3) 所有引用保留
    old_refs = set(re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", old_draft))
    new_refs = set(re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", output))
    missing_refs = old_refs - new_refs
    results.append((len(missing_refs) == 0, f"引用全部保留（缺失 {missing_refs}）"))

    # 4) 结构保留：原标题在输出里
    old_titles = re.findall(r"^#{1,3} .+$", old_draft, re.M)
    missing_titles = [t for t in old_titles if t.strip() not in output]
    results.append((len(missing_titles) == 0, f"原标题保留（缺失 {missing_titles[:1]}）"))

    # 5) 视角确实变了：原稿的"机会窗口"/"利好"/"马太效应"/"投资回报率"等正面词
    #    在监管视角下应该被替换。这里检查输出里没有出现至少 2 个偏乐观的词
    investor_keywords = ["机会窗口", "投资回报率", "利好"]
    still_has_optimistic = [w for w in investor_keywords if w in output]
    results.append(
        (len(still_has_optimistic) <= 1, f"投资人口吻词被改写（残留 {still_has_optimistic}）")
    )

    # 6) 引入了监管/风险语汇
    regulator_keywords = ["监管", "风险", "合规", "秩序", "稳定", "审慎"]
    has_regulator = any(w in output for w in regulator_keywords)
    results.append((has_regulator, "引入监管视角词汇"))

    return results


def main():
    prompt = build_prompt(
        OLD_DRAFT,
        from_view="投资人",
        to_view="监管者",
        audience="金融监管部门",
    )

    print("=" * 60)
    print("SMOKE TEST — Rewriter.perspective_shift (tier: T3 / Opus)")
    print("=" * 60)

    output = call_llm(prompt, tier="T3")
    print(f"\n--- LLM output ({len(output)} chars) ---\n{output}")

    print(f"\n--- Assertions ---")
    results = run_assertions(output, OLD_DRAFT)
    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    for ok, desc in results:
        print(f"  {'✅' if ok else '❌'} {desc}")
    print(f"\n--- Summary ---\n  {passed}/{total} assertions passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
