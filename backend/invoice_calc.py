"""Exact answers to common questions about an already-extracted pre-invoice, computed by code (no language model).

The model is bad at arithmetic and aggregation, so questions such as "how much VAT?" or "total weight?" are answered
here from the structured data. Anything not recognised returns None and the chat falls back to the model.
"""
import re

from backend.validators import normalize_text

_KG = ("کیلو", "kg")
_TON = ("تن",)


def _n(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def fmt(v) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.3f}".rstrip("0").rstrip(".")


def _items(inv):
    return [it for it in (inv.get("items") or []) if isinstance(it, dict)]


def _sum(items, key):
    vals = [_n(it.get(key)) for it in items]
    return sum(v for v in vals if v is not None) if vals and all(v is not None for v in vals) else None


def totals(inv: dict) -> dict:
    items = _items(inv)
    before = _n(inv.get("total_before_tax"))
    tax = _n(inv.get("tax"))
    grand = _n(inv.get("grand_total"))
    if before is None:
        before = _sum(items, "total_after_discount") or _sum(items, "total")
    if tax is None:
        tax = _sum(items, "tax")
    if grand is None:
        grand = _sum(items, "grand_total")
    return {"before": before, "tax": tax, "grand": grand, "currency": inv.get("currency") or "ریال"}


def weight(inv: dict):
    """Sum of main quantities whose unit is a weight unit (kg, or tons converted to kg)."""
    kg, used = 0.0, []
    for it in _items(inv):
        u, q = normalize_text(str(it.get("unit") or "")), _n(it.get("qty"))
        if q is None:
            continue
        if any(k in u for k in _KG):
            kg += q
            used.append(it)
        elif any(u == t or u.startswith(t + " ") for t in _TON):
            kg += q * 1000
            used.append(it)
    return kg, used


def answer(question: str, inv: dict):
    """Return {"intent", "answer"} or None when the question is not a known calculation."""
    q = normalize_text(question)
    t, items = totals(inv), _items(inv)
    cur = t["currency"]
    if not items and t["grand"] is None:
        return None
    if re.search(r"قبل از (مالیات|ارزش افزوده)|بدون (مالیات|ارزش افزوده)|جمع خالص", q) and t["before"] is not None:
        return {"intent": "before_tax", "answer": f"جمع قبل از مالیات: {fmt(t['before'])} {cur}"}
    if re.search(r"(درصد|نرخ)\s*(ارزش افزوده|مالیات)", q) and t["tax"] is not None and t["before"]:
        return {"intent": "tax_rate", "answer": f"نرخ مالیات: {t['tax'] / t['before'] * 100:.1f}٪ ({fmt(t['tax'])} روی {fmt(t['before'])} {cur})"}
    if re.search(r"ارزش افزوده|مالیات|عوارض", q) and t["tax"] is not None:
        return {"intent": "tax", "answer": f"ارزش افزوده (مالیات): {fmt(t['tax'])} {cur}"}
    if re.search(r"وزن|تناژ|کیلو|\bتن\b", q):
        kg, used = weight(inv)
        if used:
            names = "، ".join(f"{it.get('name', '?')} ({fmt(_n(it['qty']))} {it.get('unit', '')})" for it in used)
            return {"intent": "weight", "answer": f"جمع وزن: {fmt(kg)} کیلوگرم ({fmt(kg / 1000)} تن)\nاقلام: {names}"}
    if re.search(r"چند (قلم|ردیف|آیتم)|تعداد (اقلام|ردیف)", q):
        return {"intent": "count", "answer": f"تعداد اقلام: {len(items)}"}
    if re.search(r"گران‌?ترین|بیشترین (مبلغ|قیمت)", q) and items:
        top = max((it for it in items if _n(it.get("total")) is not None), key=lambda it: it["total"], default=None)
        if top:
            return {"intent": "max_item", "answer": f"بیشترین مبلغ: {top.get('name')} با {fmt(top['total'])} {cur}"}
    if re.search(r"جمع کل|مبلغ (کل|نهایی)|چقدر (شد|می‌شود)|مبلغ پرداختی|قابل پرداخت", q) and t["grand"] is not None:
        return {"intent": "grand", "answer": f"جمع کل (با مالیات): {fmt(t['grand'])} {cur}"}
    # a named item: show its details
    words = [w for w in re.findall(r"[\w\u0600-\u06FF]{3,}", q) if w not in ("قیمت", "مبلغ", "چقدر", "است", "برای", "کالا")]
    for it in items:
        name = normalize_text(str(it.get("name") or ""))
        if any(w in name for w in words):
            parts = [f"{it.get('name')}: {fmt(_n(it['qty']))} {it.get('unit', '')}" if _n(it.get("qty")) is not None else str(it.get("name"))]
            if _n(it.get("unit_price")) is not None:
                parts.append(f"فی {fmt(it['unit_price'])}")
            if _n(it.get("total")) is not None:
                parts.append(f"مبلغ {fmt(it['total'])} {cur}")
            return {"intent": "item", "answer": " · ".join(parts)}
    return None
