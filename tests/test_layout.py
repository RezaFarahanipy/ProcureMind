"""Unit test for RTL layout-aware PDF text extraction (backend.main.layout_text / normalize_fa).
Needs a TTF with Persian letters to build the sample PDF:  FONT_TTF=path\to\font.ttf python tests/test_layout.py
(The woff2 files in frontend/fonts cannot be embedded by PyMuPDF; point FONT_TTF at the original .ttf.)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import fitz
from backend.main import layout_text, normalize_fa

def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        sys.exit(1)

# 1) presentation forms -> standard letters
check("normalize presentation forms", normalize_fa("ﺗﺎﯾﯿﺪ ﺳﻔﺎﺭﺵ ﭘﯿﺶ ﻓﺎﮐﺘﻮﺭ") == "تایید سفارش پیش فاکتور")
check("normalize arabic kaf/yeh", normalize_fa("كتاب علي") == "کتاب علی")

ttf = os.environ.get("FONT_TTF")
if not ttf or not os.path.isfile(ttf):
    print("SKIP layout test: set FONT_TTF to a TTF that has Persian letters")
    sys.exit(0)

doc = fitz.open(); page = doc.new_page()
page.insert_font(fontname="f1", fontfile=ttf)
import re
def put(x, y, t):
    # Real Persian PDFs place glyphs in VISUAL order (right-to-left on the page), and the extractor restores logical order.
    # insert_text draws left-to-right, so reverse Persian strings to mimic that. Content-stream order here = left to right.
    if re.search(r"[\u0600-\u06FF]", t):
        t = t[::-1]
    page.insert_text((x, y), t, fontname="f1", fontsize=11)
for x, t in ((200, "مبلغ"), (300, "مقدار"), (400, "کالا"), (500, "ردیف")): put(x, 100, t)
for x, t in ((200, "11,363,700"), (300, "693"), (400, "لمبه"), (500, "1")): put(x, 120, t)
put(400, 160, "ایران"); put(470, 160, ":"); put(480, 160, "نام")
out = layout_text(doc[0]).split("\n")
print(out)
check("table header read right-to-left", out[0] == "ردیف | کالا | مقدار | مبلغ", out[0])
check("table row read right-to-left", out[1] == "1 | لمبه | 693 | 11,363,700", out[1])
check("lone colon sticks to its label", out[2] == "نام: | ایران", out[2])
print("ALL OK")
