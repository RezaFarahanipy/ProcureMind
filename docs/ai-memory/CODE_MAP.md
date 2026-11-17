# CODE_MAP

| فایل | مسئولیت |
|---|---|
| `backend/main.py` | تنها فایل بک‌اند. env config؛ `/api/health` (پینگ دو llama-server)، `/api/chat` (پراکسی استریم به Qwen، زمان‌سنجی، `chat_template_kwargs.enable_thinking`)، `/api/ocr` (ذخیره فایل اصلی در `data/uploads`، PDF→تصویر با PyMuPDF، کوچک‌کردن به `OCR_MAX_SIDE`، یک صفحه در هر درخواست به Dots، قفل: یک کار OCR همزمان)، سرو `frontend/` |
| `backend/requirements.txt` | وابستگی‌های Python |
| `frontend/index.html` | تمام UI (CSS+JS داخل یک فایل). فونت‌ها در `@font-face`/`:root`. متغیر `history` پیام‌ها، `PROMPTS` پرامپت‌های تحلیل، `poll()` وضعیت سلامت |
| `frontend/fonts/*.woff2` | SG Kara (FaNum و Std)؛ داخل گیت است (مجوز را مالک تأیید کرده) |
| `scripts/setup_windows.ps1` | ساخت venv و دانلود آخرین llama.cpp CPU |
| `scripts/start_qwen.bat` / `start_ocr.bat` / `start_app.bat` | اجرای سرورها (پورت‌ها ۸۰۸۰ / ۸۰۸۱ / ۸۰۰۰) |
| `tests/mock_llama.py` | llama-server ساختگی برای تست |
| `tests/smoke_test.py` | تست دود سراسری روی بک‌اند |
| `docs/` | مستندات؛ `docs/ai-memory/` حافظه دستیار |

## پروتکل‌ها
- چت: POST `/api/chat` → SSE با رویدادهای `delta`، `reasoning`، `error`، `done{stats}`
- OCR: POST `/api/ocr` (multipart `file`) → NDJSON با رویدادهای `queued`، `start`، `page`، `error`، `done{stats}`
