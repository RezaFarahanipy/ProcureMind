"""Unit test of backend/invoice_parser.py with a synthetic pre-invoice in the same layout format (fake data).
Usage: python tests/test_invoice_parser.py   (optionally: PDF=path\\to\\real.pdf GOLDEN=path\\to\\private_x.json for a real check)"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend.invoice_parser import parse_proforma

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

TEXT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "proforma_layout.txt"), encoding="utf-8").read()
r = parse_proforma(TEXT)
a, b = r["items"]
check("two items parsed", len(r["items"]) == 2 and not r["unparsed"], r["problems"])
check("main quantity/unit/price/total (not the secondary quantity)", (b["qty"], b["unit"], b["unit_price"], b["total"]) == (5, "کیلوگرم", 2000, 10000), b)
check("secondary quantity kept apart", (b["sub_qty"], b["sub_unit"]) == (2, "شاخه"))
check("code split from name", (a["code"], a["name"]) == ("101", "ورق ابعاد ( نمونه 1/25*2 )") and b["code"] is None, a)
check("discount/tax/grand verified", (a["discount"], a["tax"], a["grand_total"]) == (0, 1000, 11000))
check("totals computed and found in the text", (r["totals"]["total_before_tax"], r["totals"]["tax"], r["totals"]["grand_total"]) == (20000, 2000, 22000) and all(r["totals"]["confirmed"].values()), r["totals"])
check("header text excludes table + fragments", "شرکت نمونه" in r["header_text"] and "ردیف" not in r["header_text"] and not r["header_text"].rstrip().endswith("مبلغ کل پس از"))
check("no problems on a clean invoice", r["problems"] == [])

# a row that does not add up must be reported, never guessed
bad = TEXT.replace("2 | تیرآهن | 5 کیلوگرم | 2 | شاخه | 2,000 | 10,000", "2 | تیرآهن | 5 کیلوگرم | 2 | شاخه | 2,000 | 10,500")
rb = parse_proforma(bad)
check("inconsistent row is reported as unparsed", len(rb["items"]) == 1 and len(rb["unparsed"]) == 1 and any("خوانده نشد" in p for p in rb["problems"]), rb["problems"])
# Persian digits and separators are accepted
fa = TEXT.replace("10,000", "۱۰٬۰۰۰").replace("1,000", "۱٬۰۰۰")
check("Persian digits accepted", len(parse_proforma(fa)["items"]) == 2)
check("no table -> no items", parse_proforma("سلام\nاین متن جدول ندارد")["items"] == [])

pdf, golden = os.environ.get("PDF"), os.environ.get("GOLDEN")
if pdf and golden:
    import fitz
    from backend.main import layout_text
    g = json.load(open(golden, encoding="utf-8"))
    rr = parse_proforma(layout_text(fitz.open(pdf)[0]))
    ok = all(rr["items"][i][k] == g["items"][i][k] for i in range(len(g["items"])) for k in ("qty", "unit_price", "total"))
    check("REAL document matches golden", ok and not rr["problems"], rr["problems"])

# ---- header: the model's {seller, buyer} is verified against the document; number/date/currency/buyer come from regex
from backend.invoice_parser import merge_header
ht = r["header_text"]
ok = merge_header({"seller": "شرکت نمونه", "buyer": "شرکت خریدار"}, ht, TEXT)
check("good model header accepted, rest read by code", ok["header"] == {"seller": "شرکت نمونه", "buyer": "شرکت خریدار", "number": "1001", "date": "1405/01/01", "currency": "ریال"} and ok["warnings"] == [], ok)
bad_seller = merge_header({"seller": "شرکتی که وجود ندارد", "buyer": "شرکت خریدار"}, ht, TEXT)
check("invented seller is rejected with a warning", bad_seller["header"]["seller"] is None and bad_seller["warnings"], bad_seller["warnings"])
swapped = merge_header({"seller": "شرکت خریدار", "buyer": "شرکت خریدار"}, ht, TEXT)
check("seller taken from the buyer section is rejected", swapped["header"]["seller"] is None and swapped["header"]["buyer"] == "شرکت خریدار", swapped)
empty = merge_header({}, ht, TEXT)
check("model failed: number/date/currency/buyer still read by code", empty["header"]["number"] == "1001" and empty["header"]["buyer"] == "شرکت خریدار" and empty["header"]["seller"] is None)
check("non-dict model output tolerated", merge_header(None, ht, TEXT)["header"]["number"] == "1001")
print("ALL OK")
