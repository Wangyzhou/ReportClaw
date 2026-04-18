#!/usr/bin/env python3
"""
Smoke test — Writer.outline_generation

验证 outline_generation skill 能根据主题 + retrieval results 产出合规提纲 JSON。
"""
import os
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOCK_DIR = ROOT / "mocks"


def build_outline_prompt(topic: str, max_length: int, chunks: list, language: str = "zh-CN") -> str:
    chunks_block = "\n".join(
        f"[chunk_id={c['chunk_id']}]\ncategory: {c['source'].get('category', '')}\n摘要: {c['content'][:120]}..."
        for c in chunks
    )
    return f"""任务：根据主题和检索到的资料，生成一个层级化提纲。

主题：{topic}
目标长度：{max_length} 字
语言：{language}

可用资料（chunk 清单）：
{chunks_block}

要求：
1. 一级章节数遵守下表：
   - <2000 字：3-4 章
   - 2000-5000 字：4-6 章
   - >5000 字：5-8 章
2. 每个一级章节至少分配 1-3 个 supporting chunks（必须来自上面的 chunk 清单）
3. 覆盖 retrieval_results 能支撑的全部主要 topic，不超纲
4. 章节顺序按"总→分"或"时序"组织
5. 标题用中文数字 "一、二、三..."，二级用 "1.1 / 1.2"
6. 每个一级章节带 guidance（一句话写作提示）

输出 JSON 数组（只输出 JSON，无前后文）：
[
  {{ "level": 1, "title": "一、X", "guidance": "...", "supporting_chunks": ["chunk_id_1"] }},
  {{ "level": 2, "title": "1.1 Y", "supporting_chunks": ["chunk_id_2"] }}
]
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
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def extract_json(text: str):
    """从 LLM 输出里抽 JSON 数组（容忍 ```json fence）"""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text
    # fallback：找第一个 [ 到最后一个 ]
    if not m:
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    return json.loads(raw)


def run_assertions(outline, chunks, max_length):
    results = []
    valid_chunk_ids = {c["chunk_id"] for c in chunks}

    # 1) outline 是 list
    results.append((isinstance(outline, list) and len(outline) > 0, "输出是非空 list"))

    # 2) 一级章节数量符合 max_length 分档
    lv1 = [s for s in outline if s.get("level") == 1]
    if max_length < 2000:
        rng = (3, 4)
    elif max_length <= 5000:
        rng = (4, 6)
    else:
        rng = (5, 8)
    lv1_ok = rng[0] <= len(lv1) <= rng[1]
    results.append((lv1_ok, f"一级章节数 {len(lv1)} ∈ [{rng[0]},{rng[1]}] (max_length={max_length})"))

    # 3) 每个一级章节有 supporting_chunks
    all_lv1_have = all(
        s.get("supporting_chunks") and len(s["supporting_chunks"]) >= 1 for s in lv1
    )
    results.append((all_lv1_have, "每个一级章节有 ≥1 supporting_chunks"))

    # 4) 所有 supporting_chunks ∈ valid
    invalid_ids = []
    for s in outline:
        for cid in s.get("supporting_chunks", []):
            if cid not in valid_chunk_ids:
                invalid_ids.append(cid)
    results.append((len(invalid_ids) == 0, f"无虚构 chunk_id（违规 {invalid_ids[:3]}）"))

    # 5) 一级章节有 guidance
    all_lv1_guidance = all(s.get("guidance") for s in lv1)
    results.append((all_lv1_guidance, "每个一级章节有 guidance"))

    # 6) 标题用中文数字
    cn_nums = set("一二三四五六七八九十")
    lv1_titles_ok = all(s["title"] and s["title"][0] in cn_nums for s in lv1)
    results.append((lv1_titles_ok, "一级章节用中文数字开头"))

    return results


def main():
    retriever = json.loads((MOCK_DIR / "retriever-response-high-coverage.json").read_text())
    chunks = retriever["results"]
    max_length = 5000

    prompt = build_outline_prompt(
        topic="2025 年中国生成式 AI 产业分析报告",
        max_length=max_length,
        chunks=chunks,
    )

    print("=" * 60)
    print("SMOKE TEST — outline_generation (tier: T2 / Sonnet)")
    print("=" * 60)
    print(f"\nSupporting chunks: {len(chunks)}")

    raw = call_llm(prompt, tier="T2")
    print(f"\n--- LLM raw output ({len(raw)} chars) ---\n{raw}")

    try:
        outline = extract_json(raw)
    except Exception as e:
        print(f"\n❌ JSON parse failed: {e}")
        sys.exit(1)

    print(f"\n--- Parsed outline: {len(outline)} sections ---")
    for s in outline:
        indent = "  " * (s.get("level", 1) - 1)
        print(f"{indent}[{s.get('level')}] {s.get('title', '')}")

    print(f"\n--- Assertions ---")
    results = run_assertions(outline, chunks, max_length)
    passed = sum(1 for ok, _ in results if ok)
    total = len(results)

    for ok, desc in results:
        print(f"  {'✅' if ok else '❌'} {desc}")

    print(f"\n--- Summary ---\n  {passed}/{total} assertions passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
