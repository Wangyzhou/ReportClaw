# OpenClaw 接入适应化说明

> 分支：`adapt/openclaw-yata`
> 作者：林宇泰
> 日期：2026-04-21
> 目的：把 ReportClaw 的 5 个 Agent 调整到 OpenClaw 原生可加载格式，并提供安全的同步路径

## ⚠️ 集成模型（读这一节，不要跳过）

**不要**让 `openclaw agents add --workspace` 直接指向 git 仓库里的 `agents/<name>/`。
实测（2026-04-21 本机 OpenClaw 2026.4.15）：

- `agents add` 时 OpenClaw 用它的默认模板 stub **覆盖** SOUL.md / AGENTS.md / HEARTBEAT.md 等用户文件
- `agents add` 时 OpenClaw 在 workspace 下 `git init` 了一个嵌套 `.git/`
- `agents delete` 时 OpenClaw 把**整个 workspace 目录移到废纸篓**（不是只删配置）

所以正确模型是**单向同步**：

```
git 仓库 (ReportClaw/agents/<x>/)       ← 源头
          │
          ▼  rsync --exclude=OpenClaw运行时文件
~/.openclaw/workspace-reportclaw-<x>/   ← OpenClaw 管理
```

工具：`scripts/sync_to_openclaw_workspace.py`（见下）

---

## 1. 本次改了什么

全部对标 MediaClaw 现有结构（已在 OpenClaw 跑通的唯一样本）。

### 1.1 skill 目录格式（影响 25 个 skill）

```
# 之前（扁平）
agents/writer/skills/section_writing.md

# 现在（MediaClaw 约定）
agents/writer/skills/section_writing/SKILL.md
```

每个 SKILL.md 顶部自动加了 frontmatter：

```yaml
---
name: section_writing
description: "按章节逐一生成内容..."   # 自动从原文首段抽取
---
```

### 1.2 补齐每个子 Agent 的 7 个文件（对齐 MediaClaw workspace-\*）

|  | 之前 | 现在 |
|---|---|---|
| coordinator | SOUL / AGENTS / AGENT-ROUTING / HEARTBEAT / MEMORY + skills | 补齐 **IDENTITY / TOOLS / USER** |
| retriever | 仅 SOUL + skills | 补齐 **AGENTS / HEARTBEAT / IDENTITY / MEMORY / TOOLS / USER** |
| writer | 仅 SOUL + skills | 同上 |
| rewriter | 仅 SOUL + skills | 同上 |
| reviewer | 仅 SOUL + skills | 同上 |

补齐的 `AGENTS.md` 和 `TOOLS.md` 是有内容的（任务分派表 + skill 列表）；`IDENTITY.md / MEMORY.md` 是空文件（MediaClaw 的生产环境里也是空的，OpenClaw 运行时写入）；`HEARTBEAT.md` 是 5 行注释占位；`USER.md` 是 Eddie 的 profile 模板。

### 1.3 修 registry.yaml

- ❌ 5 处 `soul: agents/xxx/soul.md`（小写）→ ✅ `SOUL.md`（Linux 大小写敏感会 404）
- ❌ `envelope_schema: docs/a2a-message-schema.md`（文件已标 deprecated）→ 删除；payload 契约指向 `docs/payload-schema.md`
- ➕ 每个 agent 显式列出 `skills: [...]` 和 `shared_skills: [...]`（34 条路径，脚本已校验全部 resolve），OpenClaw 不用 glob 猜
- ➕ 新增 `workspace: agents/xxx` 字段，便于 OpenClaw 按 workspace-\* 约定映射

### 1.4 清理

- 移除了 `docs/mediaclaw-digest.md` / `docs/mediaclaw-digest-v2.md` / `docs/dogfood-shifu-feedback.md`（这些是 Eddie 的私人研究笔记，不是 ReportClaw 交付物）
- 删除 `docs/a2a-message-schema.md.deprecated`（envelope 归 OpenClaw，这份文档已作废）
- 新增 `.env.example`（smoke test 前置）

---

## 2. 改动工具

三个脚本，都幂等可重跑：

