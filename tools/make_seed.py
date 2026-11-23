import csv
from pathlib import Path

from dataset import BUYER, GRNS, LEDGER, PURCHASE_ORDERS, VENDORS, po_by_id

OUT = Path(__file__).resolve().parents[1] / "backend" / "seed"
OUT.mkdir(parents=True, exist_ok=True)


def write(name, rows, cols):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})


write("buyer.csv", [BUYER], ["name", "address", "gstin"])
write("vendors.csv", VENDORS,
      ["vendor_id", "name", "address", "state", "pan", "gstin", "bank_name", "account_no", "ifsc", "status",
       "phone", "email"])

pos, lines = [], []
for po_id, vid, date, status, ls in PURCHASE_ORDERS:
    pos.append({"po_no": po_id, "vendor_id": vid, "po_date": date, "status": status,
                "taxable_value": round(sum(q * r for _, _, _, q, _, r, _ in ls), 2)})
    for ln, item, hsn, q, unit, rate, gst in ls:
        lines.append({"po_no": po_id, "line_no": ln, "item": item, "hsn": hsn, "qty": q,
                      "unit": unit, "rate": rate, "gst_rate": gst})
write("purchase_orders.csv", pos, ["po_no", "vendor_id", "po_date", "status", "taxable_value"])
write("po_lines.csv", lines, ["po_no", "line_no", "item", "hsn", "qty", "unit", "rate", "gst_rate"])

write("grn.csv", [{"grn_no": g, "po_no": p, "line_no": l, "qty_received": q, "grn_date": d}
                  for g, p, l, q, d in GRNS],
      ["grn_no", "po_no", "line_no", "qty_received", "grn_date"])

led, led_lines = [], []
for inv in LEDGER:
    po = po_by_id(inv["po"])
    gst = {ln: g for ln, _, _, _, _, _, g in po[4]}
    taxable = round(sum(q * r for _, q, r in inv["lines"]), 2)
    tax = round(sum(q * r * gst[ln] / 100 for ln, q, r in inv["lines"]), 2)
    led.append({"invoice_no": inv["invoice_no"], "vendor_id": inv["vendor_id"], "po_no": inv["po"],
                "invoice_date": inv["date"], "taxable_value": taxable, "tax": tax,
                "total": round(taxable + tax, 2), "status": inv["status"], "paid_on": inv["paid_on"]})
    for ln, q, r in inv["lines"]:
        led_lines.append({"invoice_no": inv["invoice_no"], "po_no": inv["po"], "line_no": ln, "qty": q, "rate": r})
write("invoice_ledger.csv", led,
      ["invoice_no", "vendor_id", "po_no", "invoice_date", "taxable_value", "tax", "total", "status", "paid_on"])
write("invoice_ledger_lines.csv", led_lines, ["invoice_no", "po_no", "line_no", "qty", "rate"])
print("seed written to", OUT)
