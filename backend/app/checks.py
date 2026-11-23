"""
Every check is plain Python against the ledger. Each stage gets the shared
run context, adds what it learned, and raises findings. Findings carry a level
(reject / hold / note) and an owner, and rules.decide() turns them into one decision.
"""
import hashlib
from datetime import date, timedelta

from . import db, gstin
from .normalize import (canonical_invoice_no, fmt_inr, item_similarity, name_similarity, parse_date)

CRITICAL = ["invoice_no", "invoice_date", "total", "vendor_gstin"]
LABEL = {"invoice_no": "Invoice number", "invoice_date": "Invoice date", "total": "Invoice total",
         "vendor_gstin": "Vendor GSTIN", "vendor_name": "Vendor name", "po_ref": "PO reference"}


def finding(ctx, code, level, owner, title, detail="", action=""):
    ctx["findings"].append({"code": code, "level": level, "owner": owner, "title": title,
                            "detail": detail, "action": action, "stage": ctx["_stage"]})


def mask(acct):
    return "xxxx" + acct[-4:] if acct and len(acct) > 4 else (acct or "-")


# ------------------------------------------------------------------ 1 intake
def intake(ctx):
    data = ctx["data"]
    ctx["file_hash"] = hashlib.sha256(data).hexdigest()
    from .extract import pdftext
    text = "" if pdftext.is_image(ctx["file_name"]) else pdftext.text_layer(data)
    has_text = len(text.strip()) >= 50
    ctx["has_text"] = has_text
    pages = pdftext.page_count(data, ctx["file_name"])
    facts = [("File", ctx["file_name"]), ("Size", f"{len(data) / 1024:.0f} KB"), ("Pages", pages),
             ("Fingerprint", ctx["file_hash"][:12]),
             ("Text layer", "yes, machine-readable" if has_text else "no, looks like a scan or photo")]
    if pages == 0:
        ctx["unreadable"] = True
        finding(ctx, "UNREADABLE", "hold", "AP team", "File could not be opened",
                "The file is not a readable PDF or image.", "Ask the vendor to resend the invoice.")
        return "fail", "Could not open the file", facts
    return "ok", ("Machine-readable PDF" if has_text else "Scanned / image invoice"), facts


# ------------------------------------------------------------------ 2 extract
def extract(ctx):
    from . import extract as ex
    result, method, notes = ex.run(ctx["data"], ctx["file_name"], ctx["file_hash"], ctx["settings"])
    for field, value in (ctx.get("overrides") or {}).items():
        if field in result["fields"]:
            result["fields"][field] = {"value": value, "confidence": 1.0, "source": "confirmed by AP"}
    ctx["ext"] = result
    ctx["method"] = method
    f = result["fields"]
    found = sum(1 for v in f.values() if v["value"] is not None)
    facts = [("Read with", method), ("Fields found", f"{found} of {len(f)}"), ("Line items", len(result["lines"]))]
    for n in notes:
        facts.append(("Note", n))
    floor = ctx["settings"]["confidence_floor"]
    shaky = [k for k in CRITICAL if f[k]["value"] is not None and f[k]["confidence"] < floor]
    if method == "none":
        finding(ctx, "UNREADABLE", "hold", "AP team", "Nothing could be read from the file",
                "No text layer, and neither OCR nor an LLM is configured.", "Key the invoice manually or add an API key.")
        return "fail", "Nothing extracted", facts
    if shaky:
        return "warn", f"Extracted, but {len(shaky)} critical field(s) are low confidence", facts
    return "ok", f"{found} fields and {len(result['lines'])} line item(s) extracted", facts


