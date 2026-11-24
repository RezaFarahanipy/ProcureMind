"""Validation and normalisation of Iranian identifiers and contact data (pure functions, no I/O).

Every function returns {"ok", "normalized", "errors", "warnings", ...extra}. Errors mean the value must be corrected;
warnings mean "unusual - ask the user to confirm". Nothing is ever guessed: unknown bank codes give bank=None.
"""
import re
import unicodedata

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# First three digits after "IRkk" in a Shaba (IBAN) identify the bank. Seed list: the owner must verify it;
# an unknown code is reported, never guessed.
IBAN_BANKS = {
    "010": "بانک مرکزی", "011": "بانک صنعت و معدن", "012": "بانک ملت", "013": "بانک رفاه کارگران", "014": "بانک مسکن",
    "015": "بانک سپه", "016": "بانک کشاورزی", "017": "بانک ملی ایران", "018": "بانک تجارت", "019": "بانک صادرات ایران",
    "020": "بانک توسعه صادرات", "021": "پست بانک ایران", "022": "بانک توسعه تعاون", "053": "بانک کارآفرین",
    "054": "بانک پارسیان", "055": "بانک اقتصاد نوین", "056": "بانک سامان", "057": "بانک پاسارگاد", "058": "بانک سرمایه",
    "059": "بانک سینا", "061": "بانک شهر", "062": "بانک آینده", "063": "بانک انصار", "064": "بانک گردشگری",
    "065": "بانک حکمت ایرانیان", "066": "بانک دی", "069": "بانک ایران زمین",
}


def digits(s) -> str:
    return re.sub(r"\D", "", str(s if s is not None else "").translate(_FA_DIGITS))


def normalize_text(s: str) -> str:
    """Standard Persian text: presentation forms -> letters, Arabic ي/ك -> ی/ک, no tatweel, single spaces."""
    t = unicodedata.normalize("NFKC", str(s)).replace("ي", "ی").replace("ك", "ک").replace("ـ", "")
    return re.sub(r"\s+", " ", t).strip()


def fold(s: str) -> str:
    """Key for duplicate detection / lookup matching: ignores spaces, half-spaces, letter variants and case."""
    return normalize_text(s).replace("\u200c", "").replace(" ", "").casefold()


def _res(ok, normalized=None, errors=(), warnings=(), **extra):
    return {"ok": ok, "normalized": normalized, "errors": list(errors), "warnings": list(warnings), **extra}


def national_id_person(value) -> dict:
    d = digits(value)
    if len(d) != 10:
        return _res(False, d or None, [f"کد ملی باید ۱۰ رقم باشد (الان {len(d)} رقم)"])
    if len(set(d)) == 1:
        return _res(False, d, ["کد ملی نامعتبر است (همه ارقام یکسان)"])
    s = sum(int(d[i]) * (10 - i) for i in range(9))
    r = s % 11
    ok = int(d[9]) == (r if r < 2 else 11 - r)
    return _res(ok, d, [] if ok else ["رقم کنترل کد ملی درست نیست؛ احتمالاً یک رقم اشتباه است"])


def national_id_legal(value) -> dict:
    d = digits(value)
    if len(d) != 11:
        return _res(False, d or None, [f"شناسه ملی شخص حقوقی باید ۱۱ رقم باشد (الان {len(d)} رقم)"])
    dd = int(d[9]) + 2
    w = [29, 27, 23, 19, 17, 29, 27, 23, 19, 17]
    r = sum((int(d[i]) + dd) * w[i] for i in range(10)) % 11
    r = 0 if r == 10 else r
    ok = r == int(d[10])
    return _res(ok, d, [] if ok else ["رقم کنترل شناسه ملی درست نیست؛ احتمالاً یک رقم اشتباه است"])


def national_id(value) -> dict:
    """10 digits -> individual (کد ملی); 11 digits -> legal entity (شناسه ملی)."""
    n = len(digits(value))
    if n == 10:
        return {**national_id_person(value), "kind": "person"}
    if n == 11:
        return {**national_id_legal(value), "kind": "legal"}
    return _res(False, digits(value) or None, [f"شناسه باید ۱۰ رقم (حقیقی) یا ۱۱ رقم (حقوقی) باشد؛ الان {n} رقم"], kind=None)


