"""Fake llama-server for testing the backend without real models.
Usage: python -m uvicorn tests.mock_llama:app --port 18080
"""
import asyncio, json, os, time
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI()
T0 = time.time()
DELAY = float(os.environ.get("LOAD_DELAY", "0"))  # simulate model loading time

@app.get("/health")
async def health():
    if time.time() - T0 < DELAY:
        return JSONResponse({"status": "loading"}, status_code=503)
    return {"status": "ok"}

@app.post("/v1/chat/completions")
async def completions(req: Request):
    body = await req.json()
    if not body.get("stream"):
        return JSONResponse({"choices": [{"message": {"content": "# پیش‌فاکتور\nفروشنده: شرکت نمونه\nجمع: 1,000,000 ریال"}}]})
    joined = " ".join(str(m.get("content", "")) for m in body.get("messages", []))
    if "دو کلید seller و buyer" in joined:  # header-only prompt
        data = '{"seller":"شرکت نمونه","buyer":"شرکت خریدار"}'
        words = [data[i:i + 12] for i in range(0, len(data), 12)]
    elif "items[" in joined:  # full pre-invoice prompt: answer with JSON (row 2 qty deliberately wrong)
        data = ('{"seller":"شرکت نمونه","number":"1001","date":"1405/01/01","currency":"ریال","items":['
                '{"row":1,"qty":10,"unit":"کیلوگرم","unit_price":1000,"total":10000},'
                '{"row":2,"qty":4,"unit":"متر","unit_price":2000,"total":10000}],'
                '"total_before_tax":20000,"tax":2000,"grand_total":22000}')
        words = [data[i:i + 12] for i in range(0, len(data), 12)]
    else:
        words = ["سلام", " این", " یک", " پاسخ", " آزمایشی", " است."]

    async def gen():
        for w in words:
            yield "data: " + json.dumps({"choices": [{"delta": {"content": w}}]}, ensure_ascii=False) + "\n\n"
            await asyncio.sleep(0.05)
        yield "data: " + json.dumps({"choices": [], "timings": {"predicted_per_second": 3.2}}) + "\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