# ------------------------------------------------------------------ 3 normalise
def normalise(ctx):
    f = ctx["ext"]["fields"]
    v = lambda k: f[k]["value"]
    inv = {
        "vendor_name": v("vendor_name"), "gstin": (v("vendor_gstin") or "").upper() or None,
        "buyer_gstin": v("buyer_gstin"), "invoice_no": v("invoice_no"),
        "canonical_no": canonical_invoice_no(v("invoice_no")), "date": parse_date(v("invoice_date")),
        "po_ref": (v("po_ref") or "").upper() or None,
        "taxable": v("taxable_value"), "cgst": v("cgst") or 0.0, "sgst": v("sgst") or 0.0, "igst": v("igst") or 0.0,
        "round_off": v("round_off") or 0.0, "total": v("total"),
        "bank_account": "".join(ch for ch in (v("bank_account") or "") if ch.isdigit()) or None,
        "ifsc": v("ifsc"), "bank_name": v("bank_name"), "remarks": v("remarks"),
        "lines": ctx["ext"]["lines"],
    }
    if inv["taxable"] is None and inv["lines"]:
        inv["taxable"] = round(sum(l["amount"] for l in inv["lines"]), 2)
    inv["tax"] = round(inv["cgst"] + inv["sgst"] + inv["igst"], 2)
    inv["tax_type"] = "IGST (inter-state)" if inv["igst"] else ("CGST + SGST (intra-state)" if inv["tax"] else "none")
    ctx["inv"] = inv
    facts = [("Invoice no.", f"{inv['invoice_no'] or '-'}  →  {inv['canonical_no'] or '-'} (for duplicate checks)"),
             ("Date", inv["date"].strftime("%d %b %Y") if inv["date"] else "-"),
             ("Taxable value", fmt_inr(inv["taxable"])), ("Tax", f"{fmt_inr(inv['tax'])} as {inv['tax_type']}"),
             ("Total", fmt_inr(inv["total"])), ("Currency", "INR")]
    return "ok", "Values cleaned and put in standard form", facts


