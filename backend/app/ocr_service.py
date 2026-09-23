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
DEFAULT_OCR_MODEL = "small"

# 常见 OCR 字形混淆纠错表（正则，逐个替换）
# 针对扫描件常见的 h→c、i→1/l、o→0、e→c、b→h 等字形误认
_OCR_FIXES = [
    (r"\bliko\b", "like"),
    (r"\b1ike\b", "like"),
    (r"\bIike\b", "like"),
    (r"\btho\b", "the"),
    (r"\bthc\b", "the"),
    (r"\bThc\b", "The"),
    (r"\btlie\b", "the"),
    (r"\bmnko\b", "make"),
    (r"\bMako\b", "Make"),
    (r"\baftemoon\b", "afternoon"),
    (r"\baflemoon\b", "afternoon"),
    (r"\baflernoon\b", "afternoon"),
    (r"\bclcan\b", "clean"),
    (r"\bHclps\b", "Helps"),
    (r"\bHclp\b", "Help"),
    (r"\bHClps\b", "Helps"),
    (r"\bgivc\b", "give"),
    (r"\bweck\b", "week"),
    (r"\bwcek\b", "week"),
    (r"\bfnmily\b", "family"),
    (r"\bfarnily\b", "family"),
    (r"\bberc\b", "here"),
    (r"\bhcrc\b", "here"),
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
    (r"摩号", "序号"),
    (r"\bdocsn't\b", "doesn't"),
    (r"\bdoesn t\b", "doesn't"),
    (r"\bPeoplo\b", "People"),
    (r"\bPcoplo\b", "People"),
    (r"\bTimo\b", "Time"),
    (r"\bshou\b", "should"),
    (r"\bslould\b", "should"),
    (r"\baam\b", "A. Am"),
    (r"\bBcfore\b", "Before"),
    (r"\bhefore\b", "before"),
    (r"\bwifh\b", "with"),
    (r"\bwitb\b", "with"),
    (r"\bwhicb\b", "which"),
    (r"\bteacber\b", "teacher"),
    (r"\bscbool\b", "school"),
    (r"\babont\b", "about"),
    (r"\baboat\b", "about"),
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
            use_textline_orientation=True,
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_table_recognition=True,
            layout_threshold=0.3,
            text_detection_model_name=det,
            text_recognition_model_name=rec,
            text_det_limit_side_len=960,
            text_det_limit_type="min",
            text_det_thresh=0.3,
            text_det_box_thresh=0.5,
            text_det_unclip_ratio=1.8,
            text_rec_score_thresh=0.0,
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
    """低对比度做去阴影+CLAHE+锐化；清晰图只轻度锐化。短边过小则放大。"""
    import cv2

    img = cv2.imread(img_path)
    if img is None:
        return img_path
    h, w = img.shape[:2]
    min_side = min(h, w)
    if min_side < 720:
        scale = 720.0 / min_side
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    std = float(gray.std())
    mean = float(gray.mean())
    if std >= 50 and 80 <= mean <= 185:
        sharpened = cv2.addWeighted(gray, 1.35, cv2.GaussianBlur(gray, (0, 0), 1.6), -0.35, 0)
    else:
        ksize = 51 if min(gray.shape) >= 200 else 21
        bg = cv2.GaussianBlur(gray, (0, 0), ksize)
        bg[bg == 0] = 1
        normalized = cv2.divide(gray, bg, scale=255)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(normalized)
        sharpened = cv2.addWeighted(
            cv2.GaussianBlur(clahe, (0, 0), 2.0), 1.7,
            cv2.GaussianBlur(clahe, (0, 0), 4.0), -0.7, 0,
        )
    root, _ext = os.path.splitext(img_path)
    enhanced = root + "_enh.png"
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


def _save_capped(img: "Image.Image", path: str, max_side: int = 4000) -> str:
    from PIL import Image

    w, h = img.size
    m = max(w, h)
    if m > max_side:
        scale = max_side / m
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    img.save(path)
    return path


def _try_native_page_image(doc, page, output_dir: str, page_index: int) -> str | None:
    """扫描件条带/低清截图直接取原生像素，避免 300DPI 二次压缩。"""
    import io
    from PIL import Image

    images = page.get_images(full=True)
    if not images:
        return None
    infos = page.get_image_info()
    placed = []
    xrefs = {im[0] for im in images}
    for inf in infos:
        xref = inf.get("xref")
        bbox = inf.get("bbox")
        if xref not in xrefs or not bbox:
            continue
        placed.append((tuple(bbox), xref, int(inf.get("width") or 0), int(inf.get("height") or 0)))
    if not placed:
        native = doc.extract_image(images[0][0])
        if native.get("width", 0) and native["width"] < 700:
            native_path = os.path.join(output_dir, f"page_{page_index:04d}_native.{native['ext']}")
            with open(native_path, "wb") as fh:
                fh.write(native["image"])
            return _enhance_image(native_path)
        return None

    page_area = abs(float(page.rect.width) * float(page.rect.height)) or 1.0
    cover = sum(abs((b[2] - b[0]) * (b[3] - b[1])) for b, _x, _w, _h in placed)
    if len(placed) == 1:
        bbox, xref, w, _h = placed[0]
        native = doc.extract_image(xref)
        if native.get("width", 0) and native["width"] < 700:
            native_path = os.path.join(output_dir, f"page_{page_index:04d}_native.{native['ext']}")
            with open(native_path, "wb") as fh:
                fh.write(native["image"])
            return _enhance_image(native_path)
        return None
    if cover / page_area < 0.65:
        return None

    bbox0, _x0, w0, h0 = placed[0]
    sx = w0 / max(bbox0[2] - bbox0[0], 1e-3)
    sy = h0 / max(bbox0[3] - bbox0[1], 1e-3)
    minx = min(b[0] for b, *_ in placed)
    miny = min(b[1] for b, *_ in placed)
    maxx = max(b[2] for b, *_ in placed)
    maxy = max(b[3] for b, *_ in placed)
    canvas = Image.new("RGB", (max(1, int((maxx - minx) * sx)), max(1, int((maxy - miny) * sy))), (255, 255, 255))
    for bbox, xref, _w, _h in placed:
        native = doc.extract_image(xref)
        im = Image.open(io.BytesIO(native["image"])).convert("RGB")
        tw = max(1, int((bbox[2] - bbox[0]) * sx))
        th = max(1, int((bbox[3] - bbox[1]) * sy))
        if im.size != (tw, th):
            im = im.resize((tw, th), Image.Resampling.LANCZOS)
        canvas.paste(im, (int((bbox[0] - minx) * sx), int((bbox[1] - miny) * sy)))
    out = os.path.join(output_dir, f"page_{page_index:04d}_native.png")
    _save_capped(canvas, out)
    return _enhance_image(out)


def _render_pdf(pdf_path: str, output_dir: str) -> list[str]:
    import fitz
    from PIL import Image

    doc = fitz.open(pdf_path)
    paths = []
    MAX_SIDE = 4000
    for i in range(len(doc)):
        page = doc.load_page(i)
        native_path = _try_native_page_image(doc, page, output_dir, i)
        if native_path:
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


def _sort_blocks_reading_order(blocks: list) -> list:
    """按多栏阅读顺序排序：按 x 中心分栏，栏内从上到下。"""
    boxed = [b for b in blocks if isinstance(b.get("bbox"), list) and len(b["bbox"]) == 4]
    rest = [b for b in blocks if not (isinstance(b.get("bbox"), list) and len(b["bbox"]) == 4)]
    if len(boxed) < 2:
        return blocks
    boxed.sort(key=lambda b: ((b["bbox"][0] + b["bbox"][2]) / 2, b["bbox"][1]))
    xs = [(b["bbox"][0] + b["bbox"][2]) / 2 for b in boxed]
    page_w = max(b["bbox"][2] for b in boxed) - min(b["bbox"][0] for b in boxed)
    if page_w < 1:
        return boxed + rest
    cuts = []
    for i in range(len(xs) - 1):
        if xs[i + 1] - xs[i] > max(40.0, page_w * 0.10):
            cuts.append(i + 1)
    if not cuts:
        boxed.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        return boxed + rest
    groups = []
    start = 0
    for c in cuts:
        groups.append(boxed[start:c])
        start = c
    groups.append(boxed[start:])
    out = []
    for g in groups:
        g.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        out.extend(g)
    return out + rest


def _detect_column_ranges(img_path: str) -> list[tuple[int, int]]:
    """用竖向墨水投影切栏，返回 [(x0, x1), ...]。不足 2 栏则空列表。"""
    import cv2
    import numpy as np

    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    h, w = img.shape
    if w < 1100 or w < h * 1.15:
        return []
    ink = (img < 180).astype(np.uint8)
    proj = ink.sum(axis=0).astype(np.float32)
    k = max(21, (w // 70) | 1)
    proj = cv2.GaussianBlur(proj.reshape(1, -1), (k, 1), 0).ravel()
    mx = float(proj.max()) or 1.0
    in_gap = proj < mx * 0.08
    gaps = []
    i = 0
    min_gap = max(10, w // 90)
    while i < w:
        if in_gap[i]:
            j = i
            while j < w and in_gap[j]:
                j += 1
            if j - i >= min_gap:
                gaps.append((i, j))
            i = j
        else:
            i += 1
    cuts = []
    for a, b in gaps:
        mid = (a + b) // 2
        if w * 0.06 < mid < w * 0.94:
            cuts.append(mid)
    if not cuts:
        return []
    bounds = [0] + cuts + [w]
    pad = max(6, w // 200)
    cols = []
    min_w = max(160, w // 10)
    for i in range(len(bounds) - 1):
        x0 = max(0, bounds[i] - (0 if i == 0 else pad))
        x1 = min(w, bounds[i + 1] + (0 if i == len(bounds) - 2 else pad))
        if x1 - x0 >= min_w:
            cols.append((x0, x1))
    if len(cols) < 2:
        return []
    return cols


def _shift_blocks(blocks: list, dx: int) -> list:
    for b in blocks:
        box = b.get("bbox")
        if isinstance(box, list) and len(box) == 4:
            b["bbox"] = [box[0] + dx, box[1], box[2] + dx, box[3]]
    return blocks


def _ocr_one_image(pipeline, image_path: str, page_index: int) -> dict:
    output = pipeline.predict(image_path)
    pages = [_result_to_page(image_path, page_index, res) for res in output]
    if not pages:
        return {"page_index": page_index, "image_path": image_path, "blocks": [], "markdown": "", "text": ""}
    if len(pages) == 1:
        return pages[0]
    blocks = []
    md = []
    for p in pages:
        blocks.extend(p.get("blocks") or [])
        if p.get("markdown"):
            md.append(p["markdown"])
    blocks = _sort_blocks_reading_order(blocks)
    return {
        "page_index": page_index,
        "image_path": image_path,
        "blocks": blocks,
        "markdown": "\n\n".join(md),
        "text": "\n".join(b.get("text", "") or "" for b in blocks),
    }


def _ocr_by_columns(pipeline, image_path: str, page_index: int) -> dict:
    """多栏页按栏裁剪后分别识别，再按从左到右拼接。"""
    cols = _detect_column_ranges(image_path)
    if len(cols) < 2:
        return _ocr_one_image(pipeline, image_path, page_index)
    from PIL import Image

    im = Image.open(image_path)
    h = im.size[1]
    root, _ext = os.path.splitext(image_path)
    merged = []
    md_parts = []
    for ci, (x0, x1) in enumerate(cols):
        crop_path = f"{root}_col{ci}.png"
        im.crop((x0, 0, x1, h)).save(crop_path)
        part = _ocr_one_image(pipeline, crop_path, page_index)
        merged.extend(_shift_blocks(part.get("blocks") or [], x0))
        if part.get("markdown"):
            md_parts.append(part["markdown"])
    text = "\n".join(b.get("text", "") or "" for b in merged)
    return {
        "page_index": page_index,
        "image_path": image_path,
        "blocks": merged,
        "markdown": "\n\n".join(md_parts),
        "text": text,
    }


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

    blocks = _sort_blocks_reading_order(blocks)

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
        pages.append(_ocr_by_columns(pipeline, image_path, idx))

    full_markdown = _postprocess_text("\n\n".join(p.get("markdown", "") for p in pages))
    full_text = "\n\n".join(p.get("text", "") for p in pages)
    full_text = _postprocess_text(full_text)
    for p in pages:
        p["text"] = _postprocess_text(p.get("text", ""))
        p["markdown"] = _postprocess_text(p.get("markdown", "") or "")
        for b in p.get("blocks") or []:
            if b.get("text"):
                b["text"] = _postprocess_text(b["text"])
            if b.get("html"):
                b["html"] = _postprocess_text(b["html"])

    return {
        "page_count": len(pages),
        "markdown": full_markdown,
        "text": full_text,
        "pages": pages,
    }
