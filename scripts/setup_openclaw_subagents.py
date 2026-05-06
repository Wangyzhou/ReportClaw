#!/usr/bin/env python3
"""setup_openclaw_subagents.py — 一键配 reportclaw-coordinator 的 sessions_spawn 白名单。

为什么需要：
- OpenClaw runtime 默认禁止任何 agent 通过 sessions_spawn 派发到其他 agent
- 我们要让 reportclaw-coordinator 能 spawn reportclaw-retriever/writer/rewriter/reviewer
- 必须显式配置 agents.list[reportclaw-coordinator].subagents.allowAgents

跑一次即可，幂等，自动备份原文件。

使用：
    python3 scripts/setup_openclaw_subagents.py
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CONFIG = Path.home() / ".openclaw" / "openclaw.json"
ALLOW_AGENTS = [
    "reportclaw-retriever",
    "reportclaw-writer",
    "reportclaw-rewriter",
    "reportclaw-reviewer",
]
TARGET_ID = "reportclaw-coordinator"


def main() -> int:
    if not CONFIG.exists():
        print(f"[setup] {CONFIG} 不存在 — 请先跑 `openclaw onboard` 装好 OpenClaw 再来。", file=sys.stderr)
        return 1

    raw = CONFIG.read_text(encoding="utf-8")
    cfg = json.loads(raw)
    agents_list = cfg.get("agents", {}).get("list", [])
    coord = next((a for a in agents_list if a.get("id") == TARGET_ID), None)

    if coord is None:
        print(f"[setup] agents.list 里没找到 id={TARGET_ID} — 请确认 reportclaw 5 agents 已部署。", file=sys.stderr)
        print("[setup] 已知 agents:", [a.get("id") for a in agents_list], file=sys.stderr)
        return 2

    existing = set((coord.get("subagents") or {}).get("allowAgents") or [])
    needed = set(ALLOW_AGENTS)
    if existing >= needed:
        print(f"[setup] reportclaw-coordinator.subagents.allowAgents 已包含全部 4 个子 agent，跳过。")
        return 0

    backup = CONFIG.with_name(f"openclaw.json.bak.before-reportclaw-allow-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(CONFIG, backup)
    print(f"[setup] 备份 -> {backup.name}")

    coord.setdefault("subagents", {})["allowAgents"] = sorted(existing | needed)
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[setup] 已写入 allowAgents = {sorted(existing | needed)}")
    print("[setup] 完成。下次 openclaw agent 调用就能 sessions_spawn 派发子 agent。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
