# CODE_MAP

| فایل | مسئولیت |
|---|---|
| `backend/main.py` | تنها فایل بک‌اند. مدیر مدل‌ها: `/api/models` (لیست فایل‌های `models/` + وضعیت)، `/api/models/load` و `unload` (اجرا/توقف `llama-server` به‌عنوان زیرفرایند، لاگ در `logs/llama_<role>.log`)؛ `/api/pdfinfo`؛ انتخاب صفحه PDF (`parse_pages`) و خواندن مستقیم لایه متنی (`load_pages`؛ `layout_text` حرف‌به‌حرف (rawdict) ردیف و سلول می‌سازد و با `visual_to_logical` ترتیب راست‌به‌چپ را برمی‌گرداند، `normalize_fa` شکل‌های نمایشی را به حروف استاندارد برمی‌گرداند؛ فرم `text_style` = layout|raw).  env config؛ `/api/health` (پینگ دو llama-server)، `/api/chat` (پراکسی استریم به Qwen، زمان‌سنجی، `chat_template_kwargs.enable_thinking`)، `/api/ocr` (ذخیره فایل اصلی در `data/uploads`، PDF→تصویر با PyMuPDF، کوچک‌کردن به `OCR_MAX_SIDE`، یک صفحه در هر درخواست به Dots، قفل: یک کار OCR همزمان)، سرو `frontend/` |
| `backend/requirements.txt` | وابستگی‌های Python |
| `backend/validators.py` | اعتبارسنجی و نرمال‌سازی شناسه‌ها (کد/شناسه ملی، شبا + بانک، موبایل، تلفن، کد پستی، کد اقتصادی، کارت) و `normalize_text`/`fold`؛ endpoint: `/api/validate` |
| `backend/lookup.py` | استانداردسازی متن آزاد (استان، واحد…) با نام مستعار و پیشنهاد نزدیک؛ مدل درون‌حافظه‌ی `lookup_values`/`lookup_aliases`؛ endpoint: `/api/lookup/canonicalize` |
| `backend/invoice_calc.py` | پاسخ دقیق با کد به سؤال‌های محاسباتی روی پیش‌فاکتور استخراج‌شده؛ endpoint: `/api/invoice/query` |
| `scripts/update.py`, `scripts/update.bat` | به‌روزرسانی با یک کلیک از گیت‌هاب (پوشه‌های کاربر را حفظ می‌کند) |
| `VERSION`, `CHANGELOG.md`, `scripts/release.py` | نسخه‌بندی؛ `/api/version` |
| `backend/doc_classifier.py` | تشخیص نوع سند با قواعد (پیش‌فاکتور، فاکتور، درخواست خرید، استعلام، رسید پرداخت، رسید انبار، سفارش/قرارداد، بارنامه)؛ endpoint: `/api/classify` |
| `backend/invoice_parser.py` | خواندن جدول پیش‌فاکتور بدون مدل: ردیف‌ها را با شرط «تعداد×فی=مبلغ» (کنار هم) پیدا می‌کند، تخفیف/مالیات/جمع هر ردیف و جمع‌های کل را تأیید می‌کند، متن سربرگ را جدا می‌دهد. endpoint: `/api/invoice/parse`؛ `code_header` شماره/تاریخ/ارز/خریدار را با regex می‌خواند و `merge_header` پاسخ مدل ({seller,buyer}) را با متن سند تطبیق می‌دهد؛ endpoint: `/api/invoice/header-check` |
| `backend/paddle_engine.py` | موتور سوم OCR (PaddleOCR) داخل همان فرایند؛ بارگذاری تنبل با `load(lang)`، `read(img)`، `unload()`؛ اختیاری (`requirements-paddle.txt`) |
| `frontend/index.html` | تمام UI (CSS+JS داخل یک فایل، بدون build): منوی راست جمع‌شونده + سوابق (localStorage)، چت، پنل چپ فایل‌ها/خلاصه‌ی پیش‌فاکتور، تم، پنجره‌ی تنظیمات. منطق: `handleSend`, `askModel`, `createCard`, `runExtraction`, `analyze`, `classifyAndPick`, `analyzeHybrid`, `tryInvoiceQuery`, `checkInvoice`, `normalizeFa`, `refreshModels`, `saveChat/openChat` |
| `frontend/fonts/*.woff2` | SG Kara (FaNum و Std)؛ داخل گیت است (مجوز را مالک تأیید کرده) |
| `scripts/setup_windows.ps1` | ساخت venv و دانلود آخرین llama.cpp CPU |
| `scripts/bench_chat.py` | مقایسه خودکار مدل‌های چت روی یک PDF از طریق بک‌اند در حال اجرا (زمان، JSON، حساب‌ها، دقت نسبت به golden). پرامپت‌ها را از `frontend/index.html` می‌خواند |
| `tests/golden/` | فایل‌های «پاسخ درست»؛ فقط `example_proforma.json` در گیت است، `private_*.json` ignore می‌شود |
| `scripts/start_app.bat` | اجرای برنامه (پورت ۸۰۰۰). `start_qwen.bat` و `start_ocr.bat` اختیاری و دستی‌اند (پورت ۸۰۸۰ و ۸۰۸۱) |
| `tests/mock_llama.py` | llama-server ساختگی برای تست |
| `tests/smoke_test.py` | تست دود سراسری روی بک‌اند |
| `tests/ui_test.js` | تست سراسری رابط با jsdom (نیاز به `npm install jsdom`) |
| `tests/test_lookup.py` | تست استانداردسازی |
| `tests/test_validators.py`, `tests/test_invoice_calc.py` | تست اعتبارسنج‌ها و محاسبات |
| `tests/test_classifier.py` | تست تشخیص نوع سند (با `PDF=` روی سند واقعی) |
| `tests/test_invoice_parser.py` + `tests/fixtures/proforma_layout.txt` | تست پارسر با پیش‌فاکتور ساختگی؛ با `PDF=` و `GOLDEN=` روی سند واقعی |
| `tests/test_text_engine.py` | روش «فقط لایه متنی» و `/api/upload` |
| `tests/test_layout.py` | تست ترتیب راست‌به‌چپ و جدول (نیاز به `FONT_TTF` برای ساخت PDF نمونه) |
| `tests/test_paddle.py` + `tests/fakes/paddleocr/` | تست موتور Paddle با بسته‌ی ساختگی (`PYTHONPATH=tests/fakes`) |
| `tests/fake_llama_server.py`, `tests/test_models.py` | تست مدیر مدل‌ها و PDF با llama-server ساختگی (`LLAMA_SERVER_CMD`, `MODELS_DIR`) |
| `docs/` | مستندات؛ `docs/ai-memory/` حافظه دستیار |

## پروتکل‌ها
- چت: POST `/api/chat` → SSE با رویدادهای `delta`، `reasoning`، `error`، `done{stats}`
- OCR: POST `/api/ocr` (multipart `file`, `engine` = text|dots|paddle, `paddle_lang`, `pages`, `mode`, `prompt`, `max_tokens`) → NDJSON با رویدادهای `queued`، `start`، `status`، `delta` (فقط Dots)، `page`، `error`، `done{stats}`
