#!/usr/bin/env python3
"""
Smoke test — Coordinator.task_dispatch (M4 + M4.1)

验证 Coordinator 接到用户请求时能产出合规的 dispatch payload JSON 或触发 Step 0 澄清。

调用 DeepSeek（OpenAI 兼容 schema），不依赖 ANTHROPIC_API_KEY / dotenv。

4 个用例：
  - Case 1 G1 search_knowledge   : 单步 retriever
  - Case 2 G2 generate_report    : retriever -> writer -> reviewer
  - Case 3 G3 perspective_shift  : fetch_document -> rewriter -> reviewer
  - Case 4 Step 0 澄清           : 模糊请求应触发澄清而非派发

Exit:
  0 — 全 PASS
  1 — 至少 1 case FAIL
  2 — 环境/网络问题
"""
import json
import sys
from pathlib import Path

# 共享工具（DeepSeek + extract_json 兜底）
from _smoke_common import call_deepseek, extract_json, load_deepseek_key

ROOT = Path(__file__).parent.parent
COORDINATOR_DIR = ROOT / "agents" / "coordinator"

VALID_AGENTS = {"retriever", "writer", "rewriter", "reviewer"}
VALID_TASK_TYPES = {"retrieve", "fetch_document", "write", "rewrite", "review"}
VALID_GEARS = {"G1", "G2", "G3"}


# ---------------------------------------------------------------------------
# system prompt 构建 — 复刻 OpenClaw runtime 真相
# ---------------------------------------------------------------------------


def build_system_prompt() -> str:
    """构建 system prompt — 与生产端 OpenClaw runtime 保持一致：

    OpenClaw runtime 实际加载: SOUL.md + skills/<name>/SKILL.md（裸文件原文拼接），
    没有任何 SYSTEM-INJECT 之类额外的 instruction 注入。

    历史 (Round 2 baseline) 的 strict/lenient instruction override 是 smoke 自造，
    生产端不存在 — 那段 override 把 LLM 强制推过 Step 0，掩盖了 SKILL.md 自身在
    "应该追问 vs 应该派发" 上的真实表现。Round 3 起删除该 drift。

    输出格式提示已在 SKILL.md `## 输出格式` 章节里有 JSON 示例；不再在 system prompt
    末尾追加额外 instruction。
    """
    soul = (COORDINATOR_DIR / "SOUL.md").read_text()
    gear = (COORDINATOR_DIR / "skills" / "gear_detection" / "SKILL.md").read_text()
    dispatch = (COORDINATOR_DIR / "skills" / "task_dispatch" / "SKILL.md").read_text()
    return "\n\n---\n\n".join([soul, gear, dispatch])


# ---------------------------------------------------------------------------
# assertions
# ---------------------------------------------------------------------------


def assert_payload_shape(payload) -> list:
    """通用 schema 检查，返回 (ok, desc) 列表。"""
    results = []

    is_dict = isinstance(payload, dict)
    results.append((is_dict, "payload 是 JSON 对象"))
    if not is_dict:
        return results

    # 顶层必填
    for key in ("intent", "gear", "subtasks"):
        results.append((key in payload, f"顶层包含 `{key}`"))

    gear_ok = payload.get("gear") in VALID_GEARS
    results.append((gear_ok, f"gear ∈ {sorted(VALID_GEARS)}（实际：{payload.get('gear')!r}）"))

    subtasks = payload.get("subtasks")
    is_list = isinstance(subtasks, list) and len(subtasks) > 0
    results.append((is_list, "subtasks 是非空 list"))
    if not is_list:
        return results

    # 每个 subtask schema
    seen_task_ids = set()
    invalid_agents = []
    invalid_task_types = []
    invalid_depends = []
    missing_fields = []

    for idx, st in enumerate(subtasks):
        if not isinstance(st, dict):
            missing_fields.append(f"#{idx} 不是 dict")
            continue
        for f in ("task_id", "to_agent", "task_type", "depends_on"):
            if f not in st:
                missing_fields.append(f"#{idx} 缺 `{f}`")

        tid = st.get("task_id")
        if tid:
            seen_task_ids.add(tid)

        if st.get("to_agent") not in VALID_AGENTS:
            invalid_agents.append(f"#{idx}={st.get('to_agent')!r}")
        if st.get("task_type") not in VALID_TASK_TYPES:
            invalid_task_types.append(f"#{idx}={st.get('task_type')!r}")
        depends = st.get("depends_on", [])
        if not isinstance(depends, list):
            invalid_depends.append(f"#{idx} depends_on 非 list")

    results.append((not missing_fields, f"subtask 必填字段齐全（缺失 {missing_fields[:3]}）"))
    results.append(
        (
            not invalid_agents,
            f"to_agent ∈ {sorted(VALID_AGENTS)}（违规 {invalid_agents[:3]}）",
        )
    )
    results.append(
        (
            not invalid_task_types,
            f"task_type ∈ {sorted(VALID_TASK_TYPES)}（违规 {invalid_task_types[:3]}）",
        )
    )
    results.append(
        (not invalid_depends, f"depends_on 是 list（违规 {invalid_depends[:3]}）")
    )

    # depends_on 引用必须存在
    dangling = []
    for st in subtasks:
        if not isinstance(st, dict):
            continue
        for d in st.get("depends_on", []) or []:
            if d not in seen_task_ids:
                dangling.append(d)
    results.append((not dangling, f"depends_on 引用都存在（dangling {dangling[:3]}）"))

    return results


