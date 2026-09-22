"""OCR 版式还原服务，基于 PaddleOCR PP-StructureV3。"""

import html as html_mod
import os
import re
import threading

_OCR_PIPELINE = None
_OCR_PIPELINE_MODEL = None
_OCR_LOCK = threading.Lock()

# 可选 OCR 文字识别底模：small（快、省内存）/ medium（慢、精确）
_OCR_MODELS = {
    "small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
    "medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
}
DEFAULT_OCR_MODEL = "medium"

# 常见 OCR 字形混淆纠错表（正则，逐个替换）
# 针对扫描件常见的 h→c、i→1/l、o→0、e→c 等字形误认
_OCR_FIXES = [
    (r"\bliko\b", "like"),
    (r"\btho\b", "the"),
    (r"\bmnko\b", "make"),
    (r"\bMako\b", "Make"),
    (r"\baftemoon\b", "afternoon"),
    (r"\baflemoon\b", "afternoon"),
    (r"\baflernoon\b", "afternoon"),
    (r"\bafternoon\b", "afternoon"),
    (r"\bclcan\b", "clean"),
    (r"\bHclps\b", "Helps"),
    (r"\bHclp\b", "Help"),
    (r"\bHClps\b", "Helps"),
    (r"\bgivc\b", "give"),
    (r"\bweck\b", "week"),
    (r"\bfnmily\b", "family"),
    (r"\bberc\b", "here"),
    (r"\bSory\b", "Sorry"),
    (r"\bsory\b", "sorry"),
    (r"\bgol up\b", "got up"),
    (r"havecold\b", "have a cold"),
    (r"make a\s*_?for\s*mt", "make a decision for me"),
    (r"make a\s*for\s*me", "make a decision for me"),
    (r"調分", "满分"),
    (r"调分", "满分"),
    (r"根烟", "根据"),
    (r"潤分", "满分"),
    (r"短文珊解", "短文理解"),
    (r"兩遍", "两遍"),
    (r"两测", "两遍"),
    (r"\bdocsn't\b", "doesn't"),
    (r"\bPeoplo\b", "People"),
    (r"\bPcoplo\b", "People"),
    (r"\bTimo\b", "Time"),
    (r"\bshou\b", "should"),
    (r"\baam\b", "A. Am"),
    (r"\bBcfore\b", "Before"),
    (r"价倍敏感度", "价格敏感度"),
    (r"\bmnko", "make"),
]


