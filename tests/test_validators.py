"""Validators with synthetic valid values (computed here). Usage: python tests/test_validators.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend.validators import *

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

def person_id(base9):
    r = sum(int(base9[i]) * (10 - i) for i in range(9)) % 11
    return base9 + str(r if r < 2 else 11 - r)

def legal_id(base10):
    dd = int(base10[9]) + 2
    r = sum((int(base10[i]) + dd) * w for i, w in enumerate([29, 27, 23, 19, 17, 29, 27, 23, 19, 17])) % 11
    return base10 + str(0 if r == 10 else r)

def make_iban(bank, acct19):
    num = int("".join(str(int(c, 36)) for c in bank + acct19 + "IR00"))
    return "IR" + f"{98 - num % 97:02d}" + bank + acct19

p = person_id("123456789"); l = legal_id("1010175238"); ib = make_iban("019", "0000000000000123456")
check("person national id ok", national_id(p)["ok"] and national_id(p)["kind"] == "person", p)
check("person id wrong digit rejected", not national_id(p[:-1] + str((int(p[-1]) + 1) % 10))["ok"])
check("person id all same digits rejected", not national_id("1111111111")["ok"])
check("legal id ok + kind", national_id(l)["ok"] and national_id(l)["kind"] == "legal", l)
check("legal id wrong digit rejected", not national_id(l[:-1] + str((int(l[-1]) + 1) % 10))["ok"])
check("wrong length rejected with a clear message", "۱۰" in national_id("12345")["errors"][0])
check("Persian digits accepted", national_id("".join("۰۱۲۳۴۵۶۷۸۹"[int(c)] for c in p))["ok"])
check("IBAN ok and bank detected", iban(ib)["ok"] and iban(ib)["bank"] == "بانک صادرات ایران", iban(ib))
check("IBAN with spaces/lowercase", iban(" ".join(ib.lower()[i:i + 4] for i in range(0, 26, 4)))["ok"])
check("IBAN checksum error caught", not iban(ib[:-1] + str((int(ib[-1]) + 1) % 10))["ok"])
check("IBAN with IR glued at the end is repaired", iban(ib[2:] + "IR")["ok"] and iban(ib[2:] + "IR")["warnings"])
check("IBAN without IR prefix is repaired", iban(ib[2:])["ok"])
check("unknown bank code is reported, not guessed", iban(make_iban("999", "0000000000000123456"))["bank"] is None and iban(make_iban("999", "0000000000000123456"))["warnings"])
check("IBAN wrong length", not iban("IR12345")["ok"])
for v in ("09123456789", "۰۹۱۲۳۴۵۶۷۸۹", "+98 912 345 6789", "9123456789", "00989123456789"):
    check(f"mobile {v}", mobile(v)["normalized"] == "09123456789")
check("mobile wrong length", not mobile("0912345678")["ok"])
check("landline normalised with area code", landline("02112345678")["normalized"] == "021-12345678" and landline("(021) 1234 5678")["area_code"] == "021")
check("landline without area code rejected", not landline("12345678")["ok"])
check("phone() picks mobile or landline", phone("09123456789")["kind"] == "mobile" and phone("02112345678")["kind"] == "landline")
check("postal code", postal_code("1675619466")["ok"] and not postal_code("12345")["ok"])
check("economic code warns on odd length only", economic_code("411111111111")["warnings"] == [] and economic_code("123")["warnings"])
check("card number Luhn", card_number("4111111111111111")["ok"] and not card_number("4111111111111112")["ok"])
check("text normalisation: ي/ك, spaces", normalize_text("علي   كتاب") == "علی کتاب")
check("fold ignores spaces, half-space and letter variants", fold("آهن‌سازان نمونه") == fold("آهن سازان  نمونه") and fold("علي") == fold("علی"))
print("ALL OK")
