"""ProcureMind - Phase 1 prototype backend (chat + OCR test harness).

No database. Talks to two llama-server instances (Qwen chat, Dots OCR).
Every request is timed and appended to logs/tests.jsonl.
"""
import asyncio
import base64
import io
import json
import os
import time
import uuid
from pathlib import Path

import fitz  # PyMuPDF
import httpx
import psutil
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent


def env(key: str, default: str) -> str:
    return os.environ.get(key, default)


QWEN_URL = env("QWEN_URL", "http://127.0.0.1:8080").rstrip("/")
OCR_URL = env("OCR_URL", "http://127.0.0.1:8081").rstrip("/")
QWEN_THINKING = env("QWEN_THINKING", "0") == "1"
OCR_PROMPT = env("OCR_PROMPT", "Extract the text content from this image.")
OCR_MAX_SIDE = int(env("OCR_MAX_SIDE", "800"))  # smaller image = far fewer vision tokens = much faster on CPU
OCR_PDF_DPI = int(env("OCR_PDF_DPI", "130"))
OCR_MAX_PAGES = int(env("OCR_MAX_PAGES", "10"))
OCR_MAX_TOKENS = int(env("OCR_MAX_TOKENS", "1024"))
OCR_TEMPERATURE = float(env("OCR_TEMPERATURE", "0.1"))  # greedy (0) tends to loop; 0.1 is the model authors' suggestion
OCR_REPEAT_PENALTY = float(env("OCR_REPEAT_PENALTY", "1.05"))
MAX_UPLOAD_MB = 30

UPLOADS = ROOT / "data" / "uploads"
LOGS = ROOT / "logs"
UPLOADS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ProcureMind Phase 1 prototype")
ocr_lock = asyncio.Semaphore(1)  # one OCR job at a time (CPU/RAM protection)
chat_lock = asyncio.Semaphore(1)


# ---------- helpers ----------
def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def nd(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def resources() -> dict:
    vm = psutil.virtual_memory()
    return {
        "ram_used_gb": round((vm.total - vm.available) / 1e9, 2),
        "ram_percent": vm.percent,
        "cpu_percent": psutil.cpu_percent(interval=None),
    }


def log_test(entry: dict) -> None:
    entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), **entry}
    with open(LOGS / "tests.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


psutil.cpu_percent(interval=None)  # prime


# ---------- health ----------
@app.get("/api/health")
async def health():
    async def ping(url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(f"{url}/health")
            return {"ok": r.status_code == 200, "status": r.status_code}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": str(type(e).__name__)}

    qwen, ocr = await asyncio.gather(ping(QWEN_URL), ping(OCR_URL))
    return {"qwen": qwen, "ocr": ocr, "resources": resources()}


# ---------- chat ----------
class Msg(BaseModel):
    role: str
    content: str


class ChatReq(BaseModel):
    messages: list[Msg]
    temperature: float = 0.7
    max_tokens: int = 1024


@app.post("/api/chat")
async def chat(req: ChatReq):
    payload = {
        "messages": [m.model_dump() for m in req.messages],
        "stream": True,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "chat_template_kwargs": {"enable_thinking": QWEN_THINKING},
    }

    async def gen():
        t0 = time.perf_counter()
        first = None
        chunks = 0
        timings = None
        text = ""
        res_before = resources()
        async with chat_lock:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=5)) as c:
                    async with c.stream("POST", f"{QWEN_URL}/v1/chat/completions", json=payload) as r:
                        if r.status_code != 200:
                            body = (await r.aread()).decode("utf-8", "replace")[:500]
                            yield sse({"type": "error", "message": f"Qwen HTTP {r.status_code}: {body}"})
                            return
                        async for line in r.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                j = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            if j.get("timings"):
                                timings = j["timings"]
                            choices = j.get("choices") or []
                            if not choices:
                                continue
                            delta = choices[0].get("delta") or {}
                            if delta.get("reasoning_content"):
                                yield sse({"type": "reasoning", "text": delta["reasoning_content"]})
                            piece = delta.get("content")
                            if piece:
                                if first is None:
                                    first = time.perf_counter() - t0
                                chunks += 1
                                text += piece
                                yield sse({"type": "delta", "text": piece})
            except httpx.ConnectError:
                yield sse({"type": "error", "message": "اتصال به سرور Qwen برقرار نشد. start_qwen.bat را اجرا کنید."})
                return
            except Exception as e:  # noqa: BLE001
                yield sse({"type": "error", "message": f"خطا: {type(e).__name__}: {e}"})
                return
        total = time.perf_counter() - t0
        tps = None
        if timings and timings.get("predicted_per_second"):
            tps = round(timings["predicted_per_second"], 2)
        elif first is not None and chunks > 1 and total > first:
            tps = round(chunks / (total - first), 2)
        stats = {
            "total_s": round(total, 2),
            "first_token_s": round(first, 2) if first is not None else None,
            "tokens_per_s": tps,
            "chars": len(text),
            "resources": resources(),
        }
        log_test({"kind": "chat", "prompt_chars": sum(len(m.content) for m in req.messages),
                  "ram_before_gb": res_before["ram_used_gb"], **stats})
        yield sse({"type": "done", "stats": stats})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- OCR ----------
