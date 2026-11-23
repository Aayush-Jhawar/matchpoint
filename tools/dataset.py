"""
Master data for the demo company (Kaveri Auto Components) and the invoices
used in the demo. make_seed.py writes the CSVs, make_invoices.py draws the PDFs.
All names, GSTINs and account numbers are made up.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.gstin import make_gstin  # noqa: E402

BUYER = {
    "name": "Kaveri Auto Components Pvt. Ltd.",
    "address": "Plot B-14, MIDC Phase II, Chakan, Pune 410501, Maharashtra",
    "gstin": make_gstin("27", "AAECK4417M"),
}

# id, name, city/address, state code, PAN, bank name, account, IFSC
_V = [
    ("V001", "Shree Ganesh Packaging Pvt. Ltd.", "Gat No. 212, Bhosari MIDC, Pune 411026", "27", "AAMCS2281K",
     "HDFC Bank, Bhosari", "50200041127783", "HDFC0001342"),
    ("V002", "Deccan Fasteners & Tools", "Shop 7, Sector 10, Pimpri, Pune 411018", "27", "AAHFD6619Q",
     "State Bank of India, Pimpri", "39912047761", "SBIN0011524"),
    ("V003", "Precision Castings India Pvt. Ltd.", "Survey 88, Shapar Industrial Area, Rajkot 360024", "24", "AAKCP3305R",
     "ICICI Bank, Rajkot", "024105008831", "ICIC0000241"),
    ("V004", "Sai Industrial Lubricants", "B-41, Ambad MIDC, Nashik 422010", "27", "ABRPS7712H",
     "Bank of Maharashtra, Ambad", "60118842207", "MAHB0000415"),
    ("V005", "Bharat Electricals & Controls Pvt. Ltd.", "No. 56, 3rd Phase, Peenya Industrial Area, Bengaluru 560058", "29",
     "AACCB9021L", "Canara Bank, Peenya", "0412201008836", "CNRB0000412"),
    ("V006", "Coimbatore Bearings Co.", "14/3 Avinashi Road, Peelamedu, Coimbatore 641004", "33", "AAFFC4458D",
     "Indian Overseas Bank, Peelamedu", "117702000004519", "IOBA0001177"),
    ("V007", "Nexa Safety Solutions LLP", "Unit 302, Wagle Estate, Thane 400604", "27", "AAUFN1186B",
     "Axis Bank, Wagle Estate", "921020038814472", "UTIB0001884"),
    ("V008", "Vardhman Steel Traders", "G.T. Road, Focal Point, Ludhiana 141010", "03", "AAGFV5530C",
     "Punjab National Bank, Focal Point", "0611002100023391", "PUNB0061100"),
]

VENDORS = []
for vid, name, addr, st, pan, bank, acct, ifsc in _V:
    VENDORS.append({
        "vendor_id": vid, "name": name, "address": addr, "state": st, "pan": pan,
        "gstin": make_gstin(st, pan), "bank_name": bank, "account_no": acct, "ifsc": ifsc,
        "status": "active",
    })
V = {v["vendor_id"]: v for v in VENDORS}

# POs: amounts are taxable value. lines = (line_no, item, hsn, qty, unit, rate, gst%)
PURCHASE_ORDERS = [
    ("PO-2026-0412", "V001", "2026-10-29", "open", [
        (1, "Corrugated box 5-ply 600x400x400 mm", "4819", 1200, "nos", 48.50, 18),
        (2, "PP strapping roll 12 mm", "3920", 40, "roll", 610.00, 18),
    ]),
    ("PO-2026-0405", "V006", "2026-10-24", "open", [
        (1, "Deep groove ball bearing 6205-2RS", "8482", 500, "nos", 186.00, 18),
        (2, "Taper roller bearing 30206", "8482", 200, "nos", 412.00, 18),
    ]),
    ("PO-2026-0398", "V003", "2026-10-06", "open", [
        (1, "CI pump housing, machined (drg PH-220 rev C)", "8413", 400, "nos", 1250.00, 18),
    ]),
    ("PO-2026-0377", "V002", "2026-10-14", "open", [
        (1, "Hex bolt M10x40 gr 8.8 zinc plated", "7318", 5000, "nos", 6.40, 18),
        (2, "Nylock nut M10", "7318", 5000, "nos", 2.10, 18),
        (3, "Plain washer M10", "7318", 5000, "nos", 0.85, 18),
    ]),
    ("PO-2026-0409", "V005", "2026-10-27", "open", [
        (1, "MCB 32A 4-pole C-curve", "8536", 60, "nos", 1840.00, 18),
        (2, "Power contactor 25A 415V", "8536", 40, "nos", 2275.00, 18),
        (3, "Control cable 1.5 sqmm 4C (100 m roll)", "8544", 12, "roll", 6350.00, 18),
    ]),
    ("PO-2026-0420", "V004", "2026-11-02", "open", [
        (1, "Hydraulic oil ISO VG 68 (20 L)", "2710", 30, "can", 3150.00, 18),
        (2, "Soluble cutting fluid (20 L)", "3403", 20, "can", 2480.00, 18),
    ]),
    ("PO-2026-0416", "V004", "2026-10-31", "open", [
        (1, "Lithium grease EP2 (18 kg bucket)", "3403", 25, "bucket", 4120.00, 18),
    ]),
    ("PO-2026-0414", "V007", "2026-10-30", "open", [
        (1, "Safety shoes, steel toe (pair)", "6403", 150, "pair", 1180.00, 18),
        (2, "Cut-resistant gloves level 5 (pair)", "6116", 300, "pair", 145.00, 18),
    ]),
    # older, already closed
    ("PO-2026-0341", "V001", "2026-09-12", "closed", [
        (1, "Corrugated box 3-ply 400x300x300 mm", "4819", 2000, "nos", 22.00, 18),
    ]),
    ("PO-2026-0352", "V006", "2026-09-18", "closed", [
        (1, "Deep groove ball bearing 6204-2RS", "8482", 300, "nos", 152.00, 18),
    ]),
]

# (grn_no, po, line_no, qty_received, date)
GRNS = [
    ("GRN-26-1561", "PO-2026-0412", 1, 1200, "2026-11-10"),
    ("GRN-26-1561", "PO-2026-0412", 2, 40, "2026-11-10"),
    ("GRN-26-1544", "PO-2026-0405", 1, 500, "2026-11-07"),
    ("GRN-26-1544", "PO-2026-0405", 2, 200, "2026-11-07"),
    ("GRN-26-1488", "PO-2026-0398", 1, 240, "2026-10-20"),
    ("GRN-26-1552", "PO-2026-0398", 1, 160, "2026-11-09"),
    ("GRN-26-1497", "PO-2026-0377", 1, 5000, "2026-10-26"),
    ("GRN-26-1497", "PO-2026-0377", 2, 5000, "2026-10-26"),
    ("GRN-26-1497", "PO-2026-0377", 3, 5000, "2026-10-26"),
    ("GRN-26-1549", "PO-2026-0409", 1, 60, "2026-11-08"),
    ("GRN-26-1549", "PO-2026-0409", 2, 40, "2026-11-08"),
    ("GRN-26-1549", "PO-2026-0409", 3, 12, "2026-11-08"),
    ("GRN-26-1570", "PO-2026-0420", 1, 30, "2026-11-12"),
    ("GRN-26-1570", "PO-2026-0420", 2, 20, "2026-11-12"),
    ("GRN-26-1558", "PO-2026-0414", 1, 150, "2026-11-09"),
    ("GRN-26-1558", "PO-2026-0414", 2, 300, "2026-11-09"),
    ("GRN-26-1302", "PO-2026-0341", 1, 2000, "2026-09-20"),
    ("GRN-26-1355", "PO-2026-0352", 1, 300, "2026-09-25"),
]

# invoices already in the books. lines = [(po_line, qty, rate)]
LEDGER = [
    {"invoice_no": "SGP/2026/0964", "vendor_id": "V001", "po": "PO-2026-0341", "date": "2026-09-22",
     "lines": [(1, 2000, 22.00)], "status": "paid", "paid_on": "2026-10-21"},
    {"invoice_no": "CBC/0981/26-27", "vendor_id": "V006", "po": "PO-2026-0352", "date": "2026-09-27",
     "lines": [(1, 300, 152.00)], "status": "paid", "paid_on": "2026-10-27"},
    {"invoice_no": "PC/26-27/118", "vendor_id": "V003", "po": "PO-2026-0398", "date": "2026-10-22",
     "lines": [(1, 240, 1250.00)], "status": "paid", "paid_on": "2026-11-12"},
    {"invoice_no": "INV-0442", "vendor_id": "V002", "po": "PO-2026-0377", "date": "2026-10-28",
     "lines": [(1, 5000, 6.40), (2, 5000, 2.10), (3, 5000, 0.85)], "status": "paid", "paid_on": "2026-11-03"},
]


def po_by_id(po_id):
    for p in PURCHASE_ORDERS:
        if p[0] == po_id:
            return p
    raise KeyError(po_id)


# ---- the demo invoices ------------------------------------------------------
# lines: (description, hsn, qty, unit, rate). tax_mode: "intra" (CGST+SGST) or "inter" (IGST)
INVOICES = [
    {"file": "01_shree_ganesh_SGP-2026-1187.pdf", "layout": "boxed", "vendor": "V001",
     "invoice_no": "SGP/2026/1187", "date": "2026-11-12", "po": "PO-2026-0412", "tax_mode": "intra",
     "lines": [("Corrugated Box 5 Ply 600x400x400mm", "4819", 1200, "Nos", 48.50),
               ("PP Strapping Roll 12mm", "3920", 40, "Roll", 610.00)]},

    {"file": "02_coimbatore_bearings_CBC-1126.pdf", "layout": "linetax", "vendor": "V006",
     "invoice_no": "CBC/1126/26-27", "date": "2026-11-10", "po": "PO-2026-0405", "tax_mode": "inter",
     "lines": [("Ball Bearing 6205 2RS", "8482", 500, "Nos", 188.25),
               ("Taper Roller Brg 30206", "8482", 200, "Nos", 412.00)]},

    {"file": "03_precision_castings_PC-131.pdf", "layout": "tally", "vendor": "V003",
     "invoice_no": "PC/26-27/131", "date": "2026-11-13", "po": "PO-2026-0398", "tax_mode": "inter",
     "lines": [("C.I. Pump Housing Machined - Drg PH-220 Rev C", "8413", 192, "Nos", 1250.00)]},

    {"file": "04_deccan_fasteners_INV-0442.pdf", "layout": "minimal", "vendor": "V002",
     "invoice_no": "INV/0442", "date": "2026-10-28", "po": "PO-2026-0377", "tax_mode": "intra",
     "lines": [("Hex Bolt M10 x 40 Gr 8.8 ZP", "7318", 5000, "Nos", 6.40),
               ("Nylock Nut M10", "7318", 5000, "Nos", 2.10),
               ("Plain Washer M10", "7318", 5000, "Nos", 0.85)]},

    {"file": "05_bharat_electricals_BEC-0873.pdf", "layout": "minimal", "vendor": "V005",
     "invoice_no": "BEC/2026-27/0873", "date": "2026-11-11", "po": "PO-2026-0409", "tax_mode": "inter",
     "bank_override": ("YES Bank, Koramangala", "077910020001882", "YESB0000779"),
     "note": "Please note: our bank account has changed w.e.f. 01-Nov-2026. Kindly remit to the account below.",
     "lines": [("MCB 32A 4P C Curve", "8536", 60, "Nos", 1840.00),
               ("Power Contactor 25A 415V AC", "8536", 40, "Nos", 2275.00),
               ("Control Cable 1.5 sq mm 4 Core - 100 m", "8544", 12, "Roll", 6350.00)]},

    {"file": "06_sai_lubricants_scan.pdf", "layout": "tally", "vendor": "V004", "scan": True,
     "invoice_no": "SIL/583", "date": "2026-11-14", "po": None, "tax_mode": "intra",
     "lines": [("Hydraulic Oil ISO VG 68 - 20 Ltr", "2710", 30, "Can", 3150.00),
               ("Soluble Cutting Oil - 20 Ltr", "3403", 20, "Can", 2480.00)]},

    {"file": "07_nexa_safety_NSS-219.pdf", "layout": "boxed", "vendor": "V007",
     "invoice_no": "NSS/2026/219", "date": "2026-11-12", "po": "PO-2026-0414", "tax_mode": "inter",
     "lines": [("Safety Shoes Steel Toe", "6403", 150, "Pair", 1180.00),
               ("Cut Resistant Gloves Level 5", "6116", 300, "Pair", 145.00)]},
]
