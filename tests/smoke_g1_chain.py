#!/usr/bin/env python3
"""
Smoke test — Coordinator G1 full-chain (M5)

验证 G1 search_knowledge 全链路：
  Step 1: Coordinator 接到检索请求 → 产出 dispatch JSON（G1 + 单 retriever）
  Step 2: Mock Retriever 返回（读 mocks/retriever-response-high-coverage.json）
  Step 3: Coordinator 聚合 retrieval_results + 原 query → 输出 markdown 答案
  Step 4: 验证 markdown 长度 + [ref:chunk_id] 引用合法（不能虚构 chunk_id）

调用 DeepSeek（OpenAI 兼容 schema），不依赖 ANTHROPIC_API_KEY / dotenv。
2 个真实 LLM 调用：dispatch + 聚合。

Exit:
  0 — 全 PASS
  1 — 至少 1 步 FAIL
  2 — 环境/网络问题
"""
import json
import re
import sys
from pathlib import Path

# 共享工具（DeepSeek + extract_json 兜底）
from _smoke_common import call_deepseek, extract_json, load_deepseek_key

ROOT = Path(__file__).parent.parent
COORDINATOR_DIR = ROOT / "agents" / "coordinator"
MOCK_RETRIEVER_FILE = ROOT / "mocks" / "retriever-response-high-coverage.json"

USER_QUERY = "帮我查一下AI产业最新政策法规"

VALID_AGENTS = {"retriever", "writer", "rewriter", "reviewer"}
VALID_TASK_TYPES = {"retrieve", "fetch_document", "write", "rewrite", "review"}
VALID_GEARS = {"G1", "G2", "G3"}

REF_PATTERN = re.compile(r"\[ref:([^\]]+)\]")


# ---------------------------------------------------------------------------
# system prompt 构建 — 与 smoke_coordinator_dispatch 保持一致，无 strict override
# ---------------------------------------------------------------------------


def build_system_prompt() -> str:
    """复刻 OpenClaw runtime: SOUL.md + skills/*/SKILL.md 裸文件拼接，0 instruction override."""
    soul = (COORDINATOR_DIR / "SOUL.md").read_text()
    gear = (COORDINATOR_DIR / "skills" / "gear_detection" / "SKILL.md").read_text()
    dispatch = (COORDINATOR_DIR / "skills" / "task_dispatch" / "SKILL.md").read_text()
    return "\n\n---\n\n".join([soul, gear, dispatch])


# ---------------------------------------------------------------------------
# step assertions
# ---------------------------------------------------------------------------


def step1_dispatch(api_key: str, system_prompt: str) -> tuple:
    """Step 1: 调 Coordinator 出 dispatch payload。

    Round 3 起删除 strict instruction override。OpenClaw runtime 不会在 SOUL+SKILL 之外
    注入 "严格输出 JSON" 之类的 system prompt — 让 SKILL.md `## 输出格式` 自然引导。

    返回 (passed, total, payload, raw, err)
    """
    raw = call_deepseek(api_key, system_prompt, USER_QUERY)

    try:
        payload = extract_json(raw)
    except Exception as e:
        return (0, 4, None, raw, f"JSON parse failed: {e}")

    checks = []

    # 1. intent == search_knowledge
    intent_ok = payload.get("intent") == "search_knowledge"
    checks.append((intent_ok, f"intent=search_knowledge（实际 {payload.get('intent')!r}）"))

    # 2. gear == G1
    gear_ok = payload.get("gear") == "G1"
    checks.append((gear_ok, f"gear=G1（实际 {payload.get('gear')!r}）"))

    # 3. subtasks 是单元素 list
    subtasks = payload.get("subtasks")
    subtasks_ok = isinstance(subtasks, list) and len(subtasks) == 1
    checks.append((subtasks_ok, f"subtasks 长度=1（实际 {len(subtasks) if isinstance(subtasks, list) else 'N/A'}）"))

    # 4. 唯一子任务 to_agent=retriever / task_type=retrieve
    if subtasks_ok:
        st0 = subtasks[0] if isinstance(subtasks[0], dict) else {}
        agent_ok = st0.get("to_agent") == "retriever"
        type_ok = st0.get("task_type") == "retrieve"
        checks.append((agent_ok and type_ok,
                       f"subtask to_agent=retriever & task_type=retrieve（实际 to_agent={st0.get('to_agent')!r} task_type={st0.get('task_type')!r}）"))
    else:
        checks.append((False, "subtask 缺失，无法验证 to_agent/task_type"))

    passed = sum(1 for ok, _ in checks if ok)
    total = len(checks)

    print("\n--- Step 1 dispatch payload ---")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])
    print("\n--- Step 1 assertions ---")
    for ok, desc in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    return (passed, total, payload, raw, None)


