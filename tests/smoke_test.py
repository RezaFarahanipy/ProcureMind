"""Smoke test: backend + (mock or real) llama servers must already be running.
Usage: python tests/smoke_test.py [http://127.0.0.1:8000]
"""
import io, json, sys
import httpx
import fitz
from PIL import Image, ImageDraw

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

h = httpx.get(f"{BASE}/api/health").json()
check("health: qwen+ocr reachable", h["qwen"]["ok"] and h["ocr"]["ok"], h)

events = []
with httpx.stream("POST", f"{BASE}/api/chat", json={"messages": [{"role": "user", "content": "سلام"}]}, timeout=60) as r:
    for line in r.iter_lines():
        if line.startswith("data:"):
            events.append(json.loads(line[5:]))
text = "".join(e["text"] for e in events if e["type"] == "delta")
check("chat streams text", len(text) > 0 and events[-1]["type"] == "done", text)

img = Image.new("RGB", (800, 600), "white"); ImageDraw.Draw(img).text((50, 50), "Invoice 123", fill="black")
buf = io.BytesIO(); img.save(buf, "PNG")
def run_ocr(name, data):
    evs = []
    with httpx.stream("POST", f"{BASE}/api/ocr", files={"file": (name, data)}, data={"pages": "1-3", "mode": "ocr"}, timeout=120) as r:
        for line in r.iter_lines():
            if line.strip():
                evs.append(json.loads(line))
    return evs
evs = run_ocr("t.png", buf.getvalue())
check("ocr image", [e["type"] for e in evs][-1] == "done" and any(e["type"] == "page" for e in evs))

doc = fitz.open()
for i in range(3):
    doc.new_page().insert_text((72, 72), f"page {i+1}")
evs = run_ocr("t.pdf", doc.tobytes())
check("ocr pdf 3 pages", sum(e["type"] == "page" for e in evs) == 3)

evs = run_ocr("bad.png", b"not an image")
check("ocr bad file -> error event", any(e["type"] == "error" for e in evs))
print("ALL OK")
