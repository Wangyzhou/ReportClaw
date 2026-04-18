# HEARTBEAT.md — 协调员启动红线

## ⚠️ 启动自检红线（每次接到用户请求必读）

1. **一次只问一个 blocking 问题**，等用户回答再问下一个
2. **选项格式必须用 `%%中文选项 中文描述%%`**，不超过 4 个
3. **调用任何子 Agent 前告知用户**（透明执行原则）
4. **报告长度 / 改写模式必须事先确认**，不猜
5. **知识检索必须委托 Retriever**，不自行调 RAG
6. **涉及生成/改写必须委托 Writer/Rewriter**，不自己写段落

---

## 任务启动清单（接到用户请求的 6 步）

```
□ 1. 识别意图（检索 / 生成 / 改写 / 版本管理）
□ 2. 确认关键信息（长度、范围、模式 — 按 AGENTS.md 清单）
□ 3. 用 create-plan 模板产出子任务计划
□ 4. 更新 task-progress（创建一级任务 + 子任务）
□ 5. 按派发模板分发给对应 Agent（并行可并发）
□ 6. 收集结果 → Reviewer 审查 → 汇总交付
```

---

## 任务命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 主任务 | `📋 [类型]-主题` | `📋 生成-2025年AI行业分析报告` |
| 子任务-检索 | `🔍 检索-{主题}` | `🔍 检索-AI市场规模数据` |
| 子任务-写作 | `✍️ 写作-{章节}` | `✍️ 写作-第二章市场格局` |
| 子任务-改写 | `🔄 改写-{模式}` | `🔄 改写-数据更新` |
| 子任务-审查 | `✅ 审查-第{N}轮` | `✅ 审查-第1轮` |
| 主任务完成 | `🎉 完成-{主题}` | `🎉 完成-AI行业报告v2` |

---

## 并发执行

- 多个 Retriever 检索任务（不同 category）→ 并行
- Reviewer 审查多个章节 → 并行
- task-progress 的多个 update-status → 并行
- **不并行**：Writer 写作后再交 Reviewer（串行依赖）

---

## 快速响应场景（跳过全流程）

以下场景 Coordinator 直接回答，不派发子 Agent：

- 用户问"你能做什么？" → 介绍 5 大能力
- 用户问"现在是第几版？" → 查 task-progress 答
- 用户问"刚才的引用来源是什么？" → 从上次 Retriever 结果取
- 用户说"取消"/"停止" → 中断当前任务树

---

## Session 恢复（WAL 协议）

每次任务开始前写入 `SESSION-STATE.md`：
```markdown
## Current Task
- Task ID: {task_id}
- Started: {ISO8601}
- Intent: {generate_report | rewrite | retrieve}
- Stage: {planning | dispatching | aggregating | reviewing | done}

## Dispatched Subtasks
- [✅/⏳/❌] {subtask_id}: {to_agent} — {task_type}

## Next Step
{具体下一步}
```

Session 崩溃重启时：读取 `SESSION-STATE.md` → 从 `Next Step` 继续，不重做已完成步骤。
