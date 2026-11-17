# CODING_RULES

- Backend: Python + FastAPI، Pydantic، (از فاز دو) SQLAlchemy 2 + Alembic + SQLite. مدل‌ها فقط از طریق سرویس‌های تعریف‌شده به داده دسترسی دارند، نه SQL آزاد.
- Frontend فعلی: یک HTML ساده بدون build. از فاز دو: React + TypeScript + Tailwind/shadcn.
- رابط فارسی و راست‌چین (`dir="rtl"`)؛ متن پیام‌ها `dir="auto"`. فیلدهای فنی (شناسه، شماره حساب، نام مدل، پورت) با کلاس `.tech`/`.ltr` و فونت SG Kara Standard (ارقام لاتین).
- فونت: متغیر `--font-ui` (SG Kara FaNum) و `--font-tech` (SG Kara) فقط در `:root`؛ جایگزین Tahoma/system-ui. woff2 محلی، نه CDN.
- خطاها به فارسی و قابل فهم به کاربر نشان داده شوند؛ هیچ خطای مدل بدون نمایش رها نشود.
- هر عملیات سنگین (OCR/چت) با قفل صف‌بندی شود؛ مصرف منابع روی ۱۶GB RAM محدود است.
- تغییرات: patch موضعی؛ بازنویسی کامل فایل فقط با دلیل و تأیید.
- هر قابلیت جدید تست خودکار (حداقل smoke) داشته باشد.
