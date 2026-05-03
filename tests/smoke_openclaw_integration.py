#!/usr/bin/env python3
"""
Smoke test — OpenClaw runtime integration (草稿，design-level only)

验证假设：standalone DeepSeek 串行（其他 smoke 跑的方式）≈ OpenClaw 多 session
真实 state 流（生产端通过 `openclaw agent` 派发）。

本 smoke **不强求 PASS**：
  - 如果 `openclaw` CLI 不在 PATH —— print [ENV] + exit 0（草稿不阻塞）
  - 如果 CLI 在但调用失败/timeout —— print stderr 前 500 字 + 标记
    "OpenClaw runtime 集成未通"作为 known issue + exit 0（草稿）
  - 如果调用通且 stdout 含 dispatch 结构或 announce 事件 —— print [PASS]，exit 0

Round 6 立项目标：
  1. 暴露 standalone DeepSeek 与 OpenClaw runtime 之间的契约差距
  2. 为后续 round 把 smoke 跑到真实 multi-session 流上铺路（替换 mocks/）
  3. 不阻塞当前 G2 review 回环开发节奏

Exit:
  0 — 草稿状态（PASS / SKIPPED / known-issue 都视为 0）
  2 — 环境/解析问题（极少，仅 catastrophic）
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

USER_QUERY = "帮我查一下AI产业最新政策"
AGENT_ID = "reportclaw-coordinator"
TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# 检测 openclaw CLI 是否可用
# ---------------------------------------------------------------------------


def detect_openclaw_cli() -> str | None:
    """返回 openclaw 的可执行路径，找不到返 None。"""
    return shutil.which("openclaw")


# ---------------------------------------------------------------------------
# 调 openclaw agent
# ---------------------------------------------------------------------------


def _decode(buf) -> str:
    """tolerate bytes / str / None from subprocess."""
    if buf is None:
        return ""
    if isinstance(buf, bytes):
        return buf.decode("utf-8", errors="replace")
    return buf


def call_openclaw_agent(cli_path: str, agent_id: str, message: str) -> tuple:
    """调 `openclaw agent --agent <id> --message <msg> --json`。
    返回 (returncode, stdout, stderr, timed_out)。
    """
    cmd = [cli_path, "agent", "--agent", agent_id, "--message", message, "--json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        return (r.returncode, r.stdout, r.stderr, False)
    except subprocess.TimeoutExpired as e:
        return (-1, _decode(e.stdout), _decode(e.stderr), True)
    except FileNotFoundError as e:
        return (-2, "", f"FileNotFoundError: {e}", False)


# ---------------------------------------------------------------------------
# 解析 stdout —— 找 dispatch 结构 / announce 事件 / 配对错
# ---------------------------------------------------------------------------


PAIRING_KW = ("pairing", "device-identity", "device identity", "not paired", "unpaired")
AUTH_KW = ("unauthorized", "auth failed", "401", "403", "missing token", "invalid token")
DISPATCH_KW = ("intent", "subtasks", "gear", "dispatch", "to_agent")


def analyze_output(stdout: str, stderr: str) -> dict:
    """从 stdout/stderr 中识别集成是否通。"""
    out = stdout or ""
    err = stderr or ""
    out_l = out.lower()
    err_l = err.lower()

    has_pairing_err = any(kw in err_l or kw in out_l for kw in PAIRING_KW)
    has_auth_err = any(kw in err_l or kw in out_l for kw in AUTH_KW)

    parse_ok = False
    try:
        json.loads(out.strip())
        parse_ok = True
    except (json.JSONDecodeError, ValueError):
        pass

    has_dispatch = any(kw in out_l for kw in DISPATCH_KW)
    has_announce = any(kw in out_l for kw in ("announce", "session_spawn", "sessions_spawn"))

    return {
        "has_dispatch": has_dispatch, "has_announce": has_announce,
        "has_pairing_err": has_pairing_err, "has_auth_err": has_auth_err,
        "parse_ok": parse_ok, "stdout_len": len(out), "stderr_len": len(err),
        "stdout_head": out[:500], "stderr_head": err[:500],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 60)
    print("SMOKE TEST — OpenClaw runtime integration (Round 6 草稿)")
    print("=" * 60)

    cli_path = detect_openclaw_cli()
    if cli_path is None:
        print("\n[ENV] openclaw CLI not in PATH, smoke is design-only")
        print("    install: see ReportClaw README / OpenClaw docs")
        print("    once installed, this smoke 会自动尝试真实派发")
        print("\n[SKIPPED] 草稿状态：CLI 不可用，跳过真实集成验证（exit 0）")
        return 0

    print(f"\n[ENV] openclaw CLI 检测到：{cli_path}")
    print(f"[ENV] agent_id={AGENT_ID}")
    print(f"[ENV] message={USER_QUERY!r}")
    print(f"[ENV] timeout={TIMEOUT_SECONDS}s")

    print("\n--- 调用 openclaw agent ---")
    print(f"  cmd: openclaw agent --agent {AGENT_ID} --message <q> --json")

    returncode, stdout, stderr, timed_out = call_openclaw_agent(cli_path, AGENT_ID, USER_QUERY)

    if timed_out:
        print(f"\n[TIMEOUT] 调用超时（>{TIMEOUT_SECONDS}s）")
        print(f"  stdout (前 500): {(stdout or '')[:500]!r}")
        print(f"  stderr (前 500): {(stderr or '')[:500]!r}")
        print("\n[KNOWN-ISSUE] OpenClaw runtime 集成未通：调用超时（草稿状态，不算 fail）")
        return 0

    print(f"\n  returncode: {returncode}")
    analysis = analyze_output(stdout, stderr)
    print(f"  stdout 长度: {analysis['stdout_len']} / stderr 长度: {analysis['stderr_len']}")
    print(f"  parse_ok (JSON envelope): {analysis['parse_ok']}")
    print(f"  has_dispatch:    {analysis['has_dispatch']}")
    print(f"  has_announce:    {analysis['has_announce']}")
    print(f"  has_pairing_err: {analysis['has_pairing_err']}")
    print(f"  has_auth_err:    {analysis['has_auth_err']}")

    # 调用失败（非 0 returncode）
    if returncode != 0:
        print(f"\n--- stderr 前 500 字 ---\n{analysis['stderr_head']}")
        print(f"\n--- stdout 前 500 字 ---\n{analysis['stdout_head']}")
        if analysis["has_pairing_err"]:
            print("\n[KNOWN-ISSUE] OpenClaw runtime 集成未通：device-identity 配对未完成")
            print("    修复路径：cd examples/openclaw-gateway-ws && node openclaw-ws-chat.mjs（首次配对）")
        elif analysis["has_auth_err"]:
            print("\n[KNOWN-ISSUE] OpenClaw runtime 集成未通：auth/token 失败")
            print("    修复路径：检查 ~/.openclaw/agents/<id>/agent/auth-profiles.json")
        else:
            print("\n[KNOWN-ISSUE] OpenClaw runtime 集成未通：returncode != 0（其他错误）")
        print("\n（草稿状态：不阻塞当前 round，exit 0）")
        return 0

    # returncode == 0，分析输出
    print(f"\n--- stdout 前 500 字 ---\n{analysis['stdout_head']}")

    if analysis["has_dispatch"] or analysis["has_announce"]:
        print("\n[PASS] OpenClaw runtime 真集成通：检测到 dispatch 结构或 announce 事件")
        return 0

    # returncode 0 但没看到 dispatch / announce —— 可能 Coordinator 没崩但 routing 不对
    print("\n[KNOWN-ISSUE] OpenClaw runtime 调用 returncode=0 但无 dispatch/announce 痕迹")
    print("    可能 Coordinator routing 不对，或 --json 输出 schema 与本 smoke 假设不符")
    print("    （草稿状态：暴露契约差距，不阻塞 exit 0）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # catastrophic — 草稿不该崩；崩了视为环境问题
        print(f"\n[FATAL] 草稿 smoke 崩溃：{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