```bash
# 把 skills/<x>.md 转成 skills/<x>/SKILL.md + frontmatter
python3 scripts/migrate_skills_to_openclaw.py

# 反向：SKILL.md 退回扁平 .md
python3 scripts/migrate_skills_to_openclaw.py --rollback

# 为子 Agent 补齐 MediaClaw 的 7 件套（已存在的文件绝不覆盖）
python3 scripts/generate_agent_stubs.py

# 单向同步：git agent 定义 → ~/.openclaw/workspace-reportclaw-<x>/
# 默认 dry-run，加 --apply 才真同步；--agent <name> 只同步一个
python3 scripts/sync_to_openclaw_workspace.py
python3 scripts/sync_to_openclaw_workspace.py --apply
python3 scripts/sync_to_openclaw_workspace.py --agent coordinator --apply
```

同步前置：5 个 OpenClaw agent 必须已经注册并存在对应 workspace 目录。在本机上已经有（`openclaw agents list` 能看到 `reportclaw-coordinator/retriever/writer/rewriter/reviewer`）。王亚洲那边若没有，先跑：

```bash
for a in coordinator retriever writer rewriter reviewer; do
  openclaw agents add reportclaw-$a --model minimax/MiniMax-M2.7 --non-interactive
done
```
（**注意不要加 `--workspace` 参数指向 git 目录，让 OpenClaw 自己在 `~/.openclaw/` 下建独立 workspace**；然后再跑 sync 脚本把 git 里的定义拷贝过去。）

---

## 3. 假设 & 回滚路径

### 假设（来自 `/Users/eddie/Desktop/Workspace/mediaclaw/` 现有结构反推）

1. OpenClaw 扫描 `skills/*/SKILL.md`，不扫扁平 `.md`
2. SKILL.md frontmatter 要求至少有 `name` + `description`
3. agent 目录必须齐 SOUL/AGENTS/HEARTBEAT/IDENTITY/MEMORY/TOOLS/USER 7 件套
4. 顶层 `agents/_shared/` 不是 OpenClaw 原生约定 —— 通过 `registry.yaml` 的 `shared_skills` 字段显式引用

### 如果有一条假设错了

每一项都独立可撤：

| 出错项 | 回滚命令 |
|--------|---------|
| skill 目录格式 | `python3 scripts/migrate_skills_to_openclaw.py --rollback` |
| 子 agent 多出来的文件 | `git checkout master -- agents/<agent>/` |
| registry.yaml | `git checkout master -- agents/registry.yaml` |
| 全盘放弃 | `git checkout master && git branch -D adapt/openclaw-yata` |

master 分支保持王亚洲首次 pull 的状态，没动。

---

## 4. 还需王亚洲确认 / 处理

| # | 事项 | 责任方 | 来源 |
|---|------|-------|------|
| 1 | RAGFlow 字段映射透传（10 行代码） | 王亚洲 | HANDOFF §3 P0-1 |
| 2 | 验证 OpenClaw loader 是否认我们的 `workspace: agents/<name>` 映射（如果它硬编码 `workspace-<name>/` 目录名，需要做一个 symlink 层） | 王亚洲 | 本次适应化的唯一假设 |
| 3 | 确认 `shared_skills` 字段在 registry 是否被 OpenClaw 识别；不识别就把 `_shared/*/SKILL.md` 复制进各 agent 的 `skills/`（有脚本可自动化） | 王亚洲 | §1.2 假设 4 |

---

## 5. 验证

- ✅ `registry.yaml` 34 条 skill 路径 + 10 个 agent 文件路径全部 resolve（Python 脚本校验）
- ✅ Smoke test 不读 skill 文件（只读 `mocks/`），所以本次改动不影响 `tests/smoke_*.py` 的 7/7 验证
- ✅ 本机 OpenClaw 2026.4.15 已识别 5 个 `reportclaw-*` agent 注册（`openclaw agents list` 能列出）
- ✅ 本机 rsync 同步脚本 dry-run 通过：5 个 agent 共 40+ 个文件变更计划，路径格式 `skills/<name>/SKILL.md` 正确
- 🟡 实际跑一次 agent turn（`openclaw agent --local --agent reportclaw-coordinator -m "..."`）—— 未测，需要 sync --apply + provider auth 就绪

---

## 6. 合并流程建议

```bash
# 王亚洲端
git fetch origin
git checkout adapt/openclaw-yata
# 在 OpenClaw 里试挂载；如果能加载 5 个 Agent 且 skill 发现无误
git checkout master
git merge adapt/openclaw-yata
git push
```

如果 OpenClaw 在 adapt 分支上报错，把错误贴回来，我这边按错误一次性改完再合。
