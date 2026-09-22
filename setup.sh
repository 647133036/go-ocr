#!/bin/bash
# go-ocr 一键安装：装 Python 依赖 + 下载翻译模型 + 准备 Paddle OCR 模型
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "===== go-ocr 安装 ====="
echo "安装目录：$ROOT"

# 1. 装 Python 依赖
echo ""
echo "[1/3] 安装 Python 依赖..."
pip install -r "$ROOT/backend/requirements.txt"

# 2. 检查/下载翻译模型 GGUF
GGUF="$ROOT/backend/models/translategemma-4b-it.Q4_K_M.gguf"
if [ -f "$GGUF" ]; then
  echo "[2/3] 翻译模型已存在：$GGUF"
else
  echo "[2/3] 翻译模型缺失，需要 2.49GB GGUF，请从以下来源获取并放到 $GGUF："
  echo "  - HuggingFace 官方：https://huggingface.co/google/translategemma-4b-it （Quantizations 页选 Q4_K_M，需 HF 账号接受条款）"
  echo "  或用命令： huggingface-cli download google/translategemma-4b-it --include '*Q4_K_M*' --local-dir $ROOT/backend/models"
  exit 1
fi

# 3. 触发 Paddle OCR 模型下载（首次运行自动下载，这里预拉一次）
echo "[3/3] 预下载 Paddle OCR 模型（首次运行自动下载约 3GB 到 ~/.paddlex/）..."
python3 - <<'PY'
import os
os.environ.setdefault("PADDLE_HUB_HOME", os.path.expanduser("~/.paddlex"))
try:
    from paddleocr import Pipeline
    Pipeline(
        pipeline_name="PP-StructureV3",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_layout_detection=True,
        use_ocr=True,
        use_formula_recognition=False,
        use_chart_recognition=False,
        use_seal_recognition=False,
        use_seal_detection=False,
    )
    print("Paddle OCR 模型下载完成。")
except Exception as e:
    print(f"Paddle 预下载失败（首次启动时仍会自动下载）：{e}")
PY

echo ""
echo "===== 安装完成 ====="
echo "启动方式：  bash $ROOT/start.sh   （自动打开浏览器）"
echo "或直接：   双击 start.sh          （需桌面环境）"
echo "首次 OCR 识别约 3–6 分钟/页（small 模型）"
