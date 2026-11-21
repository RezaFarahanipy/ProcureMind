// End-to-end UI test with jsdom (no browser needed).  Setup:  npm install jsdom
// Backend must run with fake llama servers on 18080/18081 and PYTHONPATH=tests/fakes (see run notes in docs).
// Usage: node tests/ui_test.js http://127.0.0.1:8000 /path/to/text.pdf /path/to/image.png tests/fixtures/proforma_layout.txt
const { JSDOM } = require("jsdom");
const fs = require("fs");
const base = process.argv[2], pdfPath = process.argv[3], pngPath = process.argv[4], synPath = process.argv[5];
const sleep = ms => new Promise(r => setTimeout(r, ms));
let failed = 0;
const check = (name, ok, extra = "") => { console.log((ok ? "PASS " : "FAIL ") + name, extra); if (!ok) failed++; };
async function until(fn, ms = 15000) { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (fn()) return true; } catch (e) {} await sleep(100); } return false; }

(async () => {
  const errors = [];
  const dom = await JSDOM.fromURL(base + "/", {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
    beforeParse(w) {
      w.TextDecoder = TextDecoder;
      w.addEventListener("error", e => errors.push(e.message));
      w.fetch = async (url, opts = {}) => {
        let body = opts.body;
        if (body && body.constructor.name === "FormData") {
          const fd = new FormData();
          for (const [k, v] of body.entries()) {
            if (typeof v === "string") fd.append(k, v);
            else { const buf = await new Promise(res => { const fr = new w.FileReader(); fr.onload = () => res(Buffer.from(fr.result)); fr.readAsArrayBuffer(v); }); fd.append(k, new Blob([buf]), v.name); }
          }
          body = fd;
        }
        return fetch(new URL(url, base), { ...opts, body, signal: undefined });
      };
    },
  });
  const w = dom.window, d = w.document, $ = id => d.getElementById(id);
  await until(() => $("chatModel") && $("chatModel").options.length > 0);
  check("page loads without script errors", errors.length === 0, errors.join("|"));
  check("empty-state shown", !!d.querySelector(".empty"));
  check("chat model list filled", $("chatModel").options.length > 0, [...$("chatModel").options].map(o => o.value).join(","));
  check("OCR model list + mmproj filled", $("ocrModel").options.length > 0 && $("ocrMmproj").options.length > 0);

  // 1) plain chat
  $("input").value = "سلام"; $("send").click();
  check("plain chat gets an answer", await until(() => [...d.querySelectorAll(".msg.assistant")].some(m => m.textContent.includes("پاسخ آزمایشی"))));
  await until(() => !$("send").disabled);

  // 2) text-layer PDF + message -> card -> auto analysis
  const pdf = new w.File([fs.readFileSync(pdfPath)], "invoice.pdf", { type: "application/pdf" });
  await w.attach(pdf);
  check("PDF chip shown with page info", $("chips").textContent.includes("invoice.pdf") && $("chips").textContent.includes("لایه متنی: دارد"), $("chips").textContent);
  check("method stays on text layer", $("method").value === "text");
  check("auto-analyze defaults on for text layer", $("autoAnalyze").checked);
  $("input").value = "این را خلاصه کن"; $("send").click();
  check("card created with extracted text", await until(() => { const c = d.querySelector(".card .ctext"); return c && c.value.includes("real text layer"); }));
  check("assistant answered automatically", await until(() => d.querySelectorAll(".msg.assistant").length >= 2 && !$("send").disabled));
  check("attachment cleared after send", $("chips").children.length === 0);

  // 3) image -> manual method (no text layer) -> paste text -> send to model
  const png = new w.File([fs.readFileSync(pngPath)], "scan.png", { type: "image/png" });
  await w.attach(png);
  check("image switches method to manual", $("method").value === "manual");
  check("auto-analyze off for manual", !$("autoAnalyze").checked);
  const before = d.querySelectorAll(".msg.assistant").length;
  $("input").value = ""; $("send").click();
  const cards = () => d.querySelectorAll(".card");
  check("manual card appears, empty and waiting", await until(() => cards().length === 2) && cards()[1].querySelector(".ctext").value === "");
  const c2 = cards()[1];
  c2.querySelector(".ctext").value = "فروشنده: نمونه  ۱۲٬۳۴۵";
  c2.querySelector(".norm").click();
  check("normalize button works", c2.querySelector(".ctext").value.includes("12,345"), c2.querySelector(".ctext").value);
  c2.querySelector(".analyze").click();
  check("manual text analyzed by model", await until(() => d.querySelectorAll(".msg.assistant").length > before));
  await until(() => !$("send").disabled);

  // 4) Dots OCR on an image (mock OCR server streams text); review before sending
  $("method").value = "dots"; $("method").onchange();
  await w.attach(png);
  check("method kept as dots for image", $("method").value === "dots");
  check("auto-analyze off for dots", !$("autoAnalyze").checked);
  $("send").click();
  check("dots card gets streamed text", await until(() => { const cs = cards(); return cs.length === 3 && cs[2].querySelector(".ctext").value.length > 0; }));
  await until(() => cards()[2].querySelector(".cmeta").textContent.includes("بررسی"));
  check("waits for user review (no auto send)", cards()[2].querySelector(".cmeta").textContent.includes("بررسی"));

  // 5) PaddleOCR on an image (fake paddleocr package)
  $("method").value = "paddle"; $("method").onchange();
  await w.attach(png); $("send").click();
  check("paddle card has recognized lines", await until(() => { const cs = cards(); return cs.length === 4 && cs[3].querySelector(".ctext").value.includes("خط اول"); }), cards()[3] && cards()[3].querySelector(".ctext").value);

  // 6) hybrid pre-invoice: table read by code, header by the model
  $("method").value = "manual"; $("method").onchange();
  await w.attach(png); $("send").click();
  await until(() => cards().length === 5);
  const c5 = cards()[4];
  check("hybrid is the default task when there is no message", c5.querySelector(".task").value === "hybrid");
  c5.querySelector(".ctext").value = fs.readFileSync(synPath, "utf8");
  c5.querySelector(".analyze").click();
  const asst = () => [...d.querySelectorAll(".msg.assistant")].map(m => m.textContent);
  check("table message (read by code) appears", await until(() => asst().some(t => t.includes("خوانده‌شده با کد") && t.includes('"qty": 5'))));
  check("final result: header from model + totals from code", await until(() => asst().some(t => t.includes("نتیجه نهایی") && t.includes("شرکت نمونه") && t.includes('"grand_total": 22000'))));
  check("arithmetic check passes on the merged result", asst().some(t => t.includes("✓ بررسی خودکار")));
  await until(() => !$("send").disabled);

  // 7) new conversation
  $("clear").click();
  check("new conversation resets the log", !!d.querySelector(".empty") && cards().length === 0);
  console.log(failed ? `\n${failed} FAILED` : "\nALL OK");
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error("CRASH", e); process.exit(2); });
