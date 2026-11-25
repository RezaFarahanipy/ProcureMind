"""Standardisation of free text. Usage: python tests/test_lookup.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend.lookup import canonicalize

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

c = lambda lk, v: canonicalize(lk, v)
check("alias طهران -> تهران", c("province", "طهران")["value"] == "تهران")
check("Latin spelling -> تهران", c("province", "Tehran")["value"] == "تهران")
check("canonical value passes through", c("province", "تهران")["status"] == "exact")
check("letter variants + spaces: اذربایجان شرقی", c("province", "اذربایجان  شرقی")["value"] == "آذربایجان شرقی")
check("Arabic yeh/kaf variants", c("province", "كرمان")["value"] == "کرمان" and c("province", "كرمانشاه")["value"] == "کرمانشاه")
check("half-space variants", c("province", "چهارمحال و بختیاری")["value"] == "چهارمحال و بختیاری")
check("typo -> suggestion, never auto-accepted", c("province", "تهرن")["status"] == "suggest" and c("province", "تهرن")["suggestions"][0] == "تهران")
check("unknown value is flagged as new", c("province", "سیاره‌ی مریخ")["status"] == "new")
check("units: کیلو / kg -> کیلوگرم", c("unit", "کیلو")["value"] == "کیلوگرم" and c("unit", "KG")["value"] == "کیلوگرم")
check("extra (database) entries merge over the seeds", canonicalize("unit", "حلقه", {"رول": ["حلقه"]})["value"] == "رول")
check("empty value", c("province", "  ")["status"] == "empty")
print("ALL OK")
