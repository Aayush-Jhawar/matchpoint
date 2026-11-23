"""
Vendor master, purchase orders and goods receipts.

In a real deployment these come from the ERP. Here they can be maintained from
the UI so the demo company can be extended without touching CSVs. Everything is
validated server-side; the UI validates the same rules as you type.
"""
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Body, HTTPException

from . import db, gstin

router = APIRouter(prefix="/api")

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
ACCT_RE = re.compile(r"^\d{9,18}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GST_RATES = (0, 5, 12, 18, 28)
BANK_FIELDS = ("bank_name", "account_no", "ifsc")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fail(errors):
    raise HTTPException(422, {"errors": errors})


def _next(prefix, table, col, width):
    nums = [int(m.group(1)) for r in db.q(f"SELECT {col} v FROM {table}")
            if (m := re.match(rf"^{re.escape(prefix)}(\d+)$", r["v"] or ""))]
    return f"{prefix}{(max(nums) + 1 if nums else 1):0{width}d}"


def _iso(d, field, errors):
    try:
        return date.fromisoformat(d).isoformat()
    except (TypeError, ValueError):
        errors[field] = "Use a valid date."


# ------------------------------------------------------------------ vendors
def _vendor_errors(v, existing_id=None):
    e = {}
    if len((v.get("name") or "").strip()) < 3:
        e["name"] = "Enter the vendor's legal name."
    g = (v.get("gstin") or "").strip().upper()
    probs = gstin.check(g)
    if probs:
        e["gstin"] = "GSTIN " + probs[0] + "."
    else:
        dup = db.q1("SELECT vendor_id, name FROM vendors WHERE gstin=? AND vendor_id!=?", (g, existing_id or ""))
        if dup:
            e["gstin"] = f"Already registered to {dup['name']} ({dup['vendor_id']})."
    if not (v.get("address") or "").strip():
        e["address"] = "Enter the registered address."
    if not (v.get("bank_name") or "").strip():
        e["bank_name"] = "Enter the bank and branch."
    if not ACCT_RE.match((v.get("account_no") or "").strip()):
        e["account_no"] = "Account number should be 9 to 18 digits."
    if not IFSC_RE.match((v.get("ifsc") or "").strip().upper()):
        e["ifsc"] = "IFSC is 11 characters: 4 letters, 0, then 6 letters or digits."
    if v.get("email") and not EMAIL_RE.match(v["email"].strip()):
        e["email"] = "That doesn't look like an email address."
    if len(re.sub(r"\D", "", v.get("phone") or "")) < 10:
        e["phone"] = "A phone number is needed: it's what AP calls to verify bank changes."
    return e


def _clean_vendor(v):
    g = v["gstin"].strip().upper()
    return {
        "name": v["name"].strip(), "address": v["address"].strip(), "gstin": g, "state": g[:2], "pan": g[2:12],
        "bank_name": v["bank_name"].strip(), "account_no": v["account_no"].strip(), "ifsc": v["ifsc"].strip().upper(),
        "phone": (v.get("phone") or "").strip(), "email": (v.get("email") or "").strip(),
        "status": v.get("status") if v.get("status") in ("active", "blocked") else "active",
    }


@router.get("/vendors")
def list_vendors():
    out = []
    for v in db.q("SELECT * FROM vendors ORDER BY vendor_id"):
        v["open_pos"] = db.q1("SELECT COUNT(*) n FROM purchase_orders WHERE vendor_id=? AND status='open'",
                              (v["vendor_id"],))["n"]
        v["invoices"] = db.q1("SELECT COUNT(*) n FROM ledger WHERE vendor_id=?", (v["vendor_id"],))["n"]
        v["state_name"] = gstin.STATES.get(v["state"], v["state"])
        out.append(v)
    return out


@router.get("/vendors/{vendor_id}")
def get_vendor(vendor_id: str):
    v = db.q1("SELECT * FROM vendors WHERE vendor_id=?", (vendor_id,))
    if not v:
        raise HTTPException(404, "No such vendor")
    v["state_name"] = gstin.STATES.get(v["state"], v["state"])
    v["pos"] = db.q("SELECT * FROM purchase_orders WHERE vendor_id=? ORDER BY po_date DESC", (vendor_id,))
    v["invoices"] = db.q("SELECT invoice_no, po_no, invoice_date, total, status, run_id FROM ledger "
                         "WHERE vendor_id=? ORDER BY invoice_date DESC", (vendor_id,))
    v["changes"] = db.q("SELECT * FROM vendor_changes WHERE vendor_id=? ORDER BY changed_at DESC", (vendor_id,))
    return v


@router.post("/vendors")
def create_vendor(body: dict = Body(...)):
    errors = _vendor_errors(body)
    if errors:
        _fail(errors)
    v = _clean_vendor(body)
    v["vendor_id"] = _next("V", "vendors", "vendor_id", 3)
    cols = list(v.keys())
    db.ex(f"INSERT INTO vendors ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [v[c] for c in cols])
    db.ex("INSERT INTO vendor_changes VALUES (?,?,?,?,?,?)", (v["vendor_id"], "created", "", v["name"], _now(), ""))
    return get_vendor(v["vendor_id"])


@router.put("/vendors/{vendor_id}")
def update_vendor(vendor_id: str, body: dict = Body(...)):
    old = db.q1("SELECT * FROM vendors WHERE vendor_id=?", (vendor_id,))
    if not old:
        raise HTTPException(404, "No such vendor")
    errors = _vendor_errors(body, vendor_id)
    if errors:
        _fail(errors)
    new = _clean_vendor(body)
    changed = [k for k in new if str(new[k] or "") != str(old.get(k) or "")]
    bank_changed = any(k in BANK_FIELDS for k in changed)
    note = (body.get("verification_note") or "").strip()
    if bank_changed and (not body.get("verified") or len(note) < 10):
        _fail({"verified": "Bank details changed. Confirm you verified this with the vendor on the phone number "
                           "already on file, and note who you spoke to."})
    if not changed:
        return get_vendor(vendor_id)
    sets = ", ".join(f"{k}=?" for k in changed)
    db.ex(f"UPDATE vendors SET {sets} WHERE vendor_id=?", [new[k] for k in changed] + [vendor_id])
    for k in changed:
        db.ex("INSERT INTO vendor_changes VALUES (?,?,?,?,?,?)",
              (vendor_id, k, str(old.get(k) or ""), str(new[k] or ""), _now(), note if k in BANK_FIELDS else ""))
    return get_vendor(vendor_id)


# ------------------------------------------------------------------ purchase orders
def _po_line_stats(po_no):
    lines = db.q("SELECT * FROM po_lines WHERE po_no=? ORDER BY line_no", (po_no,))
    for l in lines:
        l["received"] = db.q1("SELECT COALESCE(SUM(qty_received),0) s FROM grn WHERE po_no=? AND line_no=?",
                              (po_no, l["line_no"]))["s"]
        l["billed"] = db.q1("SELECT COALESCE(SUM(ll.qty),0) s FROM ledger_lines ll JOIN ledger g ON g.id=ll.ledger_id "
                            "WHERE ll.po_no=? AND ll.line_no=? AND g.status IN ('paid','approved')",
                            (po_no, l["line_no"]))["s"]
        l["on_hold"] = db.q1("SELECT COALESCE(SUM(ll.qty),0) s FROM ledger_lines ll JOIN ledger g ON g.id=ll.ledger_id "
                             "WHERE ll.po_no=? AND ll.line_no=? AND g.status='on_hold'", (po_no, l["line_no"]))["s"]
        l["value"] = round(l["qty"] * l["rate"], 2)
    return lines


@router.get("/pos")
def list_pos(status: str = "all"):
    sql = "SELECT p.*, v.name vendor FROM purchase_orders p JOIN vendors v USING (vendor_id)"
    args = ()
    if status in ("open", "closed"):
        sql += " WHERE p.status=?"
        args = (status,)
    out = []
    for po in db.q(sql + " ORDER BY p.po_date DESC, p.po_no DESC", args):
        n = po["po_no"]
        po["billed"] = db.q1("SELECT COALESCE(SUM(taxable_value),0) s FROM ledger WHERE po_no=? AND status IN "
                             "('paid','approved')", (n,))["s"]
        po["on_hold"] = db.q1("SELECT COALESCE(SUM(taxable_value),0) s FROM ledger WHERE po_no=? AND status='on_hold'",
                              (n,))["s"]
        po["received_value"] = db.q1("SELECT COALESCE(SUM(g.qty_received*l.rate),0) s FROM grn g JOIN po_lines l "
                                     "ON g.po_no=l.po_no AND g.line_no=l.line_no WHERE g.po_no=?", (n,))["s"]
        po["value"] = po["taxable_value"]
        po["lines"] = db.q1("SELECT COUNT(*) n FROM po_lines WHERE po_no=?", (n,))["n"]
        out.append(po)
    return out


@router.get("/pos/next-number")
def next_po_number():
    year = date.today().year
    return {"po_no": _next(f"PO-{year}-", "purchase_orders", "po_no", 4)}


@router.get("/pos/{po_no}")
def get_po(po_no: str):
    po = db.q1("SELECT p.*, v.name vendor, v.gstin vendor_gstin FROM purchase_orders p JOIN vendors v USING (vendor_id) "
               "WHERE p.po_no=?", (po_no,))
    if not po:
        raise HTTPException(404, "No such PO")
    po["lines"] = _po_line_stats(po_no)
    grns = {}
    for g in db.q("SELECT g.*, l.item FROM grn g JOIN po_lines l ON g.po_no=l.po_no AND g.line_no=l.line_no "
                  "WHERE g.po_no=? ORDER BY g.grn_date DESC, g.grn_no DESC", (po_no,)):
        grns.setdefault(g["grn_no"], {"grn_no": g["grn_no"], "grn_date": g["grn_date"], "lines": []})["lines"].append(
            {"line_no": g["line_no"], "item": g["item"], "qty": g["qty_received"]})
    po["receipts"] = list(grns.values())
    po["invoices"] = db.q("SELECT invoice_no, invoice_date, taxable_value, total, status, run_id FROM ledger "
                          "WHERE po_no=? ORDER BY invoice_date DESC", (po_no,))
    po["billed"] = sum(i["taxable_value"] for i in po["invoices"] if i["status"] in ("paid", "approved"))
    return po


@router.post("/pos")
def create_po(body: dict = Body(...)):
    e = {}
    vendor = db.q1("SELECT * FROM vendors WHERE vendor_id=?", (body.get("vendor_id"),))
    if not vendor:
        e["vendor_id"] = "Pick a vendor."
    elif vendor["status"] != "active":
        e["vendor_id"] = "This vendor is blocked. Unblock it before raising a PO."
    po_date = _iso(body.get("po_date"), "po_date", e)
    po_no = (body.get("po_no") or "").strip().upper() or next_po_number()["po_no"]
    if not re.match(r"^PO-\d{4}-\d{3,5}$", po_no):
        e["po_no"] = "Use the format PO-2026-0431."
    elif db.q1("SELECT 1 FROM purchase_orders WHERE po_no=?", (po_no,)):
        e["po_no"] = f"{po_no} already exists."
    lines = [l for l in body.get("lines") or [] if (l.get("item") or "").strip() or l.get("qty") or l.get("rate")]
    if not lines:
        e["lines"] = "Add at least one line."
    clean = []
    for i, l in enumerate(lines):
        try:
            qty, rate, gst = float(l.get("qty")), float(l.get("rate")), float(l.get("gst_rate", 18))
        except (TypeError, ValueError):
            e[f"line_{i}"] = "Quantity, rate and GST must be numbers."
            continue
        if not (l.get("item") or "").strip():
            e[f"line_{i}"] = "Describe the item."
        elif qty <= 0 or rate <= 0:
            e[f"line_{i}"] = "Quantity and rate must be more than zero."
        elif gst not in GST_RATES:
            e[f"line_{i}"] = "GST must be 0, 5, 12, 18 or 28%."
        elif l.get("hsn") and not re.match(r"^\d{4,8}$", str(l["hsn"]).strip()):
            e[f"line_{i}"] = "HSN is 4 to 8 digits."
        clean.append({"line_no": i + 1, "item": (l.get("item") or "").strip(), "hsn": str(l.get("hsn") or "").strip(),
                      "qty": qty, "unit": (l.get("unit") or "nos").strip(), "rate": rate, "gst_rate": gst})
    if e:
        _fail(e)
    total = round(sum(l["qty"] * l["rate"] for l in clean), 2)
    db.ex("INSERT INTO purchase_orders VALUES (?,?,?,?,?)", (po_no, vendor["vendor_id"], po_date, "open", total))
    for l in clean:
        db.ex("INSERT INTO po_lines VALUES (?,?,?,?,?,?,?,?)",
              (po_no, l["line_no"], l["item"], l["hsn"], l["qty"], l["unit"], l["rate"], l["gst_rate"]))
    return get_po(po_no)


@router.post("/pos/{po_no}/receipts")
def receive_goods(po_no: str, body: dict = Body(...)):
    po = db.q1("SELECT * FROM purchase_orders WHERE po_no=?", (po_no,))
    if not po:
        raise HTTPException(404, "No such PO")
    e = {}
    if po["status"] != "open":
        e["form"] = "This PO is closed. Reopen it to record a receipt."
    grn_date = _iso(body.get("grn_date"), "grn_date", e)
    stats = {l["line_no"]: l for l in _po_line_stats(po_no)}
    rows = []
    for r in body.get("lines") or []:
        try:
            ln, qty = int(r.get("line_no")), float(r.get("qty") or 0)
        except (TypeError, ValueError):
            continue
        if qty == 0:
            continue
        l = stats.get(ln)
        if not l:
            e[f"line_{ln}"] = "Not a line on this PO."
        elif qty < 0:
            e[f"line_{ln}"] = "Can't receive a negative quantity."
        elif qty > l["qty"] - l["received"] + 1e-9:
            e[f"line_{ln}"] = f"Only {l['qty'] - l['received']:g} still to receive on this line."
        rows.append((ln, qty))
    if not rows and not e:
        e["form"] = "Enter the quantity received on at least one line."
    if e:
        _fail(e)
    grn_no = _next(f"GRN-{str(date.today().year)[2:]}-", "grn", "grn_no", 4)
    for ln, qty in rows:
        db.ex("INSERT INTO grn VALUES (?,?,?,?,?)", (grn_no, po_no, ln, qty, grn_date))
    return get_po(po_no)


@router.post("/pos/{po_no}/status")
def set_po_status(po_no: str, body: dict = Body(...)):
    status = body.get("status")
    if status not in ("open", "closed"):
        _fail({"status": "Status must be open or closed."})
    if not db.q1("SELECT 1 FROM purchase_orders WHERE po_no=?", (po_no,)):
        raise HTTPException(404, "No such PO")
    db.ex("UPDATE purchase_orders SET status=? WHERE po_no=?", (status, po_no))
    return get_po(po_no)
