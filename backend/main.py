"""ProcureMind - Phase 1 prototype backend (chat + OCR test harness).

No database. Talks to two llama-server instances (Qwen chat, Dots OCR).
Every request is timed and appended to logs/tests.jsonl.
"""
import asyncio
import atexit
import base64
import io
import json
import os
import re
import shlex
import subprocess
import time
import unicodedata
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import fitz  # PyMuPDF
import httpx
import psutil
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from backend import paddle_engine as paddle
from backend.doc_classifier import classify
from backend import invoice_calc, lookup, validators
from backend.invoice_parser import merge_header, parse_proforma

ROOT = Path(__file__).resolve().parent.parent


def env(key: str, default: str) -> str:
    return os.environ.get(key, default)


QWEN_URL = env("QWEN_URL", "http://127.0.0.1:8080").rstrip("/")
OCR_URL = env("OCR_URL", "http://127.0.0.1:8081").rstrip("/")
QWEN_THINKING = env("QWEN_THINKING", "0") == "1"
OCR_PROMPT = env("OCR_PROMPT", "Extract the text content from this image.")
OCR_MAX_SIDE = int(env("OCR_MAX_SIDE", "800"))  # smaller image = far fewer vision tokens = much faster on CPU
OCR_PDF_DPI = int(env("OCR_PDF_DPI", "130"))
PADDLE_PDF_DPI = int(env("PADDLE_PDF_DPI", "200"))  # classic OCR needs sharper pages than the vision-LLM
PADDLE_MAX_SIDE = int(env("PADDLE_MAX_SIDE", "2200"))
OCR_MAX_PAGES = int(env("OCR_MAX_PAGES", "10"))
OCR_MAX_TOKENS = int(env("OCR_MAX_TOKENS", "1024"))
OCR_TEMPERATURE = float(env("OCR_TEMPERATURE", "0.1"))  # greedy (0) tends to loop; 0.1 is the model authors' suggestion
OCR_REPEAT_PENALTY = float(env("OCR_REPEAT_PENALTY", "1.05"))
MAX_UPLOAD_MB = 30

UPLOADS = ROOT / "data" / "uploads"
LOGS = ROOT / "logs"
UPLOADS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

MODELS_DIR = Path(env("MODELS_DIR", str(ROOT / "models")))
THREADS = int(env("LLAMA_THREADS", "4"))
_exe = ROOT / "bin" / "llama.cpp" / ("llama-server.exe" if os.name == "nt" else "llama-server")
LLAMA_CMD = shlex.split(env("LLAMA_SERVER_CMD", "")) or [str(_exe)]
URLS = {"chat": QWEN_URL, "ocr": OCR_URL}
PORTS = {"chat": urlparse(QWEN_URL).port or 8080, "ocr": urlparse(OCR_URL).port or 8081}
SERVERS: dict = {"chat": {}, "ocr": {}}  # role -> running llama-server process info
model_lock = asyncio.Lock()


def _stop(role: str) -> None:
    s = SERVERS.get(role) or {}
    proc = s.get("proc")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    if s.get("logf"):
        s["logf"].close()
    SERVERS[role] = {}


def _stop_all() -> None:
    for r in list(SERVERS):
        try:
            _stop(r)
        except Exception:  # noqa: BLE001
            pass


atexit.register(_stop_all)


@asynccontextmanager
async def lifespan(_app):
    yield
    _stop_all()


app = FastAPI(title="ProcureMind Phase 1 prototype", lifespan=lifespan)
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


def crash_msg(role: str) -> str:
    """Message for a dropped connection to llama-server (usually a crash / out of memory) with the log tail."""
    tail = ""
    try:
        tail = (LOGS / f"llama_{role}.log").read_bytes()[-500:].decode("utf-8", "replace")
    except OSError:
        pass
    return f"ارتباط با مدل قطع شد؛ احتمالاً مدل کرش کرد یا RAM کم آمد (جزئیات: logs\\llama_{role}.log).\n{tail}".strip()


