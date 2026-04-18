#!/usr/bin/env python3
"""
Smoke test — Writer.section_writing

目的：验证 section_writing skill 的 prompt 模板在真实 LLM 下能否产出符合
约束的报告片段。对比 expected output，给出差异报告。

运行前准备：
  1. 在 .env 加 ANTHROPIC_API_KEY
  2. pip install anthropic python-dotenv (若未装)

运行：
  python3 reportclaw/tests/smoke_section_writing.py

退出码：
  0 = 核心断言全部通过
  1 = 有断言失败（具体原因打印）
  2 = 环境问题（key 缺失、SDK 缺失）
"""
import os
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOCK_DIR = ROOT / "mocks"
SKILL_DIR = ROOT / "agents" / "writer" / "skills"


def load_mocks():
    retriever = json.loads((MOCK_DIR / "retriever-response-high-coverage.json").read_text())
    expected = (MOCK_DIR / "writer-expected-output.md").read_text()
    return retriever, expected


def build_section_prompt(section_title: str, section_guidance: str, chunks: list, target_words: int = 800) -> str:
    """对齐 section_writing.md 里定义的 prompt 模板。"""
    chunks_block = "\n\n".join(
        f"[chunk_id={c['chunk_id']}]\n{c['content']}" for c in chunks
    )
    lower, upper = int(target_words * 0.8), int(target_words * 1.2)
    return f"""你是专业的报告写作员。

任务：写报告的"{section_title}"章节。
写作指引：{section_guidance}

**长度硬约束**：中文字符数严格在 {lower}-{upper} 之间。
- 超过 {upper} 字视为违规，必须删减
- 少于 {lower} 字视为偷懒，必须补充
- 在章节末尾自己点一下字数（最后一行写 `<!-- approx {{N}} 中文字符 -->`）

可用的资料片段（必须基于这些写，不要虚构）：
{chunks_block}

要求：
1. 用 markdown 格式，章节主标题用 ##（二级），子小节最多一层 ###
2. 每个数据/论断后必须用 [ref:chunk_id] 标注来源
3. 不引用 supporting_chunks 之外的 chunk_id
4. 语言：zh-CN
5. 结构紧凑，不要硬拆太多子节（2-3 个即可，不要做成 5-6 个子节撑字数）

直接输出章节内容，不要前言后语。写完立即停。
"""


def call_llm(prompt: str, tier: str = "T2") -> str:
    """按 Shifu delegate 的 tier 选模型调用。"""
    try:
        from anthropic import Anthropic
    except ImportError:
        print("❌ 缺少 anthropic SDK。pip install anthropic python-dotenv", file=sys.stderr)
        sys.exit(2)

    # 尝试从 .env 加载（override 空值的 shell 变量）
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT.parent / ".env", override=True)
    except ImportError:
        pass

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("❌ 缺少 ANTHROPIC_API_KEY。加到 .env 后重试。", file=sys.stderr)
        sys.exit(2)

    MODEL_MAP = {
        "T1": "claude-haiku-4-5-20251001",
        "T2": "claude-sonnet-4-6",
        "T3": "claude-opus-4-7",
    }
    client = Anthropic(api_key=key)
    msg = client.messages.create(
        model=MODEL_MAP.get(tier, MODEL_MAP["T2"]),
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def run_assertions(output: str, chunks: list, target_words: int = 800) -> list:
    """返回 (pass/fail, description) 列表"""
    results = []

    # 1) 有输出
    results.append((bool(output.strip()), "有非空输出"))

    # 2) 至少 1 个 [ref:xxx]
    refs = re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", output)
    results.append((len(refs) >= 1, f"至少 1 个引用 (实际 {len(refs)})"))

    # 3) 所有 [ref:xxx] 必须 ∈ supporting_chunks
    valid_ids = {c["chunk_id"] for c in chunks}
    invalid = [r for r in refs if r not in valid_ids]
    results.append((len(invalid) == 0, f"无虚构引用（违规 {invalid[:3]}）"))

    # 4) 长度 ±20%：算"有效字符数"——中文 + 数字 + 百分号 + 常见符号（近似人类读的字数）
    #    排除：markdown 标记符（# * [] \n）、空格
    exclude = set("#*[]()`>- \n\t\r")
    effective = sum(1 for ch in output if ch not in exclude)
    lower, upper = int(target_words * 0.8), int(target_words * 1.2)
    results.append((lower <= effective <= upper, f"长度 {effective} ∈ [{lower},{upper}]"))

    # 5) 是 markdown 格式（有 ## 标题）
    results.append(("##" in output, "含 markdown 二级标题"))

    # 6) 没 English 前缀污染（Let me / Now I）
    english_preface = bool(re.search(r"^(Let me|Now I|Here is)", output.strip(), re.I | re.M))
    results.append((not english_preface, "无英文前缀污染"))

    return results


def main():
    retriever, expected = load_mocks()
    chunks = retriever["results"]

    prompt = build_section_prompt(
        section_title="一、中国生成式 AI 行业概览",
        section_guidance="概述 2025 年中国生成式 AI 市场规模、主要玩家、增长趋势",
        chunks=chunks,
        target_words=800,
    )

    print("=" * 60)
    print("SMOKE TEST — section_writing (tier: T2 / Sonnet)")
    print("=" * 60)
    print(f"\nPrompt length: {len(prompt)} chars")
    print(f"Supporting chunks: {len(chunks)}")
    print(f"\n--- Calling LLM ---")

    output = call_llm(prompt, tier="T2")
    print(f"\n--- LLM output ({len(output)} chars) ---")
    print(output)
    print(f"\n--- Assertions ---")

    results = run_assertions(output, chunks, target_words=800)
    passed = sum(1 for ok, _ in results if ok)
    total = len(results)

    for ok, desc in results:
        print(f"  {'✅' if ok else '❌'} {desc}")

    print(f"\n--- Summary ---")
    print(f"  {passed}/{total} assertions passed")
    print(f"  Expected output preview (for manual diff): {len(expected)} chars in mocks/writer-expected-output.md")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
