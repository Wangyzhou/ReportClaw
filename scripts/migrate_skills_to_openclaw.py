#!/usr/bin/env python3
"""
Migrate flat skill layout to MediaClaw/OpenClaw layout.

Before:
  agents/<agent>/skills/<skill>.md

After:
  agents/<agent>/skills/<skill>/SKILL.md   (with frontmatter)

Rollback:
  python3 scripts/migrate_skills_to_openclaw.py --rollback

Idempotent: rerunning forward is a no-op once migrated.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"

# Directories containing flat skill .md files to migrate.
SKILL_PARENTS = [
    AGENTS_DIR / "coordinator" / "skills",
    AGENTS_DIR / "retriever" / "skills",
    AGENTS_DIR / "writer" / "skills",
    AGENTS_DIR / "rewriter" / "skills",
    AGENTS_DIR / "reviewer" / "skills",
    AGENTS_DIR / "_shared",
]


def extract_description(body: str, fallback: str) -> str:
    """Take first non-empty non-heading line as description, trimmed."""
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.startswith(">"):
            continue
        # Strip surrounding markdown emphasis / quotes.
        s = re.sub(r"^[*_`\"'\s]+|[*_`\"'\s]+$", "", s)
        if s:
            return s[:200]
    return fallback


def build_frontmatter(name: str, description: str) -> str:
    safe_desc = description.replace('"', "'")
    return (
        "---\n"
        f"name: {name}\n"
        f"description: \"{safe_desc}\"\n"
        "---\n\n"
    )


def already_migrated(flat_md: Path) -> bool:
    """True if a directory with the same stem exists and has SKILL.md."""
    target_dir = flat_md.with_suffix("")
    return target_dir.is_dir() and (target_dir / "SKILL.md").is_file()


def migrate_forward(skill_parent: Path, dry_run: bool) -> list[tuple[Path, Path]]:
    migrated = []
    if not skill_parent.is_dir():
        return migrated
    for flat in sorted(skill_parent.glob("*.md")):
        # Skip READMEs and any SKILL.md already at this level.
        if flat.name.upper() in {"README.MD", "SKILL.MD"}:
            continue
        if already_migrated(flat):
            continue

        name = flat.stem
        body = flat.read_text(encoding="utf-8")
        description = extract_description(body, fallback=name.replace("_", " "))
        fm = build_frontmatter(name=name, description=description)

        # If body already starts with its own frontmatter, preserve it verbatim
        # (don't double-wrap).
        new_content = body if body.lstrip().startswith("---\n") else fm + body

        target_dir = flat.with_suffix("")
        target_file = target_dir / "SKILL.md"

        print(f"  {flat.relative_to(ROOT)}  ->  {target_file.relative_to(ROOT)}")
        if dry_run:
            continue

        target_dir.mkdir(parents=True, exist_ok=False)
        target_file.write_text(new_content, encoding="utf-8")
        flat.unlink()
        migrated.append((flat, target_file))
    return migrated


def rollback(skill_parent: Path, dry_run: bool) -> list[tuple[Path, Path]]:
    restored = []
    if not skill_parent.is_dir():
        return restored
    for skill_dir in sorted(p for p in skill_parent.iterdir() if p.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        body = skill_file.read_text(encoding="utf-8")
        # Strip frontmatter we added (leave others alone by checking marker).
        stripped = re.sub(
            r"^---\nname:[^\n]+\ndescription:[^\n]*\n---\n\n", "", body, count=1
        )
        flat_target = skill_dir.with_suffix(".md")
        print(f"  {skill_file.relative_to(ROOT)}  ->  {flat_target.relative_to(ROOT)}")
        if dry_run:
            continue
        flat_target.write_text(stripped, encoding="utf-8")
        shutil.rmtree(skill_dir)
        restored.append((skill_file, flat_target))
    return restored


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollback", action="store_true", help="Reverse the migration.")
    ap.add_argument("--dry-run", action="store_true", help="Print plan, change nothing.")
    args = ap.parse_args()

    action = "ROLLBACK" if args.rollback else "FORWARD"
    mode = " (dry-run)" if args.dry_run else ""
    print(f"== Skill layout migration: {action}{mode} ==")

    total = 0
    for parent in SKILL_PARENTS:
        print(f"\n[{parent.relative_to(ROOT)}]")
        changes = (
            rollback(parent, args.dry_run)
            if args.rollback
            else migrate_forward(parent, args.dry_run)
        )
        total += len(changes)

    print(f"\nDone. {total} file(s) {'would be ' if args.dry_run else ''}processed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
