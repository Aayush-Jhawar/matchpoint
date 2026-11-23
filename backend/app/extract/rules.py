"""
Rule-based extractor. Used when no LLM key is set, or when the LLM call fails.
It works off layout text (pdfplumber for real PDFs, tesseract for scans), so
labels and values keep their column positions. Two ideas carry most of it:
  - header fields: find a label, read the value to its right or right below it
  - line items: a row is any line with three numbers where qty x rate = amount
"""
import re

from ..gstin import GSTIN_RE
from ..normalize import parse_date, to_num

NUM_RE = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{2,3})+(?:\.\d+)?(?![\w])|(?<![\w.,])\d+(?:\.\d+)?(?![\w,])")
DATE_RE = re.compile(r"\b(\d{1,2}[-/.](?:\d{1,2}|[A-Za-z]{3})[-/.]\d{2,4}|[A-Z][a-z]{2} \d{1,2}, \d{4}|\d{4}-\d{2}-\d{2})\b")
PO_RE = re.compile(r"\bPO[-/ ]?\d{4}[-/]\d{3,4}\b", re.I)
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
ACCT_RE = re.compile(r"\b\d{9,18}\b")
INVNO_RE = re.compile(r"\b(?=[A-Z0-9/\-]*\d)[A-Z][A-Z0-9]*(?:[/\-][A-Z0-9]+)+\b|\b[A-Z]{2,}\d{2,}\b", re.I)

LABELS = {
    "invoice_no": [r"invoice\s*(?:no\.?|number|#)", r"bill\s*no\.?", r"inv\.?\s*no\.?", r"tax invoice no"],
    "invoice_date": [r"invoice\s*date", r"bill\s*date", r"\bdated\b", r"\bdate\b"],
    "po_ref": [r"\bpo\s*no\.?", r"your\s*po", r"p\.?o\.?\s*ref", r"buyer'?s\s*order\s*no\.?", r"purchase\s*order",
               r"po\s*number", r"order\s*ref"],
    "total": [r"grand\s*total", r"total\s*due", r"bill\s*amount", r"invoice\s*total", r"amount\s*payable",
              r"net\s*payable"],
    "taxable_value": [r"taxable\s*value", r"total\s*taxable", r"sub\s*-?\s*total"],
    "bank_account": [r"a\s*[/l|i1]\s*c\.?\s*no\.?", r"account\s*(?:no\.?|number)", r"acct\.?\s*no"],
    "bank_name": [r"bank\s*name", r"our\s*bankers", r"^\s*bank\s*:"],
}
TITLE_WORDS = re.compile(r"^(tax invoice|invoice|gst invoice|original for recipient|to,?|bill of supply)$", re.I)


def _segments(line):
    """Split a layout line into column chunks (3+ spaces apart), keeping start positions."""
    return [(m.start(), m.group().strip()) for m in re.finditer(r"\S+(?: {1,2}\S+)*", line)]


def _find_labelled(lines, patterns, value_re, look_below=2):
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for i, line in enumerate(lines):
            m = rx.search(line)
            if not m:
                continue
            # same line, right of the label (skip separators)
            rest = re.sub(r"^[\s:#.\-]+", " ", line[m.end():])
            seg = _segments(rest)
            if seg:
                first = re.sub(r"^[\s:#.\-]+", "", seg[0][1])
                v = value_re.search(first) if value_re else None
                if v:
                    return v.group(0), 0.92, line.strip()
                if value_re is None and first:
                    return first, 0.9, line.strip()
            # below the label, roughly the same column
            col = m.start()
            for j in range(i + 1, min(i + 1 + look_below, len(lines))):
                below = lines[j]
                window = below[max(0, col - 3): col + 40]
                v = value_re.search(window) if value_re else None
                if v:
                    return v.group(0), 0.85, (line.strip() + " / " + below.strip())[:160]
    return None, 0.0, None


