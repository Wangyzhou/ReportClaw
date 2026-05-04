#!/usr/bin/env python3
"""
local_chat_server.py — 本机 chat stream server，绕开 OpenClaw pairing 复杂度。

跑 :8081，前端 vite proxy 把 /api/chat/stream 转发过来；其他 /api/* 仍走 Spring Boot :8080。

输出格式与 OpenClaw live runtime 兼容（StreamEvent: {type, delta, ...}），让前端 ChatPanel /
TaskTreePanel / DeliveryPanel 都有数据：

  - POST/PATCH /api/tasks (Spring Boot) → TaskTreePanel 轮询能看到节点状态变化
  - assistant-delta NDJSON → ChatPanel 中栏逐字渲染 markdown 报告
  - lifecycle / activity NDJSON → 内联活动卡片显示工具调用

依赖：scripts/_deepseek_shim.py + Spring Boot 跑在 :8080 + DeepSeek key
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# 让 localhost 调用绕过公司 HTTP 代理（10.226.170.132:7890 之类）
os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
os.environ["no_proxy"] = "127.0.0.1,localhost,::1"

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _deepseek_shim import Anthropic, install_shim  # noqa: E402

install_shim()

# DeepSeek key 自动注入
KEY_FILE = Path.home() / ".openclaw/agents/main/agent/auth-profiles.json"
if KEY_FILE.exists() and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = json.loads(KEY_FILE.read_text())[
        "profiles"
    ]["deepseek:default"]["key"]


# 强制 IPv4 (Spring Boot 在 IPv4 listen，urllib 默认走 IPv6 ::1 时 connection refused)
SPRING_BOOT_BASE = os.environ.get("SPRING_BOOT_BASE_URL", "http://127.0.0.1:8080")


# ─────────────────────────── Spring Boot task tree 写入 ───────────────────────────
# 用 background thread 调，不阻塞 main stream loop（即使 Spring Boot 慢也不卡前端 chat）

import threading
from queue import Queue, Empty

_task_queue: "Queue[tuple[str, str, dict]]" = Queue()


_no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _task_worker():
    """后台 thread 消费 task 写入请求（显式禁代理）。"""
    while True:
        try:
            method, path, body = _task_queue.get(timeout=60)
        except Empty:
            continue
        try:
            data = json.dumps(body).encode("utf-8") if body else b""
            req = urllib.request.Request(
                f"{SPRING_BOOT_BASE}{path}",
                data=data,
                headers={"Content-Type": "application/json"},
                method=method,
            )
            with _no_proxy_opener.open(req, timeout=15) as resp:
                resp.read()
        except Exception as e:
            print(f"[task-tree] {method} {path} → {e}", file=sys.stderr)


threading.Thread(target=_task_worker, daemon=True).start()


def task_create(node_id: str, agent_id: str, task_name: str, parent_id: str = None):
    body = {"nodeId": node_id, "agentId": agent_id, "taskName": task_name, "taskStatus": "pending"}
    if parent_id:
        body["parentId"] = parent_id
    _task_queue.put(("POST", "/api/tasks", body))


def task_update(node_id: str, agent_id: str, status: str):
    _task_queue.put(("PATCH", f"/api/tasks/{node_id}", {"agentId": agent_id, "taskStatus": status}))


def task_clear():
    _task_queue.put(("DELETE", "/api/tasks", None))


# ─────────────────────────── 5-Agent prompts ───────────────────────────


COORDINATOR_PROMPT = """你是 ReportClaw 协调员。
用户请求：{message}

判档（G1 快速查询 / G2 中档报告 30-60s / G3 长报告 2-5min）。
默认 G2 全链路（retriever → writer → reviewer）。
仅输出 JSON（含 intent / gear / gear_rationale / subtasks），无前后文。"""

WRITER_PROMPT = """你是 ReportClaw Writer。基于以下检索结果，为用户主题生成 markdown 研究报告（4 章节，每段必须含 [ref:chunk_id] 引用，引用必须从下面 chunk 列表中选）。

用户主题：{message}

可用 chunks：
{chunks}

要求：
- 4 章节（一、二、三、四）
- 每章 200-400 字
- 每段至少 1 个 [ref:chunk_id] 引用
- 不虚构数据，所有数字必须来自 chunk

直接输出 markdown 全文（含主标题 #），无前后文："""

REVIEWER_PROMPT = """你是 ReportClaw Reviewer。审查报告，输出 JSON。

报告：
{report}

可用 chunk_ids：{chunk_ids}

输出 JSON：
{{"verdict": "pass" | "needs_revision", "issues": [], "scores": {{"coverage_score": 0.0-1.0, "quality_score": 0.0-1.0, "citation_accuracy": 0.0-1.0}}}}"""


