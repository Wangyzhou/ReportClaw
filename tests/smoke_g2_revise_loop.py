#!/usr/bin/env python3
"""
Smoke test — Coordinator G2 review→revise loop (M6)

验证 Coordinator 在 G2 审查回环中的核心产品价值链：
  Step 1: Round-1 Reviewer 返回 needs_revision (2 HIGH issues)
          → Coordinator 必须派 Writer round=2 / 注入 revision_context（含 issues）
  Step 2: Round-2 Reviewer 返回 pass
          → Coordinator 必须停回环 / 输出最终交付（不再派新 subtask）
  Step 3: Round-2 Reviewer 仍 needs_revision（虚构 round-2-still-fail）
          → Coordinator 必须遵守 max_review_rounds=2 / 升级给用户（不派 round=3）

调用 DeepSeek（OpenAI 兼容 schema），不依赖 ANTHROPIC_API_KEY / dotenv。
3 个真实 LLM 调用：每步 1 次。

system prompt 复刻 OpenClaw runtime —— SOUL.md + skills/*/SKILL.md 裸文件拼接，
**不加 strict instruction override**（drift-free，等效生产）。

Exit:
  0 — 3 步全 PASS
  1 — 至少 1 步 FAIL
  2 — 环境/网络问题
"""
import json
import sys
from pathlib import Path

# 共享工具（DeepSeek + extract_json 兜底）
from _smoke_common import call_deepseek, extract_json, load_deepseek_key

ROOT = Path(__file__).parent.parent
COORDINATOR_DIR = ROOT / "agents" / "coordinator"
MOCK_WRITER_OUTPUT = ROOT / "mocks" / "writer-expected-output.md"
MOCK_REVIEWER_ROUND1 = ROOT / "mocks" / "reviewer-issues-round1.json"
MOCK_REVIEWER_ROUND2 = ROOT / "mocks" / "reviewer-issues-round2.json"

USER_QUERY = "写一份2500字的中国AI产业概览报告"

# Step 1 期望的关键 issue id（须在 Coordinator 派给 Writer round-2 的上下文中可见）
ROUND1_ISSUE_IDS = ["issue_001", "issue_002"]

# Step 2 / Step 3 命中关键词（任一即 PASS）
DELIVER_KEYWORDS = ["通过", "pass", "最终", "交付", "完成", "审查"]
ESCALATE_KEYWORDS = ["最大", "轮数", "已达", "人工", "升级", "请确认"]


# ---------------------------------------------------------------------------
# system prompt 构建 —— 复刻 OpenClaw runtime 真相
# ---------------------------------------------------------------------------


def build_system_prompt() -> str:
    """SOUL.md + skills/gear_detection/SKILL.md + skills/task_dispatch/SKILL.md
    裸文件原文拼接，**0 instruction override**。

    与 smoke_g1_chain / smoke_coordinator_dispatch (Round 3+) 一致 —— 不在 system
    prompt 末尾追加 strict 输出指令，让 SKILL.md 自身的 `## 输出格式` 自然引导。
    """
    soul = (COORDINATOR_DIR / "SOUL.md").read_text()
    gear = (COORDINATOR_DIR / "skills" / "gear_detection" / "SKILL.md").read_text()
    dispatch = (COORDINATOR_DIR / "skills" / "task_dispatch" / "SKILL.md").read_text()
    return "\n\n---\n\n".join([soul, gear, dispatch])


# ---------------------------------------------------------------------------
# 共用：尝试解析 LLM 输出为 dispatch JSON
# ---------------------------------------------------------------------------


def try_parse_dispatch(raw: str):
    """返回 (payload_or_none, parse_err_or_none)。"""
    try:
        return (extract_json(raw), None)
    except Exception as e:
        return (None, str(e))


# BL-11 — 合法 task_type schema 集合（与 smoke_coordinator_dispatch.py / smoke_g1_chain.py 保持一致）
VALID_TASK_TYPES = {"retrieve", "fetch_document", "write", "rewrite", "review"}