def _last_amount_on(lines, patterns, exclude=None):
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for line in lines:
            if rx.search(line) and not (exclude and re.search(exclude, line, re.I)):
                nums = [n for n in NUM_RE.findall(line[rx.search(line).end():])]
                nums = [to_num(n) for n in nums if to_num(n) is not None]
                if nums:
                    return nums[-1], 0.9, line.strip()
    return None, 0.0, None


def _tax_amount(lines, name):
    for line in lines:
        if re.search(rf"\b{name}\b", line, re.I) and "GSTIN" not in line.upper() and "%" in line or \
                re.match(rf"^\s*{name}\s+[\d,]+\.\d\d\s*$", line, re.I):
            after = line[re.search(name, line, re.I).end():]
            nums = [to_num(n) for n in NUM_RE.findall(after)]
            nums = [n for n in nums if n is not None]
            # skip the rate itself (9, 18, 2.5 ...) and take the rupee amount
            amts = [n for n in nums if n not in (0, 2.5, 5, 6, 9, 12, 14, 18, 28)]
            if amts:
                return amts[-1], 0.9, line.strip()
    return None, 0.0, None


def _line_items(lines):
    items = []
    for line in lines:
        low = line.lower()
        if re.search(r"total|gst|tax|round|amount chargeable|bill amount|subtotal", low):
            continue
        toks = [(m.start(), m.group(), to_num(m.group())) for m in NUM_RE.finditer(line)]
        toks = [t for t in toks if t[2] is not None]
        found = None
        # prefer the right-most triple: descriptions are full of stray numbers (5 ply, 600x400, M10)
        for k in range(len(toks) - 1, 1, -1):
            amt = toks[k][2]
            for j in range(k - 1, 0, -1):
                rate = toks[j][2]
                for i in range(j - 1, -1, -1):
                    qty = toks[i][2]
                    if qty <= 0 or rate <= 0 or amt < 1:
                        continue
                    if abs(qty * rate - amt) <= max(1.0, amt * 0.001):
                        found = (i, j, k)
                        break
                if found:
                    break
            if found:
                break
        if not found:
            continue
        i, j, k = found
        qpos = toks[i][0]
        head = line[:qpos]
        hsn = None
        mh = re.search(r"\b(\d{4,8})\s*$", head)
        if mh:
            hsn = mh.group(1)
            head = head[:mh.start()]
        desc = re.sub(r"^\s*\d{1,2}[.)]?\s+", "", head).strip(" -|")
        desc = re.sub(r"\s{2,}", " ", desc)
        unit_m = re.match(r"\s*([A-Za-z]{2,6})\b", line[qpos + len(toks[i][1]):])
        if not desc:
            continue
        items.append({"description": desc, "hsn": hsn, "qty": toks[i][2], "unit": unit_m.group(1) if unit_m else None,
                      "rate": toks[j][2], "amount": toks[k][2], "confidence": 0.9, "source": line.strip()[:160]})
    return items


def _vendor_name(lines, buyer_name):
    for line in lines[:12]:
        segs = _segments(line)
        if not segs:
            continue
        # wide letter-spaced headings come out as several chunks; glue close ones back
        start, s = segs[0]
        end = start + len(s)
        for st, txt in segs[1:]:
            if st - end > 8 or re.search(r"invoice|dated?\b|no\.|#|gstin|bill", txt, re.I):
                break
            s, end = s + " " + txt, st + len(txt)
        s = re.sub(r"\s+", " ", s).strip()
        for _ in [0]:
            if not s or TITLE_WORDS.match(s) or len(s) < 4:
                continue
            if buyer_name and buyer_name.lower()[:12] in s.lower():
                continue
            if re.search(r"invoice\s*no|gstin|^\d", s, re.I) or DATE_RE.search(s) or re.search(r"\d", s.split()[0]):
                continue
            return s, 0.8, line.strip()
    return None, 0.0, None


