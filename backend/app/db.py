import csv
import json
import sqlite3
import threading

from .config import DB_PATH, DEFAULT_SETTINGS, SEED_DIR

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS buyer (name TEXT, address TEXT, gstin TEXT);
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id TEXT PRIMARY KEY, name TEXT, address TEXT, state TEXT, pan TEXT, gstin TEXT,
    bank_name TEXT, account_no TEXT, ifsc TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_no TEXT PRIMARY KEY, vendor_id TEXT, po_date TEXT, status TEXT, taxable_value REAL);
CREATE TABLE IF NOT EXISTS po_lines (
    po_no TEXT, line_no INTEGER, item TEXT, hsn TEXT, qty REAL, unit TEXT, rate REAL, gst_rate REAL);
CREATE TABLE IF NOT EXISTS grn (grn_no TEXT, po_no TEXT, line_no INTEGER, qty_received REAL, grn_date TEXT);
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT, canonical_no TEXT, vendor_id TEXT, po_no TEXT,
    invoice_date TEXT, taxable_value REAL, tax REAL, total REAL, status TEXT, paid_on TEXT,
    file_hash TEXT, run_id TEXT);
CREATE TABLE IF NOT EXISTS ledger_lines (ledger_id INTEGER, po_no TEXT, line_no INTEGER, qty REAL, rate REAL);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, created_at TEXT, finished_at TEXT, file_name TEXT, file_path TEXT, file_hash TEXT,
    state TEXT, decision TEXT, owner TEXT, headline TEXT, vendor_name TEXT, invoice_no TEXT, po_no TEXT,
    total REAL, method TEXT, duration_ms INTEGER, parent_run TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS run_events (run_id TEXT, seq INTEGER, stage TEXT, status TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS extraction_cache (file_hash TEXT PRIMARY KEY, method TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def q(sql, args=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def q1(sql, args=()):
    rows = q(sql, args)
    return rows[0] if rows else None


def ex(sql, args=()):
    with _lock, conn() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid


def _load_csv(c, table, fname):
    with open(SEED_DIR / fname, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return rows
    cols = list(rows[0].keys())
    c.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                  [[r[k] for k in cols] for r in rows])
    return rows


def reset(keep_cache=True):
    """Drop everything except the extraction cache and load the seed CSVs again."""
    from .normalize import canonical_invoice_no
    with _lock, conn() as c:
        c.executescript(SCHEMA)
        for t in ["buyer", "vendors", "purchase_orders", "po_lines", "grn", "ledger", "ledger_lines",
                  "runs", "run_events", "settings"] + ([] if keep_cache else ["extraction_cache"]):
            c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM sqlite_sequence WHERE name='ledger'") if c.execute(
            "SELECT name FROM sqlite_master WHERE name='sqlite_sequence'").fetchone() else None
        for t, f in [("buyer", "buyer.csv"), ("vendors", "vendors.csv"), ("purchase_orders", "purchase_orders.csv"),
                     ("po_lines", "po_lines.csv"), ("grn", "grn.csv")]:
            _load_csv(c, t, f)
        with open(SEED_DIR / "invoice_ledger.csv", encoding="utf-8") as f:
            inv = list(csv.DictReader(f))
        with open(SEED_DIR / "invoice_ledger_lines.csv", encoding="utf-8") as f:
            lines = list(csv.DictReader(f))
        for r in inv:
            cur = c.execute(
                "INSERT INTO ledger (invoice_no, canonical_no, vendor_id, po_no, invoice_date, taxable_value, tax,"
                " total, status, paid_on) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["invoice_no"], canonical_invoice_no(r["invoice_no"]), r["vendor_id"], r["po_no"],
                 r["invoice_date"], float(r["taxable_value"]), float(r["tax"]), float(r["total"]),
                 r["status"], r["paid_on"]))
            for l in lines:
                if l["invoice_no"] == r["invoice_no"]:
                    c.execute("INSERT INTO ledger_lines VALUES (?,?,?,?,?)",
                              (cur.lastrowid, l["po_no"], int(l["line_no"]), float(l["qty"]), float(l["rate"])))
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT INTO settings VALUES (?,?)", (k, json.dumps(v)))


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        empty = c.execute("SELECT COUNT(*) FROM vendors").fetchone()[0] == 0
    if empty:
        reset()


def get_settings():
    s = dict(DEFAULT_SETTINGS)
    for r in q("SELECT key, value FROM settings"):
        s[r["key"]] = json.loads(r["value"])
    return s


def save_settings(new):
    for k, v in new.items():
        if k in DEFAULT_SETTINGS:
            ex("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, json.dumps(type(DEFAULT_SETTINGS[k])(v))))


def buyer():
    return q1("SELECT * FROM buyer")