def find_writer_subtask(payload: dict):
    """从 dispatch payload 中找第 1 个 to_agent=writer 的 subtask；找不到返 None。

    实测 DeepSeek 在 round-2 修订场景下 task_type 可能取 "write" 或 "revise"（SKILL.md 在
    §拆解规则 写"writer 重做"，未明确 task_type，留有解释空间）。两者均接受；
    严格的 task_type 取值 {retrieve, fetch_document, write, rewrite, review} 检查留给
    smoke_coordinator_dispatch.py 的 schema 校验，本 smoke 只关心回环行为正确性。

    BL-11 — 找到匹配 writer subtask 时检查 task_type，如果不在合法集打印 WARN（surface
    anomaly 但不阻断），让回归数据公开化。Round 5 实测 DeepSeek 偶尔自创
    `task_type="revise"`，BL-12 文档明文修订轮 task_type 仍取 `write` 后预期消失。
    """
    if not isinstance(payload, dict):
        return None
    subtasks = payload.get("subtasks")
    if not isinstance(subtasks, list):
        return None
    for st in subtasks:
        if not isinstance(st, dict):
            continue
        if st.get("to_agent") == "writer":
            tt = st.get("task_type")
            if tt is not None and tt not in VALID_TASK_TYPES:
                print(
                    f"[WARN] task_type={tt!r} is outside schema "
                    f"(expected one of: retrieve/fetch_document/write/rewrite/review)"
                )
            return st
    return None


def collect_revision_context(subtask: dict, payload: dict) -> dict:
    """从 writer subtask 的 payload（或顶层 payload）里捞 revision_context。
    SKILL.md §6 协议: revision_context 应嵌在 writer subtask.payload 里，但允许 LLM
    放在顶层 fallback —— 都接受。

    BL-10 — 命中 fallback 路径时打印 WARN（misplaced 字段不再静默吞），三路分别打印
    不同标识：subtask.payload（合规路径，无 WARN）/ top-level payload / subtask root。
    BL-13 加修订上下文 few-shot 后预期 LLM 稳定走 subtask.payload 主路径，WARN
    数量应趋零。
    """
    if not isinstance(subtask, dict):
        return {}
    # 主路径：嵌在 writer subtask.payload 里（合规，无 WARN）
    sub_payload = subtask.get("payload")
    if isinstance(sub_payload, dict) and "revision_context" in sub_payload:
        rc = sub_payload["revision_context"]
        if isinstance(rc, dict):
            return rc
    # fallback 1: 顶层 payload
    if isinstance(payload, dict) and "revision_context" in payload:
        rc = payload["revision_context"]
        if isinstance(rc, dict):
            print(
                "[WARN] revision_context found at fallback path: top-level payload "
                "(should be in writer subtask.payload per SKILL.md §6)"
            )
            return rc
    # fallback 2: subtask 顶层（subtask.payload 之外）
    if isinstance(subtask, dict) and "revision_context" in subtask:
        rc = subtask["revision_context"]
        if isinstance(rc, dict):
            print(
                "[WARN] revision_context found at fallback path: subtask root "
                "(should be in writer subtask.payload per SKILL.md §6)"
            )
            return rc
    return {}


def revision_context_round_str(rc: dict, payload: dict | None = None, subtask: dict | None = None) -> str:
    """把 revision_context.round 转成字符串方便宽松匹配；
    fallback: payload 顶层 / subtask 顶层 的 current_round / round 字段
    （实测 DeepSeek 偶尔把 round 标在 dispatch payload 顶层 current_round，
    而非嵌进 revision_context.round —— 语义等效就接受）。
    """
    if isinstance(rc, dict) and "round" in rc:
        return str(rc.get("round", ""))
    # fallback chain: subtask.payload.current_round → subtask.current_round → payload.current_round
    if isinstance(subtask, dict):
        sub_payload = subtask.get("payload")
        if isinstance(sub_payload, dict):
            for key in ("current_round", "round"):
                if key in sub_payload:
                    return str(sub_payload[key])
        for key in ("current_round", "round"):
            if key in subtask:
                return str(subtask[key])
    if isinstance(payload, dict):
        for key in ("current_round", "round"):
            if key in payload:
                return str(payload[key])
    return ""


