# ProcureMind

سامانه هوشمند مدیریت بازرگانی و تدارکات با رابط چت‌محور.
سند مبنا: [`docs/ProcureMind_Development_Guidelines.md`](docs/ProcureMind_Development_Guidelines.md)

## وضعیت فعلی: فاز صفر و یک (نمونه اولیه تست مدل‌ها)

یک چت ساده فارسی + OCR برای آزمایش مدل‌ها روی سخت‌افزار واقعی. **هنوز دیتابیس و ماژول کسب‌وکار ندارد** (طبق دستورالعمل).

| بخش | کار |
|---|---|
| چت | گفت‌وگوی استریم با Qwen، نمایش زمان، توکن بر ثانیه و مصرف RAM/CPU |
| OCR | آپلود تصویر یا PDF (حداکثر ۱۰ صفحه)، نمایش پیشرفت هر صفحه، متن قابل ویرایش |
| تحلیل | ارسال متن اصلاح‌شده به Qwen (خلاصه، یا استخراج JSON پیش‌فاکتور/درخواست خرید) |
| لاگ | هر درخواست در `logs/tests.jsonl` ثبت می‌شود؛ فایل‌های آپلودی اصلی در `data/uploads/` |

## نصب روی ویندوز

پیش‌نیاز: Python 3.10 به بالا (با تیک Add to PATH) و اینترنت برای نصب اولیه.

1. مخزن را clone کنید.
2. `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1`
   (محیط `.venv`، وابستگی‌ها و آخرین llama.cpp نسخه CPU را نصب می‌کند)
3. مدل‌ها را در پوشه `models\` بگذارید (نام فایل‌ها دقیقاً همین‌ها باشد):
   - `Qwen3.5-9B-Q4_K_M.gguf`
   - `Dots.Ocr-1.8B-Q8_0.gguf`
   - `mmproj-Dots.Ocr-F16.gguf`
4. فونت SG Kara همراه مخزن است (`frontend\fonts\`).
5. اجرا (هر کدام یک پنجره جدا):
   - `scripts\start_qwen.bat`
   - `scripts\start_ocr.bat`
   - `scripts\start_app.bat` ← سپس <http://127.0.0.1:8000>

نقطه‌های سبز بالای صفحه نشان می‌دهند هر مدل بالا آمده است.

## نکات سخت‌افزار (۱۶ گیگ RAM، بدون GPU)

- Qwen 9B و Dots OCR با هم حدود ۱۰ تا ۱۱ گیگ RAM می‌گیرند (تخمین؛ باید اندازه‌گیری شود). اگر RAM پر شد، **هر بار فقط یکی را اجرا کنید**.
- سرعت Qwen 9B روی CPU کند است (چند توکن در ثانیه). همین عدد را در نتایج ثبت کنید.
- OCR با ctx=8192 اجرا می‌شود؛ مقدار پیشنهادی مدل ۱۳۱۰۷۲ است ولی RAM زیادی می‌خواهد.

## سازگاری مدل‌ها (باید تست شود)

Dots OCR فقط با نسخه‌ای از llama.cpp کار می‌کند که پروژکتور `dots_ocr` را دارد (طبق صفحه‌های مدل، build شماره b8731 به بعد). اگر `start_ocr.bat` خطای معماری یا mmproj داد، llama.cpp را به‌روز کنید یا fork ذکرشده در صفحه مدل را امتحان کنید. نتیجه را در `docs/AI_OCR_TESTS.md` بنویسید.

## تست بدون مدل واقعی

```
python -m uvicorn tests.mock_llama:app --port 18080
python -m uvicorn tests.mock_llama:app --port 18081
set QWEN_URL=http://127.0.0.1:18080 & set OCR_URL=http://127.0.0.1:18081
python -m uvicorn backend.main:app --port 8000
python tests\smoke_test.py
```

## برای دستیار هوش مصنوعی

اول `docs/ai-memory/AI_START_HERE.md` را بخوانید.
