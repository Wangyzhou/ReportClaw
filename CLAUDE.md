# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ReportClaw is an AI agent team for intelligent report writing, built for the T5 competition. It provides knowledge-base-driven report generation and 4-mode "rewrite from draft" capabilities. The system runs on the OpenClaw platform.

The project has two distinct layers:
- **Agent definitions** (`agents/`) — pure markdown prompt/persona files loaded by OpenClaw
- **Chat UI** (`openclaw-chat-ui/`) — Spring Boot 3 / Java 21 streaming chat interface connecting to OpenClaw Gateway

## Build & Run Commands

### Chat UI (Spring Boot)

Requires Java 21. Maven wrapper is not included; use system `mvn`.

```bash
# Build (from openclaw-chat-ui/)
cd openclaw-chat-ui
mvn -s settings.xml clean package

# Run dev server (port 8080)
mvn -s settings.xml spring-boot:run

# Environment overrides
OPENCLAW_GATEWAY_URL=ws://192.168.4.188:18789   # Gateway WebSocket
SERVER_PORT=8080
OPENCLAW_DEVICE_TOKEN=...                        # Optional: explicit device token
```

### Smoke Tests (Python)

Prerequisites: `pip install anthropic python-dotenv`, `ANTHROPIC_API_KEY` in `.env` at project root.

```bash
# Run all 7 smoke tests
cd tests
for f in smoke_*.py; do python3 "$f"; done

# Run a single test
python3 tests/smoke_section_writing.py
```

Exit codes: 0 = pass, 1 = assertion failure, 2 = environment issue.

### Node.js Gateway Example

```bash
cd examples/openclaw-gateway-ws
node openclaw-ws-chat.mjs
```

Used for initial device pairing; produces `.runtime/` files shared with the Spring Boot app.

## Architecture

### 5-Agent Team

All agent definitions live in `agents/`. Each agent has a `soul.md` (persona) and `skills/` directory (capability prompts). Deployment metadata is in `agents/registry.yaml`.

| Agent | Model | Role |
|-------|-------|------|
| **Coordinator** | sonnet-4-6 (T=0.3) | Orchestrator: gear detection, task dispatch, quality check. Never executes work directly. |
| **Retriever** | haiku-4-5 (T=0.0) | RAGFlow hybrid search, source tracking, coverage analysis |
| **Writer** | sonnet-4-6 (T=0.6) | Outline generation, section writing, style mimicking, citation insertion |
| **Rewriter** | sonnet-4-6 (T=0.4) | 4 rewrite modes: data_update, perspective_shift, content_expansion, style_conversion |
| **Reviewer** | sonnet-4-6 (T=0.2) | Citation verification, review checklist, coverage scoring |

Shared meta-skills in `agents/_shared/`: loop circuit breaker, verification-before-completion, fact-check-before-trust, WAL protocol, task progress manager.

### Gear System

Coordinator classifies requests into three gears (defined in `agents/coordinator/skills/gear_detection.md`):
- **G1**: Direct answer or Retriever only (<10s)
- **G2**: Full pipeline, 1 review round (30-60s)
- **G3**: Parallel retrieval, up to 2 review rounds (2-5min)

Dynamic upgrade: low coverage or HIGH reviewer issues trigger G2 -> G3.

### Inter-Agent Communication

Payload contracts for all 5 `task_type` values (retrieve, write, rewrite, review, dispatch) are defined in `docs/payload-schema.md`. OpenClaw handles the message envelope and transport; ReportClaw defines payload content only.

Review loop: Writer -> Reviewer -> Writer, max 2 rounds (configurable in `registry.yaml`).

### Chat UI Data Flow

1. Browser -> `POST /api/chat/stream` (NDJSON) -> Spring Boot
2. Spring Boot -> OpenClaw Gateway (WebSocket, device-identity auth with v3 signature)
3. Gateway loads agent team from `agents/registry.yaml`
4. Coordinator dispatches to agents via OpenClaw CollaborationService
5. Results stream back as `chat` events -> NDJSON -> browser

Device identity files (`.runtime/`) are shared between the Node.js example and Spring Boot app.

### Chat UI Source Structure

- `api/ChatController.java` — `GET /api/sessions`, `POST /api/chat/stream`
- `service/OpenClawGatewayService.java` — WebSocket connection, challenge/connect handshake, streaming
- `service/OpenClawDeviceStateStore.java` — Persists device identity/tokens to `.runtime/`
- `config/OpenClawProperties.java` — `@ConfigurationProperties(prefix = "openclaw")`
- `static/` — Single-page chat UI (vanilla HTML/JS/CSS)

## Key Files

- `agents/registry.yaml` — Agent deployment metadata, model assignments, tool declarations
- `docs/payload-schema.md` — All inter-agent payload contracts
- `mocks/` — Test fixtures for smoke tests (no RAGFlow dependency needed)
- `alignment-王亚洲.md` — Backend integration alignment checklist (RAGFlow field mapping)

## Conventions

- All agent prompts are written in Chinese (zh-CN). Agent output must be Chinese.
- Agents must never fabricate citations; all `[ref:chunk_id]` must trace to actual RAGFlow chunks.
- The Coordinator dispatches only; it never generates report content itself.
- RAGFlow backend endpoint is at `http://localhost:9380` (placeholder in registry.yaml).

## Team

- **林宇泰 (Eddie)**: Agent architecture, skills, Coordinator logic, frontend
- **王亚洲**: RAGFlow backend, Claw integration, communication layer
