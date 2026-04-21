#!/usr/bin/env python3
"""
One-way sync: git agent definitions -> OpenClaw-managed workspaces.

Source of truth:
  ReportClaw/agents/<name>/            (git, this repo)

Target (OpenClaw-managed, MUST already exist via `openclaw agents add`):
  ~/.openclaw/workspace-reportclaw-<name>/

This script copies user-authored files (SOUL.md / AGENTS.md / HEARTBEAT.md /
IDENTITY.md / MEMORY.md / TOOLS.md / USER.md / AGENT-ROUTING.md / skills/**)
and leaves OpenClaw runtime files untouched (config/, .openclaw/,
BOOTSTRAP.md, scripts/, sessions/).

Why this script exists:
  We learned the hard way that pointing `openclaw agents add --workspace`
  at a git repo is destructive — `agents delete` trashes the whole
  directory, and `agents add` overwrites user files with stubs. The safe
  model is: git is the source, OpenClaw workspaces are derived copies.

Usage:
  # dry-run (default), shows what would change
  python3 scripts/sync_to_openclaw_workspace.py

  # actually apply
  python3 scripts/sync_to_openclaw_workspace.py --apply

  # just one agent
  python3 scripts/sync_to_openclaw_workspace.py --agent coordinator --apply
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_BASE = REPO_ROOT / "agents"
DST_BASE = Path.home() / ".openclaw"

AGENT_NAMES = ["coordinator", "retriever", "writer", "rewriter", "reviewer"]

# Files/dirs OpenClaw manages — never overwrite or delete on the target side.
# These are additive on the target; we rsync WITHOUT --delete to keep them.
OPENCLAW_RUNTIME = {
    ".openclaw",
    "config",
    "scripts",
    "sessions",
    "BOOTSTRAP.md",
    # .git is excluded in case OpenClaw ever init'd one inside the source dir
    # (it has; we clean it, but defensive exclude is cheap):
    ".git",
    ".DS_Store",
}


def target_workspace(agent: str) -> Path:
    return DST_BASE / f"workspace-reportclaw-{agent}"


def ensure_target_exists(agent: str) -> Path:
    t = target_workspace(agent)
    if not t.is_dir():
        print(
            f"  ERROR: {t} does not exist.\n"
            f"  Register the agent first with OpenClaw, e.g.:\n"
            f"    openclaw agents add reportclaw-{agent} --model minimax/MiniMax-M2.7 --non-interactive",
            file=sys.stderr,
        )
        sys.exit(2)
    return t


def sync_one(agent: str, apply: bool) -> int:
    src = SRC_BASE / agent
    if not src.is_dir():
        print(f"  SKIP {agent}: source {src} missing")
        return 0
    dst = ensure_target_exists(agent)

    # rsync flags:
    #   -a : archive (preserve structure)
    #   --itemize-changes : print what would change
    #   --omit-dir-times : avoid touching mtime on OpenClaw-managed dirs
    #   NO --delete: we never remove files from target (keeps OpenClaw runtime safe)
    #   --exclude-from via per-item --exclude for OpenClaw runtime entries
    cmd = [
        "rsync",
        "-a",
        "--itemize-changes",
        "--omit-dir-times",
    ]
    for name in OPENCLAW_RUNTIME:
        cmd += ["--exclude", name]
    if not apply:
        cmd.append("--dry-run")
    # Trailing slash on src = copy contents, not the dir itself.
    cmd += [f"{src}/", f"{dst}/"]

    print(f"\n== {agent}:  {src}  ->  {dst} ==")
    print("  " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        for line in result.stdout.splitlines():
            print(f"    {line}")
    if result.returncode != 0:
        print(f"  rsync exited {result.returncode}", file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr, file=sys.stderr)
    return result.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually sync. Default is dry-run.")
    ap.add_argument(
        "--agent",
        choices=AGENT_NAMES + ["all"],
        default="all",
        help="Which agent to sync (default: all).",
    )
    args = ap.parse_args()

    if not (REPO_ROOT / "agents").is_dir():
        print(f"ERROR: expected {REPO_ROOT}/agents/ to exist", file=sys.stderr)
        return 2

    targets = AGENT_NAMES if args.agent == "all" else [args.agent]
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== sync_to_openclaw_workspace: {mode} ==")

    rc = 0
    for agent in targets:
        this = sync_one(agent, apply=args.apply)
        rc = rc or this

    if not args.apply:
        print("\n(dry-run) rerun with --apply to actually copy files.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