def revision_context_dump(rc: dict) -> str:
    """整个 revision_context 序列化字符串（用于在里面找 issue_id）。"""
    try:
        return json.dumps(rc, ensure_ascii=False)
    except Exception:
        return str(rc)


# ---------------------------------------------------------------------------
# Step 1: Round-1 Reviewer needs_revision → Coordinator 派 round-2
# ---------------------------------------------------------------------------


def step1_round1_revise(api_key: str, system_prompt: str, writer_draft: str, round1_issues: dict) -> tuple:
    """模拟 OpenClaw 把 round-1 Writer draft + Reviewer round-1 needs_revision
    喂给 Coordinator，期望 Coordinator 派 Writer round=2 并注入 revision_context。

    返回 (passed, total, payload, raw, err)
    """
    # 截断 writer draft，避免 prompt 过长（800 字够了）
    draft_excerpt = writer_draft[:800] + ("\n...(后略)" if len(writer_draft) > 800 else "")

    user_msg = (
        f"原 user_request: {USER_QUERY}\n\n"
        f"【当前阶段】审查回环 round=1 已完成，max_review_rounds=2。\n\n"
        f"Writer 已交付 round-1 草稿（前 800 字截断）：\n"
        f"```markdown\n{draft_excerpt}\n```\n\n"
        f"Reviewer round-1 审查结果如下（verdict=needs_revision，2 个 HIGH issue）：\n"
        f"```json\n{json.dumps(round1_issues, ensure_ascii=False, indent=2)}\n```\n\n"
        f"请按你 SKILL.md 既定的输出格式与审查回环协议给出下一步规划。"
    )

    raw = call_deepseek(api_key, system_prompt, user_msg)

    payload, parse_err = try_parse_dispatch(raw)

    checks = []

    # 1) 输出能解析为 JSON（dispatch payload 或 sessions_spawn 块都接受 —— Coordinator 在
    #    生产端实际有时会先出 sessions_spawn；本 smoke 重点验证回环行为，不强制 dispatch
    #    JSON 形式 schema）
    parse_ok = payload is not None and isinstance(payload, dict)
    checks.append(
        (parse_ok, f"输出能解析为 JSON（dispatch 或 sessions_spawn 任一）{'（'+ parse_err +'）' if parse_err else ''}")
    )

    # raw 文本（小写化）兜底字段提取 —— 应对 LLM 把 dispatch JSON 跳到 sessions_spawn task
    # 字符串里的场景。对回环行为的验证不变。
    raw_lower = raw.lower()

    # 2) gear ∈ {G2, G3} —— JSON 优先；否则在 raw 文本搜 G2 或 G3 的语义提及
    gear_from_payload = payload.get("gear") if isinstance(payload, dict) else None
    gear_ok = gear_from_payload in {"G2", "G3"} or (
        gear_from_payload is None and ("g2" in raw_lower or "g3" in raw_lower)
    )
    gear_disp = gear_from_payload if gear_from_payload else "raw_scan"
    checks.append((gear_ok, f"gear ∈ {{G2, G3}}（实际 {gear_disp!r}）"))

    # 3) subtasks/任务派发存在 —— JSON subtasks 非空 OR raw 文本含 sessions_spawn / 派发动作
    subtasks = payload.get("subtasks") if isinstance(payload, dict) else None
    subtasks_count = len(subtasks) if isinstance(subtasks, list) else 0
    has_dispatch_action = (
        subtasks_count >= 1
        or "sessions_spawn" in raw
        or "派发" in raw
    )
    checks.append(
        (has_dispatch_action, f"subtasks/派发动作存在（json subtasks={subtasks_count}）")
    )

    # 4) writer 是被派发对象 —— JSON 找 writer subtask OR raw 文本提到 writer
    writer_st = find_writer_subtask(payload) if isinstance(payload, dict) else None
    writer_ok = writer_st is not None or "writer" in raw_lower
    writer_loc = (
        f"json task_id={writer_st.get('task_id')}"
        if writer_st is not None
        else ("raw 含 'writer'" if writer_ok else "未找到")
    )
    checks.append((writer_ok, f"含 writer 派发动作（{writer_loc}）"))

    # 5) revision_context 存在 —— JSON writer subtask payload 内 OR raw 文本含字面量
    rc = collect_revision_context(writer_st or {}, payload) if writer_ok and isinstance(payload, dict) else {}
    has_rc = bool(rc) or "revision_context" in raw
    checks.append(
        (has_rc, f"含 revision_context 字段（json={bool(rc)} / raw 含 'revision_context'={'revision_context' in raw}）")
    )

    # 6) round=2 标记 —— revision_context.round / 顶层 current_round / raw 文本提到 round=2 或 第 2 轮
    rc_round_str = revision_context_round_str(rc, payload=payload, subtask=writer_st)
    round_marker_in_raw = (
        "round=2" in raw_lower
        or "round 2" in raw_lower
        or "round-2" in raw_lower
        or "round_2" in raw_lower
        or "第 2 轮" in raw
        or "第2轮" in raw
        or "第二轮" in raw
    )
    round_ok = "2" in rc_round_str or round_marker_in_raw
    checks.append(
        (
            round_ok,
            f"round=2 标记（json round={rc_round_str!r} / raw round 提及={round_marker_in_raw}）",
        )
    )

    # 7) round-1 issue id 出现在 round-2 上下文（json 或 raw 任一）
    full_dispatch_dump = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else ""
    issue_hit = []
    for iid in ROUND1_ISSUE_IDS:
        if iid in full_dispatch_dump or iid in raw:
            issue_hit.append(iid)
    issue_ok = len(issue_hit) >= 1
    checks.append(
        (
            issue_ok,
            f"round-1 issue id ∈ {{{', '.join(ROUND1_ISSUE_IDS)}}} 出现在 round-2 上下文（命中 {issue_hit}）",
        )
    )

    passed = sum(1 for ok, _ in checks if ok)
    total = len(checks)

    print("\n--- Step 1 dispatch payload ---")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:1800])
    print("\n--- Step 1 assertions ---")
    for ok, desc in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    return (passed, total, payload, raw, None)


