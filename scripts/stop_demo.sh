#!/usr/bin/env bash
# stop_demo.sh — 关掉 start_demo.sh 启的 3 进程
set -uo pipefail

PID_FILE="/tmp/reportclaw-demo.pids"

if [ -f "$PID_FILE" ]; then
  while IFS='=' read -r name pid; do
    [ -z "$pid" ] && continue
    if ps -p "$pid" >/dev/null 2>&1; then
      echo "killing $name ($pid)..."
      kill "$pid" 2>/dev/null || true
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi

# 兜底: 杀任何还监听 8080/8081/3000 的进程
for port in 8080 8081 3000; do
  pids=$(lsof -nPi ":$port" -t 2>/dev/null | head -3 || true)
  if [ -n "$pids" ]; then
    echo "兜底 kill port $port ($pids)..."
    echo "$pids" | xargs -r kill 2>/dev/null || true
  fi
done

echo "✓ ReportClaw demo 已停止"
