"""Deterministic pre-invoice table parser (no LLM).

Works on the text produced by layout_text(): rows are lines, table cells are separated by " | ".
Instead of trusting column positions it uses ARITHMETIC: in every item row it looks for numbers where
quantity x unit price = line total, then reads discount / tax / grand total after the line total and
verifies them too. Anything that does not add up is reported, never guessed.
"""
import re

_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬٫", "01234567890123456789,.")
_NUM = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
_NUM_UNIT = re.compile(r"^(\d[\d,]*(?:\.\d+)?)\s+([^\d|\s][^\d|]*)$")
_UNIT_ONLY = re.compile(r"^[^\d|\s][^\d|]*$")
_ANY_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _to_num(s: str):
    v = float(s.replace(",", ""))
    return int(v) if v.is_integer() else v


def _close(a, b, tol: float = 1.0) -> bool:
    return abs(a - b) <= tol  # rounding to whole currency units


def _parse_row(cells: list[str]):
    """Return (item, None) or (None, reason)."""
    row_no = int(cells[0])
    rest = cells[1:]
    code = None
    if rest and _NUM.match(rest[0]) and len(rest) > 1 and not _NUM.match(rest[1]) and not _NUM_UNIT.match(rest[1]):
        code, rest = rest[0], rest[1:]  # code in its own cell
    if not rest:
        return None, "empty row"
    name, rest = rest[0], rest[1:]
    m = re.match(r"^(\d{2,})\s+(\S.*)$", name)
    if m and code is None:
        code, name = m.group(1), m.group(2)
    vals = []
    for c in rest:
        if _NUM.match(c):
            vals.append({"v": _to_num(c), "unit": None})
            continue
        mu = _NUM_UNIT.match(c)
        if mu:
            vals.append({"v": _to_num(mu.group(1)), "unit": mu.group(2).strip()})
        elif _UNIT_ONLY.match(c) and vals and vals[-1]["unit"] is None:
            vals[-1]["unit"] = c
    n = len(vals)
    found = None
    for i in range(n):
        q = vals[i]["v"]
        if q <= 0:
            continue
        for j in range(n):
            p = vals[j]["v"]
            if j == i or p <= 0:
                continue
            k = max(i, j) + 1  # the line total must sit right next to the price/quantity cell; a skipped number means a misread row
            if k < n and _close(q * p, vals[k]["v"], 0.51):  # decimal quantities round to the nearest unit
                found = (i, j, k)
                break
        if found:
            break
    if not found:
        return None, "no numbers satisfy quantity x price = total"
    i, j, k = found
    item = {"row": row_no, "code": code, "name": name.strip(), "qty": vals[i]["v"], "unit": vals[i]["unit"],
            "unit_price": vals[j]["v"], "total": vals[k]["v"]}
    subs = [vals[x] for x in range(k) if x not in (i, j)]
    if subs:
        item["sub_qty"], item["sub_unit"] = subs[0]["v"], subs[0]["unit"]
    r = vals[k + 1:]
    t = item["total"]
    if len(r) >= 4 and _close(r[1]["v"], t - r[0]["v"]) and _close(r[3]["v"], r[1]["v"] + r[2]["v"]):
        item.update(discount=r[0]["v"], total_after_discount=r[1]["v"], tax=r[2]["v"], grand_total=r[3]["v"])
    elif len(r) >= 2 and _close(r[1]["v"], t + r[0]["v"]):
        item.update(tax=r[0]["v"], grand_total=r[1]["v"])
    return item, None