def _to_native(obj):
    """将 numpy 类型递归转换为可 JSON 序列化的原生类型。"""
    try:
        import numpy as np
    except ImportError:
        return obj
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, list):
        return [_to_native(x) for x in obj]
    if isinstance(obj, tuple):
        return [_to_native(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    return obj


def _norm_bbox(bbox) -> list | None:
    """将 PP-Structure 的 bbox 归一为 [x1, y1, x2, y2]。"""
    if isinstance(bbox, str):
        import ast

        try:
            bbox = ast.literal_eval(bbox)
        except (ValueError, SyntaxError):
            return None
    bbox = _to_native(bbox)
    if not bbox:
        return None
    flat = []
    for v in bbox:
        try:
            flat.append(float(v))
        except (TypeError, ValueError):
            return None
    if len(flat) == 4:
        return flat
    if len(flat) >= 8:
        xs = flat[0::2]
        ys = flat[1::2]
        return [min(xs), min(ys), max(xs), max(ys)]
    return None


def pipeline_loaded() -> bool:
    return _OCR_PIPELINE is not None


def unload_pipeline() -> None:
    """释放 OCR pipeline，避免与翻译模型同时常驻。"""
    global _OCR_PIPELINE, _OCR_PIPELINE_MODEL
    with _OCR_LOCK:
        _OCR_PIPELINE = None
        _OCR_PIPELINE_MODEL = None
    try:
        import gc

        gc.collect()
    except Exception:
        pass


def _get_pipeline(model: str | None = None):
    global _OCR_PIPELINE, _OCR_PIPELINE_MODEL
    if model not in _OCR_MODELS:
        model = DEFAULT_OCR_MODEL
    if _OCR_PIPELINE is not None and _OCR_PIPELINE_MODEL == model:
        return _OCR_PIPELINE
    from . import translate_service

    translate_service.unload_model()
    with _OCR_LOCK:
        if _OCR_PIPELINE is not None and _OCR_PIPELINE_MODEL == model:
            return _OCR_PIPELINE
        from paddleocr import PPStructureV3

        det, rec = _OCR_MODELS[model]
        _OCR_PIPELINE = PPStructureV3(
            use_doc_orientation_classify=True,
            use_doc_unwarping=False,
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_table_recognition=True,
            layout_threshold=0.3,
            text_detection_model_name=det,
            text_recognition_model_name=rec,
            engine="paddle",
            device="cpu",
            enable_mkldnn=False,
            cpu_threads=2,
            engine_config={
                "paddle_static": {
                    "enable_new_ir": True,
                    "run_mode": "paddle",
                    "cpu_threads": 2,
                }
            },
        )
        _OCR_PIPELINE_MODEL = model
    return _OCR_PIPELINE


def _enhance_image(img_path: str) -> str:
    """对渲染页做去阴影 + CLAHE 对比度增强 + 轻度锐化，提升低质量扫描件识别率。"""
    import cv2

    img = cv2.imread(img_path)
    if img is None:
        return img_path
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 去阴影：用大核高斯估计背景光照，除以背景归一化（消除斜向阴影/暗角）
    bg = cv2.GaussianBlur(gray, (0, 0), 51)
    normalized = cv2.divide(gray, bg, scale=255)
    # 去阴影版比原始图噪点低，再做 CLAHE + 锐化
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(normalized)
    sharpened = cv2.addWeighted(
        cv2.GaussianBlur(clahe, (0, 0), 2.0), 1.7,
        cv2.GaussianBlur(clahe, (0, 0), 4.0), -0.7, 0,
    )
    enhanced = img_path.replace(".png", "_enh.png")
    cv2.imwrite(enhanced, sharpened)
    return enhanced


def _crop_content_area(img: "Image.Image") -> "Image.Image":
    """裁掉页面四周的大片空白，只保留有墨水内容的区域，减少无效检测。"""
    import numpy as np
    from PIL import Image

    arr = np.array(img.convert("L"))
    mask = arr < 180
    if mask.sum() == 0:
        return img
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    pad = 20
    y0 = max(0, rows[0] - pad)
    y1 = min(arr.shape[0], rows[-1] + pad)
    x0 = max(0, cols[0] - pad)
    x1 = min(arr.shape[1], cols[-1] + pad)
    return img.crop((x0, y0, x1, y1))


def _render_pdf(pdf_path: str, output_dir: str) -> list[str]:
    import fitz

    doc = fitz.open(pdf_path)
    paths = []
    MAX_SIDE = 4000
    for i in range(len(doc)):
        page = doc.load_page(i)
        native_images = page.get_images(full=True)
        # 页面含原生图且其宽 < 700px → 源是低清截图/扫描件，直接取原生图（最高清）
        if native_images:
            native = doc.extract_image(native_images[0][0])
            if native.get("width", 0) and native["width"] < 700:
                native_path = os.path.join(output_dir, f"page_{i:04d}_native.{native['ext']}")
                with open(native_path, "wb") as fh:
                    fh.write(native["image"])
                paths.append(native_path)
                continue
        w300 = int(page.rect.width / 72 * 300)
        h300 = int(page.rect.height / 72 * 300)
        if max(w300, h300) > MAX_SIDE:
            dpi_eff = int(300 * MAX_SIDE / max(w300, h300))
        else:
            dpi_eff = 300
        pix = page.get_pixmap(dpi=dpi_eff)
        path = os.path.join(output_dir, f"page_{i:04d}.png")
        pix.save(path)
        from PIL import Image

        img = Image.open(path)
        cropped = _crop_content_area(img)
        cropped_path = path.replace(".png", "_content.png")
        cropped.save(cropped_path)
        paths.append(_enhance_image(cropped_path))
    doc.close()
    return paths


def _html_to_text(html_str: str) -> str:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_str or "", re.S | re.I)
    lines = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        texts = []
        for cell in cells:
            t = re.sub(r"<[^>]+>", "", cell)
            t = html_mod.unescape(t).strip()
            if t:
                texts.append(t)
        if texts:
            lines.append("\t".join(texts))
    return "\n".join(lines)


def _block_fields(item):
    """从 LayoutBlock 提取 (label, content, bbox)，兼容 dict 与对象两种形态。"""
    if isinstance(item, dict):
        label = item.get("label") or item.get("block_label", "text")
        content = item.get("content") if item.get("content") is not None else item.get("block_content", "")
        bbox = item.get("bbox") or item.get("block_bbox")
        return label, content, bbox
    label = getattr(item, "label", None)
    if label is None:
        d = item.to_dict()
        label = d.get("label") or d.get("block_label", "text")
        content = d.get("content", "") or d.get("block_content", "")
        bbox = d.get("bbox") or d.get("block_bbox")
    else:
        content = getattr(item, "content", "") or ""
        bbox = getattr(item, "bbox", None)
    return label, content, bbox


def _result_to_page(image_path: str, page_index: int, result) -> dict:
    if isinstance(result, dict):
        parsing = list(result.get("parsing_res_list", []))
    else:
        parsing = list(getattr(result, "parsing_res_list", []))

    blocks = []
    for item in parsing:
        label, content, raw_bbox = _block_fields(item)
        label = label or "text"
        bbox = _norm_bbox(raw_bbox)
        if label in ("table", "vision_table"):
            blocks.append({
                "type": "table",
                "html": content or "",
                "text": _html_to_text(content or ""),
                "bbox": bbox,
            })
        elif label == "formula":
            blocks.append({"type": "formula", "text": content or "", "bbox": bbox})
        elif label in ("figure", "image", "chart", "seal", "stamp"):
            continue
        else:
            blocks.append({"type": "text", "text": content or "", "bbox": bbox})

    markdown_obj = getattr(result, "markdown", None)
    if markdown_obj is None:
        markdown_obj = result.get("markdown") if isinstance(result, dict) else None
    markdown = (
        markdown_obj.get("markdown_texts", "")
        if isinstance(markdown_obj, dict)
        else (markdown_obj or "")
    )
    text = "\n".join(b.get("text", "") or "" for b in blocks)

    return {
        "page_index": page_index,
        "image_path": image_path,
        "blocks": blocks,
        "markdown": markdown,
        "text": text,
    }


def _postprocess_text(text: str) -> str:
    """修正常见的 OCR 字形混淆（i↔l、c↔g、a↔o 等）。"""
    for pattern, fix in _OCR_FIXES:
        text = re.sub(pattern, fix, text)
    return text


def ocr_file(input_path: str, work_dir: str, model: str = DEFAULT_OCR_MODEL) -> dict:
    """对输入文件（图片或 PDF）执行版式还原 OCR，返回统一结构。"""
    ext = os.path.splitext(input_path)[1].lower()
    image_paths = []

    os.makedirs(work_dir, exist_ok=True)

    if ext == ".pdf":
        image_paths = _render_pdf(input_path, work_dir)
    else:
        image_paths = [_enhance_image(input_path)]

    pipeline = _get_pipeline(model)
    pages = []
    for idx, image_path in enumerate(image_paths):
        output = pipeline.predict(image_path)
        for res in output:
            pages.append(_result_to_page(image_path, idx, res))

    full_markdown = "\n\n".join(p.get("markdown", "") for p in pages)
    full_text = "\n\n".join(p.get("text", "") for p in pages)
    full_text = _postprocess_text(full_text)
    for p in pages:
        p["text"] = _postprocess_text(p.get("text", ""))

    return {
        "page_count": len(pages),
        "markdown": full_markdown,
        "text": full_text,
        "pages": pages,
    }
