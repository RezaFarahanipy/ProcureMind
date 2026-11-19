# CODE_MAP

| فایل | مسئولیت |
|---|---|
| `backend/main.py` | تنها فایل بک‌اند. مدیر مدل‌ها: `/api/models` (لیست فایل‌های `models/` + وضعیت)، `/api/models/load` و `unload` (اجرا/توقف `llama-server` به‌عنوان زیرفرایند، لاگ در `logs/llama_<role>.log`)؛ `/api/pdfinfo`؛ انتخاب صفحه PDF (`parse_pages`) و خواندن مستقیم لایه متنی (`load_pages`؛ `layout_text` حرف‌به‌حرف (rawdict) ردیف و سلول می‌سازد و با `visual_to_logical` ترتیب راست‌به‌چپ را برمی‌گرداند، `normalize_fa` شکل‌های نمایشی را به حروف استاندارد برمی‌گرداند؛ فرم `text_style` = layout|raw).  env config؛ `/api/health` (پینگ دو llama-server)، `/api/chat` (پراکسی استریم به Qwen، زمان‌سنجی، `chat_template_kwargs.enable_thinking`)، `/api/ocr` (ذخیره فایل اصلی در `data/uploads`، PDF→تصویر با PyMuPDF، کوچک‌کردن به `OCR_MAX_SIDE`، یک صفحه در هر درخواست به Dots، قفل: یک کار OCR همزمان)، سرو `frontend/` |
| `backend/requirements.txt` | وابستگی‌های Python |
| `backend/paddle_engine.py` | موتور سوم OCR (PaddleOCR) داخل همان فرایند؛ بارگذاری تنبل با `load(lang)`، `read(img)`، `unload()`؛ اختیاری (`requirements-paddle.txt`) |
| `frontend/index.html` | تمام UI (CSS+JS داخل یک فایل). فونت‌ها در `@font-face`/`:root`. متغیر `history` پیام‌ها، `PROMPTS` پرامپت‌های تحلیل، `poll()` وضعیت سلامت |
| `frontend/fonts/*.woff2` | SG Kara (FaNum و Std)؛ داخل گیت است (مجوز را مالک تأیید کرده) |
| `scripts/setup_windows.ps1` | ساخت venv و دانلود آخرین llama.cpp CPU |
| `scripts/start_app.bat` | اجرای برنامه (پورت ۸۰۰۰). `start_qwen.bat` و `start_ocr.bat` اختیاری و دستی‌اند (پورت ۸۰۸۰ و ۸۰۸۱) |
| `tests/mock_llama.py` | llama-server ساختگی برای تست |
| `tests/smoke_test.py` | تست دود سراسری روی بک‌اند |
| `tests/test_layout.py` | تست ترتیب راست‌به‌چپ و جدول (نیاز به `FONT_TTF` برای ساخت PDF نمونه) |
| `tests/test_paddle.py` + `tests/fakes/paddleocr/` | تست موتور Paddle با بسته‌ی ساختگی (`PYTHONPATH=tests/fakes`) |
| `tests/fake_llama_server.py`, `tests/test_models.py` | تست مدیر مدل‌ها و PDF با llama-server ساختگی (`LLAMA_SERVER_CMD`, `MODELS_DIR`) |
| `docs/` | مستندات؛ `docs/ai-memory/` حافظه دستیار |

## پروتکل‌ها
- چت: POST `/api/chat` → SSE با رویدادهای `delta`، `reasoning`، `error`، `done{stats}`
- OCR: POST `/api/ocr` (multipart `file`, `engine` = dots|paddle, `paddle_lang`, `pages`, `mode`, `prompt`, `max_tokens`) → NDJSON با رویدادهای `queued`، `start`، `status`، `delta` (فقط Dots)، `page`، `error`، `done{stats}`