def parse_proforma(text: str) -> dict:
    text = text.translate(_DIG)
    lines = [ln.strip() for ln in text.split("\n")]
    items, unparsed, problems = [], [], []
    first = last = None
    for idx, line in enumerate(lines):
        cells = [c.strip() for c in line.split(" | ")]
        if len(cells) < 6 or not re.fullmatch(r"\d{1,3}", cells[0]):
            continue
        item, why = _parse_row(cells)
        if first is None:
            first = idx
        last = idx
        if item:
            items.append(item)
        else:
            unparsed.append({"line": line, "reason": why})
            problems.append(f"سطر «{cells[0]}» خوانده نشد: {why}")
    rows = [it["row"] for it in items]
    if rows and rows != list(range(rows[0], rows[0] + len(rows))):
        problems.append("شماره ردیف‌ها پشت‌سرهم نیستند؛ احتمالاً ردیفی جا افتاده است")

    # header text = everything before the table header (minus broken header fragments)
    head_idx = next((i for i, ln in enumerate(lines) if "ردیف" in ln and ("شرح" in ln or "کالا" in ln)), first)
    header = lines[:head_idx] if head_idx is not None else []
    while header and (":" not in header[-1] and len(header[-1]) < 30):
        header.pop()

    totals = {"total_before_tax": None, "tax": None, "grand_total": None, "confirmed": {}}
    if items:
        tail_nums = set()
        for ln in lines[(last or 0) + 1:(last or 0) + 13]:
            if "خریدار محترم" in ln or "بانک" in ln:
                break
            tail_nums |= {_to_num(x) for x in _ANY_NUM.findall(ln)}
        def total_of(key):
            vals = [it.get(key) for it in items]
            return sum(vals) if vals and all(v is not None for v in vals) else None
        before = total_of("total_after_discount")
        if before is None:
            before = total_of("total")
        for name, val in (("total_before_tax", before), ("tax", total_of("tax")), ("grand_total", total_of("grand_total"))):
            totals[name] = val
            totals["confirmed"][name] = (val in tail_nums) if val is not None else None
            if val is not None and not totals["confirmed"][name]:
                problems.append(f"جمع محاسبه‌شده‌ی {name} ({val:,}) در متن سند پیدا نشد")
    return {"items": items, "totals": totals, "header_text": "\n".join(header), "unparsed": unparsed, "problems": problems}


# ---------------------------------------------------------------- header (seller / buyer / number / date / currency)
_DATE = re.compile(r"(?<!\d)(1[34]\d{2}/\d{1,2}/\d{1,2})(?!\d)")
_NUM_LABELS = [re.compile(r"(?:سریال|شماره\s*پیش\s*فاکتور|شماره)\s*:?\s*(\d{1,15})(?!\d)"),
               re.compile(r"(?<!\d)(\d{1,15})\s*:\s*(?:سریال|شماره)")]


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_DIG)).strip()


def code_header(header_text: str, full_text: str) -> dict:
    """Number, date, currency and buyer read by regex (exact; never hallucinated)."""
    ht, ft = header_text.translate(_DIG), full_text.translate(_DIG)
    out = {"number": None, "date": None, "currency": None, "buyer": None}
    m = _DATE.search(ht)
    out["date"] = m.group(1) if m else None
    for rx in _NUM_LABELS:
        m = rx.search(ht)
        if m:
            out["number"] = m.group(1)
            break
    out["currency"] = "ریال" if "ریال" in ft else ("تومان" if "تومان" in ft else None)
    m = re.search(r"خریدار[^\n]*?نام\s*:\s*([^\n|]+)", ht)
    if m:
        out["buyer"] = m.group(1).strip()
    return out


def merge_header(model: dict, header_text: str, full_text: str) -> dict:
    """Combine the model's {seller, buyer} with the regex fields and verify every claim against the document text.
    Anything the model wrote that is not in the document (or in the wrong place) is dropped and reported."""
    model = model if isinstance(model, dict) else {}
    code = code_header(header_text, full_text)
    lines = header_text.translate(_DIG).split("\n")
    marker = next((i for i, ln in enumerate(lines) if ln.strip().startswith("خریدار")), None)
    whole = _flat(header_text)
    before = _flat("\n".join(lines[:marker])) if marker is not None else whole

    def found(value, text) -> bool:
        words = _flat(str(value)).split()
        return bool(words) and all(w in text for w in words)

    warnings, out = [], {"seller": None, "buyer": None}
    s = model.get("seller")
    if isinstance(s, str) and s.strip():
        if found(s, before):
            out["seller"] = s.strip()
        else:
            warnings.append(f"فروشنده‌ی پیشنهادی مدل («{s.strip()}») در بخش بالای «خریدار» سند پیدا نشد؛ آن را دستی وارد کنید")
    else:
        warnings.append("فروشنده خوانده نشد؛ آن را دستی وارد کنید")
    b = model.get("buyer")
    if code["buyer"]:
        out["buyer"] = code["buyer"]
    elif isinstance(b, str) and found(b, whole):
        out["buyer"] = b.strip()
    else:
        warnings.append("خریدار خوانده نشد؛ آن را دستی وارد کنید")
    if out["seller"] and out["buyer"] and _flat(out["seller"]) == _flat(out["buyer"]):
        warnings.append("فروشنده و خریدار یکی شدند؛ فروشنده را بررسی کنید")
        out["seller"] = None
    for k in ("number", "date", "currency"):
        out[k] = code[k]
        if code[k] is None:
            warnings.append(f"{k} در سند پیدا نشد")
    return {"header": out, "warnings": warnings}