def log_test(entry: dict) -> None:
    entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), **entry}
    with open(LOGS / "tests.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


psutil.cpu_percent(interval=None)  # prime


# ---------- health ----------
async def ping(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{url}/health")
        return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": str(type(e).__name__)}


@app.get("/api/health")
async def health():
    qwen, ocr_ = await asyncio.gather(ping(QWEN_URL), ping(OCR_URL))
    return {"qwen": qwen, "ocr": ocr_, "resources": resources()}


# ---------- model manager (start/stop llama-server from the UI) ----------
def list_models() -> dict:
    files = sorted(MODELS_DIR.rglob("*.gguf")) if MODELS_DIR.exists() else []

    def info(p: Path) -> dict:
        return {"file": str(p.relative_to(MODELS_DIR)).replace("\\", "/"), "size_gb": round(p.stat().st_size / 1e9, 2)}

    mmproj = [info(p) for p in files if "mmproj" in p.name.lower()]
    llm = [p for p in files if "mmproj" not in p.name.lower()]
    is_ocr = lambda p: bool(re.search(r"dots|ocr", p.name, re.I))  # noqa: E731
    ocr_ = [info(p) for p in sorted(llm, key=lambda p: (not is_ocr(p), p.name.lower()))]  # any vision model + mmproj can read images
    chat_ = [info(p) for p in llm if not is_ocr(p)]
    return {"chat": chat_, "ocr": ocr_, "mmproj": mmproj}


def resolve_model(rel: str) -> Path:
    p = (MODELS_DIR / rel).resolve()
    if p.suffix.lower() != ".gguf" or not p.is_file() or MODELS_DIR.resolve() not in p.parents:
        raise HTTPException(400, f"فایل مدل معتبر نیست: {rel}")
    return p


def _start(role: str, model: Path, mmproj: Path | None, ctx: int) -> None:
    cmd = LLAMA_CMD + ["-m", str(model), "--host", "127.0.0.1", "--port", str(PORTS[role]),
                       "-np", "1", "-c", str(ctx), "-t", str(THREADS), "--jinja"]
    if role == "ocr" and mmproj:
        cmd += ["--mmproj", str(mmproj), "-n", "4096", "--temp", "0.1"]
    logf = open(LOGS / f"llama_{role}.log", "wb")
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=str(ROOT),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    SERVERS[role] = {"proc": proc, "logf": logf, "model": model.name, "mmproj": mmproj.name if mmproj else None,
                     "ctx": ctx, "t0": time.time(), "ready_s": None}


class LoadReq(BaseModel):
    role: str
    model: str
    mmproj: str = ""
    ctx: int = 0
    unload_other: bool = True


class UnloadReq(BaseModel):
    role: str


@app.get("/api/models")
async def models_state():
    out = {**list_models(), "servers": {}}
    for role, s in SERVERS.items():
        if not s:
            ext = await ping(URLS[role])
            out["servers"][role] = {"state": "external" if ext["ok"] else "stopped"}
            continue
        code = s["proc"].poll()
        if code is not None:
            try:
                tail = (LOGS / f"llama_{role}.log").read_bytes()[-1500:].decode("utf-8", "replace")
            except OSError:
                tail = ""
            out["servers"][role] = {"state": "failed", "exit_code": code, "model": s["model"], "log_tail": tail}
            continue
        ok = (await ping(URLS[role]))["ok"]
        if ok and s["ready_s"] is None:
            s["ready_s"] = round(time.time() - s["t0"], 1)
            log_test({"kind": "model_load", "role": role, "model": s["model"], "mmproj": s["mmproj"],
                      "ctx": s["ctx"], "load_s": s["ready_s"], "resources": resources()})
        out["servers"][role] = {"state": "ready" if ok else "starting", "model": s["model"], "mmproj": s["mmproj"],
                                "ctx": s["ctx"], "elapsed_s": round(time.time() - s["t0"]), "load_s": s["ready_s"]}
    return out


@app.post("/api/models/load")
async def models_load(req: LoadReq):
    if req.role not in SERVERS:
        raise HTTPException(400, "role باید chat یا ocr باشد")
    model = resolve_model(req.model)
    mm = None
    if req.role == "ocr":
        if not req.mmproj:
            raise HTTPException(400, "برای OCR باید فایل mmproj هم انتخاب شود")
        mm = resolve_model(req.mmproj)
    ctx = req.ctx or (8192 if req.role == "ocr" else 4096)
    async with model_lock:
        if req.unload_other:
            await asyncio.to_thread(_stop, "ocr" if req.role == "chat" else "chat")
        await asyncio.to_thread(_stop, req.role)
        if (await ping(URLS[req.role]))["ok"]:
            raise HTTPException(409, "روی این پورت سرور دیگری (مثلاً از start_*.bat) در حال اجراست. پنجره‌اش را ببندید.")
        try:
            await asyncio.to_thread(_start, req.role, model, mm, ctx)
        except FileNotFoundError:
            raise HTTPException(500, f"llama-server پیدا نشد: {LLAMA_CMD[0]} — setup_windows.ps1 را اجرا کنید.")
    return {"ok": True}


@app.post("/api/models/unload")
async def models_unload(req: UnloadReq):
    if req.role not in SERVERS:
        raise HTTPException(400, "role باید chat یا ocr باشد")
    async with model_lock:
        await asyncio.to_thread(_stop, req.role)
    return {"ok": True}


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
                yield sse({"type": "error", "message": "مدل چت آماده نیست. از بخش «مدل‌ها» بالای صفحه یک مدل چت بارگذاری کنید."})
                return
            except (httpx.ReadError, httpx.RemoteProtocolError):
                yield sse({"type": "error", "message": crash_msg("chat")})
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
            "model": SERVERS["chat"].get("model"),
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


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_pages(spec: str, total: int) -> list[int]:
    spec = (spec or "1").translate(_DIGITS).strip().lower()
    if spec in ("all", "همه"):
        nums = list(range(1, total + 1))
    else:
        nums = []
        for part in re.split(r"[,\s،]+", spec):
            if "-" in part:
                x, _, y = part.partition("-")
                if x.isdigit() and y.isdigit():
                    nums += list(range(int(x), int(y) + 1))
            elif part.isdigit():
                nums.append(int(part))
    return sorted({n for n in nums if 1 <= n <= total})[:OCR_MAX_PAGES]


_STRONG_R = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_MIRROR = str.maketrans("()[]<>«»{}", ")(][><»«}{")


def normalize_fa(s: str) -> str:
    """Presentation forms (ﺗﺎﯾﯿﺪ) -> standard letters (تایید); Arabic kaf/yeh -> Persian ک / ی."""
    s = unicodedata.normalize("NFKC", s)
    return s.replace("\u0643", "\u06A9").replace("\u064A", "\u06CC")


def _cls(ch: str) -> str:
    c = ch[0]
    if c.isdigit():
        return "L"
    if _STRONG_R.match(c):
        return "R"
    return "L" if c.isalpha() else "N"


def visual_to_logical(items: list[str]) -> str:
    """`items` are characters in visual (left-to-right) order. Returns the logical string for an RTL base direction
    (simplified Unicode bidi: Persian/Arabic runs are reversed, digits/Latin runs keep their order)."""
    cls = [_cls(c) for c in items]
    if "R" not in cls:
        return "".join(items)
    n, res, i = len(items), cls[:], 0
    while i < n:  # resolve neutrals (rules N1/N2)
        if cls[i] == "N":
            j = i
            while j < n and cls[j] == "N":
                j += 1
            left = cls[i - 1] if i else "R"
            right = cls[j] if j < n else "R"
            for k in range(i, j):
                res[k] = left if left == right else "R"
            i = j
        else:
            i += 1
    segs: list[list] = []
    for ch, c in zip(items, res):
        if segs and segs[-1][0] == c:
            segs[-1][1].append(ch)
        else:
            segs.append([c, [ch]])
    out = ""
    for c, chs in reversed(segs):
        part = "".join(chs) if c == "L" else "".join(chs[::-1]).translate(_MIRROR)
        if out and not out[-1].isspace() and not part[0].isspace() and c != prev:
            out += " "  # digits glued to letters ("693متر") -> separate them
        out += part
        prev = c
    return out


def layout_text(page) -> str:
    """Text-layer extraction from character positions: rebuilds visual rows (by y), splits them into cells at wide gaps
    (table columns), converts each cell from visual to logical order and orders cells right-to-left. Cells joined by ' | '."""
    chars = []  # (x0, x1, yc, size, text)
    for b in page.get_text("rawdict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    t = normalize_fa(ch["c"])
                    x0, y0, x1, y1 = ch["bbox"]
                    if t:
                        chars.append((x0, x1, (y0 + y1) / 2, sp["size"], t))
    if not chars:
        return ""
    sizes = sorted(c[3] for c in chars)
    size = sizes[len(sizes) // 2] or 9.0
    letters = [c for c in chars if c[4].strip() and (c[4][0].isalpha())]
    page_rtl = bool(letters) and sum(1 for c in letters if _STRONG_R.match(c[4][0])) * 10 >= len(letters) * 3
    chars.sort(key=lambda c: c[2])
    rows: list[dict] = []
    for c in chars:
        if rows and abs(c[2] - rows[-1]["yc"]) <= 0.5 * size:
            r = rows[-1]
            r["c"].append(c)
            r["yc"] += (c[2] - r["yc"]) / len(r["c"])
        else:
            rows.append({"yc": c[2], "c": [c]})
    gap_limit = 1.2 * size
    lines = []
    for r in rows:
        cs = sorted(r["c"], key=lambda c: (c[0] + c[1]) / 2)
        cells, cur = [], [cs[0]]
        for prev_c, c in zip(cs, cs[1:]):
            if c[0] - prev_c[1] > gap_limit:
                cells.append(cur)
                cur = []
            cur.append(c)
        cells.append(cur)
        has_r = any(_STRONG_R.match(c[4][0]) for c in cs)
        texts = []
        for cell in cells:
            s = visual_to_logical([c[4] for c in cell]).strip()
            if s:
                texts.append(s)
        if has_r or page_rtl:
            texts.reverse()  # right-most cell first
        if texts:
            lines.append(" | ".join(texts))
    return "\n".join(lines)


def load_pages(data: bytes, filename: str, spec: str, mode: str, dpi: int = 0, text_style: str = "layout") -> tuple[list[dict], int]:
    """Return (items, total pages). Each item: {index, image|None, text|None}.
    For PDFs in 'auto' mode, a page that already has a text layer is read directly (no OCR)."""
    if filename.lower().endswith(".pdf") or data[:4] == b"%PDF":
        doc = fitz.open(stream=data, filetype="pdf")
        total = doc.page_count
        items = []
        for n in parse_pages(spec, total):
            page = doc[n - 1]
            if mode == "auto":
                txt = page.get_text("text").strip()
                if len(txt) >= 30:
                    items.append({"index": n, "image": None, "text": layout_text(page) if text_style == "layout" else txt})
                    continue
            pix = page.get_pixmap(dpi=dpi or OCR_PDF_DPI)
            items.append({"index": n, "image": Image.frombytes("RGB", (pix.width, pix.height), pix.samples), "text": None})
        if not items:
            raise ValueError(f"شماره صفحه معتبر نیست (فایل {total} صفحه دارد)")
        return items, total
    return [{"index": 1, "image": Image.open(io.BytesIO(data)), "text": None}], 1


@app.get("/api/paddle/status")
async def paddle_status():
    return paddle.status()


@app.post("/api/paddle/unload")
async def paddle_unload():
    await asyncio.to_thread(paddle.unload)
    return {"ok": True}


class ParseReq(BaseModel):
    text: str


@app.post("/api/classify")
async def classify_document(req: ParseReq):
    """Detect what kind of document this text is (pre-invoice, invoice, purchase request, ...) with plain rules."""
    return classify(req.text)


@app.post("/api/invoice/parse")
async def invoice_parse(req: ParseReq):
    """Read the item table of a pre-invoice with code only (arithmetic-verified); returns the header text for the LLM."""
    return parse_proforma(req.text)


class HeaderReq(BaseModel):
    header_text: str
    full_text: str = ""
    model: dict = {}


@app.post("/api/invoice/header-check")
async def invoice_header_check(req: HeaderReq):
    """Merge the model's {seller, buyer} with regex-read number/date/currency/buyer and verify against the document."""
    return merge_header(req.model, req.header_text, req.full_text)


class ValidateReq(BaseModel):
    kind: str
    value: str


@app.post("/api/validate")
async def validate_field(req: ValidateReq):
    """Validate + normalise one identifier (national_id, economic_code, mobile, landline, phone, postal_code, iban, card_number)."""
    try:
        return validators.validate(req.kind, req.value)
    except ValueError as e:
        raise HTTPException(400, str(e))


class CanonReq(BaseModel):
    list_key: str
    value: str


@app.post("/api/lookup/canonicalize")
async def lookup_canonicalize(req: CanonReq):
    """Standardise a free-text value (province, unit, ...) to its canonical form, suggest close matches, or flag it as new."""
    return lookup.canonicalize(req.list_key, req.value)


class QueryReq(BaseModel):
    question: str
    invoice: dict


@app.post("/api/invoice/query")
async def invoice_query(req: QueryReq):
    """Answer a calculation question (VAT, total weight, ...) about an extracted invoice with code, or say it is not handled."""
    r = invoice_calc.answer(req.question, req.invoice)
    return {"handled": r is not None, **(r or {})}


@app.get("/api/version")
async def version():
    v = (ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else "0.0.0"
    commit = date = None
    try:
        run = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, timeout=3).stdout.strip() or None  # noqa: E731
        commit, date = run("rev-parse", "--short", "HEAD"), run("log", "-1", "--format=%cs")
    except Exception:  # noqa: BLE001  (git missing: show the version only)
        pass
    return {"version": v, "commit": commit, "date": date}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Keep the original file (used when the text is entered manually)."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"حداکثر حجم فایل {MAX_UPLOAD_MB}MB است")
    saved = UPLOADS / f"{time.strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:6]}_{Path(file.filename or 'upload').name}"
    saved.write_bytes(data)
    return {"file": saved.name, "size": len(data)}


@app.post("/api/pdfinfo")
async def pdfinfo(file: UploadFile = File(...)):
    data = await file.read()
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "PDF خوانده نشد")
    sample = [len(doc[i].get_text("text").strip()) for i in range(min(doc.page_count, 3))]
    return {"pages": doc.page_count, "text_chars_first_pages": sample, "has_text_layer": any(c >= 30 for c in sample)}


@app.post("/api/ocr")
async def ocr(file: UploadFile = File(...), prompt: str = Form(""), max_tokens: int = Form(0),
              pages_spec: str = Form("1", alias="pages"), mode: str = Form("auto"),
              engine: str = Form("dots"), paddle_lang: str = Form("fa"), text_style: str = Form("layout")):
    if engine not in ("dots", "paddle", "text"):
        raise HTTPException(400, "engine باید dots یا paddle یا text باشد")
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
                dpi = 20 if engine == "text" else (PADDLE_PDF_DPI if engine == "paddle" else OCR_PDF_DPI)
                items, total = await asyncio.to_thread(load_pages, data, name, pages_spec, mode, dpi, text_style)
            except Exception as e:  # noqa: BLE001
                yield nd({"type": "error", "message": f"فایل خوانده نشد: {e}"})
                return
            yield nd({"type": "start", "pages": len(items), "total_pages": total, "file": saved.name, "engine": engine})
            page_times = []
            if engine == "paddle" and any(it["text"] is None for it in items):
                if not paddle.installed():
                    yield nd({"type": "error", "message": "PaddleOCR نصب نیست. دستور: pip install -r backend\\requirements-paddle.txt"})
                    return
                yield nd({"type": "status", "message": f"بارگذاری مدل PaddleOCR ({paddle_lang})؛ بار اول ممکن است مدل‌ها از اینترنت دانلود شوند…"})
                try:
                    load_s, fresh = await asyncio.to_thread(paddle.load, paddle_lang)
                except Exception as e:  # noqa: BLE001
                    yield nd({"type": "error", "message": f"بارگذاری PaddleOCR ناموفق بود: {type(e).__name__}: {str(e)[:300]}"})
                    return
                if fresh:
                    log_test({"kind": "model_load", "role": "paddle", "model": f"PaddleOCR-{paddle_lang}", "load_s": load_s, "resources": resources()})
                yield nd({"type": "status", "message": f"PaddleOCR آماده است ({load_s} ثانیه)"})
            for item in items:
                i, img = item["index"], item["image"]
                if engine == "text" and item["text"] is None:  # text-layer-only method: never run OCR
                    page_times.append(0)
                    yield nd({"type": "page", "index": i, "text": "", "seconds": 0, "empty": True, "finish_reason": None,
                              "completion_tokens": None, "source": "no-text-layer"})
                    continue
                if item["text"] is not None:  # PDF text layer: no OCR needed
                    page_times.append(0)
                    yield nd({"type": "page", "index": i, "text": item["text"], "seconds": 0, "empty": False,
                              "finish_reason": None, "completion_tokens": None, "source": "text-layer"})
                    continue
                if engine == "paddle":
                    tp = time.perf_counter()
                    w, h = img.size
                    if max(w, h) > PADDLE_MAX_SIDE:
                        k = PADDLE_MAX_SIDE / max(w, h)
                        img = img.resize((int(w * k), int(h * k)), Image.LANCZOS)
                    try:
                        pr = await asyncio.to_thread(paddle.read, img)
                    except Exception as e:  # noqa: BLE001
                        yield nd({"type": "error", "page": i, "message": f"PaddleOCR: {type(e).__name__}: {str(e)[:300]}"})
                        return
                    sec = round(time.perf_counter() - tp, 2)
                    page_times.append(sec)
                    yield nd({"type": "page", "index": i, "text": pr["text"], "seconds": sec, "empty": not pr["text"].strip(),
                              "finish_reason": None, "completion_tokens": None, "source": "paddle",
                              "lines": pr["lines"], "mean_score": pr["mean_score"]})
                    continue
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
                    yield nd({"type": "error", "message": "مدل OCR آماده نیست. از بخش «مدل‌ها» بالای صفحه یک مدل OCR بارگذاری کنید."})
                    return
                except (httpx.ReadError, httpx.RemoteProtocolError):
                    yield nd({"type": "error", "page": i, "message": crash_msg("ocr")})
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
        log_test({"kind": "ocr", "engine": engine, "file": saved.name, "pages": len(items),
                  "model": (f"PaddleOCR-{paddle_lang}" if engine == "paddle" else SERVERS["ocr"].get("model")), **stats})
        yield nd({"type": "done", "stats": stats})

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------- static frontend (must be last) ----------
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
