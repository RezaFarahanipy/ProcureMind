"""Text-layer-only method and upload endpoint. Usage: python tests/test_text_engine.py [http://127.0.0.1:8000]"""
import io, json, sys
import httpx, fitz
from PIL import Image

c = httpx.Client(base_url=sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000", timeout=60)
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok: sys.exit(1)
def run(data, name, **form):
    with c.stream("POST", "/api/ocr", files={"file": (name, data)}, data=form) as r:
        return [json.loads(l) for l in r.iter_lines() if l.strip()]

doc = fitz.open()
doc.new_page().insert_text((72, 72), "This page has a real text layer with enough characters in it.")
doc.new_page()  # scanned-like page: no text at all
pdf = doc.tobytes()
evs = run(pdf, "t.pdf", engine="text", mode="auto", pages="1-2")
pg = [e for e in evs if e["type"] == "page"]
check("text method: page 1 read from text layer", pg[0]["source"] == "text-layer" and "real text layer" in pg[0]["text"])
check("text method: page 2 reports no text layer and never runs OCR", pg[1]["source"] == "no-text-layer" and pg[1]["text"] == "")
b = io.BytesIO(); Image.new("RGB", (100, 80), "white").save(b, "PNG")
evs = run(b.getvalue(), "a.png", engine="text")
check("text method on an image -> no-text-layer", [e for e in evs if e["type"] == "page"][0]["source"] == "no-text-layer")
r = c.post("/api/upload", files={"file": ("orig.pdf", pdf)})
check("upload keeps the original", r.status_code == 200 and r.json()["file"].endswith("orig.pdf"), r.text)
print("ALL OK")