def assert_case_specific(payload, expected) -> list:
    """case-specific 期望：intent / gear / agent 序列。"""
    results = []
    intent_ok = payload.get("intent") == expected["intent"]
    results.append((intent_ok, f"intent={expected['intent']}（实际 {payload.get('intent')!r}）"))

    gear_ok = payload.get("gear") == expected["gear"]
    results.append((gear_ok, f"gear={expected['gear']}（实际 {payload.get('gear')!r}）"))

    if "sub_mode" in expected:
        sub_mode_ok = payload.get("sub_mode") == expected["sub_mode"]
        results.append(
            (
                sub_mode_ok,
                f"sub_mode={expected['sub_mode']}（实际 {payload.get('sub_mode')!r}）",
            )
        )

    subtasks = payload.get("subtasks", []) or []
    actual_agents = [st.get("to_agent") for st in subtasks if isinstance(st, dict)]
    actual_types = [st.get("task_type") for st in subtasks if isinstance(st, dict)]

    expected_agents = expected["agents"]
    agents_ok = actual_agents == expected_agents
    results.append(
        (
            agents_ok,
            f"agent 序列 = {expected_agents}（实际 {actual_agents}）",
        )
    )

    if "task_types" in expected:
        types_ok = actual_types == expected["task_types"]
        results.append(
            (
                types_ok,
                f"task_type 序列 = {expected['task_types']}（实际 {actual_types}）",
            )
        )

    if "subtask_count" in expected:
        cnt_ok = len(subtasks) == expected["subtask_count"]
        results.append(
            (cnt_ok, f"subtasks 长度 = {expected['subtask_count']}（实际 {len(subtasks)}）")
        )

    return results


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------


def build_cases() -> list:
    return [
        {
            "name": "Case 1 — G1 search_knowledge",
            "user": "帮我查一下AI产业最新政策法规",
            "mentioned_docs": None,
            "mode": "dispatch",
            "expected": {
                "intent": "search_knowledge",
                "gear": "G1",
                "agents": ["retriever"],
                "subtask_count": 1,
            },
        },
        {
            "name": "Case 2 — G2 generate_report",
            "user": "写一份2500字的中国AI产业概览报告",
            "mentioned_docs": None,
            "mode": "dispatch",
            "expected": {
                "intent": "generate_report",
                "gear": "G2",
                "agents": ["retriever", "writer", "reviewer"],
                "task_types": ["retrieve", "write", "review"],
            },
        },
        {
            "name": "Case 3 — G3 rewrite perspective_shift",
            "user": "把@AI产业概览.pdf 这份报告改成投资人视角",
            "mentioned_docs": [
                {
                    "docId": "doc_xxx",
                    "docName": "AI产业概览.pdf",
                    "category": "行业报告",
                    "datasetId": "reportclaw_industry",
                }
            ],
            "mode": "dispatch",
            "expected": {
                "intent": "rewrite_report",
                "sub_mode": "perspective_shift",
                "gear": "G3",
                "agents": ["retriever", "rewriter", "reviewer"],
                "task_types": ["fetch_document", "rewrite", "review"],
            },
        },
        {
            "name": "Case 4 — Step 0 澄清（rewrite 缺信息）",
            "user": "帮我改一下这份报告",
            "mentioned_docs": None,
            "mode": "clarify",
            "expected": {
                # 任一满足即 PASS:
                #   (a) 输出无法解析为合法 JSON 对象
                #   (b) 解析出 JSON 但无 subtasks
                # AND 文本含中文澄清关键词之一
                "clarify_keywords": ["请问", "请描述", "请@", "请提供", "请告知"],
            },
        },
    ]


