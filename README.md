# go-ocr

本地离线 Web 应用：`PP-StructureV3` OCR 版式还原 + `Translategemma` 离线翻译，浏览器直接访问，导出 TXT / Word / Excel / PDF / JSON。

## 版本

- 当前版本：**v0.0.1**

## 功能

- **OCR 识别**（`/ocr`）：`.jpg/.jpeg/.png/.bmp/.webp/.tif/.tiff/.pdf`，最大 50MB。自动排版（标题/表格/多栏），去阴影 + CLAHE + 锐化预处理，高频错字正则纠错。
- **离线翻译**（`/translate`）：`google/translategemma`（Q4_K_M GGUF），无需联网，支持中英日法德等。
- **导出**：TXT / DOCX / XLSX / PDF / JSON。
- 两个功能独立分页，视觉风格参考 FlowConvert。

## 系统要求

- CPU：≥2 核（4 核更快，medium 模型约 4–6 分钟/页）
- 内存：≥8GB（medium 模型推理峰值贴顶；small 模型更稳）
- 无 GPU 要求；磁盘预留 ≥3GB（Paddle 模型缓存）
- Python：3.10+

## 快速开始

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 启动服务（监听 8000，自动打开浏览器）
# Linux / macOS：
bash start.sh
# Windows：
powershell -ExecutionPolicy Bypass -File start.ps1
```

访问：

- `http://localhost:8000/` — 首页
- `http://localhost:8000/ocr` — OCR 识别
- `http://localhost:8000/translate` — 离线翻译

### 一键安装（首次）

```bash
# Linux / macOS
bash setup.sh

# Windows
powershell -ExecutionPolicy Bypass -File setup.ps1
```

## 目录结构

```
backend/
  app/
    main.py            FastAPI 入口 + 异步 OCR 任务 + 静态页路由
    ocr_service.py     PP-StructureV3 + 预处理 + 纠错表 + 模型缓存
    translate_service.py  Translategemma 加载/卸载 + 推理
    export_service.py  TXT/DOCX/XLSX/PDF/JSON 导出
  static/              前端页面（ocr.html / translate.html / index.html / style.css / ocr.js / translate.js）
  models/
    translategemma-4b-it.Q4_K_M.gguf   翻译模型二进制（2.4GB，git 不追踪，需另行下载或随 Release 提供）
  requirements.txt     Python 依赖
start.sh               一键启动脚本（Linux / macOS，自动开浏览器）
setup.sh               一键安装脚本（Linux / macOS）
start.ps1              一键启动脚本（Windows PowerShell，自动开浏览器）
setup.ps1              一键安装脚本（Windows PowerShell）
```

## 依赖说明

Python 依赖（`backend/requirements.txt`）：

```
fastapi>=0.110
uvicorn[standard]>=0.29
python-multipart>=0.0.9
python-docx>=1.1.0
openpyxl>=3.1.2
PyMuPDF>=1.24.0
pillow>=10.0.0
paddlepaddle>=3.0.0
paddleocr>=3.0.0
llama-cpp-python>=0.3.0
```

二进制文件获取（git 仓库不含大文件，见 `.gitignore`）：

### 翻译模型 `translategemma-4b-it.Q4_K_M.gguf`（约 2.49GB）

- **来源**：HuggingFace 官方模型仓库 `google/translategemma-4b-it`（受限模型，需 HF 账号登录并接受 Google 使用条款）
  - 仓库页：`https://huggingface.co/google/translategemma-4b-it`
  - 该仓库 `Quantizations` 标签页下有 42 个社区量化版本，选用 `Q4_K_M` GGUF 文件（约 2.49GB）
- **获取方式**（任选其一）：
  1. HuggingFace CLI（推荐）：
     ```
     pip install -U "huggingface_hub[cli]"
     huggingface-cli login
     # 从官方仓库下载 Q4_K_M 量化版到 backend/models/
     huggingface-cli download google/translategemma-4b-it \
       --include "*Q4_K_M*" \
       --local-dir backend/models
     ```
  2. `ollama`（最省事，自动拉取量化版）：
     ```
     ollama pull google/translategemma-4b-it
     # 拉取后从 Ollama 模型目录复制 gguf 到 backend/models/
     ```
  3. 手动下载：在 `https://huggingface.co/google/translategemma-4b-it` 的 `Quantizations` 标签页选 `Q4_K_M` 对应的 `.gguf` 文件下载，放置到 `backend/models/translategemma-4b-it.Q4_K_M.gguf`
- **校验**：官方 GGUF 约 2.49GB（`2489909760` bytes 左右），放置后 `start.sh` 默认指向该路径（`TRANSLATE_MODEL_PATH`）

### OCR 模型（`PP-OCRv6_medium` / `PP-OCRv6_small` 的 det/rec）

- **来源**：PaddleX 官方模型仓库，首次启动自动下载到 `~/.paddlex/official_models/`，约 3GB
- **离线部署**：提前在有网环境下载好 `~/.paddlex/` 目录并挂载到离线机器同路径，避免首次启动联网下载失败

> 说明：GitHub Release 单附件上限 2GB，本仓库 2.49GB 的翻译模型无法作为 Release 附件直接上传，故统一指向 HuggingFace 官方源。本 Release 仅含源码与文档。

## 模型选择

| 模型 | 特点 | 适用场景 | 内存峰值 |
|------|------|---------|---------|
| `PP-OCRv6_small`（默认） | 快 1–3 分钟/页，占用低，不 530 | 日常识别、稳定优先 | ~7.8GB（7.8GB 机器贴顶可扛） |
| `PP-OCRv6_medium` | 识别率更高，4–6 分钟/页 | 模糊字迹、考试卷/低清扫描 | 易 OOM，大文件 530 风险 |

前端 `/ocr` 页可选，默认 small。medium 在大文件上内存峰值超 7.8GB 会触发 OOM kill，前置代理返回 530；重启服务即可恢复。

## OCR 任务异步化

`POST /api/ocr` 立即返回 `task_id`，识别在后台线程执行，前端每 3s 轮询 `GET /api/ocr/{task_id}`。短请求绕过代理超时，避免 medium 模型 4–6 分钟推理导致 530。

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `TRANSLATE_MODEL_PATH` | 翻译模型 GGUF 路径 | `backend/models/translategemma-4b-it.Q4_K_M.gguf` |

## 已知限制

- medium 模型在 7.8GB 内存机器上易 OOM，大文件建议用 small
- 横向/多栏文档依赖 `use_doc_orientation_classify=True`，首次推理需额外布局模型
- 翻译模型与 OCR 模型不同时常驻（识别前自动卸载翻译模型），二者并发会 OOM

## License

MIT