# ------------------------------------------------------------------ 4 validate
def validate(ctx):
    inv, f, s = ctx["inv"], ctx["ext"]["fields"], ctx["settings"]
    buyer = db.buyer()
    facts = []

    missing = [k for k in CRITICAL if f[k]["value"] is None and not (k == "vendor_gstin" and inv["vendor_name"])]
    if missing:
        finding(ctx, "MISSING_FIELD", "hold", "AP team", "Required fields missing: " + ", ".join(LABEL[k] for k in missing),
                "These could not be found on the invoice. They may be absent or unreadable.",
                "Check the PDF. If they really are missing, ask the vendor for a corrected invoice.")
    shaky = [k for k in CRITICAL if f[k]["value"] is not None and f[k]["confidence"] < s["confidence_floor"]]
    if shaky:
        ctx["needs_confirmation"] = shaky
        finding(ctx, "LOW_CONFIDENCE", "hold", "AP team",
                "Not sure I read " + ", ".join(LABEL[k].lower() for k in shaky) + " correctly",
                "; ".join(f"{LABEL[k]} read as '{f[k]['value']}' ({int(f[k]['confidence'] * 100)}% confidence)" for k in shaky)
                + ". These fields drive duplicate checks and payment, so they are not guessed.",
                "Confirm or correct the values and re-run.")

    if inv["lines"] and inv["taxable"] is not None:
        lsum = round(sum(l["amount"] for l in inv["lines"]), 2)
        facts.append(("Line items add up to", fmt_inr(lsum)))
        if abs(lsum - inv["taxable"]) > s["total_rounding"]:
            finding(ctx, "LINE_SUM_MISMATCH", "hold", "Vendor", "Line items don't add up to the taxable value",
                    f"Lines total {fmt_inr(lsum)}, invoice says {fmt_inr(inv['taxable'])}.",
                    "Ask the vendor for a corrected invoice.")
    if inv["total"] is not None and inv["taxable"] is not None:
        computed = round(inv["taxable"] + inv["tax"] + inv["round_off"], 2)
        facts.append(("Taxable + tax", fmt_inr(computed)))
        if abs(computed - inv["total"]) > s["total_rounding"]:
            finding(ctx, "TOTAL_MISMATCH", "hold", "Vendor", "Invoice total doesn't add up",
                    f"Taxable {fmt_inr(inv['taxable'])} + tax {fmt_inr(inv['tax'])} = {fmt_inr(computed)}, "
                    f"but the invoice total is {fmt_inr(inv['total'])}.", "Ask the vendor for a corrected invoice.")
        elif abs(computed - inv["total"]) > 0.005:
            facts.append(("Rounding", f"{fmt_inr(inv['total'] - computed)} (within ₹{s['total_rounding']:.0f})"))

    if inv["gstin"]:
        probs = gstin.check(inv["gstin"])
        facts.append(("Vendor GSTIN", inv["gstin"] + (" - " + "; ".join(probs) if probs else " - format and checksum OK")))
        if probs:
            finding(ctx, "GSTIN_INVALID", "hold", "Tax", "Vendor GSTIN is not valid",
                    f"{inv['gstin']}: {'; '.join(probs)}.", "Input tax credit can't be claimed on an invalid GSTIN. "
                    "Ask the vendor to confirm their GSTIN.")
    if inv["buyer_gstin"] and inv["buyer_gstin"] != buyer["gstin"]:
        finding(ctx, "BILLED_TO_OTHER", "hold", "AP team", "Invoice is addressed to a different GSTIN",
                f"Billed to {inv['buyer_gstin']}, ours is {buyer['gstin']}.", "Return to vendor.")

    vstate = gstin.state_of(inv["gstin"]) if inv["gstin"] else None
    bstate = gstin.state_of(buyer["gstin"])
    if vstate and inv["tax"]:
        same = vstate == bstate
        expected = "CGST + SGST" if same else "IGST"
        facts.append(("Place of supply", f"vendor in {gstin.STATES.get(vstate, vstate)}, we are in "
                                         f"{gstin.STATES.get(bstate, bstate)} → expect {expected}"))
        if same and inv["igst"]:
            finding(ctx, "WRONG_TAX_TYPE", "hold", "Tax", "IGST charged on an intra-state supply",
                    f"Vendor and buyer are both in {gstin.STATES.get(vstate)} (state code {vstate}), so the invoice "
                    f"should carry CGST + SGST. It charges IGST of {fmt_inr(inv['igst'])}.",
                    "Input credit on wrongly charged IGST is not available. Ask the vendor to reissue with CGST + SGST.")
        if not same and (inv["cgst"] or inv["sgst"]):
            finding(ctx, "WRONG_TAX_TYPE", "hold", "Tax", "CGST/SGST charged on an inter-state supply",
                    f"Vendor is in {gstin.STATES.get(vstate, vstate)}, we are in {gstin.STATES.get(bstate)}. "
                    "Inter-state supplies carry IGST.", "Ask the vendor to reissue with IGST.")
        if same and abs(inv["cgst"] - inv["sgst"]) > 1:
            finding(ctx, "WRONG_TAX_TYPE", "hold", "Tax", "CGST and SGST are not equal",
                    f"CGST {fmt_inr(inv['cgst'])} vs SGST {fmt_inr(inv['sgst'])}.", "Ask the vendor to correct.")
    if inv["date"] and inv["date"] > date.today() + timedelta(days=1):
        finding(ctx, "FUTURE_DATE", "hold", "AP team", "Invoice is dated in the future",
                f"Dated {inv['date']:%d %b %Y}.", "Check with the vendor.")

    n = len([x for x in ctx["findings"] if x["stage"] == "validate"])
    return ("warn" if n else "ok"), (f"{n} problem(s) on the document itself" if n else "Document is internally consistent"), facts


