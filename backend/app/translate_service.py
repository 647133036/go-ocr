"""本地离线翻译服务，基于 Google Translation Gemma + llama.cpp。"""

import os
import threading

_LLM = None
_LLM_LOCK = threading.Lock()

MODEL_PATH = os.environ.get(
    "TRANSLATE_MODEL_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "translategemma-4b-it.Q4_K_M.gguf"),
)

SUPPORTED_LANGS = {"zh", "en", "ar"}


def model_loaded() -> bool:
    return _LLM is not None


def unload_model() -> None:
    """释放翻译模型，避免与 OCR pipeline 同时常驻。"""
    global _LLM
    with _LLM_LOCK:
        llm = _LLM
        _LLM = None
    if llm is not None:
        try:
            del llm
        except Exception:
            pass
    try:
        import gc

        gc.collect()
    except Exception:
        pass


def _get_llm():
    global _LLM
    if _LLM is None:
        from . import ocr_service

        ocr_service.unload_pipeline()
        with _LLM_LOCK:
            if _LLM is None:
                from llama_cpp import Llama

                _LLM = Llama(
                    model_path=MODEL_PATH,
                    n_ctx=4096,
                    n_threads=2,
                    verbose=False,
                    use_mlock=True,
                )
    return _LLM


def _translate_chunk(llm, text: str, src_code: str, tgt_code: str) -> str:
    out = llm.create_chat_completion(
        messages=[{
            "role": "user",
            "content": [{
                "type": "text",
                "source_lang_code": src_code,
                "target_lang_code": tgt_code,
                "text": text.strip(),
            }],
        }],
        max_tokens=512,
        temperature=0.1,
        top_p=0.9,
    )
    return out["choices"][0]["message"]["content"].strip()


def _split_text(text: str, max_chars: int = 800) -> list[str]:
    """按换行分段，并将相邻段合并为不超过 max_chars 的块。"""
    lines = [line.strip() for line in text.split("\n")]
    chunks = []
    current = ""
    for line in lines:
        if not line:
            continue
        if current and len(current) + len(line) + 1 > max_chars:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def translate(text: str, src_lang: str = "zh", tgt_lang: str = "en") -> str:
    """本地离线翻译。src_lang/tgt_lang 取 'zh'/'en'/'ar'。长文本自动分段。"""
    if not text or not text.strip():
        return ""

    src_code = src_lang if src_lang in SUPPORTED_LANGS else "zh"
    tgt_code = tgt_lang if tgt_lang in SUPPORTED_LANGS else "en"

    llm = _get_llm()
    chunks = _split_text(text)
    translated_parts = [_translate_chunk(llm, chunk, src_code, tgt_code) for chunk in chunks]
    return "\n".join(translated_parts)