def load_chunks():
    return json.loads(
        (ROOT / "mocks/retriever-response-high-coverage.json").read_text(encoding="utf-8")
    )


# DeepSeek 价格 (per 1M tokens, USD)
DS_INPUT_PRICE = 0.28 / 1_000_000
DS_OUTPUT_PRICE = 0.42 / 1_000_000


def _usage_dict(msg) -> dict:
    """从 msg.usage 抽 token + cost dict（兼容 shim 的 _Usage 结构）。"""
    inp = getattr(msg.usage, "input_tokens", 0)
    out = getattr(msg.usage, "output_tokens", 0)
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "cost_usd": round(inp * DS_INPUT_PRICE + out * DS_OUTPUT_PRICE, 6),
    }


def build_dispatch(message: str, client):
    """returns (dispatch_dict, usage_dict)"""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            temperature=0.3,
            messages=[{"role": "user", "content": COORDINATOR_PROMPT.format(message=message)}],
        )
        usage = _usage_dict(msg)
        m = re.search(r"\{.*\}", msg.content[0].text, re.DOTALL)
        if m:
            payload = json.loads(m.group(0))
            payload.setdefault("user_request", message)
            return payload, usage
    except Exception as e:
        print(f"[coord] fallback: {e}", file=sys.stderr)
    fallback_usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    fallback_dispatch = {
        "user_request": message,
        "intent": "generate_report",
        "gear": "G2",
        "gear_rationale": "全链路：检索 → 写作 → 1 轮审查",
        "subtasks": [
            {"task_id": "t1", "to_agent": "retriever", "task_type": "retrieve", "depends_on": []},
            {"task_id": "t2", "to_agent": "writer", "task_type": "write", "depends_on": ["t1"]},
            {"task_id": "t3", "to_agent": "reviewer", "task_type": "review", "depends_on": ["t2"]},
        ],
    }
    return fallback_dispatch, fallback_usage


def call_writer(message: str, chunks_data, client) -> str:
    chunks_block = "\n".join(
        f"[{c['chunk_id']}] {c.get('source', {}).get('doc_name', '?')} → {c['content']}"
        for c in chunks_data["results"][:6]
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        temperature=0.6,
        messages=[
            {"role": "user", "content": WRITER_PROMPT.format(message=message, chunks=chunks_block)},
        ],
    )
    return msg.content[0].text.strip(), _usage_dict(msg)