# ------------------------------------------------------------------ 5 vendor
def vendor(ctx):
    inv = ctx["inv"]
    vendors = db.q("SELECT * FROM vendors")
    match, how = None, None
    if inv["gstin"]:
        match = next((v for v in vendors if v["gstin"] == inv["gstin"]), None)
        how = "GSTIN exact match" if match else None
    if not match and inv["vendor_name"]:
        best = max(vendors, key=lambda v: name_similarity(v["name"], inv["vendor_name"]))
        score = name_similarity(best["name"], inv["vendor_name"])
        if score >= 88:
            match, how = best, f"name match ({score:.0f}%), GSTIN did not match"
            if inv["gstin"]:
                finding(ctx, "GSTIN_NOT_MASTER", "hold", "Procurement", "GSTIN on invoice differs from vendor master",
                        f"Invoice: {inv['gstin']}. Master record for {best['name']}: {best['gstin']}.",
                        "Confirm whether the vendor has a second registration before paying.")
    if not match:
        finding(ctx, "UNKNOWN_VENDOR", "hold", "Procurement", "Vendor is not in the vendor master",
                f"No vendor with GSTIN {inv['gstin'] or '-'} or a name close to '{inv['vendor_name'] or '-'}'.",
                "Onboard the vendor before this invoice can be processed.")
        ctx["vendor"] = None
        return "fail", "No matching vendor", [("Searched", f"{len(vendors)} vendors")]

    ctx["vendor"] = match
    facts = [("Vendor", f"{match['name']} ({match['vendor_id']})"), ("Matched on", how)]
    if how.startswith("GSTIN") and inv["vendor_name"] and name_similarity(match["name"], inv["vendor_name"]) < 70:
        finding(ctx, "NAME_DIFFERS", "note", "AP team", "Name on invoice differs from vendor master",
                f"Invoice says '{inv['vendor_name']}', master says '{match['name']}'. GSTIN matches.")
    if match["status"] != "active":
        finding(ctx, "VENDOR_INACTIVE", "hold", "Procurement", f"Vendor is marked {match['status']}")

    if inv["bank_account"]:
        same_acct = inv["bank_account"].lstrip("0") == match["account_no"].lstrip("0")
        same_ifsc = not inv["ifsc"] or inv["ifsc"] == match["ifsc"]
        facts.append(("Bank on invoice", f"A/c {mask(inv['bank_account'])}, {inv['ifsc'] or '-'}"))
        facts.append(("Bank in master", f"A/c {mask(match['account_no'])}, {match['ifsc']}"))
        if not (same_acct and same_ifsc):
            extra = f" The invoice also says: \"{inv['remarks']}\"" if inv["remarks"] else ""
            finding(ctx, "BANK_CHANGED", "hold", "Treasury", "Bank details differ from the vendor master",
                    f"Invoice asks for payment to A/c {mask(inv['bank_account'])} ({inv['ifsc']}, {inv['bank_name'] or 'bank not named'}). "
                    f"Vendor master has A/c {mask(match['account_no'])} ({match['ifsc']}).{extra} "
                    "This is the usual pattern of invoice fraud, so no other check can override it.",
                    "Don't update the master from the invoice. Call the vendor on the phone number already on file, "
                    "get the change confirmed in writing on letterhead with a cancelled cheque, then re-run.")
            return "fail", "Vendor found, but the bank account has changed", facts
    else:
        facts.append(("Bank on invoice", "not printed; will pay to master account"))
    return "ok", f"{match['name']}", facts


# ------------------------------------------------------------------ helpers for PO work
def po_lines(po_no):
    return db.q("SELECT * FROM po_lines WHERE po_no=? ORDER BY line_no", (po_no,))


def received(po_no, line_no):
    r = db.q1("SELECT COALESCE(SUM(qty_received),0) q, COUNT(*) n FROM grn WHERE po_no=? AND line_no=?", (po_no, line_no))
    return r["q"], r["n"]


def billed(po_no, line_no, exclude_run=None):
    rows = db.q("SELECT l.invoice_no, ll.qty FROM ledger_lines ll JOIN ledger l ON l.id=ll.ledger_id "
                "WHERE ll.po_no=? AND ll.line_no=? AND l.status IN ('paid','approved') AND COALESCE(l.run_id,'')!=?",
                (po_no, line_no, exclude_run or "__none__"))
    return sum(r["qty"] for r in rows), [r["invoice_no"] for r in rows]


def po_billed_value(po_no, exclude_run=None):
    rows = db.q("SELECT invoice_no, taxable_value FROM ledger WHERE po_no=? AND status IN ('paid','approved') "
                "AND COALESCE(run_id,'')!=?", (po_no, exclude_run or "__none__"))
    return sum(r["taxable_value"] for r in rows), rows


