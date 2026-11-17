# AI_START_HERE — اول این را بخوان

**پروژه:** ProcureMind، سامانه چت‌محور مدیریت تدارکات و بازرگانی (فارسی، RTL، فونت SG Kara).
**سند مبنا:** `docs/ProcureMind_Development_Guidelines.md` (نسخه ۱.۱).
**محیط:** سرور داخلی Windows، CPU/RAM (بدون GPU)، ۵ کاربر LAN. مدل‌ها با llama.cpp.

## قواعد طلایی
1. هیچ جدول/فیلد دیتابیسی بدون پیشنهاد و تأیید صریح مالک ساخته نشود.
2. بازنویسی کد تأییدشده ممنوع؛ فقط اصلاح موضعی (patch). بخش‌های `FROZEN.md` بدون اجازه تغییر نکنند.
3. قبل از ساخت هر چیز، `CODE_MAP.md` را ببین؛ فرض نکن چیزی ساخته نشده است.
4. فونت فقط در یک نقطه تعریف می‌شود (`:root --font-ui` در `frontend/index.html`).
5. تصمیم تجاری را به‌جای مالک نگیر؛ فرض‌ها را اعلام کن.
6. پایان هر کار: `PROJECT_STATE.md` و `SESSION_LOG.md` (و در صورت لزوم `CODE_MAP.md`، `DECISIONS.md`) را به‌روز کن.

## فایل‌ها
- `PROJECT_STATE.md` — وضعیت و گام بعدی
- `CODE_MAP.md` — نقشه کد
- `FROZEN.md` — بخش‌های قفل‌شده
- `CODING_RULES.md` — قواعد کدنویسی
- `SESSION_LOG.md` — لاگ نشست‌ها
- `../DECISIONS.md` — تصمیم‌ها