def step2_load_mock() -> tuple:
    """Step 2: 加载 mock retriever response。
    返回 (passed, total, mock_data, err)
    """
    checks = []
    if not MOCK_RETRIEVER_FILE.exists():
        return (0, 1, None, f"mock 文件不存在：{MOCK_RETRIEVER_FILE}")

    try:
        mock = json.loads(MOCK_RETRIEVER_FILE.read_text())
    except Exception as e:
        return (0, 1, None, f"mock JSON 解析失败：{e}")

    results = mock.get("results", [])
    has_results = isinstance(results, list) and len(results) > 0
    checks.append((has_results, f"mock 包含非空 results（实际 {len(results) if isinstance(results, list) else 'N/A'} 条）"))

    print("\n--- Step 2 mock load ---")
    print(f"  scenario: {mock.get('_mock_scenario', 'N/A')}")
    print(f"  results: {len(results)} chunks")
    print("\n--- Step 2 assertions ---")
    for ok, desc in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    passed = sum(1 for ok, _ in checks if ok)
    return (passed, len(checks), mock, None)


def step3_aggregate(api_key: str, system_prompt: str, mock: dict) -> tuple:
    """Step 3: 喂 Coordinator (mock retrieval results + 原 query)，要求按 G1 流程汇总成 markdown 答案。

    Round 3 起 — Step 3 仅保留"阶段标记"（告诉 Coordinator 现在是聚合阶段、Retriever 已返回），
    SOUL.md 的"来源不妥协" + 工作节奏中的"聚合阶段" 自然引导引用格式与不虚构。
    删除原有 4 条硬性输出指令（不要 JSON/fence、必须基于 results、必须 [ref:chunk_id]、面向用户简明），
    这些是 Coordinator 在生产端 run aggregation 时由 SOUL.md 已经覆盖的内容。

    返回 (passed, total, markdown, raw, err)
    """
    user_payload = (
        f"原 user_request: {USER_QUERY}\n\n"
        f"Retriever 已返回结果。请按 G1 search_knowledge 流程进入【聚合阶段】，"
        f"基于下方 retrieval_results 给用户最终答案。\n\n"
        f"retrieval_results:\n```json\n"
        f"{json.dumps(mock, ensure_ascii=False, indent=2)}\n"
        f"```\n"
    )

    raw = call_deepseek(api_key, system_prompt, user_payload)

    # 把 ```markdown / ```md fence 剥掉（如果有）
    md = raw.strip()
    fence_match = re.match(r"^```(?:markdown|md)?\s*\n(.*?)\n```\s*$", md, re.DOTALL)
    if fence_match:
        md = fence_match.group(1).strip()

    checks = []

    # 长度 ≥ 50
    length_ok = len(md) >= 50
    checks.append((length_ok, f"答案长度 ≥ 50 字（实际 {len(md)} 字）"))

    # 含 ≥ 1 个 [ref:chunk_id]
    refs = REF_PATTERN.findall(md)
    refs_count_ok = len(refs) >= 1
    checks.append((refs_count_ok, f"含 ≥ 1 个 [ref:chunk_id]（实际 {len(refs)} 个：{refs[:5]}）"))

    # 所有引用 chunk_id 都在 mock results 里
    valid_chunk_ids = {r.get("chunk_id") for r in mock.get("results", []) if isinstance(r, dict)}
    invalid_refs = [ref for ref in refs if ref not in valid_chunk_ids]
    no_fab_ok = not invalid_refs
    checks.append((no_fab_ok,
                   f"所有 [ref:*] 都能在 mock results 找到（不能虚构）"
                   f"（违规 {invalid_refs[:5]}）"))

    passed = sum(1 for ok, _ in checks if ok)
    total = len(checks)

    print("\n--- Step 3 aggregated markdown ---")
    print(md[:1500])
    print("\n--- Step 3 assertions ---")
    for ok, desc in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    return (passed, total, md, raw, None)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    print("=" * 60)
    print("SMOKE TEST — Coordinator G1 full chain (DeepSeek)")
    print("=" * 60)

    api_key = load_deepseek_key()
    system_prompt = build_system_prompt()
    print(f"\nSystem prompt: {len(system_prompt)} chars")
    print(f"User query: {USER_QUERY}")

    overall_ok = True
    summary_rows = []

    # Step 1 — dispatch
    print("\n" + "=" * 60)
    print("Step 1 — Coordinator dispatch (LLM 调用 1)")
    print("=" * 60)
    p1, t1, payload, raw1, err1 = step1_dispatch(api_key, system_prompt)
    s1_ok = err1 is None and p1 == t1
    if err1:
        print(f"\n[FAIL] Step 1 — {err1}")
        print(f"\n--- Raw LLM output (first 500) ---\n{raw1[:500]}")
    elif p1 != t1:
        print(f"\n[FAIL] Step 1 — {p1}/{t1} assertions passed")
        print(f"\n--- Raw LLM output (first 500) ---\n{raw1[:500]}")
    else:
        print(f"\n[PASS] Step 1 — {p1}/{t1} assertions passed")
    summary_rows.append(("Step 1 dispatch", "PASS" if s1_ok else "FAIL", f"{p1}/{t1}"))
    overall_ok = overall_ok and s1_ok

    # Step 2 — mock load
    print("\n" + "=" * 60)
    print("Step 2 — Mock Retriever response (本地读文件，无 LLM 调用)")
    print("=" * 60)
    p2, t2, mock, err2 = step2_load_mock()
    s2_ok = err2 is None and p2 == t2
    if err2:
        print(f"\n[FAIL] Step 2 — {err2}")
    else:
        print(f"\n[{'PASS' if s2_ok else 'FAIL'}] Step 2 — {p2}/{t2} assertions passed")
    summary_rows.append(("Step 2 mock load", "PASS" if s2_ok else "FAIL", f"{p2}/{t2}"))
    overall_ok = overall_ok and s2_ok

    # Step 2 失败则直接退出（后面没法跑）
    if not s2_ok or mock is None:
        print("\n" + "=" * 60)
        print("SUMMARY (early exit — Step 2 failed)")
        print("=" * 60)
        for name, verdict, score in summary_rows:
            print(f"  {verdict:4s}  {score:6s}  {name}")
        sys.exit(1)

    # Step 3 — aggregate
    print("\n" + "=" * 60)
    print("Step 3 — Coordinator 聚合 (LLM 调用 2)")
    print("=" * 60)
    p3, t3, md, raw3, err3 = step3_aggregate(api_key, system_prompt, mock)
    s3_ok = err3 is None and p3 == t3
    if err3:
        print(f"\n[FAIL] Step 3 — {err3}")
        print(f"\n--- Raw LLM output (first 500) ---\n{raw3[:500]}")
    elif p3 != t3:
        print(f"\n[FAIL] Step 3 — {p3}/{t3} assertions passed")
        print(f"\n--- Raw LLM output (first 500) ---\n{raw3[:500]}")
    else:
        print(f"\n[PASS] Step 3 — {p3}/{t3} assertions passed")
    summary_rows.append(("Step 3 aggregate (含 Step 4 验证)", "PASS" if s3_ok else "FAIL", f"{p3}/{t3}"))
    overall_ok = overall_ok and s3_ok

    # 总结
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, verdict, score in summary_rows:
        print(f"  {verdict:4s}  {score:6s}  {name}")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