def map_lines(inv_lines, pls):
    """Greedy: each invoice line takes the best PO line not already taken."""
    pairs, taken = [], set()
    for il in inv_lines:
        best, best_score = None, 0
        for pl in pls:
            if pl["line_no"] in taken:
                continue
            sim = item_similarity(il["description"], pl["item"])
            score = sim
            if pl["rate"] and abs(il["rate"] - pl["rate"]) / pl["rate"] <= 0.05:
                score += 20
            if il.get("hsn") and str(il["hsn"]) == str(pl["hsn"]):
                score += 10
            if (sim >= 55 or score >= 85) and score > best_score:
                best, best_score = pl, score
        if best:
            taken.add(best["line_no"])
        pairs.append((il, best, best_score))
    return pairs


# ------------------------------------------------------------------ 6 PO
def match_po(ctx):
    inv, v, s = ctx["inv"], ctx["vendor"], ctx["settings"]
    ctx["po"] = None
    if not v:
        return "skip", "Skipped: no vendor", []
    if inv["po_ref"]:
        po = db.q1("SELECT * FROM purchase_orders WHERE po_no=?", (inv["po_ref"],))
        if not po:
            finding(ctx, "PO_NOT_FOUND", "hold", "Procurement", f"PO {inv['po_ref']} does not exist",
                    "The PO quoted on the invoice is not in the PO register.", "Ask the vendor or the requester which PO this is.")
            return "fail", f"{inv['po_ref']} not found", []
        if po["vendor_id"] != v["vendor_id"]:
            finding(ctx, "PO_VENDOR_MISMATCH", "hold", "Procurement", f"{po['po_no']} belongs to a different vendor",
                    f"PO is raised on {po['vendor_id']}, invoice is from {v['vendor_id']}.", "Check with procurement.")
            return "fail", "PO belongs to another vendor", []
        if po["status"] != "open":
            finding(ctx, "PO_CLOSED", "hold", "Procurement", f"{po['po_no']} is {po['status']}",
                    "Invoices can't be booked against a closed PO.", "Reopen the PO or raise a new one.")
        ctx["po"] = po
        return "ok", f"{po['po_no']} quoted on the invoice", [
            ("PO", po["po_no"]), ("How", "quoted on the invoice"), ("PO date", po["po_date"]),
            ("PO value (taxable)", fmt_inr(po["taxable_value"])), ("Status", po["status"])]

    # no PO printed: score every open PO of this vendor on what's being billed
    cands = []
    for po in db.q("SELECT * FROM purchase_orders WHERE vendor_id=? AND status='open'", (v["vendor_id"],)):
        pls = po_lines(po["po_no"])
        pairs = map_lines(inv["lines"], pls)
        sims = [item_similarity(il["description"], pl["item"]) if pl else 0 for il, pl, _ in pairs]
        desc = sum(sims) / len(sims) if sims else 0
        qty_ok = [1 if pl and il["qty"] <= received(po["po_no"], pl["line_no"])[0] - billed(po["po_no"], pl["line_no"])[0]
                  else 0 for il, pl, _ in pairs]
        qty_fit = 100 * sum(qty_ok) / len(qty_ok) if qty_ok else 0
        balance = po["taxable_value"] - po_billed_value(po["po_no"])[0]
        amt_fit = 100 if (inv["taxable"] or 0) <= balance * 1.02 else max(0, 100 - 100 * ((inv["taxable"] or 0) - balance) / max(balance, 1))
        score = round(0.6 * desc + 0.2 * qty_fit + 0.2 * amt_fit, 1)
        cands.append({"po_no": po["po_no"], "score": score, "desc": round(desc), "qty_fit": round(qty_fit),
                      "amount_fit": round(amt_fit), "po": po})
    cands.sort(key=lambda c: -c["score"])
    ctx["po_candidates"] = [{k: c[k] for k in ("po_no", "score", "desc", "qty_fit", "amount_fit")} for c in cands]
    facts = [("PO on invoice", "none printed")] + [
        (c["po_no"], f"score {c['score']}  (items {c['desc']}, qty {c['qty_fit']}, amount {c['amount_fit']})") for c in cands]
    if not cands:
        finding(ctx, "PO_NOT_IDENTIFIED", "hold", "Procurement", "No PO quoted and the vendor has no open PO",
                "", "Ask the requester for the PO, or raise one.")
        return "fail", "No open PO for this vendor", facts
    top = cands[0]
    margin = top["score"] - (cands[1]["score"] if len(cands) > 1 else 0)
    if top["score"] >= s["po_inference_min_score"] and margin >= s["po_inference_margin"]:
        ctx["po"] = top["po"]
        finding(ctx, "PO_INFERRED", "note", "AP team", f"No PO on the invoice; matched to {top['po_no']}",
                f"Picked on what is billed: score {top['score']} vs next best "
                f"{cands[1]['score'] if len(cands) > 1 else 'none'}. Items, quantities and amount all fit.",
                "Ask the vendor to quote the PO number on future invoices.")
        return "warn", f"Inferred {top['po_no']} (no PO printed)", facts
    finding(ctx, "PO_AMBIGUOUS", "hold", "Procurement", "No PO quoted and more than one PO could fit",
            "Candidates: " + ", ".join(f"{c['po_no']} ({c['score']})" for c in cands[:3]) + ".",
            "Pick the right PO and re-run.")
    return "fail", "Could not pick a PO with confidence", facts


