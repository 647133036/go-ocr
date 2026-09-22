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

# 启动服务（监听 8000）
bash start.sh
```

访问：

- `http://localhost:8000/` — 首页
- `http://localhost:8000/ocr` — OCR 识别
- `http://localhost:8000/translate` — 离线翻译

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
start.sh               启动脚本
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

二进制文件：

- `backend/models/translategemma-4b-it.Q4_K_M.gguf`（约 2.4GB）
  - git 仓库默认不追踪此文件（`.gitignore` 排除），避免仓库体积膨胀
  - 获取方式：从 `google/translategemma` 仓库下载对应 GGUF 量化文件，或从本仓库 GitHub Release 下载
  - 放置到 `backend/models/` 后，`start.sh` 默认指向该路径
- Paddle OCR 模型（`PP-OCRv6_medium` / `PP-OCRv6_small` 的 det/rec）
  - 首次启动时自动下载到 `~/.paddlex/official_models/`，约 3GB
  - 离线环境下需提前下载好并挂载到该目录

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
