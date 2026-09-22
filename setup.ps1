# go-ocr 一键安装（Windows）：装依赖 + 检查 GGUF + 预拉 Paddle 模型
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "===== go-ocr 安装 (Windows) ====="
Write-Host "安装目录：$ROOT"

Write-Host ""
Write-Host "[1/3] 安装 Python 依赖..."
pip install -r "$ROOT\backend\requirements.txt"

Write-Host ""
$GGUF = "$ROOT\backend\models\translategemma-4b-it.Q4_K_M.gguf"
if (Test-Path $GGUF) {
  Write-Host "[2/3] 翻译模型已存在：$GGUF"
} else {
  Write-Host "[2/3] 翻译模型缺失（需 2.49GB GGUF），请从以下来源获取并放到 $GGUF ："
  Write-Host "  - HuggingFace 官方：https://huggingface.co/google/translategemma-4b-it （Quantizations 页选 Q4_K_M，需 HF 账号接受条款）"
  Write-Host "  - 或用命令： huggingface-cli download google/translategemma-4b-it --include "*Q4_K_M*" --local-dir $ROOT\backend\models"
  exit 1
}

Write-Host ""
Write-Host "[3/3] 预下载 Paddle OCR 模型（首次运行自动下载约 3GB 到 ~/.paddlex/）..."
python -c "import os; os.environ.setdefault('PADDLE_HUB_HOME', os.path.expanduser('~/.paddlex')); from paddleocr import Pipeline; Pipeline(pipeline_name='PP-StructureV3', use_doc_orientation_classify=False, use_doc_unwarping=False, use_layout_detection=True, use_ocr=True, use_formula_recognition=False, use_chart_recognition=False, use_seal_recognition=False, use_seal_detection=False); print('Paddle OCR 模型下载完成。')"

Write-Host ""
Write-Host "===== 安装完成 ====="
Write-Host "启动方式：  double-click start.ps1  （自动打开浏览器）"
Write-Host "首次 OCR 识别约 3–6 分钟/页（small 模型）"
