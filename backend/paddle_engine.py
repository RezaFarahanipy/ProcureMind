"""Optional third OCR engine: PaddleOCR (runs in-process on CPU).

`paddleocr` is NOT in requirements.txt (it is large). Install with:
    pip install -r backend/requirements-paddle.txt
It is imported lazily, so the app works without it.
"""
import gc
import importlib.util
import os
import threading
import time

import numpy as np

_lock = threading.Lock()
_state = {"ocr": None, "lang": None, "load_s": None}


def installed() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


def status() -> dict:
    return {"installed": installed(), "loaded": _state["ocr"] is not None,
            "lang": _state["lang"], "load_s": _state["load_s"]}


def _unload_locked() -> None:
    _state.update(ocr=None, lang=None, load_s=None)
    gc.collect()


def unload() -> None:
    with _lock:
        _unload_locked()


def load(lang: str) -> tuple[float, bool]:
    """Load the recognition model for `lang` (first use may download models from the internet).
    Returns (seconds, loaded_now)."""
    with _lock:
        if _state["ocr"] is not None and _state["lang"] == lang:
            return _state["load_s"], False
        _unload_locked()
        t0 = time.time()
        from paddleocr import PaddleOCR  # noqa: PLC0415

        kw = dict(lang=lang, use_doc_orientation_classify=False, use_doc_unwarping=False,
                  use_textline_orientation=False)
        # oneDNN (mkldnn) is disabled by default: some paddlepaddle 3.x CPU builds crash with it.
        mkldnn = os.environ.get("PADDLE_MKLDNN", "0") == "1"
        try:
            ocr = PaddleOCR(enable_mkldnn=mkldnn, **kw)
        except (TypeError, ValueError):
            ocr = PaddleOCR(**kw)
        _state.update(ocr=ocr, lang=lang, load_s=round(time.time() - t0, 1))
        return _state["load_s"], True


def _extract(res) -> tuple[list[str], list[float]]:
    texts, scores = [], []
    for r in res or []:
        if isinstance(r, list):  # legacy 2.x format: [[box, (text, score)], ...]
            for line in r or []:
                texts.append(line[1][0])
                scores.append(float(line[1][1]))
            continue
        try:
            d = r if "rec_texts" in r else r.json["res"]
        except Exception:  # noqa: BLE001
            d = r.json["res"]
        texts += [str(t) for t in d.get("rec_texts", [])]
        scores += [float(x) for x in d.get("rec_scores", [])]
    return texts, scores


def read(img) -> dict:
    """Run OCR on a PIL image. Returns {"text", "lines", "mean_score"}."""
    arr = np.array(img.convert("RGB"))[:, :, ::-1].copy()  # PaddleOCR expects BGR
    with _lock:
        ocr = _state["ocr"]
        if ocr is None:
            raise RuntimeError("PaddleOCR is not loaded")
        res = ocr.predict(arr) if hasattr(ocr, "predict") else ocr.ocr(arr)
    texts, scores = _extract(res)
    mean = round(sum(scores) / len(scores), 3) if scores else None
    return {"text": "\n".join(texts), "lines": len(texts), "mean_score": mean}
