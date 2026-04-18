#!/usr/bin/env python3
"""
Smoke test — Rewriter.content_expansion

验证"内容扩展"模式：在原稿末尾追加新内容，新段落必须带 [新增] 标记，原内容一字不动。
"""
import os
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOCK_DIR = ROOT / "mocks"


OLD_DRAFT = """## 1.2 市场规模

2025 年中国 AI 市场规模达 3200 亿美元 [ref:doc_001_p15_3]，较 2023 年翻倍。
市场扩张速度高于全球平均水平。"""


def build_prompt(old_draft: str, expand_topic: str, new_chunks: list) -> str:
    chunks_block = "\n\n".join(
        f"[chunk_id={c['chunk_id']}]\n{c['content']}" for c in new_chunks
    )
    return f"""任务：内容扩展模式——在原章节末尾追加新段落，补充关于「{expand_topic}」的分析。

原章节（一字不可改）：
{old_draft}

可用的新资料：
{chunks_block}

## 硬约束

1. **原章节一字不动**：现有段落、标题、引用保持原样
2. **新段落加 `> [新增]` 前缀**：每一个新增段落第一行必须是 `> [新增]`
3. **新段落必须有引用**：每个新段落至少 1 个 [ref:xxx]，来自上面的新资料
4. **承接自然**：用"此外"、"值得关注的是"、"与此同时"等过渡词衔接
5. **不要扩展到其他主题**：只围绕「{expand_topic}」
6. **追加 1-2 段即可**，不要写成长篇

输出格式（原章节全文 + 追加的新段落）：
"""


def call_llm(prompt: str, tier: str = "T3") -> str:
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


def run_assertions(output: str, old_draft: str, new_chunks: list) -> list:
    results = []
    new_ids = {c["chunk_id"] for c in new_chunks}

    # 1) 非空
    results.append((bool(output.strip()), "有非空输出"))

    # 2) 原章节核心内容保留（允许多空白/换行差异）
    old_key = "2025 年中国 AI 市场规模达 3200 亿美元"
    results.append((old_key in output, f"原章节核心句保留（找 '{old_key[:20]}...'）"))

    # 3) 有 [新增] 标记
    new_count = output.count("[新增]")
    results.append((new_count >= 1, f"至少 1 个 [新增] 标记（实际 {new_count}）"))

    # 4) 新段落引用了新资料里的 chunk_id
    all_refs = re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", output)
    new_refs_used = [r for r in all_refs if r in new_ids]
    results.append((len(new_refs_used) >= 1, f"新资料被引用（{new_refs_used[:3]}）"))

    # 5) 原有引用保留
    old_refs = set(re.findall(r"\[ref:([a-zA-Z0-9_-]+)\]", old_draft))
    new_all_refs = set(all_refs)
    missing_old = old_refs - new_all_refs
    results.append((len(missing_old) == 0, f"原引用保留（缺失 {missing_old}）"))

    # 6) 输出长于原稿（追加了东西）
    results.append(
        (len(output) > len(old_draft) * 1.3, f"输出长于原稿（{len(old_draft)} → {len(output)}）")
    )

    return results


def main():
    retriever = json.loads((MOCK_DIR / "retriever-response-high-coverage.json").read_text())
    # 挑 doc_009（数据中心电耗）作为扩展主题的新资料
    new_chunks = [c for c in retriever["results"] if "数据中心" in c["content"] or "电力" in c["content"]]
    if not new_chunks:
        new_chunks = retriever["results"][-2:]  # 兜底

    prompt = build_prompt(OLD_DRAFT, expand_topic="能耗与可持续发展", new_chunks=new_chunks)

    print("=" * 60)
    print("SMOKE TEST — Rewriter.content_expansion (tier: T3 / Opus)")
    print("=" * 60)
    print(f"\nOld draft: {len(OLD_DRAFT)} chars")
    print(f"New chunks: {len(new_chunks)}")

    output = call_llm(prompt, tier="T3")
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
