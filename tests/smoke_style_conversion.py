#!/usr/bin/env python3
"""
Smoke test — Rewriter.style_conversion

验证"风格转换"模式：正式商业 → 通俗易懂，数据/引用完全不变。
"""
import os
import sys
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


OLD_DRAFT = """## 一、市场概览

根据权威数据显示，2025 年中国生成式人工智能市场规模达 3200 亿美元 [ref:doc_001_p15_3]，
同比增长幅度达 28%，呈现显著的扩张态势。在技术渗透层面，C 端用户规模已达 4.5 亿人，
渗透率突破 31% [ref:doc_002_p8_1]，其中 18-35 岁年龄段用户群体占比高达 68%。

值得关注的是，行业在垂直场景的落地呈现差异化特征。教育领域渗透率达到 45%，金融领域
为 38%，而医疗领域仅为 21% [ref:doc_007_p4_2]，反映出各行业数据结构化程度与合规
路径清晰度的显著差异。"""


def build_prompt(old_draft: str, from_style: str, to_style: str) -> str:
    return f"""任务：风格转换——把以下段落从「{from_style}」改为「{to_style}」，中文不变。

原稿：
{old_draft}

## 硬约束

1. **数据一字不改**：所有数字、百分比、金额、年份保持精度不变（"3200 亿美元" 不能变成 "3 千多亿"）
2. **引用全部保留**：所有 [ref:xxx] 原样保留，位置可微调
3. **结构零改动**：标题层级、段落数不变
4. **风格要求（{to_style}）**：
   - 短句为主（平均句长 20 字以内）
   - 少用术语和长词（"显著"→"明显"，"呈现"→"是"）
   - 口语化表达，像跟朋友讲话
   - 避免"值得关注的是"、"根据权威数据显示"等套话
5. **事实不增不减**：段落里的事实点数量和原稿相同

直接输出改写后的 markdown，不要前言后语。
"""


def call_llm(prompt: str, tier: str = "T2") -> str:
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
    return set(re.findall(r"(\d+(?:\.\d+)?\s*(?:亿美元|亿人|亿|万人|万|%))", text))


def run_assertions(output: str, old_draft: str) -> list:
    results = []

    # 1) 非空
    results.append((bool(output.strip()), "有非空输出"))

    # 2) 数据点保留（精度不变）
    old_data = extract_numbers(old_draft)
    new_data = extract_numbers(output)
    missing = old_data - new_data
    results.append((len(missing) == 0, f"数据点精度保留（缺失 {missing}）"))

    # 3) 引用全部保留
    old_refs = set(re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", old_draft))
    new_refs = set(re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", output))
    missing_refs = old_refs - new_refs
    results.append((len(missing_refs) == 0, f"引用保留（缺失 {missing_refs}）"))

    # 4) 结构保留
    old_titles = re.findall(r"^#{1,3} .+$", old_draft, re.M)
    missing_titles = [t for t in old_titles if t.strip() not in output]
    results.append((len(missing_titles) == 0, f"原标题保留（缺失 {missing_titles[:1]}）"))

    # 5) 风格确实转了：原稿的正式套话不该出现
    formal_words = ["根据权威数据显示", "呈现显著的扩张态势", "值得关注的是", "反映出"]
    still_formal = [w for w in formal_words if w in output]
    results.append(
        (len(still_formal) <= 1, f"正式套话被改写（残留 {still_formal}）")
    )

    # 6) 平均句长相对原稿变短（相对比较，更公平）
    def avg_sentence_len(text: str) -> float:
        sents = [s.strip() for s in re.split(r"[。！？]", text) if s.strip()]
        return sum(len(s) for s in sents) / len(sents) if sents else 0
    old_avg = avg_sentence_len(old_draft)
    new_avg = avg_sentence_len(output)
    results.append(
        (new_avg < old_avg * 0.9, f"句子相对变短（{old_avg:.0f} → {new_avg:.0f} 字/句）")
    )

    return results


def main():
    prompt = build_prompt(OLD_DRAFT, from_style="正式商业", to_style="通俗口语")

    print("=" * 60)
    print("SMOKE TEST — Rewriter.style_conversion (tier: T2 / Sonnet)")
    print("=" * 60)

    output = call_llm(prompt, tier="T2")
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
