#!/usr/bin/env bash
# start_demo.sh — 一键启动 ReportClaw 本机 demo（3 进程）
#
# 跑前提：
#   - openjdk@21 装在 /opt/homebrew/opt/openjdk@21
#   - openclaw-chat-ui/.build/openclaw-chat-ui-0.1.0-exec.jar 已 build
#   - frontend/node_modules/ 已 npm install
#   - DeepSeek key 在 ~/.openclaw/agents/main/agent/auth-profiles.json
#
# 启动顺序：
#   1. Spring Boot (port 8080) — sessions/kb/tasks API
#   2. Python chat server (port 8081) — 5-Agent DeepSeek 真链路
#   3. Vite (port 3000) — React 前端 (前台跑，Ctrl+C 退出整个 demo)
#
# 停止：scripts/stop_demo.sh 或 Ctrl+C 后手动 kill

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="${LOG_DIR:-/tmp}"
SPRING_LOG="$LOG_DIR/reportclaw-spring.log"
CHAT_LOG="$LOG_DIR/reportclaw-chat.log"

# 颜色
if [ -t 1 ]; then
  BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

step() { echo "${BOLD}▶ $1${RESET}"; }
ok()   { echo "  ${GREEN}✓${RESET} $1"; }
warn() { echo "  ${YELLOW}⚠${RESET} $1"; }
fail() { echo "  ${RED}✗${RESET} $1"; exit 1; }

# Pre-flight checks
step "Pre-flight 检查"

JAVA_BIN="/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java"
[ -x "$JAVA_BIN" ] || fail "Java 21 未装。运行: brew install openjdk@21"
ok "Java 21 ($("$JAVA_BIN" --version | head -1))"

JAR="openclaw-chat-ui/.build/openclaw-chat-ui-0.1.0-exec.jar"
[ -f "$JAR" ] || fail "Spring Boot jar 未编译: $JAR。运行: cd openclaw-chat-ui && JAVA_HOME=... mvn -s settings.xml clean package"
ok "Spring Boot jar 已编译"

[ -d "frontend/node_modules" ] || fail "frontend/node_modules/ 不存在。运行: cd frontend && npm install"
ok "frontend deps 已装"

KEY_FILE="$HOME/.openclaw/agents/main/agent/auth-profiles.json"
[ -f "$KEY_FILE" ] || fail "DeepSeek key 文件不存在: $KEY_FILE"
DS_PREFIX=$(python3 -c "import json; print(json.load(open('$KEY_FILE'))['profiles']['deepseek:default']['key'][:8])")
ok "DeepSeek key (prefix: ${DS_PREFIX}***)"

# 端口检查 + 清理
step "端口 + 进程清理"
for port in 8080 8081 3000; do
  if lsof -nPi ":$port" >/dev/null 2>&1; then
    pids=$(lsof -nPi ":$port" -t 2>/dev/null | head -3 | tr '\n' ' ')
    warn "port $port 已被占用 (PID: $pids)，杀掉..."
    echo "$pids" | xargs -r kill 2>/dev/null || true
    sleep 2
    if lsof -nPi ":$port" >/dev/null 2>&1; then
      fail "port $port 仍被占用，请手动 kill -9 后重试"
    fi
  fi
done
ok "8080 / 8081 / 3000 全空闲"

# Start Spring Boot
step "启 Spring Boot (:8080)"
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
PATH="$JAVA_HOME/bin:$PATH" \
nohup "$JAVA_BIN" -jar "$JAR" > "$SPRING_LOG" 2>&1 &
SPRING_PID=$!
echo "  Spring Boot PID: $SPRING_PID"
for i in {1..15}; do
  sleep 1
  if curl -s -o /dev/null --max-time 2 http://localhost:8080/api/tasks; then
    ok "Spring Boot 健康 (用了 ${i}s)"
    break
  fi
  if [ "$i" = "15" ]; then
    fail "Spring Boot 15s 内没起来。查 $SPRING_LOG"
  fi
done

# Start Python chat server
step "启 Python chat server (:8081, 5-Agent DeepSeek 真链路)"
export USE_DEEPSEEK_SHIM=1
export PYTHONPATH="$ROOT/scripts:${PYTHONPATH:-}"
nohup python3 scripts/local_chat_server.py > "$CHAT_LOG" 2>&1 &
CHAT_PID=$!
echo "  chat server PID: $CHAT_PID"
for i in {1..10}; do
  sleep 1
  if lsof -nPi :8081 >/dev/null 2>&1; then
    ok "chat server 健康 (用了 ${i}s)"
    break
  fi
  if [ "$i" = "10" ]; then
    fail "chat server 10s 内没起来。查 $CHAT_LOG"
  fi
done

# 写 PID 文件供 stop_demo.sh 用
PID_FILE="/tmp/reportclaw-demo.pids"
echo "spring=$SPRING_PID" > "$PID_FILE"
echo "chat=$CHAT_PID" >> "$PID_FILE"
ok "PID 写到 $PID_FILE"

step "全部就绪"
cat <<EOF

  ${GREEN}✅ ReportClaw 本机 demo 启动完成${RESET}

  Spring Boot     :8080   (PID $SPRING_PID, log: $SPRING_LOG)
  Chat Server     :8081   (PID $CHAT_PID, log: $CHAT_LOG)
  React (vite)    :3000   待启动 ↓

  现在前台启 Vite (Ctrl+C 退 vite, 后端继续跑)：

    cd frontend && npm run dev

  浏览器开 http://localhost:3000

  停止 demo（关 Spring Boot + chat server）:
    bash scripts/stop_demo.sh
    或: kill $SPRING_PID $CHAT_PID

EOF