def parse(text, buyer_gstin="", buyer_name="", from_ocr=False):
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    f = {}
    penalty = 0.12 if from_ocr else 0.0

    def put(key, val, conf, src):
        f[key] = {"value": val, "confidence": round(max(0.0, conf - penalty) if val is not None else 0.0, 2),
                  "source": src}

    put("vendor_name", *_vendor_name(lines, buyer_name))

    gstins = []
    for line in lines:
        for g in GSTIN_RE.findall(line.upper()):
            if g not in gstins:
                gstins.append(g)
    vend = [g for g in gstins if g != buyer_gstin]
    put("vendor_gstin", vend[0] if vend else None, 0.95 if vend else 0, vend[0] if vend else None)
    put("buyer_gstin", buyer_gstin if buyer_gstin in gstins else None, 0.95, buyer_gstin if buyer_gstin in gstins else None)

    v, c, s = _find_labelled(lines, LABELS["invoice_no"], INVNO_RE)
    if not v:
        # labels unreadable (common on scans): take an ID-looking token from the top of the page
        best = None
        for line in lines[:10]:
            for m in INVNO_RE.finditer(line):
                tok = m.group(0)
                if GSTIN_RE.match(tok.upper()) or PO_RE.match(tok) or DATE_RE.match(tok):
                    continue
                # header metadata sits on the right and usually shares a line with the date
                score = (m.start() > 40) + bool(DATE_RE.search(line))
                if best is None or score > best[0]:
                    best = (score, tok, line.strip())
        if best:
            v, c, s = best[1], 0.6, best[2]
    put("invoice_no", v, c, s)

    v, c, s = _find_labelled(lines, LABELS["invoice_date"], DATE_RE)
    if not v:
        for line in lines:
            m = DATE_RE.search(line)
            if m and parse_date(m.group(0)):
                v, c, s = m.group(0), 0.7, line.strip()
                break
    d = parse_date(v) if v else None
    put("invoice_date", d.isoformat() if d else None, c if d else 0, s)

    v, c, s = _find_labelled(lines, LABELS["po_ref"], PO_RE, look_below=1)
    if not v:
        for line in lines:
            m = PO_RE.search(line)
            if m:
                v, c, s = m.group(0), 0.75, line.strip()
                break
    put("po_ref", v.upper().replace(" ", "-") if v else None, c, s)

    put("total", *_last_amount_on(lines, LABELS["total"]))
    if f["total"]["value"] is None:
        put("total", *_last_amount_on(lines, [r"^\s*total\b", r"\btotal\b"], exclude=r"taxable|sub"))
    put("taxable_value", *_last_amount_on(lines, LABELS["taxable_value"]))
    for t in ("cgst", "sgst", "igst"):
        put(t, *_tax_amount(lines, t))
    put("round_off", *_last_amount_on(lines, [r"round\s*off"]))

    v, c, s = _find_labelled(lines, LABELS["bank_account"], ACCT_RE)
    put("bank_account", v, c, s)
    ifsc = None
    for line in lines:
        m = IFSC_RE.search(line.upper())
        if m:
            ifsc = (m.group(0), 0.9, line.strip())
            break
    put("ifsc", *(ifsc or (None, 0, None)))
    v, c, s = _find_labelled(lines, LABELS["bank_name"], None, look_below=0)
    put("bank_name", v, c * 0.9, s)

    note = None
    for line in lines:
        if re.search(r"bank (account|details).{0,20}(changed|updated|new)|new (bank|account)", line, re.I):
            note = line.strip()
            break
    put("remarks", note, 0.9 if note else 0, note)

    items = _line_items(lines)
    if from_ocr:
        for it in items:
            it["confidence"] = round(it["confidence"] - penalty, 2)

    # if the taxable value isn't printed, the line items are the next best thing
    if f["taxable_value"]["value"] is None and items:
        put("taxable_value", round(sum(i["amount"] for i in items), 2), 0.7, "sum of line items")

    return {"fields": f, "lines": items}
