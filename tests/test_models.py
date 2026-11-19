"""Model-manager + PDF test. Backend must run with:
  MODELS_DIR=<dir with fake .gguf files>  LLAMA_SERVER_CMD="python tests/fake_llama_server.py"
Usage: python tests/test_models.py [http://127.0.0.1:8000]
"""
import json, sys, time
import httpx
import fitz

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
c = httpx.Client(base_url=BASE, timeout=60)

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

def wait_state(role, want, timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get("/api/models").json()["servers"][role]
        if s["state"] == want:
            return s
        time.sleep(0.5)
    return c.get("/api/models").json()["servers"][role]

m = c.get("/api/models").json()
check("lists models", len(m["chat"]) >= 1 and len(m["ocr"]) >= 1 and len(m["mmproj"]) >= 1, {k: [x["file"] for x in m[k]] for k in ("chat", "ocr", "mmproj")})
check("bad model rejected", c.post("/api/models/load", json={"role": "chat", "model": "../etc/passwd"}).status_code == 400)

r = c.post("/api/models/load", json={"role": "chat", "model": m["chat"][0]["file"]})
check("load chat accepted", r.status_code == 200, r.text)
s = c.get("/api/models").json()["servers"]["chat"]
check("chat is starting or ready", s["state"] in ("starting", "ready"), s)
s = wait_state("chat", "ready")
check("chat becomes ready", s["state"] == "ready", s)

r = c.post("/api/models/load", json={"role": "ocr", "model": m["ocr"][0]["file"], "mmproj": m["mmproj"][0]["file"], "unload_other": True})
check("load ocr accepted", r.status_code == 200, r.text)
s = wait_state("ocr", "ready")
check("ocr becomes ready", s["state"] == "ready", s)
check("chat unloaded (one at a time)", c.get("/api/models").json()["servers"]["chat"]["state"] == "stopped")

doc = fitz.open()
for i in range(4):
    p = doc.new_page(); p.insert_text((72, 72), f"This page {i+1} has a real text layer with enough characters.")
pdf = doc.tobytes()
info = c.post("/api/pdfinfo", files={"file": ("t.pdf", pdf)}).json()
check("pdfinfo", info["pages"] == 4 and info["has_text_layer"], info)

def ocr(mode, pages):
    evs = []
    with c.stream("POST", "/api/ocr", files={"file": ("t.pdf", pdf)}, data={"mode": mode, "pages": pages, "max_tokens": "64"}) as r:
        for line in r.iter_lines():
            if line.strip():
                evs.append(json.loads(line))
    return evs

evs = ocr("auto", "2-3")
pg = [e for e in evs if e["type"] == "page"]
check("auto mode reads text layer of pages 2-3 only", [e["index"] for e in pg] == [2, 3] and all(e.get("source") == "text-layer" for e in pg), [e["index"] for e in pg])
evs = ocr("ocr", "1")
pg = [e for e in evs if e["type"] == "page"]
check("ocr mode runs the model on page 1", len(pg) == 1 and pg[0].get("source") is None and len(pg[0]["text"]) > 0, pg[0]["text"][:30])
evs = ocr("auto", "9")
check("invalid page -> error", any(e["type"] == "error" for e in evs))

c.post("/api/models/unload", json={"role": "ocr"})
check("unload ocr", c.get("/api/models").json()["servers"]["ocr"]["state"] == "stopped")
print("ALL OK")
