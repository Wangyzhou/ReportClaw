#!/usr/bin/env python3
"""
共享 smoke 测试工具模块。

抽出来给 smoke_coordinator_dispatch.py / smoke_g1_chain.py 等共用：
  - load_deepseek_key()      : 读 DeepSeek key
  - call_deepseek()          : 调 DeepSeek (OpenAI 兼容)
  - extract_json()           : 从 LLM 文本中抽合法 JSON（含递减 rfind 兜底）

设计原则:
  - 不依赖 ANTHROPIC_API_KEY / dotenv
  - 失败必须显式 raise / sys.exit，不静默吞错
  - extract_json 用递减 rfind 兜底，扛得住 LLM 在 JSON 后追加的中文说明文字
"""
import json
import re
import sys
from pathlib import Path

import requests

DEEPSEEK_KEY_FILE = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# extract_json 兜底最大尝试次数（防递减 rfind 死循环）
EXTRACT_JSON_MAX_RETRIES = 5

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# DeepSeek 接入
# ---------------------------------------------------------------------------


def load_deepseek_key() -> str:
    """从 ~/.openclaw/agents/main/agent/auth-profiles.json 读取 deepseek:default key。

    失败时 sys.exit(2) — 视为环境问题。
    """
    if not DEEPSEEK_KEY_FILE.exists():
        print(f"[ENV] auth-profiles.json 不存在：{DEEPSEEK_KEY_FILE}", file=sys.stderr)
        sys.exit(2)
    profiles = json.loads(DEEPSEEK_KEY_FILE.read_text())
    try:
        return profiles["profiles"]["deepseek:default"]["key"]
    except KeyError as e:
        print(f"[ENV] 找不到 deepseek:default profile：{e}", file=sys.stderr)
        sys.exit(2)


def call_deepseek(
    api_key: str,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.2,
    max_tokens: int = 2500,
    timeout: int = 120,
) -> str:
    """调 DeepSeek chat completions，返回 message.content 字符串。

    网络/API 失败均 sys.exit(2)，视为环境问题，不让 smoke 把环境噪音算到 LLM 行为头上。
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=body, timeout=timeout)
    except requests.RequestException as e:
        print(f"[NET] DeepSeek 请求失败：{e}", file=sys.stderr)
        sys.exit(2)

    if resp.status_code != 200:
        print(
            f"[API] DeepSeek 非 200：{resp.status_code} — {resp.text[:300]}",
            file=sys.stderr,
        )
        sys.exit(2)

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"[API] DeepSeek 响应结构异常：{e} — {str(data)[:300]}", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# JSON 抽取（含递减 rfind 兜底）
# ---------------------------------------------------------------------------


def extract_json(text: str):
    """从 LLM 文本中抽出第一个合法 JSON 对象。

    顺序:
      1. 优先匹配 ```json ... ``` fence
      2. 退化到 first '{' .. last '}'，并对 JSONDecodeError 做递减 rfind 兜底
         （针对"...} 这是说明"这种 LLM 在 JSON 后追加中文的情况）

    递减 rfind 防死循环：最多尝试 EXTRACT_JSON_MAX_RETRIES 次，超过则 raise 原始 JSONDecodeError。

    Raises:
      ValueError — 找不到任何 '{' 或 fence 都没有
      json.JSONDecodeError — 所有边界尝试都失败
    """
    # 1) ```json fence 优先
    fence = _FENCE_RE.search(text)
    if fence:
        return json.loads(fence.group(1))

    # 2) fallback: first '{' .. last '}'
    start = text.find("{")
    if start < 0:
        raise ValueError("未找到 JSON 对象边界（无 '{'）")

    end = text.rfind("}")
    if end <= start:
        raise ValueError("未找到 JSON 对象边界（无配对的 '}'）")

    last_err: Exception | None = None
    for attempt in range(EXTRACT_JSON_MAX_RETRIES):
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            last_err = e
            # 递减 rfind: 找下一个更靠左的 '}'，再试
            new_end = text.rfind("}", start, end)
            if new_end <= start or new_end == end:
                # 没有更左的 '}' 了，停止
                break
            end = new_end

    # 全部尝试失败，抛出最后一次的真实错误
    if last_err is not None:
        raise last_err
    raise ValueError("extract_json 未能抽出合法 JSON（异常：未捕获的边界）")


# ---------------------------------------------------------------------------
# Inline 单测（python3 _smoke_common.py 直接跑）
# ---------------------------------------------------------------------------


def _selftest() -> int:
    """覆盖 extract_json 三类输入：
      1. 干净 JSON
      2. fence 包裹
      3. JSON 后追加中文说明（rfind 兜底）
      4. 嵌套 JSON 且后接说明
      5. 非法 — 应抛 JSONDecodeError
    返回失败数。
    """
    cases = [
        # (label, input_text, expected_result, should_raise)
        (
            "case1 — 干净 JSON",
            '{"a": 1, "b": "x"}',
            {"a": 1, "b": "x"},
            False,
        ),
        (
            "case2 — fence 包裹",
            "前置说明\n```json\n{\"intent\": \"x\"}\n```\n后置说明",
            {"intent": "x"},
            False,
        ),
        (
            "case3 — JSON 后追加中文（rfind 兜底关键 case）",
            '{"a": {"b": 1}}\n好的',
            {"a": {"b": 1}},
            False,
        ),
        (
            "case4 — 嵌套 JSON 且后接 } 说明文字",
            '{"x": {"y": [1, 2]}, "z": "ok"}\n上面是 dispatch payload。',
            {"x": {"y": [1, 2]}, "z": "ok"},
            False,
        ),
        (
            "case5 — JSON 后多余 } 容错",
            '{"a": 1}}}',
            {"a": 1},
            False,
        ),
        (
            "case6 — 非法 JSON（无 { ）",
            "完全没有 JSON 对象",
            None,
            True,
        ),
    ]

    fail_count = 0
    for label, text, expected, should_raise in cases:
        try:
            actual = extract_json(text)
            if should_raise:
                print(f"  FAIL {label} — 应该抛异常但返回了 {actual!r}")
                fail_count += 1
                continue
            if actual != expected:
                print(f"  FAIL {label} — expect {expected!r} got {actual!r}")
                fail_count += 1
                continue
            print(f"  PASS {label}")
        except (ValueError, json.JSONDecodeError) as e:
            if should_raise:
                print(f"  PASS {label} — 如期抛 {type(e).__name__}: {e}")
            else:
                print(f"  FAIL {label} — 不该抛但抛了 {type(e).__name__}: {e}")
                fail_count += 1
    return fail_count


if __name__ == "__main__":
    print("=" * 60)
    print("extract_json inline selftest")
    print("=" * 60)
    fails = _selftest()
    print("=" * 60)
    if fails == 0:
        print("ALL PASS")
        sys.exit(0)
    else:
        print(f"{fails} FAILED")
        sys.exit(1)
