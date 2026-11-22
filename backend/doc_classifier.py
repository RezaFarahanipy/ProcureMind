"""Rule-based document-type detection (instant, no model). Used to decide what to do with an attached file.

Later this can be backed by a small decision/classification model for the unclear cases; the rules stay as the fast path.
"""
import re
import unicodedata

LABELS = {
    "proforma": "پیش‌فاکتور",
    "invoice": "فاکتور / صورتحساب",
    "purchase_request": "درخواست خرید",
    "inquiry": "استعلام",
    "payment_receipt": "رسید یا فیش پرداخت / چک",
    "warehouse_receipt": "رسید انبار",
    "order": "سفارش خرید / قرارداد",
    "waybill": "بارنامه",
    "other": "نامشخص",
}

# (regex, weight). Persian text is normalised first (ZWNJ -> space, Arabic letters -> Persian, presentation forms -> standard).
RULES = {
    "proforma": [(r"پیش\s*فاکتور", 4), (r"proforma", 4)],
    "invoice": [(r"(?<!پیش )فاکتور\s*فروش", 3), (r"صورت\s*حساب", 3), (r"شماره\s*اقتصادی", 1), (r"(?<!پیش )فاکتور", 1)],
    "purchase_request": [(r"درخواست\s*(?:خرید|کالا)", 4), (r"درخواست\s*کننده", 1)],
    "inquiry": [(r"استعلام\s*(?:بها)?", 4)],
    "payment_receipt": [(r"فیش\s*(?:واریز|بانکی)", 4), (r"رسید\s*پرداخت", 4), (r"شماره\s*پیگیری", 1), (r"حواله\s*بانکی", 3), (r"صیاد", 2), (r"سر\s*رسید", 1)],
    "warehouse_receipt": [(r"رسید\s*انبار", 4), (r"حواله\s*انبار", 3)],
    "order": [(r"سفارش\s*خرید", 4), (r"قرارداد", 2)],
    "waybill": [(r"بارنامه", 4)],
}


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[ \t]+", " ", t)


def classify(text: str) -> dict:
    """Return {type, label, confidence, scores, evidence}. Keywords in the first lines (the title area) count double."""
    t = normalize(text)
    lines = [ln for ln in t.split("\n") if ln.strip()]
    head = "\n".join(lines[:10])
    scores, evidence = {k: 0.0 for k in RULES}, {k: [] for k in RULES}
    for kind, rules in RULES.items():
        for rx, w in rules:
            for m in re.finditer(rx, t, re.I):
                scores[kind] += w * 0.25 if m.start() > len(t) * 0.6 else w * 0.5  # mentions near the end (footer boilerplate) matter less
                evidence[kind].append(m.group(0))
            for m in re.finditer(rx, head, re.I):
                scores[kind] += w  # title area
                evidence[kind].append(m.group(0) + " (عنوان)")
    # an invoice that is really a pro-forma: "پیش فاکتور فروش ..." must not count as a plain invoice
    if scores["proforma"] >= 4:
        scores["invoice"] = max(0.0, scores["invoice"] - scores["proforma"] * 0.5)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (top, s1), (_, s2) = ranked[0], ranked[1]
    if s1 < 3:
        return {"type": "other", "label": LABELS["other"], "confidence": 0.0, "scores": scores, "evidence": []}
    conf = round(s1 / (s1 + s2 + 1.0), 2)
    return {"type": top, "label": LABELS[top], "confidence": conf, "scores": {k: round(v, 2) for k, v in scores.items()},
            "evidence": sorted(set(evidence[top]))[:4]}
