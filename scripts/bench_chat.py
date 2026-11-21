"""Benchmark chat models on ONE document, unattended.

For every chat model found in models\\ (or those matching --models) it: loads the model through the running backend,
reads the PDF text layer once, sends the same pre-invoice prompt the UI uses, and reports load time, time to first token,
tokens/s, total time, JSON validity, the arithmetic check and (optionally) accuracy against a golden JSON.

Modes:  hybrid (default) = the real app path: the item table is read by code, the model only reads the header text.
        full = the model reads everything and writes the whole JSON (slow; shows how much the hybrid path saves).
Input:  --pdf (digital PDF with a text layer) or --text-file (plain text, e.g. text pasted from Google Lens).

Usage (backend must be running, e.g. scripts\\start_app.bat; other model servers closed):
  python scripts\\bench_chat.py --pdf C:\\path\\invoice.pdf --golden tests\\golden\\private_invoice.json
  python scripts\\bench_chat.py --pdf invoice.pdf --models gemma,qwen --mode full --max-tokens 2048
Results are printed and saved to logs\\bench_<time>.md / .json
"""
import argparse, json, pathlib, re, sys, time
import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent


def ui_strings():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    pf = re.search(r'proforma:\s*"((?:[^"\\]|\\.)*)"', html)
    sy = re.search(r'SYSTEM = \{role: "system", content: "((?:[^"\\]|\\.)*)"\}', html)
    if not pf or not sy:
        sys.exit("Could not read the prompts from frontend/index.html")
    hp = re.search(r'const HEADER_PROMPT = "((?:[^"\\]|\\.)*)";', html)
    if not hp:
        sys.exit("Could not read HEADER_PROMPT from frontend/index.html")
    return json.loads('"' + pf.group(1) + '"'), json.loads('"' + sy.group(1) + '"'), json.loads('"' + hp.group(1) + '"')


def num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str) and re.fullmatch(r"[\d.,]+", v.strip()):
        try:
            return float(v.replace(",", ""))
        except ValueError:
            return None
    return None


def extract_json(text):
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None, "no complete JSON (truncated or missing)"
    try:
        return json.loads(text[a:b + 1]), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def arithmetic(j):
    """Same checks as the UI's checkInvoice. Returns (problems, checks_done)."""
    bad, done = [], 0
    items = j.get("items") if isinstance(j.get("items"), list) else []
    total_sum, sum_ok = 0.0, bool(items)
    for i, it in enumerate(items):
        q, p, t = num(it.get("qty")), num(it.get("unit_price")), num(it.get("total"))
        if t is None:
            sum_ok = False
        else:
            total_sum += t
        if None not in (q, p, t):
            done += 1
            if abs(q * p - t) > max(1, t * 1e-6):
                bad.append(f"row {it.get('row', i + 1)}: qty*price={q * p:,.0f} != total {t:,.0f}")
    before, tax, grand = num(j.get("total_before_tax")), num(j.get("tax")), num(j.get("grand_total"))
    if sum_ok and before is not None:
        done += 1
        if abs(total_sum - before) > 1:
            bad.append(f"sum of rows {total_sum:,.0f} != total_before_tax {before:,.0f}")
    if None not in (before, tax, grand):
        done += 1
        if abs(before + tax - grand) > 1:
            bad.append(f"before_tax+tax {before + tax:,.0f} != grand_total {grand:,.0f}")
    return bad, done


def norm(s):
    s = str(s)
    return re.sub(r"\s+", " ", s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("ي", "ی").replace("ك", "ک")).strip()


