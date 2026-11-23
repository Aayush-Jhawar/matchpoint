"""
Runs every demo invoice in order on a fresh database and checks the decision.
    cd backend && python -m pytest -q        (or just: python tests/test_scenarios.py)
Order matters: the ledger carries over between invoices, same as in real life.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("MATCHPOINT_DATA", tempfile.mkdtemp())
os.environ["STAGE_DELAY_MS"] = "0"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, pipeline  # noqa: E402
from app.config import SAMPLES_DIR  # noqa: E402

EXPECTED = [
    ("01_shree_ganesh_SGP-2026-1187.pdf", "AUTO_APPROVE", None),
    ("02_coimbatore_bearings_CBC-1126.pdf", "APPROVE_WITH_NOTE", "PRICE_WITHIN_TOLERANCE"),
    ("03_precision_castings_PC-131.pdf", "HOLD", "QTY_EXCEEDS_RECEIPT"),
    ("04_deccan_fasteners_INV-0442.pdf", "REJECT", "DUPLICATE_INVOICE"),
    ("05_bharat_electricals_BEC-0873.pdf", "HOLD", "BANK_CHANGED"),
    ("06_sai_lubricants_scan.pdf", "HOLD", "LOW_CONFIDENCE"),
    ("07_nexa_safety_NSS-219.pdf", "HOLD", "WRONG_TAX_TYPE"),
]


def run(name, overrides=None, parent=None):
    p = SAMPLES_DIR / name
    rid = pipeline.new_run(name, p, parent)
    pipeline.execute(rid, p.read_bytes(), name, overrides, parent)
    import json
    r = db.q1("SELECT * FROM runs WHERE id=?", (rid,))
    return rid, r, json.loads(r["payload"])


def test_demo_set():
    db.init()
    db.reset(keep_cache=False)
    ids = {}
    for name, decision, code in EXPECTED:
        rid, r, p = run(name)
        ids[name] = rid
        assert r["decision"] == decision, (name, r["headline"])
        if code:
            assert p["result"]["reasons"][0]["code"] == code, (name, p["result"]["reasons"][0])

    # clerk confirms the scanned invoice number -> approved against the inferred PO
    _, r, p = run("06_sai_lubricants_scan.pdf", {"invoice_no": "SIL/583", "invoice_date": "2026-11-14"},
                  ids["06_sai_lubricants_scan.pdf"])
    assert r["decision"] == "APPROVE_WITH_NOTE" and r["po_no"] == "PO-2026-0420"

    # same file again -> caught as a resend
    _, r, _ = run("01_shree_ganesh_SGP-2026-1187.pdf")
    assert r["decision"] == "REJECT"


def test_tighter_tolerance_holds_price():
    db.reset(keep_cache=True)
    db.save_settings({"price_tolerance_pct": 1.0})
    _, r, p = run("02_coimbatore_bearings_CBC-1126.pdf")
    assert r["decision"] == "HOLD" and p["result"]["reasons"][0]["code"] == "PRICE_OVER_TOLERANCE"
    db.reset(keep_cache=True)


if __name__ == "__main__":
    test_demo_set()
    test_tighter_tolerance_holds_price()
    print("all scenarios behave as expected")