# ------------------------------------------------------------------ 7 lines
def match_lines(ctx):
    inv, po, s = ctx["inv"], ctx["po"], ctx["settings"]
    ctx["line_table"] = []
    if not po:
        return "skip", "Skipped: no PO", []
    pls = po_lines(po["po_no"])
    pairs = map_lines(inv["lines"], pls)
    ctx["line_pairs"] = pairs
    if not inv["lines"]:
        finding(ctx, "NO_LINES", "hold", "AP team", "No line items could be read", "", "Check the invoice manually.")
        return "fail", "No line items", []
    issues = 0
    for il, pl, _ in pairs:
        row = {"description": il["description"], "inv_qty": il["qty"], "inv_rate": il["rate"], "amount": il["amount"]}
        if not pl:
            finding(ctx, "LINE_NOT_ON_PO", "hold", "Procurement", f"'{il['description']}' is not on {po['po_no']}",
                    f"Billed {il['qty']:g} at {fmt_inr(il['rate'])}.", "Confirm with the requester or get the PO amended.")
            row.update(status="not on PO")
            ctx["line_table"].append(row)
            issues += 1
            continue
        rec, n_grn = received(po["po_no"], pl["line_no"])
        prev, prev_invs = billed(po["po_no"], pl["line_no"], ctx.get("parent_run"))
        open_qty = rec - prev
        var_pct = (il["rate"] - pl["rate"]) / pl["rate"] * 100 if pl["rate"] else 0
        var_amt = (il["rate"] - pl["rate"]) * il["qty"]
        row.update(po_line=pl["line_no"], po_item=pl["item"], po_qty=pl["qty"], po_rate=pl["rate"], received=rec,
                   billed_before=prev, open_qty=open_qty, var_pct=round(var_pct, 2), status="ok")

        if var_pct > s["price_tolerance_pct"] + 1e-9 or var_amt > s["line_variance_cap"]:
            finding(ctx, "PRICE_OVER_TOLERANCE", "hold", "Procurement", f"Price above PO on '{pl['item']}'",
                    f"Billed {fmt_inr(il['rate'])} vs PO {fmt_inr(pl['rate'])} (+{var_pct:.2f}%, {fmt_inr(var_amt)} on "
                    f"{il['qty']:g} units). Tolerance is {s['price_tolerance_pct']:g}% / {fmt_inr(s['line_variance_cap'])} per line.",
                    "Get a price-revision approval or ask for a credit note.")
            row["status"] = "price over tolerance"
            issues += 1
        elif var_pct > 0.005:
            ctx["tolerated_variance"] = ctx.get("tolerated_variance", 0) + max(var_amt, 0)
            finding(ctx, "PRICE_WITHIN_TOLERANCE", "note", "AP team", f"Price {var_pct:.2f}% above PO on '{pl['item']}', within tolerance",
                    f"Billed {fmt_inr(il['rate'])} vs PO {fmt_inr(pl['rate'])}: {fmt_inr(var_amt)} extra on {il['qty']:g} units. "
                    f"Tolerance is {s['price_tolerance_pct']:g}%.", "Flag to procurement for the next PO revision.")
            row["status"] = "price within tolerance"

        if rec == 0:
            finding(ctx, "NO_GRN", "hold", "Procurement", f"Nothing received yet against '{pl['item']}'",
                    "No goods receipt note on this PO line.", "Wait for the GRN or confirm receipt with stores.")
            row["status"] = "not received"
            issues += 1
        elif il["qty"] > open_qty + 1e-6:
            over = il["qty"] - open_qty
            prev_txt = f", {prev:g} already billed ({', '.join(prev_invs)})" if prev else ""
            finding(ctx, "QTY_EXCEEDS_RECEIPT", "hold", "Procurement", f"Billing for more than was received on '{pl['item']}'",
                    f"Invoice bills {il['qty']:g}. Received {rec:g} across {n_grn} GRN(s){prev_txt}, so only {open_qty:g} are "
                    f"open. {over:g} units ({fmt_inr(over * il['rate'])}) have no receipt behind them.",
                    f"Approve {open_qty:g} units and ask the vendor for a revised invoice, or confirm a pending GRN with stores.")
            row["status"] = "qty over receipt"
            issues += 1
        ctx["line_table"].append(row)

    # tax rate vs PO
    if inv["taxable"] and inv["tax"]:
        eff = inv["tax"] / inv["taxable"] * 100
        exp = sum(pl["gst_rate"] * il["amount"] for il, pl, _ in pairs if pl) / max(
            sum(il["amount"] for il, pl, _ in pairs if pl), 1)
        if abs(eff - exp) > 0.5:
            finding(ctx, "GST_RATE_MISMATCH", "hold", "Tax", "GST rate doesn't match the PO",
                    f"Invoice charges {eff:.1f}%, PO items carry {exp:.1f}%.", "Ask the vendor to correct.")
            issues += 1
    facts = [("PO lines", len(pls)), ("Invoice lines", len(inv["lines"])),
             ("Matched", sum(1 for _, pl, _ in pairs if pl))]
    return ("warn" if issues else "ok"), (f"{issues} line problem(s)" if issues else "All lines match the PO and receipts"), facts


