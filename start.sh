#!/bin/bash
# OCR 版式还原 + 本地离线翻译 服务启动脚本
set -e

cd "$(dirname "$0")/backend"

export TRANSLATE_MODEL_PATH="${TRANSLATE_MODEL_PATH:-$(pwd)/models/translategemma-4b-it.Q4_K_M.gguf}"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
