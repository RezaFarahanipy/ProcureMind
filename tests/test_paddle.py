"""PaddleOCR-engine test. Backend must run with PYTHONPATH=tests/fakes (fake paddleocr package).
Usage: python tests/test_paddle.py [http://127.0.0.1:8000]
"""
import io, json, sys
import httpx
from PIL import Image, ImageDraw

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
c = httpx.Client(base_url=BASE, timeout=60)

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

def run(data, name, **form):
    evs = []
    with c.stream("POST", "/api/ocr", files={"file": (name, data)}, data=form) as r:
        for line in r.iter_lines():
            if line.strip():
                evs.append(json.loads(line))
    return evs

st = c.get("/api/paddle/status").json()
check("paddle installed (fake)", st["installed"] and not st["loaded"], st)

img = Image.new("RGB", (900, 500), "white"); ImageDraw.Draw(img).text((40, 40), "hello", fill="black")
buf = io.BytesIO(); img.save(buf, "PNG")
evs = run(buf.getvalue(), "t.png", engine="paddle", paddle_lang="fa")
types = [e["type"] for e in evs]
pg = [e for e in evs if e["type"] == "page"]
check("paddle image: status -> page -> done", "status" in types and len(pg) == 1 and types[-1] == "done", types)
check("paddle page content", pg[0]["source"] == "paddle" and "خط اول" in pg[0]["text"] and pg[0]["lines"] == 2 and pg[0]["mean_score"] == 0.85, pg[0])
check("paddle loaded now", c.get("/api/paddle/status").json()["loaded"])

import fitz
doc = fitz.open(); doc.new_page().insert_text((72, 72), "This page has a real text layer with enough characters in it.")
evs = run(doc.tobytes(), "t.pdf", engine="paddle", mode="auto")
pg = [e for e in evs if e["type"] == "page"]
check("pdf text layer bypasses paddle", pg[0]["source"] == "text-layer")
evs = run(doc.tobytes(), "t.pdf", engine="paddle", mode="ocr")
pg = [e for e in evs if e["type"] == "page"]
check("pdf forced OCR uses paddle", pg[0]["source"] == "paddle")

check("bad engine rejected", c.post("/api/ocr", files={"file": ("a.png", buf.getvalue())}, data={"engine": "x"}).status_code == 400)
c.post("/api/paddle/unload")
check("unload", not c.get("/api/paddle/status").json()["loaded"])
print("ALL OK")