# ------------------------------------------------------------------ 8 history
def history(ctx):
    inv, v, s = ctx["inv"], ctx["vendor"], ctx["settings"]
    facts = []
    parent = ctx.get("parent_run") or "__none__"
    same_file = db.q1("SELECT * FROM ledger WHERE file_hash=? AND COALESCE(run_id,'')!=?", (ctx["file_hash"], parent))
    if same_file:
        finding(ctx, "DUPLICATE_FILE", "reject", "AP team", "This exact file was already processed",
                f"Same file as invoice {same_file['invoice_no']} ({same_file['status']}).", "No action, it's a resend.")
    if v and inv["canonical_no"]:
        prior = db.q("SELECT * FROM ledger WHERE vendor_id=? AND canonical_no=? AND COALESCE(run_id,'')!=?",
                     (v["vendor_id"], inv["canonical_no"], parent))
        for p in prior:
            if same_file and p["id"] == same_file["id"]:
                continue
            when = f", paid on {parse_date(p['paid_on']):%d %b %Y}" if p.get("paid_on") else ""
            if inv["total"] is not None and abs(p["total"] - inv["total"]) <= 1:
                finding(ctx, "DUPLICATE_INVOICE", "reject", "AP team", f"Duplicate of {p['invoice_no']}, already {p['status']}",
                        f"'{inv['invoice_no']}' and '{p['invoice_no']}' are the same number once separators and leading "
                        f"zeros are ignored. Same vendor, same amount ({fmt_inr(p['total'])}), dated "
                        f"{parse_date(p['invoice_date']):%d %b %Y}{when}.",
                        "Don't pay. Tell the vendor it was already settled.")
            else:
                finding(ctx, "REUSED_NUMBER", "hold", "AP team", f"Invoice number already used on {p['invoice_no']}",
                        f"Same vendor and number, but a different amount ({fmt_inr(p['total'])} before, "
                        f"{fmt_inr(inv['total'])} now).", "Ask the vendor whether this is a revised invoice or a new one.")
        if inv["total"] is not None and inv["date"]:
            lo = (inv["date"] - timedelta(days=s["duplicate_window_days"])).isoformat()
            hi = (inv["date"] + timedelta(days=s["duplicate_window_days"])).isoformat()
            near = db.q("SELECT * FROM ledger WHERE vendor_id=? AND ABS(total-?)<=1 AND invoice_date BETWEEN ? AND ? "
                        "AND canonical_no!=? AND COALESCE(run_id,'')!=?",
                        (v["vendor_id"], inv["total"], lo, hi, inv["canonical_no"], parent))
            for p in near:
                finding(ctx, "POSSIBLE_DUPLICATE", "hold", "AP team", f"Same amount as {p['invoice_no']} within {s['duplicate_window_days']} days",
                        f"{p['invoice_no']} dated {parse_date(p['invoice_date']):%d %b %Y} was also {fmt_inr(p['total'])}. "
                        "Different number, so it may be a genuine repeat order.", "Check against the GRN before paying.")
        n_prev = db.q1("SELECT COUNT(*) n FROM ledger WHERE vendor_id=?", (v["vendor_id"],))["n"]
        facts.append(("Earlier invoices from vendor", n_prev))

    po = ctx.get("po")
    if po:
        prev_val, prev_rows = po_billed_value(po["po_no"], parent)
        balance = po["taxable_value"] - prev_val
        after = balance - (inv["taxable"] or 0)
        ctx["po_balance"] = {"po_no": po["po_no"], "value": po["taxable_value"], "billed_before": prev_val,
                             "this_invoice": inv["taxable"] or 0, "remaining_after": after}
        facts += [("PO value", fmt_inr(po["taxable_value"])),
                  ("Billed before", fmt_inr(prev_val) + (f" ({', '.join(r['invoice_no'] for r in prev_rows)})" if prev_rows else "")),
                  ("This invoice", fmt_inr(inv["taxable"])), ("Left after this", fmt_inr(after))]
        tolerated = ctx.get("tolerated_variance", 0)
        if -after > s["total_rounding"] and -after <= tolerated + s["total_rounding"]:
            facts.append(("Over PO by", f"{fmt_inr(-after)}, all of it the price difference already accepted within tolerance"))
        elif after < -s["total_rounding"]:
            finding(ctx, "OVER_PO_BALANCE", "hold", "Procurement", f"Takes {po['po_no']} over its value by {fmt_inr(-after)}",
                    f"PO {fmt_inr(po['taxable_value'])}; already billed {fmt_inr(prev_val)}; this invoice {fmt_inr(inv['taxable'])}. "
                    f"Billing would reach {(prev_val + (inv['taxable'] or 0)) / po['taxable_value'] * 100:.0f}% of the PO.",
                    "Approve up to the remaining balance or get a PO amendment.")
        held = db.q("SELECT invoice_no FROM ledger WHERE po_no=? AND status='on_hold' AND COALESCE(run_id,'')!=?",
                    (po["po_no"], parent))
        if held:
            facts.append(("Also on hold on this PO", ", ".join(h["invoice_no"] for h in held)))
    n = len([x for x in ctx["findings"] if x["stage"] == "history"])
    return ("warn" if n else "ok"), (f"{n} issue(s) from history" if n else "No duplicates; PO has room"), facts
