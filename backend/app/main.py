"""FastAPI 入口：OCR 版式还原与本地离线翻译为两个独立页面。"""

import json
import os
import uuid
import asyncio
import threading

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import export_service, ocr_service, translate_service

app = FastAPI(title="本地识译")


@app.exception_handler(StarletteHTTPException)
async def _api_json_errors(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    from fastapi.exception_handlers import http_exception_handler
    return await http_exception_handler(request, exc)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
WORK_ROOT = os.path.join(BASE_DIR, "runtime", "tasks")
os.makedirs(WORK_ROOT, exist_ok=True)

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".pdf"}
MAX_SIZE = 50 * 1024 * 1024

_results: dict[str, dict] = {}
# 每个 task 的运行状态：running / done / error
_task_status: dict[str, dict] = {}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ocr_ready": ocr_service.pipeline_loaded(),
        "translate_model_loaded": translate_service.model_loaded(),
    }


def _run_ocr_task(task_id: str, input_path: str, work_dir: str, ocr_model: str) -> None:
    """后台线程执行 OCR，完成后写入 _results。"""
    try:
        result = ocr_service.ocr_file(input_path, work_dir, model=ocr_model)
        result["ocr_model"] = ocr_model
        result["task_id"] = task_id
        _results[task_id] = result
        _task_status[task_id] = {"state": "done"}
    except Exception as e:
        _task_status[task_id] = {"state": "error", "detail": f"OCR 处理失败: {e}"}


@app.post("/api/ocr")
async def ocr(file: UploadFile = File(...), ocr_model: str = Form("medium")):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式 {ext}")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 50MB 限制")

    if ocr_model not in ocr_service._OCR_MODELS:
        ocr_model = ocr_service.DEFAULT_OCR_MODEL

    task_id = uuid.uuid4().hex
    work_dir = os.path.join(WORK_ROOT, task_id)
    os.makedirs(work_dir, exist_ok=True)
    input_path = os.path.join(work_dir, f"input{ext}")
    with open(input_path, "wb") as f:
        f.write(data)

    # 立即返回 task_id，OCR 放后台线程跑；前端轮询 /api/ocr/{task_id} 取结果
    # 所有 HTTP 请求都是短请求，彻底绕过代理 530 超时
    _task_status[task_id] = {"state": "running"}
    threading.Thread(
        target=_run_ocr_task, args=(task_id, input_path, work_dir, ocr_model), daemon=True
    ).start()
    return {"task_id": task_id, "state": "running"}


@app.get("/api/ocr/{task_id}")
async def ocr_status(task_id: str):
    st = _task_status.get(task_id)
    if st is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if st["state"] == "done" and task_id in _results:
        return _results[task_id]
    return {"task_id": task_id, "state": st["state"], "detail": st.get("detail")}


@app.post("/api/translate")
async def translate(payload: dict):
    text = payload.get("text", "")
    src_lang = payload.get("src_lang", "zh")
    tgt_lang = payload.get("tgt_lang", "en")
    try:
        translated = await asyncio.to_thread(
            translate_service.translate, text, src_lang, tgt_lang
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译失败: {e}")
    return {"translated": translated}


@app.get("/api/export/{task_id}")
def export(task_id: str, format: str = "docx"):
    result = _results.get(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if format == "docx":
        data = export_service.export_docx(result)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        name = "ocr_result.docx"
    elif format == "xlsx":
        data = export_service.export_xlsx(result)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        name = "ocr_result.xlsx"
    elif format == "pdf":
        data = export_service.export_pdf(result)
        media = "application/pdf"
        name = "ocr_result.pdf"
    elif format == "txt":
        data = (result.get("text") or "").encode("utf-8")
        media = "text/plain; charset=utf-8"
        name = "ocr_result.txt"
    elif format == "json":
        payload = {
            "task_id": task_id,
            "page_count": result.get("page_count"),
            "text": result.get("text", ""),
            "markdown": result.get("markdown", ""),
            "pages": result.get("pages", []),
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        media = "application/json"
        name = "ocr_result.json"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def _page(name: str) -> HTMLResponse:
    path = os.path.join(STATIC_DIR, name)
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/", response_class=HTMLResponse)
def index():
    return _page("index.html")
@app.get("/ocr", response_class=HTMLResponse)
def ocr_page():
    return _page("ocr.html")


@app.get("/translate", response_class=HTMLResponse)
def translate_page():
    return _page("translate.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
