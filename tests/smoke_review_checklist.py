#!/usr/bin/env python3
"""
Smoke test — Reviewer.review_checklist

验证 Reviewer 能识别**有缺陷**的报告：
 - 虚构引用（chunk_id 不存在）
 - 数据错误（引用和数据不符）
 - 没有引用的硬陈述

给一份故意埋雷的报告 → Reviewer 必须找出 issues。
"""
import os
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOCK_DIR = ROOT / "mocks"


# 故意埋雷的报告：3 处问题
BAD_DRAFT = """# 2025 中国 AI 产业报告

## 一、市场规模

2025 年中国 AI 市场规模达到 3200 亿美元 [ref:doc_001_p15_3]，同比增长 28%。

## 二、融资情况

2025 年 Q1 融资总额 900 亿美元 [ref:doc_003_p2_1]，头部玩家估值持续攀升。

## 三、用户数据

C 端用户规模达到 6 亿人 [ref:doc_fake_999]，渗透率突破 40%。

## 四、结论

整体来看，AI 行业是未来十年最大的投资机会，回报率可达 10 倍以上。
"""

# 真实 Retriever 返回的数据（Reviewer 反查时对照）
VALID_CHUNKS = {
    "doc_001_p15_3": "2025 年中国 AI 市场规模达 3200 亿美元，同比增长 28%，创历年最高增速。",
    "doc_002_p8_1": "C 端用户规模达 4.5 亿人，渗透率突破 31%，18-35 岁占比 68%。",
    "doc_003_p2_1": "2025 年 Q1 生成式 AI 融资总额达 580 亿美元，头部集中度提升。",
}


def build_prompt(draft: str, valid_chunks: dict) -> str:
    chunks_block = "\n".join(
        f"- chunk_id={cid}: {content}" for cid, content in valid_chunks.items()
    )
    return f"""你是报告审查员。对以下报告做质量审查，按 JSON schema 输出 issues。

## 知识库中存在的有效 chunks
{chunks_block}

（除上述 chunk_id 外，其他任何 chunk_id 都视为**虚构引用**）

## 待审查的报告
{draft}

## 审查维度

1. **citation_error**（引用错误）：引用的 chunk_id 在知识库中不存在
2. **data_mismatch**（数据不符）：引用存在，但报告里的数字/内容和 chunk 原文对不上
3. **fabrication**（虚构内容）：硬陈述没有 [ref:xxx] 标注，或明显脱离知识库能支撑的范围
4. **citation_missing**（缺引用）：具体数字/论断后没有 [ref:xxx]

## 输出要求

严格 JSON 格式（只输出 JSON，无前后文）：

```json
{{
  "verdict": "pass | needs_revision | fail",
  "issues": [
    {{
      "type": "citation_error | data_mismatch | fabrication | citation_missing",
      "location": "报告里的具体位置（章节名或段落首句）",
      "detail": "问题描述",
      "severity": "HIGH | MEDIUM | LOW"
    }}
  ],
  "scores": {{
    "quality_score": 0.0-1.0,
    "citation_accuracy": 0.0-1.0
  }}
}}
```

找到几个算几个，不要凑数也不要漏。
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


def extract_json(text: str):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text
    if not m:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    return json.loads(raw)


def run_assertions(result: dict) -> list:
    results = []

    # 1) verdict 在允许值里
    verdict = result.get("verdict", "")
    results.append(
        (verdict in {"pass", "needs_revision", "fail"}, f"verdict 合法（{verdict}）")
    )

    # 2) verdict 不是 pass（有雷没发现就失败）
    results.append((verdict != "pass", f"不是 pass（应该 needs_revision 或 fail）"))

    # 3) issues 列表非空
    issues = result.get("issues", [])
    results.append((len(issues) >= 2, f"找到 ≥2 个 issues（实际 {len(issues)}）"))

    # 4) 识别了虚构引用 doc_fake_999
    flagged_fake = any("fake_999" in str(iss).lower() or "doc_fake" in str(iss) for iss in issues)
    results.append((flagged_fake, "识别出虚构引用 doc_fake_999"))

    # 5) 识别了数据错误（"900 亿" vs 真实 "580 亿"）
    flagged_data = any(
        "900" in str(iss) or "data_mismatch" in str(iss.get("type", ""))
        for iss in issues
    )
    results.append((flagged_data, "识别出数据错误（900 vs 580 亿）"))

    # 6) 识别了虚构/无引用的投资建议结论
    flagged_fabrication = any(
        iss.get("type") in {"fabrication", "citation_missing"}
        or "结论" in str(iss.get("location", ""))
        or "10 倍" in str(iss)
        or "未来十年" in str(iss)
        for iss in issues
    )
    results.append((flagged_fabrication, "识别出结论虚构（'10 倍回报'无引用）"))

    return results


def main():
    prompt = build_prompt(BAD_DRAFT, VALID_CHUNKS)

    print("=" * 60)
    print("SMOKE TEST — Reviewer.review_checklist (tier: T2 / Sonnet)")
    print("=" * 60)
    print(f"\n注入 3 处问题：")
    print("  - doc_fake_999 虚构引用")
    print("  - 融资 900 亿（真实 580 亿）数据错误")
    print("  - 结论'10 倍回报'无引用硬陈述")

    raw = call_llm(prompt, tier="T2")
    print(f"\n--- LLM raw output ({len(raw)} chars) ---\n{raw}")

    try:
        result = extract_json(raw)
    except Exception as e:
        print(f"\n❌ JSON parse failed: {e}")
        sys.exit(1)

    print(f"\n--- Parsed ---")
    print(f"verdict: {result.get('verdict')}")
    print(f"issues: {len(result.get('issues', []))}")
    for iss in result.get("issues", []):
        print(f"  [{iss.get('severity')}] {iss.get('type')}: {iss.get('detail', '')[:80]}")

    print(f"\n--- Assertions ---")
    results = run_assertions(result)
    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    for ok, desc in results:
        print(f"  {'✅' if ok else '❌'} {desc}")
    print(f"\n--- Summary ---\n  {passed}/{total} assertions passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
