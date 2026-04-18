#!/usr/bin/env python3
"""
Smoke test — Rewriter.data_update

验证数据更新模式：旧稿 + 新 Retriever 结果 → 改写后旧数据被替换为新数据，
结构完全保留，新数据带新引用。
"""
import os
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOCK_DIR = ROOT / "mocks"


OLD_DRAFT = """# 2023 年中国生成式 AI 行业概览

## 一、市场规模与增速

2023 年中国 AI 市场规模达到 1500 亿美元 [ref:old_doc_p1_2]，同比增长 15%。
渗透率为 12% [ref:old_doc_p1_3]，仍处于早期阶段。

## 二、行业格局

头部 5 家厂商合计市场份额 40% [ref:old_doc_p2_1]，行业集中度较为分散。
Q1 融资总额为 180 亿美元 [ref:old_doc_p3_1]。"""


def build_data_update_prompt(old_draft: str, new_chunks: list) -> str:
    chunks_block = "\n\n".join(
        f"[chunk_id={c['chunk_id']}]\n{c['content']}" for c in new_chunks
    )
    return f"""任务：数据更新模式——把旧稿里的过时数据替换为新数据，其他一律不动。

## 旧稿
{old_draft}

## 新资料（Retriever 返回的最新数据）
{chunks_block}

## 硬约束
1. **结构零改动**：标题树、段落数、句式完全保留
2. **只改数据**：数字、百分比、年份跟着新数据变；叙述角度不动
3. **引用必须更新**：数据换了，后面的 [ref:xxx] 必须改为新 chunk_id（来自上面"新资料"清单）
4. **找不到对应新数据的保留原值**，不要编
5. 如果新数据里有些是旧稿没覆盖的领域，**不要插入**（那是 content_expansion 的事）

## 允许的微调
- 年份相关的时间词可跟着改（"2023 年" → "2025 年"）
- 数据单位/小数点位可四舍五入对齐原精度

直接输出改写后的 markdown，不要前言后语。
"""


def call_llm(prompt: str, tier: str = "T2") -> str:
    from anthropic import Anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT.parent / ".env", override=True)
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("❌ 缺少 ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(2)

    MODEL_MAP = {
        "T1": "claude-haiku-4-5-20251001",
        "T2": "claude-sonnet-4-6",
        "T3": "claude-opus-4-7",
    }
    client = Anthropic(api_key=key)
    msg = client.messages.create(
        model=MODEL_MAP[tier],
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def run_assertions(output: str, old_draft: str, new_chunks: list) -> list:
    results = []
    new_ids = {c["chunk_id"] for c in new_chunks}

    # 1) 非空
    results.append((bool(output.strip()), "有非空输出"))

    # 2) 结构保留：原标题的非年份骨架必须在输出里（年份允许更新）
    def strip_year(t):
        return re.sub(r"\b(19|20)\d{2}\s*年?\s*", "", t).strip()
    old_titles = re.findall(r"^#{1,3} .+$", old_draft, re.M)
    missing_titles = [
        t for t in old_titles if strip_year(t.strip()) not in strip_year(output)
    ]
    results.append(
        (len(missing_titles) == 0, f"原标题骨架保留（缺失 {missing_titles[:2]}）")
    )

    # 3) 引用被更新：至少有 1 个新 chunk_id 出现在输出中
    output_refs = re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", output)
    new_ids_used = [r for r in output_refs if r in new_ids]
    results.append(
        (len(new_ids_used) >= 1, f"至少 1 个新 chunk_id 被引用（实际 {len(new_ids_used)}）")
    )

    # 4) 旧数据要被替换：原稿里的 "1500 亿美元" / "2023 年" 应该变
    #    这里只检查最核心数据 "1500" 不应原样保留
    old_key_data = ["1500 亿美元", "15%", "12%", "180 亿美元", "40%"]
    still_present = [d for d in old_key_data if d in output]
    # 允许保留 ≤1 个（可能新资料没覆盖该点）
    results.append(
        (len(still_present) <= 1, f"旧关键数据被替换（残留 {still_present}）")
    )

    # 5) 无虚构 chunk_id（所有 ref 要么在新资料 要么保留原稿的 old_doc_*）
    old_ids_in_draft = set(re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", old_draft))
    invalid_refs = [r for r in output_refs if r not in new_ids and r not in old_ids_in_draft]
    results.append(
        (len(invalid_refs) == 0, f"无虚构 chunk_id（违规 {invalid_refs[:3]}）")
    )

    # 6) 无英文前缀污染
    results.append(
        (not bool(re.search(r"^(Let me|Now I|Here is)", output.strip(), re.I | re.M)), "无英文前缀污染")
    )

    return results


def main():
    retriever = json.loads((MOCK_DIR / "retriever-response-high-coverage.json").read_text())
    new_chunks = retriever["results"]

    prompt = build_data_update_prompt(OLD_DRAFT, new_chunks)

    print("=" * 60)
    print("SMOKE TEST — Rewriter.data_update (tier: T2 / Sonnet)")
    print("=" * 60)
    print(f"\nOld draft: {len(OLD_DRAFT)} chars")
    print(f"New chunks: {len(new_chunks)}")

    output = call_llm(prompt, tier="T2")
    print(f"\n--- LLM output ({len(output)} chars) ---\n{output}")

    print(f"\n--- Assertions ---")
    results = run_assertions(output, OLD_DRAFT, new_chunks)
    passed = sum(1 for ok, _ in results if ok)
    total = len(results)

    for ok, desc in results:
        print(f"  {'✅' if ok else '❌'} {desc}")

    print(f"\n--- Summary ---\n  {passed}/{total} assertions passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