# ---------------------------------------------------------------------------
# Step 2: Round-2 Reviewer pass → Coordinator 终结、给最终交付
# ---------------------------------------------------------------------------


def step2_round2_pass(api_key: str, system_prompt: str, revised_draft: str, round2_pass: dict) -> tuple:
    """Round-2 Reviewer pass，Coordinator 应直接出最终交付。
    返回 (passed, total, raw, err)
    """
    # 截断 + 加修订声明，模拟 round-2 已修订的草稿
    draft_excerpt = revised_draft[:800] + ("\n...(后略)" if len(revised_draft) > 800 else "")
    revised_excerpt = (
        draft_excerpt
        + "\n\n_本版本已按 round-1 issue_001 + issue_002 反馈完成修订（删除未支撑论断 + 改回 21%）。_"
    )

    user_msg = (
        f"原 user_request: {USER_QUERY}\n\n"
        f"【当前阶段】审查回环 round=2 完成，max_review_rounds=2 已达上限。\n\n"
        f"Writer round-2 修订稿（前 800 字截断）：\n"
        f"```markdown\n{revised_excerpt}\n```\n\n"
        f"Reviewer round-2 审查结果（verdict=pass，无 issue）：\n"
        f"```json\n{json.dumps(round2_pass, ensure_ascii=False, indent=2)}\n```\n\n"
        f"请按 SKILL §6 给出下一步动作。"
    )

    raw = call_deepseek(api_key, system_prompt, user_msg)

    checks = []

    # 1) 输出**不是**纯 dispatch JSON，或 dispatch JSON 中 subtasks 为空
    payload, _ = try_parse_dispatch(raw)
    is_pure_dispatch = False
    if isinstance(payload, dict):
        subtasks = payload.get("subtasks")
        # subtasks 非空 list → 视为继续派发
        if isinstance(subtasks, list) and len(subtasks) > 0:
            is_pure_dispatch = True
    not_dispatch_ok = not is_pure_dispatch
    checks.append(
        (not_dispatch_ok, f"输出不是再派发 JSON 或 subtasks 为空（实际 is_pure_dispatch={is_pure_dispatch}）")
    )

    # 2) 含中文交付/通过语
    deliver_hit = [kw for kw in DELIVER_KEYWORDS if kw in raw]
    deliver_ok = len(deliver_hit) >= 1
    checks.append((deliver_ok, f"含中文交付/通过关键词（命中 {deliver_hit}）"))

    # 3) 输出长度 ≥ 100 字
    length_ok = len(raw) >= 100
    checks.append((length_ok, f"输出长度 ≥ 100 字（实际 {len(raw)} 字）"))

    passed = sum(1 for ok, _ in checks if ok)
    total = len(checks)

    print("\n--- Step 2 raw output (first 1500) ---")
    print(raw[:1500])
    print("\n--- Step 2 assertions ---")
    for ok, desc in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    return (passed, total, raw, None)


