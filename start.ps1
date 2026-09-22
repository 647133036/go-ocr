# go-ocr 一键启动（Windows）：起服务 + 自动开默认浏览器
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ROOT\backend"

$env:TRANSLATE_MODEL_PATH = if ($env:TRANSLATE_MODEL_PATH) { $env:TRANSLATE_MODEL_PATH } else { "$ROOT\backend\models\translategemma-4b-it.Q4_K_M.gguf" }
$PORT = 8000
$URL  = "http://127.0.0.1:$PORT/"

function Open-Browser {
  # 用 Windows 自带 start 命令打开默认浏览器
  Start-Process $URL
}

# 已运行则不重复启动
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/api/health" -TimeoutSec 3 -UseBasicParsing
  Write-Host "服务已在运行：$URL"
  Open-Browser
  exit 0
} catch {
  # 服务未起，继续
}

Write-Host "启动 go-ocr 服务（端口 $PORT）..."
$proc = Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","$PORT" -PassThru -NoNewWindow
Start-Sleep -Seconds 1

# 等健康检查就绪（最多 30s）
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/api/health" -TimeoutSec 2 -UseBasicParsing
    $ok = $true
    break
  } catch {
    Start-Sleep -Seconds 1
  }
}

Open-Browser
Write-Host "服务运行中（Ctrl+C 退出）。访问地址：$URL"

# 监听退出
try {
  $proc.WaitForExit()
} catch {
  # 用户 Ctrl+C
}
Write-Host "正在停止服务..."
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
