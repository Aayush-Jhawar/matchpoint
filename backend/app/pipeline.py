import json
import time
import traceback
import uuid
from datetime import datetime, timezone

from . import checks, config, db, rules
from .normalize import fmt_inr

STAGES = [
    ("intake", "Intake", checks.intake),
    ("extract", "Extract fields", checks.extract),
    ("normalise", "Normalise", checks.normalise),
    ("validate", "Validate document", checks.validate),
    ("vendor", "Match vendor", checks.vendor),
    ("po", "Find PO", checks.match_po),
    ("lines", "Match lines to PO & GRN", checks.match_lines),
    ("history", "Check history", checks.history),
    ("decide", "Decide", None),
    ("record", "Record", None),
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run(file_name, file_path, parent_run=None):
    run_id = datetime.now().strftime("%y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    db.ex("INSERT INTO runs (id, created_at, file_name, file_path, state, parent_run) VALUES (?,?,?,?,?,?)",
          (run_id, now(), file_name, str(file_path), "running", parent_run))
    return run_id


def _event(run_id, seq, stage, status, data):
    db.ex("INSERT INTO run_events VALUES (?,?,?,?,?)", (run_id, seq, stage, status, json.dumps(data, default=str)))


def _record(ctx, result):
    """Write approved and held invoices into the ledger so the next invoice sees them."""
    inv, v, po = ctx.get("inv"), ctx.get("vendor"), ctx.get("po")
    parent = ctx.get("parent_run")
    if parent:
        # a re-run replaces whatever the earlier run had booked
        for row in db.q("SELECT id FROM ledger WHERE run_id=?", (parent,)):
            db.ex("DELETE FROM ledger_lines WHERE ledger_id=?", (row["id"],))
            db.ex("DELETE FROM ledger WHERE id=?", (row["id"],))
    d = result["decision"]
    if d == "REJECT":
        return "skip", "Not booked: rejected invoices stay out of the ledger", []
    if not v or not inv:
        return "skip", "Not booked: unknown vendor", []
    status = "approved" if d in ("AUTO_APPROVE", "APPROVE_WITH_NOTE") else "on_hold"
    lid = db.ex("INSERT INTO ledger (invoice_no, canonical_no, vendor_id, po_no, invoice_date, taxable_value, tax, total,"
                " status, file_hash, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (inv["invoice_no"], inv["canonical_no"], v["vendor_id"], po["po_no"] if po else None,
                 inv["date"].isoformat() if inv["date"] else None, inv["taxable"] or 0, inv["tax"], inv["total"] or 0,
                 status, ctx["file_hash"], ctx["run_id"]))
    for il, pl, _ in ctx.get("line_pairs", []):
        if pl:
            db.ex("INSERT INTO ledger_lines VALUES (?,?,?,?,?)", (lid, po["po_no"], pl["line_no"], il["qty"], il["rate"]))
    facts = [("Ledger status", status)]
    if po and status == "approved":
        used = db.q1("SELECT SUM(taxable_value) s FROM ledger WHERE po_no=? AND status IN ('paid','approved')",
                     (po["po_no"],))["s"] or 0
        facts.append((po["po_no"], f"{used / po['taxable_value'] * 100:.0f}% billed after this invoice"))
    return "ok", f"Booked as {status.replace('_', ' ')}", facts


def execute(run_id, data, file_name, overrides=None, parent_run=None):
    t0 = time.time()
    ctx = {"run_id": run_id, "data": data, "file_name": file_name, "settings": db.get_settings(),
           "findings": [], "overrides": overrides or {}, "parent_run": parent_run}
    stages_out, seq = [], 0
    result = None
    try:
        for key, label, fn in STAGES:
            ctx["_stage"] = key
            seq += 1
            _event(run_id, seq, key, "running", {"label": label})
            ts = time.time()
            if key == "decide":
                result = rules.decide(ctx["findings"], ctx)
                result["vendor_message"] = rules.vendor_message(result, ctx)
                status = {"AUTO_APPROVE": "ok", "APPROVE_WITH_NOTE": "ok", "HOLD": "warn", "REJECT": "fail"}[result["decision"]]
                summary = f"{result['label']}: {result['headline']}"
                facts = [("Decision", result["label"]), ("Owner", result["owner"]),
                         ("Findings", f"{sum(1 for f in ctx['findings'] if f['level'] != 'note')} blocking, "
                                      f"{sum(1 for f in ctx['findings'] if f['level'] == 'note')} notes")]
            elif key == "record":
                status, summary, facts = _record(ctx, result)
            elif ctx.get("unreadable") and key != "intake":
                status, summary, facts = "skip", "Skipped: file could not be opened", []
            else:
                status, summary, facts = fn(ctx)
            ms = int((time.time() - ts) * 1000)
            if config.STAGE_DELAY_MS:
                time.sleep(config.STAGE_DELAY_MS / 1000)
            stage = {"key": key, "label": label, "status": status, "summary": summary,
                     "facts": [[str(a), str(b)] for a, b in facts], "ms": ms,
                     "findings": [f for f in ctx["findings"] if f["stage"] == key]}
            stages_out.append(stage)
            seq += 1
            _event(run_id, seq, key, "done", stage)
    except Exception as e:
        traceback.print_exc()
        seq += 1
        _event(run_id, seq, ctx.get("_stage", "?"), "error", {"error": f"{type(e).__name__}: {e}"})
        db.ex("UPDATE runs SET state='error', finished_at=?, headline=? WHERE id=?",
              (now(), f"Pipeline error: {type(e).__name__}: {e}", run_id))
        return

    inv = ctx.get("inv") or {}
    v = ctx.get("vendor")
    po = ctx.get("po")
    payload = {
        "result": result, "stages": stages_out, "extraction": ctx.get("ext"), "method": ctx.get("method"),
        "line_table": ctx.get("line_table", []), "po_balance": ctx.get("po_balance"),
        "po_candidates": ctx.get("po_candidates"), "needs_confirmation": ctx.get("needs_confirmation", []),
        "invoice": {k: (inv.get(k).isoformat() if k == "date" and inv.get(k) else inv.get(k))
                    for k in ("vendor_name", "gstin", "invoice_no", "canonical_no", "date", "po_ref", "taxable", "cgst",
                              "sgst", "igst", "tax", "total", "bank_account", "ifsc", "tax_type")},
        "vendor": v, "overrides": overrides or {},
    }
    db.ex("UPDATE runs SET state='done', finished_at=?, file_hash=?, decision=?, owner=?, headline=?, vendor_name=?,"
          " invoice_no=?, po_no=?, total=?, method=?, duration_ms=?, payload=? WHERE id=?",
          (now(), ctx.get("file_hash"), result["decision"], result["owner"], result["headline"],
           v["name"] if v else inv.get("vendor_name"), inv.get("invoice_no"), po["po_no"] if po else None,
           inv.get("total"), ctx.get("method"),
           max(0, int((time.time() - t0) * 1000) - config.STAGE_DELAY_MS * len(STAGES)), json.dumps(payload, default=str), run_id))


def summary_line(run):
    return f"{run['invoice_no'] or '?'} from {run['vendor_name'] or '?'} for {fmt_inr(run['total'])}: {run['decision']}"