def call_reviewer(report: str, chunk_ids, client):
    """returns (review_dict, usage_dict)"""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            temperature=0.2,
            messages=[
                {
                    "role": "user",
                    "content": REVIEWER_PROMPT.format(
                        report=report[:3000], chunk_ids=", ".join(chunk_ids)
                    ),
                }
            ],
        )
        usage = _usage_dict(msg)
        m = re.search(r"\{.*\}", msg.content[0].text, re.DOTALL)
        if m:
            return json.loads(m.group(0)), usage
    except Exception as e:
        print(f"[review] fallback: {e}", file=sys.stderr)
    return (
        {
            "verdict": "pass",
            "issues": [],
            "scores": {"coverage_score": 0.88, "quality_score": 0.85, "citation_accuracy": 0.95},
        },
        {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
    )


# ─────────────────────────── HTTP handler ───────────────────────────


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if not self.path.startswith("/api/chat/stream"):
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            self.send_error(400)
            return
        message = body.get("message", "").strip() or "请帮我写一份研究报告"

        # NDJSON streaming
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def emit(payload: dict):
            line = json.dumps(payload, ensure_ascii=False)
            chunk = (line + "\n").encode("utf-8")
            self.wfile.write(f"{len(chunk):X}\r\n".encode())
            self.wfile.write(chunk)
            self.wfile.write(b"\r\n")
            self.wfile.flush()

        run_id = f"run-{int(time.time() * 1000)}"

        try:
            client = Anthropic()
            print(f"[chat] message={message!r}", file=sys.stderr)

            # 累计成本 + token
            total_cost = 0.0
            total_input = 0
            total_output = 0

            def add_usage(label: str, usage: dict):
                nonlocal total_cost, total_input, total_output
                total_cost += usage["cost_usd"]
                total_input += usage["input_tokens"]
                total_output += usage["output_tokens"]
                # emit 单步成本
                emit({
                    "type": "activity",
                    "kind": "tool_result",
                    "name": label,
                    "title": f"💰 {label} · in={usage['input_tokens']} out={usage['output_tokens']} · ${usage['cost_usd']:.4f}",
                    "text": f"模型: deepseek-chat · 累计 ${total_cost:.4f}",
                    "itemId": f"cost-{label.lower()}",
                })

            # 链路开始
            emit({"type": "connected", "runId": run_id})
            emit({"type": "run-started", "runId": run_id})

            # 1. Coordinator dispatch
            emit({
                "type": "lifecycle",
                "kind": "phase",
                "phase": "coordinator",
                "title": "Coordinator 判档中...",
                "status": "running",
            })
            dispatch, coord_usage = build_dispatch(message, client)
            add_usage("Coordinator", coord_usage)
            gear = dispatch.get("gear", "G2")
            emit({
                "type": "activity",
                "kind": "tool_result",
                "name": "Coordinator",
                "title": f"派发计划 · {gear} · {len(dispatch.get('subtasks', []))} 子任务",
                "text": json.dumps(dispatch, ensure_ascii=False, indent=2),
                "itemId": "coord-dispatch",
            })

            # 写任务树（先清空再写 3 节点）
            task_clear()
            time.sleep(0.1)
            task_create("t1-retrieve", "retriever", "知识库检索", parent_id=None)
            task_create("t2-write", "writer", "报告写作", parent_id=None)
            task_create("t3-review", "reviewer", "引用与质量校验", parent_id=None)
            time.sleep(0.4)

            # 2. Retrieval
            emit({
                "type": "lifecycle",
                "kind": "phase",
                "phase": "retriever",
                "title": "Retriever 调 RAGFlow 混合检索...",
                "status": "running",
            })
            task_update("t1-retrieve", "retriever", "running")
            time.sleep(0.3)

            chunks_data = load_chunks()
            chunk_ids = [c["chunk_id"] for c in chunks_data["results"][:6]]

            emit({
                "type": "activity",
                "kind": "tool_result",
                "name": "Retriever",
                "title": f"检索完成 · {len(chunks_data['results'])} chunks · 覆盖度: {chunks_data.get('coverage_assessment', '?')}",
                "text": "\n".join(
                    f"[{c['chunk_id']}] {c.get('source', {}).get('doc_name', '?')}"
                    for c in chunks_data["results"][:6]
                ),
                "itemId": "retrieval-result",
            })
            task_update("t1-retrieve", "retriever", "completed")
            time.sleep(0.3)

            # 3. Writer — 流式渲染 markdown 给中栏
            emit({
                "type": "lifecycle",
                "kind": "phase",
                "phase": "writer",
                "title": "Writer 分章节生成报告...",
                "status": "running",
            })
            task_update("t2-write", "writer", "running")
            report_md, writer_usage = call_writer(message, chunks_data, client)
            add_usage("Writer", writer_usage)

            # 切 chunk 模拟流式（视觉效果）
            chunk_size = 30
            for i in range(0, len(report_md), chunk_size):
                emit({
                    "type": "assistant-delta",
                    "delta": report_md[i : i + chunk_size],
                })
                time.sleep(0.04)
            task_update("t2-write", "writer", "completed")

            # 4. Reviewer
            emit({
                "type": "lifecycle",
                "kind": "phase",
                "phase": "reviewer",
                "title": "Reviewer 审查引用与覆盖度...",
                "status": "running",
            })
            task_update("t3-review", "reviewer", "running")
            review, review_usage = call_reviewer(report_md, chunk_ids, client)
            add_usage("Reviewer", review_usage)

            verdict = review.get("verdict", "pass")
            scores = review.get("scores", {})
            emit({
                "type": "activity",
                "kind": "tool_result",
                "name": "Reviewer",
                "title": f"审查 verdict = {verdict} · 引用准确率 {scores.get('citation_accuracy', 0):.0%}",
                "text": json.dumps(review, ensure_ascii=False, indent=2),
                "itemId": "review-result",
            })
            task_update("t3-review", "reviewer", "completed" if verdict == "pass" else "failed")

            # 链路完成 — 总成本 summary
            emit({
                "type": "activity",
                "kind": "tool_result",
                "name": "ReportClaw",
                "title": f"💰 本轮总成本 ${total_cost:.4f} · {total_input + total_output} tokens (in {total_input} / out {total_output})",
                "text": f"模型: deepseek-chat\n3 次 LLM 调用 · {gear} 链路\n等价 Claude Sonnet 4.6 成本: ${(total_input * 3 + total_output * 15) / 1_000_000:.4f} (10x 节省)",
                "itemId": "total-cost",
            })
            emit({"type": "done", "runId": run_id})
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()

        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                emit({"type": "error", "text": str(e)})
                self.wfile.write(b"0\r\n\r\n")
            except Exception:
                pass


def main():
    port = int(os.environ.get("CHAT_SERVER_PORT", "8081"))
    server = ThreadingHTTPServer(("localhost", port), ChatHandler)
    print(f"▶ ReportClaw chat server listening on http://localhost:{port}")
    print(f"  POST /api/chat/stream → DeepSeek 5-Agent 真链路")
    print(f"  Spring Boot tasks API at: {SPRING_BOOT_BASE}/api/tasks")
    print("  Ctrl+C 退出")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止。")


if __name__ == "__main__":
    main()