def pil_to_data_uri(img: Image.Image) -> str:
    img = img.convert("RGB")
    w, h = img.size
    scale = OCR_MAX_SIDE / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def load_pages(data: bytes, filename: str) -> tuple[list[Image.Image], int]:
    """Return (page images, total pages in the file)."""
    if filename.lower().endswith(".pdf") or data[:4] == b"%PDF":
        doc = fitz.open(stream=data, filetype="pdf")
        total = doc.page_count
        pages = []
        for i in range(min(total, OCR_MAX_PAGES)):
            pix = doc[i].get_pixmap(dpi=OCR_PDF_DPI)
            pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        return pages, total
    return [Image.open(io.BytesIO(data))], 1


@app.post("/api/ocr")
async def ocr(file: UploadFile = File(...), prompt: str = Form(""), max_tokens: int = Form(0)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"حداکثر حجم فایل {MAX_UPLOAD_MB}MB است")
    name = file.filename or "upload"
    saved = UPLOADS / f"{time.strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:6]}_{Path(name).name}"
    saved.write_bytes(data)  # original file is always preserved

    async def gen():
        t0 = time.perf_counter()
        yield nd({"type": "queued"})
        async with ocr_lock:
            try:
                pages, total = await asyncio.to_thread(load_pages, data, name)
            except Exception as e:  # noqa: BLE001
                yield nd({"type": "error", "message": f"فایل خوانده نشد: {e}"})
                return
            yield nd({"type": "start", "pages": len(pages), "total_pages": total, "file": saved.name})
            page_times = []
            for i, img in enumerate(pages, 1):
                tp = time.perf_counter()
                text, finish, ctoks = "", None, None
                payload = {
                    "messages": [{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": await asyncio.to_thread(pil_to_data_uri, img)}},
                        {"type": "text", "text": prompt.strip() or OCR_PROMPT},
                    ]}],
                    "temperature": OCR_TEMPERATURE,
                    "top_p": 1.0,
                    "repeat_penalty": OCR_REPEAT_PENALTY,
                    "max_tokens": max_tokens if max_tokens > 0 else OCR_MAX_TOKENS,
                    "stream": True,
                }
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=5)) as c:
                        async with c.stream("POST", f"{OCR_URL}/v1/chat/completions", json=payload) as r:
                            if r.status_code != 200:
                                body = (await r.aread()).decode("utf-8", "replace")[:400]
                                yield nd({"type": "error", "page": i, "message": f"OCR HTTP {r.status_code}: {body}"})
                                return
                            async for line in r.aiter_lines():
                                if not line.startswith("data:"):
                                    continue
                                d = line[5:].strip()
                                if d == "[DONE]":
                                    break
                                try:
                                    j = json.loads(d)
                                except json.JSONDecodeError:
                                    continue
                                if j.get("timings"):
                                    ctoks = j["timings"].get("predicted_n")
                                ch = j.get("choices") or []
                                if not ch:
                                    continue
                                finish = ch[0].get("finish_reason") or finish
                                piece = (ch[0].get("delta") or {}).get("content")
                                if piece:
                                    text += piece
                                    yield nd({"type": "delta", "index": i, "text": piece})
                except httpx.ConnectError:
                    yield nd({"type": "error", "message": "اتصال به سرور OCR برقرار نشد. start_ocr.bat را اجرا کنید."})
                    return
                except Exception as e:  # noqa: BLE001
                    yield nd({"type": "error", "page": i, "message": f"{type(e).__name__}: {e}"})
                    return
                sec = round(time.perf_counter() - tp, 2)
                page_times.append(sec)
                empty = not text.strip()
                if empty:  # keep details for debugging blank OCR output
                    with open(LOGS / "ocr_raw.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps({"file": saved.name, "page": i, "finish_reason": finish, "completion_tokens": ctoks}, ensure_ascii=False) + "\n")
                yield nd({"type": "page", "index": i, "text": text, "seconds": sec, "empty": empty,
                          "finish_reason": finish, "completion_tokens": ctoks})
        total_s = round(time.perf_counter() - t0, 2)
        stats = {"total_s": total_s, "page_seconds": page_times, "resources": resources()}
        log_test({"kind": "ocr", "file": saved.name, "pages": len(pages), **stats})
        yield nd({"type": "done", "stats": stats})

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------- static frontend (must be last) ----------
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