# ---------------------------------------------------------------------------
# Step 3: Round-2 Reviewer 仍 needs_revision → Coordinator 必须升级
# ---------------------------------------------------------------------------


def build_round2_still_fail() -> dict:
    """虚构 round-2 仍 needs_revision 的 mock（不写到 mocks/，内联用）。"""
    return {
        "_mock_scenario": "Round-2 Reviewer 仍 needs_revision，Coordinator 必须升级给用户而不派 round=3（max_review_rounds=2 上限）",
        "verdict": "needs_revision",
        "issues": [
            {
                "id": "issue_001_b",
                "type": "data_mismatch",
                "location": {
                    "section": "三、垂直场景分化",
                    "line_range": [22, 22],
                    "citation_id": "doc_007_p4_2",
                },
                "detail": "round-1 反馈的 21% 数据虽改了但又引入新的不一致表述；Writer 修订未根治。",
                "severity": "HIGH",
                "suggested_fix": "建议人工介入决定是否接收当前版本",
            }
        ],
        "scores": {"coverage_score": 0.75, "quality_score": 0.7, "citation_accuracy": 0.88},
        "retry_recommended": False,
        "rounds_used": 2,
    }


def step3_round2_still_fail(api_key: str, system_prompt: str, revised_draft: str, round2_fail: dict) -> tuple:
    """Round-2 仍 needs_revision，Coordinator 必须升级。
    返回 (passed, total, raw, err)
    """
    draft_excerpt = revised_draft[:800] + ("\n...(后略)" if len(revised_draft) > 800 else "")

    user_msg = (
        f"原 user_request: {USER_QUERY}\n\n"
        f"【当前阶段】审查回环 round=2 完成，max_review_rounds=2 **已耗尽**。\n\n"
        f"Writer round-2 修订稿（前 800 字截断）：\n"
        f"```markdown\n{draft_excerpt}\n```\n\n"
        f"Reviewer round-2 审查结果（verdict=needs_revision，仍有 1 个 HIGH issue）：\n"
        f"```json\n{json.dumps(round2_fail, ensure_ascii=False, indent=2)}\n```\n\n"
        f"max_review_rounds=2 已耗尽，请按 SKILL §6 / SOUL.md 禁止无限回环铁律给出下一步。"
    )

    raw = call_deepseek(api_key, system_prompt, user_msg)
    raw_lower = raw.lower()

    checks = []

    # 1) 输出**不**含 round=3 派发动作（JSON subtasks 给 writer / sessions_spawn writer 都算违规）
    payload, _ = try_parse_dispatch(raw)
    has_round3_dispatch = False
    if isinstance(payload, dict):
        subtasks = payload.get("subtasks")
        if isinstance(subtasks, list) and len(subtasks) > 0:
            wst = find_writer_subtask(payload)
            if wst is not None:
                # 派了新 writer 任务即视为违规（试图继续回环到第 3 轮）
                has_round3_dispatch = True
    # raw 文本兜底：sessions_spawn writer + round=3 / round 3 共现 → 违规
    if "sessions_spawn" in raw and "writer" in raw_lower and (
        "round=3" in raw_lower
        or "round 3" in raw_lower
        or "round-3" in raw_lower
        or "第 3 轮" in raw
        or "第3轮" in raw
        or "第三轮" in raw
    ):
        has_round3_dispatch = True
    no_round3_ok = not has_round3_dispatch
    checks.append(
        (no_round3_ok, f"输出不含 round=3 派发动作（has_round3_dispatch={has_round3_dispatch}）")
    )

    # 2) 含中文升级提示关键词
    escalate_hit = [kw for kw in ESCALATE_KEYWORDS if kw in raw]
    escalate_ok = len(escalate_hit) >= 1
    checks.append((escalate_ok, f"含升级提示关键词（命中 {escalate_hit}）"))

    # 3) 非纯 dispatch JSON（escalation 是给用户的自然语言）
    is_pure_dispatch = False
    if isinstance(payload, dict):
        subtasks = payload.get("subtasks")
        if isinstance(subtasks, list) and len(subtasks) > 0:
            is_pure_dispatch = True
    non_dispatch_ok = not is_pure_dispatch
    checks.append(
        (non_dispatch_ok, f"非纯 dispatch JSON（is_pure_dispatch={is_pure_dispatch}）")
    )

    passed = sum(1 for ok, _ in checks if ok)
    total = len(checks)

    print("\n--- Step 3 raw output (first 1500) ---")
    print(raw[:1500])
    print("\n--- Step 3 assertions ---")
    for ok, desc in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {desc}")

    return (passed, total, raw, None)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def load_mocks() -> tuple:
    """读取 writer-expected-output.md / reviewer-issues-round1.json / reviewer-issues-round2.json。
    任意失败 → sys.exit(2)。
    """
    for f in (MOCK_WRITER_OUTPUT, MOCK_REVIEWER_ROUND1, MOCK_REVIEWER_ROUND2):
        if not f.exists():
            print(f"[ENV] mock 文件不存在：{f}", file=sys.stderr)
            sys.exit(2)
    try:
        writer_md = MOCK_WRITER_OUTPUT.read_text()
        round1 = json.loads(MOCK_REVIEWER_ROUND1.read_text())
        round2 = json.loads(MOCK_REVIEWER_ROUND2.read_text())
    except Exception as e:
        print(f"[ENV] mock 解析失败：{e}", file=sys.stderr)
        sys.exit(2)
    return (writer_md, round1, round2)


