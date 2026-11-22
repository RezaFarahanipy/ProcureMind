"""Document-type rules. Usage: python tests/test_classifier.py   (optional: PDF=path to also classify a real document)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend.doc_classifier import classify

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

fx = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "proforma_layout.txt"), encoding="utf-8").read()
r = classify(fx)
check("pre-invoice detected (and not as a plain invoice)", r["type"] == "proforma" and r["confidence"] >= 0.6, r)
check("presentation-form Persian is understood", classify("ﭘﯿﺶ ﻓﺎﮐﺘﻮﺭ ﻓﺮﻭﺵ ﮐﺎﻻ\nﻓﺮﻭﺷﻨﺪﻩ")["type"] == "proforma")
check("purchase request", classify("فرم درخواست خرید\nدرخواست‌کننده: واحد فنی\nشماره: 12")["type"] == "purchase_request")
check("inquiry", classify("نامه استعلام بها\nاز شرکت محترم ...")["type"] == "inquiry")
check("payment receipt", classify("فیش واریز بانکی\nشماره پیگیری: 123456")["type"] == "payment_receipt")
check("plain invoice", classify("فاکتور فروش\nشماره اقتصادی: 411\nصورتحساب")["type"] == "invoice")
check("waybill", classify("بارنامه\nراننده: ...")["type"] == "waybill")
check("unclear text -> other", classify("سلام\nاین یک متن معمولی است")["type"] == "other")
check("footer mention of 'فاکتور' does not flip the type", classify("پیش فاکتور\n" + "x\n" * 30 + "لطفا فاکتور را نگه دارید")["type"] == "proforma")
if os.environ.get("PDF"):
    import fitz
    from backend.main import layout_text
    rr = classify(layout_text(fitz.open(os.environ["PDF"])[0]))
    check("REAL document", rr["type"] == "proforma", rr)
print("ALL OK")
