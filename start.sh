#!/bin/bash
# 本地识译：启动服务并自动打开浏览器
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"

export TRANSLATE_MODEL_PATH="${TRANSLATE_MODEL_PATH:-$ROOT/backend/models/translategemma-4b-it.Q4_K_M.gguf}"

PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}/"

open_url() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" 2>/dev/null || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" 2>/dev/null || true
  else
    echo "未检测到桌面浏览器，请手动访问：$URL"
  fi
}

# 已在本机运行则不重复启动
if curl -s -m 3 -o /dev/null "http://127.0.0.1:${PORT}/api/health"; then
  echo "服务已在运行：$URL"
  open_url
  exit 0
fi

echo "启动 go-ocr 服务（端口 ${PORT}）..."
uvicorn app.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT

# 等待服务就绪（最多 30s）
for _ in $(seq 1 30); do
  if curl -s -m 2 -o /dev/null "http://127.0.0.1:${PORT}/api/health"; then
    break
  fi
  sleep 1
done

open_url
echo "服务运行中（Ctrl+C 退出）。访问地址：$URL"
wait "$SERVER_PID"