def build_user_message(case) -> str:
    msg = case["user"]
    if case.get("mentioned_docs"):
        msg += "\n\nmentionedDocs: " + json.dumps(
            case["mentioned_docs"], ensure_ascii=False
        )
    return msg


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def run_case(api_key: str, system_prompt: str, case) -> tuple:
    """返回 (passed, total, raw_text, error)."""
    user_msg = build_user_message(case)
    raw = call_deepseek(api_key, system_prompt, user_msg)

    if case.get("mode") == "clarify":
        return run_clarify_case(raw, case)

    try:
        payload = extract_json(raw)
    except Exception as e:
        return (0, 1, raw, f"JSON parse failed: {e}")

    shape_results = assert_payload_shape(payload)
    case_results = assert_case_specific(payload, case["expected"])
    all_results = shape_results + case_results

    passed = sum(1 for ok, _ in all_results if ok)
    total = len(all_results)

    print(f"\n--- Parsed payload ---")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])

    print(f"\n--- Assertions ---")
    for ok, desc in all_results:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    return (passed, total, raw, None)


def run_clarify_case(raw: str, case) -> tuple:
    """Case 4: Step 0 澄清。
    PASS 条件:
      A. (无 JSON) 或 (JSON 无 subtasks 字段)  AND
      B. 输出含中文澄清关键词之一
    """
    results = []

    # 试解析 JSON
    parsed_ok = False
    has_subtasks = False
    try:
        payload = extract_json(raw)
        parsed_ok = isinstance(payload, dict)
        if parsed_ok:
            has_subtasks = "subtasks" in payload and isinstance(
                payload.get("subtasks"), list
            ) and len(payload["subtasks"]) > 0
    except Exception:
        parsed_ok = False
        has_subtasks = False

    # 判断 A: 没派发出 subtasks
    no_dispatch_ok = (not parsed_ok) or (not has_subtasks)
    if not parsed_ok:
        results.append((True, "未输出可解析的 dispatch JSON（澄清是自然语言）"))
    elif not has_subtasks:
        results.append((True, "解析出 JSON 但无 subtasks 字段（未派发）"))
    else:
        results.append(
            (
                False,
                f"LLM 直接输出了 dispatch JSON 跳过 Step 0（subtasks 长度 {len(payload['subtasks'])}）",
            )
        )

    # 判断 B: 含澄清关键词
    keywords = case["expected"]["clarify_keywords"]
    hit = [kw for kw in keywords if kw in raw]
    keyword_ok = len(hit) > 0
    results.append(
        (
            keyword_ok,
            f"含澄清关键词之一 {keywords}（命中 {hit}）",
        )
    )

    passed = sum(1 for ok, _ in results if ok)
    total = len(results)

    print(f"\n--- Raw output (first 800) ---")
    print(raw[:800])

    print(f"\n--- Assertions ---")
    for ok, desc in results:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    # 失败诊断: 如果第一条 FAIL（即 LLM 直接产 dispatch JSON），打印更多上下文
    if not no_dispatch_ok:
        print(f"\n--- [DIAG] LLM 跳过 Step 0 输出（first 500） ---")
        print(raw[:500])

    return (passed, total, raw, None)


def main():
    print("=" * 60)
    print("SMOKE TEST — Coordinator.task_dispatch (DeepSeek)")
    print("=" * 60)

    api_key = load_deepseek_key()
    system_prompt = build_system_prompt()
    print(f"\nSystem prompt (drift-free, 复刻 OpenClaw runtime): {len(system_prompt)} chars")

    cases = build_cases()
    overall_ok = True
    summary_rows = []

    for case in cases:
        print("\n" + "=" * 60)
        print(case["name"])
        print(f"User: {case['user']}")
        if case.get("mentioned_docs"):
            print(f"mentionedDocs: {json.dumps(case['mentioned_docs'], ensure_ascii=False)}")
        print("=" * 60)

        # 所有 case 用同一份 prompt — 不再用 strict/lenient 分裂
        passed, total, raw, err = run_case(api_key, system_prompt, case)
        case_ok = err is None and passed == total
        overall_ok = overall_ok and case_ok
        verdict = "PASS" if case_ok else "FAIL"

        if err:
            print(f"\n[FAIL] {err}")
            print(f"\n--- Raw LLM output (first 500) ---\n{raw[:500]}")
        elif passed != total:
            print(f"\n[FAIL] {passed}/{total} assertions passed")
            print(f"\n--- Raw LLM output (first 500) ---\n{raw[:500]}")
        else:
            print(f"\n[PASS] {passed}/{total} assertions passed")

        summary_rows.append((case["name"], verdict, f"{passed}/{total}"))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, verdict, score in summary_rows:
        print(f"  {verdict:4s}  {score:6s}  {name}")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
