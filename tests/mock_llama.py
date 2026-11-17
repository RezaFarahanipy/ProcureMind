"""Fake llama-server for testing the backend without real models.
Usage: python -m uvicorn tests.mock_llama:app --port 18080
"""
import asyncio, json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/v1/chat/completions")
async def completions(req: Request):
    body = await req.json()
    if not body.get("stream"):
        return JSONResponse({"choices": [{"message": {"content": "# پیش‌فاکتور\nفروشنده: شرکت نمونه\nجمع: 1,000,000 ریال"}}]})
    async def gen():
        for w in ["سلام", " این", " یک", " پاسخ", " آزمایشی", " است."]:
            yield "data: " + json.dumps({"choices": [{"delta": {"content": w}}]}, ensure_ascii=False) + "\n\n"
            await asyncio.sleep(0.05)
        yield "data: " + json.dumps({"choices": [], "timings": {"predicted_per_second": 3.2}}) + "\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
