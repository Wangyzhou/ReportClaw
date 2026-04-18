# mediaclaw 参考项目消化笔记

> 来源：`/t5/mediaclaw-ref/`（87k行，11个workspace）
> 消化时间：2026-04-17
> 用途：T5 Agent 设计参考，避免重复阅读原始材料
> 消化者：主模型一次性扫描 + 关键skill抽样阅读

---

## 1. Agent 标准文件结构（9文件模板）

每个 Agent 工作区包含以下文件，T5 应对齐：

| 文件 | 职责 | T5 是否必抄 |
|------|------|-----------|
| BOOTSTRAP.md | 首次启动的"自我发现"对话脚本 | ❌ T5 身份固定 |
| SOUL.md | 核心信念+工作节奏+禁止事项+强制语言规则 | ✅ 必抄 |
| IDENTITY.md | 名字/形象/Emoji | ⭕ 可选（前端UI加分） |
| USER.md | 用户画像 | ⭕ 改为"报告读者画像" |
| TOOLS.md | 本地配置（API/路径/账号别名） | ⭕ 改为"知识库分类清单" |
| AGENTS.md | 工作手册：任务分类表+派发模板+禁忌 | ✅ 必抄 |
| MEMORY.md | 用户规则+历史教训表 | ✅ 必抄 |
| HEARTBEAT.md | 启动红线+任务清单+命名规范 | ✅ 必抄 |
| AGENT-ROUTING.md（仅Coordinator） | 其他Agent路由速查表 | ✅ 必抄 |

## 2. 核心元能力 Skills（可直接移植）

来自 `workspace-coordinator/skills/`，共22个。T5 前期用得上的 7 个：

| Skill | 解决的问题 | T5 用法 |
|-------|-----------|---------|
| **task-progress-manager** | MCP任务树可视化 | 前端中间区显示Agent进度 |
| **file-artifact-manager** | 文件产出强制登记 | 报告版本管理 |
| **verification-before-completion** | 交付前自检 | 每个Agent返回前自查 |
| **fact-check-before-trust** | 数字/日期/实体二次核实 | Reviewer核心skill，对应"事实性错误检测" |
| **self-improving** | 三层记忆（HOT/WARM/COLD） | Reviewer写教训日志 |
| **brainstorming** | ≥3方案+4维评分 | Coordinator模糊需求时触发 |
| **loop-circuit-breaker** | 相同错误重试2次熔断 | 防审查回环死循环 |

后期可加：dangerous-action-guard / context-window-management / memory-graph-builder / find-skills / skill-creator

## 3. 通信机制关键约束

**派发强制模板**：
```
# [任务类型]任务
## 主题 / 任务描述 / 交付标准 / 输出位置
请完成后通知我。
```

**汇报格式**：`完成汇报 → 任务/状态/成果摘要/输出位置/问题`

**硬规则**：
- 子Agent 之间禁止直接传递任务，必须经 Coordinator 中转
- Coordinator 禁止递归调用自己
- Coordinator 禁止抢子Agent的活
- 选项用 `%%中文选项 中文描述%%`，不超过4个
- 隐式skill（task-progress/file-artifact）后台调用不输出

## 4. 最值得抄的 5 个设计

### (1) SOUL.md 人格化模板
57行包含：核心信念5条 + 工作节奏4阶段 + 禁止事项7条 + 原则4条。每条一句话+一段解释。

### (2) MEMORY.md 历史教训表
三列：`事故 / 根因 / 教训`。每次踩坑写一条，下次自动避免。
示例：`web_search 无意义调用 / 协调员越权自己搜 / 搜索一律委托 subagent`

### (3) AGENTS.md 任务分类调度表
横轴 Agent，纵轴任务类型，单元格 ✅/❌。下方写每种任务必须确认的字段（受众/平台/配图）。

### (4) HEARTBEAT.md 启动红线
每次任务前必读 5 条红线 + 6 步启动清单。

### (5) fact-check-before-trust（金牌skill）
三步：提取所有claim → 给每个claim打置信度 → 低/中置信度逐个核查。直击评分"事实性错误检测"。

## 5. 不该照搬的部分

- 媒体行业skill：graphic-article / wechat-topic-selector / mam-image-searcher / xhs-images / postiz / clip-generate
- 三个Agent：publisher / media-producer / art-designer（T5不需要）
- content-writer 的多平台format（T5是B端报告，不要小红书emoji）
- BOOTSTRAP 流程（身份固定）
- WhatsApp/Telegram 连接
- Obsidian 同步（T5用RAGFlow）

## 6. 意外发现

1. **memory-graph-builder**：夜间cron把扁平 MEMORY.md 构建成知识图谱，检测重复/矛盾/陈旧，省30-60% token。→ **T5 可复用到"历史报告关系图谱"**
2. **subagent-driven-development**：`exec command:"claude --print '[spec]'" background:true` 真并行多进程。→ **Retriever 可并行检索多 category**
3. **schedule-notification + cron-hygiene**：Agent 自己有 cron 能力 → **T5 支持"每周日报告定时生成"**
4. **dispatcher.md 关键词→Agent 路由表**：比 LLM 判意图更快更准 → **Coordinator 的 fast-path**
5. **proactive-agent-skill 的 WAL Protocol**：写前日志，session 重启不丢上下文 → **T5 长任务（5000字报告）防中途崩溃**
6. **SKILL.md 的 `metadata: {"openclaw": {"always": true}}`**：标记"始终加载" → **T5 核心 skill 都该这样**

## 7. 关键文件位置索引

需要读原文时的路径索引：

- Coordinator SOUL: `mediaclaw-ref/workspace-coordinator/SOUL.md`
- Coordinator AGENTS: `mediaclaw-ref/workspace-coordinator/AGENTS.md`
- Coordinator AGENT-ROUTING: `mediaclaw-ref/workspace-coordinator/AGENT-ROUTING.md`
- Coordinator MEMORY（教训表）: `mediaclaw-ref/workspace-coordinator/MEMORY.md`
- Coordinator HEARTBEAT: `mediaclaw-ref/workspace-coordinator/HEARTBEAT.md`
- 22个元skill目录: `mediaclaw-ref/workspace-coordinator/skills/`
- Reviewer SOUL: `mediaclaw-ref/workspace-reviewer/SOUL.md`
- fact-check skill: `mediaclaw-ref/workspace-analyst/skills/fact-check-before-trust/SKILL.md`
- content-research-writer: `mediaclaw-ref/workspace-analyst/skills/content-research-writer/SKILL.md`
- quality-check: `mediaclaw-ref/workspace-reviewer/skills/quality-check/SKILL.md`

## 8. T5 落地 ROI 排序

| 优先级 | 动作 | 对应评分维度 |
|-------|-----|------------|
| 🔴 P0 | 5 个 SOUL.md 升级（核心信念+禁止事项+强制语言规则） | 报告质量 25% |
| 🔴 P0 | 5 个 Agent 加 AGENTS.md（任务分类调度表） | 报告质量 25% |
| 🔴 P0 | Coordinator 加 AGENT-ROUTING.md + HEARTBEAT.md + MEMORY.md | 系统完整性 10% |
| 🔴 P0 | `agents/_shared/` 放 4 元skill：task-progress-manager / verification-before-completion / fact-check-before-trust / loop-circuit-breaker | 检索准确性 25% |
| 🟡 P1 | self-improving（Reviewer 写教训日志） | 创新故事点 |
| 🟡 P1 | brainstorming（Coordinator 模糊需求） | 报告质量 15% |
| 🟢 P2 | memory-graph-builder / schedule-notification | 答辩未来迭代 |