def golden_score(j, g):
    """Fraction of golden facts the model got right (header facts + per-row qty/unit/price/total + totals)."""
    pts = hit = 0
    def check(ok):
        nonlocal pts, hit
        pts += 1
        hit += bool(ok)
    if "buyer_contains" in g:
        check(norm(g["buyer_contains"]) in norm(json.dumps(j.get("buyer", ""), ensure_ascii=False)))
    if "seller_contains" in g:
        check(norm(g["seller_contains"]) in norm(j.get("seller", "")) if not isinstance(j.get("seller"), dict) else norm(g["seller_contains"]) in norm(json.dumps(j["seller"], ensure_ascii=False)))
    for k in ("number", "date"):
        if k in g:
            check(norm(j.get(k, "")) == norm(g[k]))
    if "currency_contains" in g:
        check(norm(g["currency_contains"]) in norm(j.get("currency", "")))
    items = j.get("items") if isinstance(j.get("items"), list) else []
    for i, gi in enumerate(g.get("items", [])):
        mi = items[i] if i < len(items) and isinstance(items[i], dict) else {}
        for k in ("qty", "unit_price", "total"):
            if k in gi:
                check(num(mi.get(k)) == float(gi[k]))
        if "unit_contains" in gi:
            check(norm(gi["unit_contains"]) in norm(mi.get("unit", "")))
    for k in ("total_before_tax", "tax", "grand_total"):
        if k in g:
            check(num(j.get(k)) == float(g[k]))
    return hit, pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--pdf", help="a PDF with a text layer (pre-invoice)")
    ap.add_argument("--text-file", help="plain text of the document instead of a PDF (e.g. pasted from Google Lens)")
    ap.add_argument("--mode", choices=["hybrid", "full"], default="hybrid")
    ap.add_argument("--pages", default="1")
    ap.add_argument("--golden", help="JSON with the correct values (see tests/golden/example_proforma.json)")
    ap.add_argument("--models", default="", help="comma-separated substrings to select models (default: all chat models)")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--max-tokens", type=int, default=0, help="default: 400 for hybrid, 2048 for full")
    ap.add_argument("--load-timeout", type=int, default=900)
    a = ap.parse_args()

    if not a.pdf and not a.text_file:
        sys.exit("Give --pdf or --text-file")
    prompt, system, header_prompt = ui_strings()
    golden = json.loads(pathlib.Path(a.golden).read_text(encoding="utf-8")) if a.golden else None
    c = httpx.Client(base_url=a.base, timeout=None)

    # 1) read the document text once
    if a.text_file:
        doc_text, label = pathlib.Path(a.text_file).read_text(encoding="utf-8"), pathlib.Path(a.text_file).name
    else:
        pdf = pathlib.Path(a.pdf)
        label, pages = pdf.name, []
        with c.stream("POST", "/api/ocr", files={"file": (pdf.name, pdf.read_bytes())},
                      data={"engine": "text", "mode": "auto", "pages": a.pages, "text_style": "layout"}) as r:
            for line in r.iter_lines():
                if line.strip():
                    ev = json.loads(line)
                    if ev["type"] == "page" and ev.get("text"):
                        pages.append(ev["text"])
                    elif ev["type"] == "error":
                        sys.exit("Text extraction failed: " + ev["message"])
        if not pages:
            sys.exit("The PDF has no text layer; this benchmark needs a digital PDF (or use --text-file).")
        doc_text = "\n\n".join(pages)
    print(f"Document: {label}, {len(doc_text)} characters")
    table_note = ""
    if a.mode == "hybrid":
        parsed = c.post("/api/invoice/parse", json={"text": doc_text}).json()
        if not parsed["items"]:
            sys.exit("The code parser found no item table in this document; try --mode full.")
        table_note = f"table read by code: {len(parsed['items'])} items, problems: {parsed['problems'] or 'none'}"
        print(table_note)
        full_prompt = header_prompt + "\n\n---\n" + (parsed.get("header_for_model") or parsed["header_text"])
        max_tokens = a.max_tokens or 400
        if golden:
            golden = {k: v for k, v in golden.items() if k in ("seller_contains", "buyer_contains", "number", "date", "currency_contains")}
    else:
        full_prompt = prompt + "\n\n---\n" + doc_text
        max_tokens = a.max_tokens or 2048

    models = c.get("/api/models").json()["chat"]
    want = [w.strip().lower() for w in a.models.split(",") if w.strip()]
    if want:
        models = [m for m in models if any(w in m["file"].lower() for w in want)]
    if not models:
        sys.exit("No chat models found in models\\ (or none match --models).")
    print(f"Models to test ({len(models)}): " + ", ".join(m["file"] for m in models) + "\n")

    results = []
    for m in models:
        name = m["file"]
        row = {"model": name, "size_gb": m["size_gb"]}
        print(f"=== {name} ({m['size_gb']} GB)")
        r = c.post("/api/models/load", json={"role": "chat", "model": name, "ctx": a.ctx, "unload_other": True})
        if r.status_code != 200:
            row["error"] = f"load refused: {r.text[:150]}"
            print("   ", row["error"]); results.append(row); continue
        t0, state = time.time(), {}
        while time.time() - t0 < a.load_timeout:
            state = c.get("/api/models").json()["servers"]["chat"]
            if state["state"] in ("ready", "failed"):
                break
            time.sleep(2)
        if state.get("state") != "ready":
            row["error"] = f"load {state.get('state', 'timeout')}: " + (state.get("log_tail", "")[-200:].replace("\n", " "))
            print("   ", row["error"]); results.append(row); continue
        row["load_s"] = state.get("load_s")
        text, stats, err = "", None, None
        with c.stream("POST", "/api/chat", json={"messages": [{"role": "system", "content": system}, {"role": "user", "content": full_prompt}],
                                                  "max_tokens": max_tokens, "temperature": 0.2}) as resp:
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                ev = json.loads(line[5:])
                if ev["type"] == "delta":
                    text += ev["text"]
                elif ev["type"] == "error":
                    err = ev["message"]
                elif ev["type"] == "done":
                    stats = ev["stats"]
        if err:
            row["error"] = err[:200]
        if stats:
            row.update(total_s=stats["total_s"], first_token_s=stats["first_token_s"], tokens_per_s=stats["tokens_per_s"], ram_gb=stats["resources"]["ram_used_gb"])
        j, jerr = extract_json(text)
        row["json_ok"] = j is not None
        if jerr:
            row["note"] = jerr
        if a.mode == "hybrid":  # same validation the app applies to the model's {seller, buyer}
            chk = c.post("/api/invoice/header-check", json={"header_text": parsed["header_text"], "full_text": doc_text, "model": j or {}}).json()
            if chk["warnings"]:
                row["note"] = (row.get("note", "") + f" {len(chk['warnings'])} warning(s) after validation").strip()
            if golden:
                h, p = golden_score(chk["header"], golden)
                row["golden"] = f"{h}/{p}"
        elif j is not None:
            bad, done = arithmetic(j)
            row["arith_checks"], row["arith_problems"] = done, bad
            if golden:
                h, p = golden_score(j, golden)
                row["golden"] = f"{h}/{p}"
        row["output"] = text
        print(f"    total {row.get('total_s')} s, first token {row.get('first_token_s')} s, {row.get('tokens_per_s')} tok/s, json_ok={row['json_ok']}, golden={row.get('golden')}, arith problems={len(row.get('arith_problems', []))}")
        results.append(row)
    c.post("/api/models/unload", json={"role": "chat"})

    # report
    lines = ["| model | GB | load s | first token s | tok/s | total s | JSON | arithmetic | golden | note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        prob = r.get("arith_problems")
        arith = ("by code" if a.mode == "hybrid" else "-") if prob is None else ("OK" if not prob and r.get("arith_checks") else ("no checks" if not prob else f"{len(prob)} problem(s)"))
        lines.append(f"| {r['model']} | {r.get('size_gb')} | {r.get('load_s', '')} | {r.get('first_token_s', '')} | {r.get('tokens_per_s', '')} | {r.get('total_s', '')} | {'yes' if r.get('json_ok') else 'NO'} | {arith} | {r.get('golden', '-')} | {r.get('error') or r.get('note') or ''} |")
    report = "\n".join(lines)
    print("\n" + report)
    out = ROOT / "logs"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out / f"bench_{stamp}.md").write_text(f"# Chat model benchmark {stamp}\n\nDocument: {label}, mode {a.mode}, ctx {a.ctx}\n{table_note}\n\n{report}\n", encoding="utf-8")
    (out / f"bench_{stamp}.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSaved: logs/bench_{stamp}.md and .json (full model outputs are in the .json)")


if __name__ == "__main__":
    main()
