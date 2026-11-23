"""
Draws the demo invoices. Four layouts on purpose, because vendors never agree
on where anything goes:
  boxed   - classic GST tax invoice with ruled boxes
  minimal - modern 'INVOICE' style, few lines, labels in small caps
  tally   - the Tally ERP print most Indian SMEs send
  linetax - tax broken out per line instead of at the bottom
The scanned one is rendered, tilted, noised and saved back as an image-only PDF.
"""
import io
import random
from datetime import date
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from dataset import BUYER, INVOICES, V

OUT = Path(__file__).resolve().parents[1] / "samples"
OUT.mkdir(exist_ok=True)
W, H = A4


def inr(x):
    """Indian digit grouping: 240000 -> 2,40,000.00"""
    neg = x < 0
    s = f"{abs(x):.2f}"
    whole, dec = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + whole + "." + dec


ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
        "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _words(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return (TENS[n // 10] + " " + ONES[n % 10]).strip()
    if n < 1000:
        return (ONES[n // 100] + " Hundred " + _words(n % 100)).strip()
    for div, name in ((10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand")):
        if n >= div:
            return (_words(n // div) + f" {name} " + _words(n % div)).strip()


def in_words(amount):
    return "INR " + _words(int(round(amount))) + " Only"


def compute(inv):
    rows = []
    for desc, hsn, q, unit, rate in inv["lines"]:
        amt = round(q * rate, 2)
        rows.append({"desc": desc, "hsn": hsn, "qty": q, "unit": unit, "rate": rate, "amt": amt})
    taxable = round(sum(r["amt"] for r in rows), 2)
    if inv["tax_mode"] == "intra":
        taxes = [("CGST @ 9%", round(taxable * 0.09, 2)), ("SGST @ 9%", round(taxable * 0.09, 2))]
    else:
        taxes = [("IGST @ 18%", round(taxable * 0.18, 2))]
    gross = taxable + sum(t for _, t in taxes)
    return rows, taxable, taxes, round(gross, 2)


def fmt_date(iso, style):
    d = date.fromisoformat(iso)
    return {
        "dmy-": d.strftime("%d-%b-%Y"),
        "mdy": d.strftime("%b %d, %Y"),
        "dmy/": d.strftime("%d/%m/%Y"),
        "dmy.": d.strftime("%d.%m.%Y"),
    }[style]


def split_addr(s, n=50):
    cut = s.rfind(",", 0, n)
    return (s[:cut + 1], s[cut + 1:].strip()) if cut > 0 and len(s) > n else (s, "")


def bank_of(inv, v):
    return inv.get("bank_override") or (v["bank_name"], v["account_no"], v["ifsc"])


# ---------------------------------------------------------------- boxed
def draw_boxed(c, inv):
    v = V[inv["vendor"]]
    rows, taxable, taxes, total = compute(inv)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(W / 2, H - 40, "TAX INVOICE")
    c.setFont("Helvetica", 7)
    c.drawRightString(W - 36, H - 40, "ORIGINAL FOR RECIPIENT")

    top = H - 52
    c.rect(36, top - 92, W / 2 - 36, 92)
    c.rect(W / 2, top - 92, W / 2 - 36, 92)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, top - 16, v["name"])
    c.setFont("Helvetica", 8)
    y = top - 30
    for line in [v["address"], f"GSTIN: {v['gstin']}", f"PAN: {v['pan']}", "Email: accounts@" +
                 v["name"].split()[0].lower() + ".in"]:
        c.drawString(42, y, line)
        y -= 12
    c.setFont("Helvetica", 9)
    y = top - 18
    for k, val in [("Invoice No:", inv["invoice_no"]), ("Invoice Date:", fmt_date(inv["date"], "dmy-")),
                   ("PO No:", inv["po"] or ""), ("Place of Supply:", "Maharashtra (27)")]:
        c.drawString(W / 2 + 8, y, k)
        c.drawString(W / 2 + 95, y, val)
        y -= 16

    btop = top - 92
    c.rect(36, btop - 58, W - 72, 58)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(42, btop - 12, "Bill To:")
    c.setFont("Helvetica", 8)
    c.drawString(42, btop - 24, BUYER["name"])
    c.drawString(42, btop - 35, BUYER["address"])
    c.drawString(42, btop - 46, f"GSTIN: {BUYER['gstin']}")

    cols = [36, 62, 270, 320, 370, 410, 480, W - 36]
    heads = ["Sr", "Description of Goods", "HSN", "Qty", "Unit", "Rate", "Amount"]
    ttop = btop - 58
    c.rect(36, ttop - 18, W - 72, 18)
    c.setFont("Helvetica-Bold", 8)
    for x, h in zip(cols, heads):
        c.drawString(x + 4, ttop - 12, h)
    y = ttop - 18
    c.setFont("Helvetica", 8)
    for i, r in enumerate(rows, 1):
        y -= 18
        vals = [str(i), r["desc"], r["hsn"], f"{r['qty']:,}", r["unit"], inr(r["rate"]), inr(r["amt"])]
        for j, (x, val) in enumerate(zip(cols, vals)):
            if j >= 5 or j == 3:
                c.drawRightString(cols[j + 1] - 4, y + 6, val)
            else:
                c.drawString(x + 4, y + 6, val)
    body_bottom = y - 60
    c.rect(36, body_bottom, W - 72, ttop - 18 - body_bottom)
    for x in cols[1:-1]:
        c.line(x, ttop, x, body_bottom)

    y = body_bottom - 16
    c.setFont("Helvetica", 9)
    for k, val in [("Taxable Value", taxable)] + taxes:
        c.drawString(380, y, k)
        c.drawRightString(W - 40, y, inr(val))
        y -= 14
    c.setFont("Helvetica-Bold", 10)
    c.line(380, y + 8, W - 36, y + 8)
    c.drawString(380, y - 4, "Grand Total")
    c.drawRightString(W - 40, y - 4, inr(total))

    bank = bank_of(inv, v)
    c.rect(36, body_bottom - 92, 300, 76)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(42, body_bottom - 30, "Bank Details")
    c.setFont("Helvetica", 8)
    c.drawString(42, body_bottom - 44, f"Bank Name: {bank[0]}")
    c.drawString(42, body_bottom - 56, f"A/c No: {bank[1]}")
    c.drawString(42, body_bottom - 68, f"IFSC: {bank[2]}")
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 40, 110, f"For {v['name']}")
    c.drawRightString(W - 40, 70, "Authorised Signatory")
    c.setFont("Helvetica", 6.5)
    c.drawString(36, 50, "Subject to Pune jurisdiction. Interest @18% p.a. will be charged on payments delayed beyond 30 days.")


# ---------------------------------------------------------------- minimal
def draw_minimal(c, inv):
    v = V[inv["vendor"]]
    rows, taxable, taxes, total = compute(inv)
    c.setFillColorRGB(0.12, 0.2, 0.32)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(40, H - 56, v["name"])
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setFont("Helvetica", 8)
    c.drawString(40, H - 70, v["address"])
    c.drawString(40, H - 81, f"GSTIN {v['gstin']}  |  PAN {v['pan']}")
    c.setFillColorRGB(0.12, 0.2, 0.32)
    c.setFont("Helvetica", 26)
    c.drawRightString(W - 40, H - 60, "INVOICE")

    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.setFont("Helvetica", 7)
    y0 = H - 125
    c.drawString(40, y0, "BILL TO")
    for i, k in enumerate(["INVOICE #", "DATE", "YOUR PO"]):
        c.drawString(360, y0 - i * 16, k)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    c.drawString(40, y0 - 13, BUYER["name"])
    c.setFont("Helvetica", 8)
    c.drawString(40, y0 - 25, split_addr(BUYER["address"], 52)[0])
    c.drawString(40, y0 - 36, split_addr(BUYER["address"], 52)[1])
    c.drawString(40, y0 - 47, f"GSTIN {BUYER['gstin']}")
    c.setFont("Helvetica", 9)
    for i, val in enumerate([inv["invoice_no"], fmt_date(inv["date"], "mdy"), inv["po"] or "-"]):
        c.drawString(430, y0 - i * 16, val)

    y = y0 - 85
    c.setStrokeColorRGB(0.12, 0.2, 0.32)
    c.setLineWidth(1.2)
    c.line(40, y, W - 40, y)
    c.setFont("Helvetica-Bold", 8)
    xs = [40, 300, 350, 410, 480]
    for x, h, right in zip(xs, ["Item", "HSN", "Qty", "Unit price", "Amount"], [0, 0, 1, 1, 1]):
        if right:
            c.drawRightString(x + 60 if x < 480 else W - 40, y - 13, h)
        else:
            c.drawString(x, y - 13, h)
    y -= 20
    c.setLineWidth(0.3)
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setFont("Helvetica", 9)
    for r in rows:
        y -= 18
        c.drawString(40, y, r["desc"])
        c.drawString(300, y, r["hsn"])
        c.drawRightString(410, y, f"{r['qty']:,}")
        c.drawRightString(470, y, inr(r["rate"]))
        c.drawRightString(W - 40, y, inr(r["amt"]))
        c.line(40, y - 6, W - 40, y - 6)

    y -= 34
    c.setFont("Helvetica", 9)
    for k, val in [("Subtotal", taxable)] + taxes:
        c.drawString(380, y, k)
        c.drawRightString(W - 40, y, inr(val))
        y -= 15
    c.setFont("Helvetica-Bold", 11)
    c.drawString(380, y - 6, "Total due (INR)")
    c.drawRightString(W - 40, y - 6, inr(total))

    bank = bank_of(inv, v)
    y = 230
    if inv.get("note"):
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColorRGB(0.6, 0.1, 0.1)
        c.drawString(40, y + 22, inv["note"])
        c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.drawString(40, y, "PAYMENT DETAILS")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 8.5)
    for i, (k, val) in enumerate([("Account name", v["name"]), ("Account number", bank[1]),
                                  ("IFSC", bank[2]), ("Bank", bank[0])]):
        c.drawString(40, y - 14 - i * 12, f"{k}:")
        c.drawString(120, y - 14 - i * 12, val)
    c.setFont("Helvetica", 8)
    c.drawString(40, y - 80, "Payment terms: 30 days from invoice date.")
    c.drawRightString(W - 40, 90, "Authorised signatory")


# ---------------------------------------------------------------- tally
def draw_tally(c, inv):
    v = V[inv["vendor"]]
    rows, taxable, taxes, gross = compute(inv)
    total = round(gross)
    roundoff = round(total - gross, 2)
    L, R, T = 30, W - 30, H - 30
    c.setLineWidth(0.6)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(W / 2, T - 4, "Tax Invoice")
    T -= 12
    c.rect(L, 60, R - L, T - 60)
    mid = W / 2 + 20
    c.line(mid, T, mid, T - 150)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(L + 5, T - 14, v["name"])
    c.setFont("Helvetica", 7.5)
    addr = v["address"]
    c.drawString(L + 5, T - 26, split_addr(addr, 48)[0])
    c.drawString(L + 5, T - 36, split_addr(addr, 48)[1])
    c.drawString(L + 5, T - 46, f"GSTIN/UIN: {v['gstin']}")
    c.drawString(L + 5, T - 56, "State Name : Maharashtra, Code : 27" if v["state"] == "27" else
                 f"State Code : {v['state']}")
    c.line(L, T - 64, mid, T - 64)
    c.setFont("Helvetica", 7)
    c.drawString(L + 5, T - 74, "Buyer (Bill to)")
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(L + 5, T - 86, BUYER["name"])
    c.setFont("Helvetica", 7.5)
    c.drawString(L + 5, T - 98, split_addr(BUYER["address"], 52)[0])
    c.drawString(L + 5, T - 108, split_addr(BUYER["address"], 52)[1])
    c.drawString(L + 5, T - 118, f"GSTIN/UIN : {BUYER['gstin']}")
    c.drawString(L + 5, T - 128, "State Name : Maharashtra, Code : 27")

    cells = [("Invoice No.", inv["invoice_no"], "Dated", fmt_date(inv["date"], "dmy/")),
             ("Delivery Note", "", "Mode/Terms of Payment", "30 Days"),
             ("Buyer's Order No.", inv["po"] or "", "Dated", ""),
             ("Dispatch Doc No.", "", "Dispatched through", "By Road"),
             ("Terms of Delivery", "", "", "")]
    half = (R - mid) / 2
    for i, (k1, v1, k2, v2) in enumerate(cells):
        yt = T - i * 30
        c.line(mid, yt - 30, R, yt - 30)
        c.line(mid + half, yt, mid + half, yt - 30)
        c.setFont("Helvetica", 6.5)
        c.drawString(mid + 4, yt - 9, k1)
        c.drawString(mid + half + 4, yt - 9, k2)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(mid + 4, yt - 22, v1)
        c.drawString(mid + half + 4, yt - 22, v2)
    T -= 150
    c.line(L, T, R, T)

    cols = [L, L + 26, L + 250, L + 305, L + 370, L + 430, L + 460, R]
    c.setFont("Helvetica", 7)
    for x, h in zip(cols, ["Sl No.", "Description of Goods", "HSN/SAC", "Quantity", "Rate", "per", "Amount"]):
        c.drawString(x + 3, T - 11, h)
    c.line(L, T - 16, R, T - 16)
    y = T - 16
    c.setFont("Helvetica", 8.5)
    for i, r in enumerate(rows, 1):
        y -= 16
        c.drawString(cols[0] + 6, y, str(i))
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(cols[1] + 3, y, r["desc"])
        c.setFont("Helvetica", 8.5)
        c.drawString(cols[2] + 3, y, r["hsn"])
        c.drawRightString(cols[4] - 4, y, f"{r['qty']} {r['unit']}")
        c.drawRightString(cols[5] - 4, y, inr(r["rate"]))
        c.drawString(cols[5] + 3, y, r["unit"])
        c.drawRightString(R - 4, y, inr(r["amt"]))
    y -= 24
    c.setFont("Helvetica-Bold", 8.5)
    for k, val in taxes:
        c.drawRightString(cols[2] - 6, y, ("Output " if "IGST" not in k else "") + k.replace(" @ ", " @ "))
        c.drawRightString(R - 4, y, inr(val))
        y -= 14
    if roundoff:
        c.setFont("Helvetica", 8.5)
        c.drawRightString(cols[2] - 6, y, "Round Off")
        c.drawRightString(R - 4, y, inr(roundoff))
        y -= 14
    tbot = 250
    for x in cols[1:-1]:
        c.line(x, T, x, tbot + 18)
    c.line(L, tbot + 18, R, tbot + 18)
    c.setFont("Helvetica", 8.5)
    c.drawRightString(cols[2] - 6, tbot + 5, "Total")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(R - 4, tbot + 5, "Rs. " + inr(total))
    c.line(L, tbot, R, tbot)
    c.setFont("Helvetica", 7)
    c.drawString(L + 4, tbot - 10, "Amount Chargeable (in words)")
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(L + 4, tbot - 22, in_words(total))
    c.setFont("Helvetica", 7.5)
    c.drawString(L + 4, tbot - 40, f"Taxable Value : {inr(taxable)}")

    bank = bank_of(inv, v)
    c.setFont("Helvetica", 7.5)
    c.drawString(mid, tbot - 60, "Company's Bank Details")
    c.drawString(mid, tbot - 72, f"Bank Name        : {bank[0]}")
    c.drawString(mid, tbot - 84, f"A/c No.            : {bank[1]}")
    c.drawString(mid, tbot - 96, f"Branch & IFS Code : {bank[2]}")
    c.drawString(L + 4, tbot - 72, f"Company's PAN : {v['pan']}")
    c.setFont("Helvetica", 6.5)
    c.drawString(L + 4, tbot - 110, "Declaration")
    c.drawString(L + 4, tbot - 120, "We declare that this invoice shows the actual price of the goods")
    c.drawString(L + 4, tbot - 129, "described and that all particulars are true and correct.")
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(R - 6, tbot - 120, f"for {v['name']}")
    c.setFont("Helvetica", 7)
    c.drawRightString(R - 6, 70, "Authorised Signatory")
    c.drawCentredString(W / 2, 48, "This is a Computer Generated Invoice")


# ---------------------------------------------------------------- linetax
def draw_linetax(c, inv):
    v = V[inv["vendor"]]
    rows, taxable, taxes, total = compute(inv)
    inter = inv["tax_mode"] == "inter"
    c.setFont("Times-Bold", 17)
    c.drawCentredString(W / 2, H - 50, v["name"].upper())
    c.setFont("Times-Roman", 9)
    c.drawCentredString(W / 2, H - 64, v["address"])
    c.drawCentredString(W / 2, H - 76, f"GSTIN : {v['gstin']}     Ph : 0422-2571" + v["account_no"][-3:])
    c.setLineWidth(1.5)
    c.line(36, H - 84, W - 36, H - 84)
    c.setFont("Times-Bold", 11)
    c.drawCentredString(W / 2, H - 100, "GST INVOICE")

    c.setFont("Times-Roman", 9.5)
    y = H - 122
    c.drawString(40, y, "To,")
    c.drawString(40, y - 13, "M/s. " + BUYER["name"])
    c.drawString(40, y - 26, split_addr(BUYER["address"], 56)[0])
    c.drawString(40, y - 39, split_addr(BUYER["address"], 56)[1])
    c.drawString(40, y - 52, "GSTIN : " + BUYER["gstin"])
    for i, (k, val) in enumerate([("Bill No", inv["invoice_no"]), ("Bill Date", fmt_date(inv["date"], "dmy.")),
                                  ("P.O. Ref", inv["po"] or ""), ("Transport", "VRL Logistics LR 77182")]):
        c.drawString(370, y - i * 13, f"{k}")
        c.drawString(430, y - i * 13, f": {val}")

    top = y - 70
    cols = [36, 54, 196, 232, 266, 322, 390, 424, 492, W - 36]
    taxname = "IGST" if inter else "GST"
    heads = ["#", "Item", "HSN", "Qty", "Rate", "Taxable", f"{taxname}%", f"{taxname} Amt", "Total"]
    c.setLineWidth(0.5)
    c.rect(36, top - 16, W - 72, 16)
    c.setFont("Times-Bold", 8.5)
    for x, h in zip(cols, heads):
        c.drawString(x + 3, top - 11, h)
    y = top - 16
    c.setFont("Times-Roman", 8.5)
    for i, r in enumerate(rows, 1):
        y -= 16
        t = round(r["amt"] * 0.18, 2)
        vals = [str(i), r["desc"], r["hsn"], str(r["qty"]), inr(r["rate"]), inr(r["amt"]), "18",
                inr(t), inr(r["amt"] + t)]
        for j, val in enumerate(vals):
            if j >= 3:
                c.drawRightString(cols[j + 1] - 3, y + 5, val)
            else:
                c.drawString(cols[j] + 3, y + 5, val)
    c.rect(36, y - 4, W - 72, top - 16 - y + 4)
    for x in cols[1:-1]:
        c.line(x, top, x, y - 4)

    y -= 30
    c.setFont("Times-Roman", 10)
    lines = [("Total Taxable", taxable)] + [(k.replace(" @ 18%", "").replace(" @ 9%", ""), val) for k, val in taxes]
    for k, val in lines:
        c.drawString(360, y, k)
        c.drawRightString(W - 40, y, inr(val))
        y -= 14
    c.setFont("Times-Bold", 11)
    c.drawString(360, y - 4, "Bill Amount")
    c.drawRightString(W - 40, y - 4, inr(total))

    bank = bank_of(inv, v)
    c.setFont("Times-Roman", 9)
    c.drawString(40, 200, "Our Bankers : " + bank[0])
    c.drawString(40, 187, "Account No  : " + bank[1])
    c.drawString(40, 174, "IFSC Code   : " + bank[2])
    c.drawString(40, 150, "Goods once sold will not be taken back. E.&O.E.")
    c.setFont("Times-Bold", 9)
    c.drawRightString(W - 40, 120, "For " + v["name"].upper())
    c.setFont("Times-Roman", 9)
    c.drawRightString(W - 40, 80, "Proprietor / Partner")


LAYOUTS = {"boxed": draw_boxed, "minimal": draw_minimal, "tally": draw_tally, "linetax": draw_linetax}


def scanify(pdf_bytes, out_path, seed=7):
    """Make it look like someone printed it and took a phone photo."""
    rnd = random.Random(seed)
    page = pdfium.PdfDocument(pdf_bytes)[0]
    img = page.render(scale=150 / 72).to_pil().convert("L")
    img = img.rotate(1.4, resample=Image.BICUBIC, expand=True, fillcolor=235)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    px = img.load()
    w, h = img.size
    for _ in range(w * h // 25):
        x, y = rnd.randrange(w), rnd.randrange(h)
        px[x, y] = max(0, min(255, px[x, y] + rnd.randint(-45, 45)))
    # uneven lighting, darker towards the bottom-right like a phone shadow
    shade = Image.linear_gradient("L").resize((w, h)).point(lambda p: 255 - p // 7)
    img = Image.composite(img, Image.new("L", (w, h), 0), shade)
    rgb = Image.merge("RGB", (img, img, img.point(lambda p: int(p * 0.94))))
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=55)
    Image.open(buf).save(out_path, "PDF", resolution=150)


def main():
    for inv in INVOICES:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setTitle(inv["invoice_no"])
        c.setAuthor(V[inv["vendor"]]["name"])
        LAYOUTS[inv["layout"]](c, inv)
        c.showPage()
        c.save()
        path = OUT / inv["file"]
        if inv.get("scan"):
            scanify(buf.getvalue(), path)
        else:
            path.write_bytes(buf.getvalue())
        print("wrote", path.name)


if __name__ == "__main__":
    main()
