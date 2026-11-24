"""Calculation answers on a synthetic extracted invoice. Usage: python tests/test_invoice_calc.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend.invoice_calc import answer

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

inv = {"currency": "ریال", "total_before_tax": 20000, "tax": 2000, "grand_total": 22000, "items": [
    {"row": 1, "name": "ورق ابعاد", "qty": 10, "unit": "کیلوگرم", "unit_price": 1000, "total": 10000},
    {"row": 2, "name": "تیرآهن", "qty": 5, "unit": "کیلوگرم", "unit_price": 2000, "total": 10000},
    {"row": 3, "name": "لوله", "qty": 2, "unit": "تن", "unit_price": 500, "total": 1000},
    {"row": 4, "name": "پیچ", "qty": 100, "unit": "عدد", "unit_price": 1, "total": 100}]}
def a(q): r = answer(q, inv); return r and r["answer"]
check("VAT", "2,000" in a("ارزش افزوده چقدر شد؟"), a("ارزش افزوده چقدر شد؟"))
check("before tax is not mistaken for VAT", answer("قبل از مالیات چقدر است؟", inv)["intent"] == "before_tax" and "20,000" in a("جمع قبل از مالیات"))
check("tax rate", "10.0" in a("درصد مالیات چقدره؟"))
check("weight sums kg and converts tons (pieces ignored)", "2,015" in a("جمع وزن آهن آلات چقدر شد؟"), a("جمع وزن آهن آلات چقدر شد؟"))
check("grand total", "22,000" in a("جمع کل چقدر شد؟"))
check("item count", "4" in a("چند قلم کالا داریم؟"))
check("most expensive item", "ورق ابعاد" in a("گران‌ترین قلم کدام است؟") or "تیرآهن" in a("گران‌ترین قلم کدام است؟"))
check("named item details", "تیرآهن" in a("تیرآهن چقدر خریدیم؟") and "2,000" in a("تیرآهن چقدر خریدیم؟"))
check("unknown question is not handled (goes to the model)", answer("سلام، حالت چطور است؟", inv) is None and answer("پیشنهادت برای مذاکره چیست؟", inv) is None)
check("no data -> not handled", answer("ارزش افزوده چقدر شد؟", {}) is None)
print("ALL OK")