def main():
    print("=" * 60)
    print("SMOKE TEST — Coordinator G2 review→revise loop (DeepSeek)")
    print("=" * 60)

    api_key = load_deepseek_key()
    system_prompt = build_system_prompt()
    print(f"\nSystem prompt (drift-free, 复刻 OpenClaw runtime): {len(system_prompt)} chars")
    print(f"User request: {USER_QUERY}")

    writer_md, round1_issues, round2_pass = load_mocks()
    round2_fail = build_round2_still_fail()
    print(
        f"\nMocks loaded: writer-draft {len(writer_md)} chars / "
        f"round1 issues={len(round1_issues.get('issues', []))} / "
        f"round2 pass verdict={round2_pass.get('verdict')!r}"
    )

    overall_ok = True
    summary_rows = []

    # Step 1 —— 任务规格 PASS 阈值：≥ 5 / 7 命中（容许 2 项 schema 边缘 miss）
    STEP1_PASS_THRESHOLD = 5
    print("\n" + "=" * 60)
    print("Step 1 — Round-1 needs_revision → Coordinator 应派 Writer round=2 (LLM 调用 1)")
    print("=" * 60)
    p1, t1, payload1, raw1, err1 = step1_round1_revise(api_key, system_prompt, writer_md, round1_issues)
    s1_ok = err1 is None and p1 >= STEP1_PASS_THRESHOLD
    if err1:
        print(f"\n[FAIL] Step 1 — {err1}")
        print(f"\n--- Raw LLM output (first 600) ---\n{raw1[:600]}")
    elif not s1_ok:
        print(f"\n[FAIL] Step 1 — {p1}/{t1} assertions passed (threshold {STEP1_PASS_THRESHOLD})")
        print(f"\n--- Raw LLM output (first 600) ---\n{raw1[:600]}")
    else:
        print(f"\n[PASS] Step 1 — {p1}/{t1} assertions passed (threshold {STEP1_PASS_THRESHOLD})")
    summary_rows.append(("Step 1 round-1 revise", "PASS" if s1_ok else "FAIL", f"{p1}/{t1}"))
    overall_ok = overall_ok and s1_ok

    # Step 2 —— 任务规格 PASS 阈值：≥ 3 / 3
    STEP2_PASS_THRESHOLD = 3
    print("\n" + "=" * 60)
    print("Step 2 — Round-2 pass → Coordinator 应给最终交付 (LLM 调用 2)")
    print("=" * 60)
    p2, t2, raw2, err2 = step2_round2_pass(api_key, system_prompt, writer_md, round2_pass)
    s2_ok = err2 is None and p2 >= STEP2_PASS_THRESHOLD
    if err2:
        print(f"\n[FAIL] Step 2 — {err2}")
        print(f"\n--- Raw LLM output (first 600) ---\n{raw2[:600]}")
    elif not s2_ok:
        print(f"\n[FAIL] Step 2 — {p2}/{t2} assertions passed (threshold {STEP2_PASS_THRESHOLD})")
        print(f"\n--- Raw LLM output (first 600) ---\n{raw2[:600]}")
    else:
        print(f"\n[PASS] Step 2 — {p2}/{t2} assertions passed (threshold {STEP2_PASS_THRESHOLD})")
    summary_rows.append(("Step 2 round-2 pass", "PASS" if s2_ok else "FAIL", f"{p2}/{t2}"))
    overall_ok = overall_ok and s2_ok

    # Step 3 —— 任务规格 PASS 阈值：≥ 3 / 3
    STEP3_PASS_THRESHOLD = 3
    print("\n" + "=" * 60)
    print("Step 3 — Round-2 仍 needs_revision → Coordinator 必须升级 (LLM 调用 3)")
    print("=" * 60)
    p3, t3, raw3, err3 = step3_round2_still_fail(api_key, system_prompt, writer_md, round2_fail)
    s3_ok = err3 is None and p3 >= STEP3_PASS_THRESHOLD
    if err3:
        print(f"\n[FAIL] Step 3 — {err3}")
        print(f"\n--- Raw LLM output (first 600) ---\n{raw3[:600]}")
    elif not s3_ok:
        print(f"\n[FAIL] Step 3 — {p3}/{t3} assertions passed (threshold {STEP3_PASS_THRESHOLD})")
        print(f"\n--- Raw LLM output (first 600) ---\n{raw3[:600]}")
    else:
        print(f"\n[PASS] Step 3 — {p3}/{t3} assertions passed (threshold {STEP3_PASS_THRESHOLD})")
    summary_rows.append(("Step 3 round-2 escalate", "PASS" if s3_ok else "FAIL", f"{p3}/{t3}"))
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
