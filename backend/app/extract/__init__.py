"""
Picks how to read the file, in this order:
  1. cache (same file hash read before - keeps demos fast and identical)
  2. LLM, if a key is set and it's switched on in settings
  3. rules parser on the PDF text layer
  4. OCR + rules parser, for scans
If the LLM call fails we fall through to 3/4 instead of failing the run.
"""
import json

from .. import db
from ..normalize import to_num
from . import llm, pdftext, rules

FIELDS = ["vendor_name", "vendor_gstin", "buyer_gstin", "invoice_no", "invoice_date", "po_ref", "taxable_value",
          "cgst", "sgst", "igst", "round_off", "total", "bank_name", "bank_account", "ifsc", "remarks"]
NUMERIC = {"taxable_value", "cgst", "sgst", "igst", "round_off", "total"}


def _clean(raw):
    """Make whatever came back conform to one shape, whichever extractor produced it."""
    f_in = raw.get("fields", {}) or {}
    fields = {}
    for k in FIELDS:
        v = f_in.get(k) or {}
        if not isinstance(v, dict):
            v = {"value": v, "confidence": 0.8, "source": None}
        val = v.get("value")
        if k in NUMERIC:
            val = to_num(val)
        elif isinstance(val, str):
            val = val.strip() or None
        conf = float(v.get("confidence") or 0) if val is not None else 0.0
        fields[k] = {"value": val, "confidence": round(min(conf, 1.0), 2), "source": v.get("source")}
    for k in ("vendor_gstin", "buyer_gstin", "ifsc"):
        if fields[k]["value"]:
            fields[k]["value"] = fields[k]["value"].replace(" ", "").upper()
    lines = []
    for ln in raw.get("lines", []) or []:
        qty, rate, amt = to_num(ln.get("qty")), to_num(ln.get("rate")), to_num(ln.get("amount"))
        if qty is None or rate is None:
            continue
        lines.append({"description": (ln.get("description") or "").strip(), "hsn": ln.get("hsn"),
                      "qty": qty, "unit": ln.get("unit"), "rate": rate,
                      "amount": amt if amt is not None else round(qty * rate, 2),
                      "confidence": round(float(ln.get("confidence") or 0.8), 2), "source": ln.get("source")})
    return {"fields": fields, "lines": lines}


def run(data, name, file_hash, settings):
    """Returns (extraction, method, notes)."""
    notes = []
    cached = db.q1("SELECT * FROM extraction_cache WHERE file_hash=?", (file_hash,))
    if cached:
        return json.loads(cached["data"]), cached["method"] + " (cached)", ["Read from cache: this exact file was extracted before."]

    buyer = db.buyer()
    result, method = None, None

    if settings.get("use_llm") and llm.available():
        try:
            raw, method = llm.extract(data, name)
            result = _clean(raw)
        except Exception as e:  # network, quota, bad JSON - fall back rather than fail
            notes.append(f"LLM extraction failed ({type(e).__name__}); fell back to the rules parser.")
            result = None

    if result is None:
        text = "" if pdftext.is_image(name) else pdftext.text_layer(data)
        if len(text.strip()) >= 50:
            result, method = _clean(rules.parse(text, buyer["gstin"], buyer["name"])), "rules:text-layer"
        elif pdftext.ocr_available():
            text = pdftext.ocr(data, name)
            result, method = _clean(rules.parse(text, buyer["gstin"], buyer["name"], from_ocr=True)), "rules:ocr"
            notes.append("No text layer, so this was read with OCR. OCR confidence is discounted.")
        else:
            result, method = _clean({}), "none"
            notes.append("No text layer and no OCR engine or LLM key available. Nothing could be read.")

    if method and method != "none":
        db.ex("INSERT OR REPLACE INTO extraction_cache VALUES (?,?,?)", (file_hash, method, json.dumps(result)))
    return result, method, notes