def economic_code(value) -> dict:
    d = digits(value)
    if not d:
        return _res(False, None, ["کد اقتصادی خالی است"])
    w = [] if len(d) in (12, 14) else [f"طول کد اقتصادی معمولاً ۱۲ یا ۱۴ رقم است (الان {len(d)}؛ این قاعده هنوز تأیید نشده)"]
    return _res(True, d, warnings=w)


def mobile(value) -> dict:
    d = digits(value)
    if d.startswith("0098"):
        d = "0" + d[4:]
    elif d.startswith("98") and len(d) == 12:
        d = "0" + d[2:]
    elif len(d) == 10 and d.startswith("9"):
        d = "0" + d
    if len(d) == 11 and d.startswith("09"):
        return _res(True, d)
    return _res(False, d or None, ["شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود"])


def landline(value) -> dict:
    d = digits(value)
    if d.startswith("0098"):
        d = "0" + d[4:]
    elif d.startswith("98") and len(d) == 12:
        d = "0" + d[2:]
    if len(d) == 11 and d.startswith("0") and not d.startswith("09"):
        return _res(True, f"{d[:3]}-{d[3:]}", area_code=d[:3])
    return _res(False, d or None, ["تلفن ثابت باید با کد شهر و ۸ رقم باشد (مثل 021-12345678)"], area_code=None)


def phone(value) -> dict:
    m = mobile(value)
    return {**m, "kind": "mobile"} if m["ok"] else {**landline(value), "kind": "landline"}


def postal_code(value) -> dict:
    d = digits(value)
    if len(d) != 10:
        return _res(False, d or None, [f"کد پستی باید ۱۰ رقم باشد (الان {len(d)} رقم)"])
    return _res(True, d, warnings=["کد پستی با صفر شروع شده است"] if d.startswith("0") else [])


def _mod97(s: str) -> int:
    return int("".join(str(int(ch, 36)) for ch in s[4:] + s[:4])) % 97


def iban(value) -> dict:
    s = re.sub(r"[\s\-]", "", str(value or "")).upper()
    warnings = []
    if s.endswith("IR") and s[:-2].isdigit():  # right-to-left text extraction often glues "IR" to the wrong end
        s, warnings = "IR" + s[:-2], ["ترتیب «IR» در ابتدای شبا اصلاح شد"]
    elif s.isdigit() and len(s) == 24:
        s, warnings = "IR" + s, ["پیشوند IR اضافه شد"]
    if not re.fullmatch(r"IR\d{24}", s):
        return _res(False, s or None, ["شبا باید IR و ۲۴ رقم باشد (در مجموع ۲۶ کاراکتر)"], bank=None, bank_code=None)
    if _mod97(s) != 1:
        return _res(False, s, ["رقم کنترل شبا درست نیست؛ احتمالاً یک رقم اشتباه است"], warnings=warnings, bank=None, bank_code=s[4:7])
    code = s[4:7]
    bank = IBAN_BANKS.get(code)
    if bank is None:
        warnings.append(f"کد بانک {code} در فهرست نیست؛ نام بانک را وارد کنید")
    return _res(True, s, warnings=warnings, bank=bank, bank_code=code)


def card_number(value) -> dict:
    d = digits(value)
    if len(d) != 16:
        return _res(False, d or None, [f"شماره کارت باید ۱۶ رقم باشد (الان {len(d)} رقم)"])
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    ok = total % 10 == 0
    return _res(ok, d, [] if ok else ["رقم کنترل شماره کارت درست نیست"])


KINDS = {"national_id": national_id, "national_id_person": national_id_person, "national_id_legal": national_id_legal,
         "economic_code": economic_code, "mobile": mobile, "landline": landline, "phone": phone,
         "postal_code": postal_code, "iban": iban, "card_number": card_number}


def validate(kind: str, value) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")
    return KINDS[kind](value)
