# Matchpoint

**Aayush Jhawar** · B.Tech, IIT Kanpur · Zamp AI Solutions Analyst case study (PS-1: invoice processing)

An accounts payable desk for one job: a vendor invoice comes in, and it goes out with a decision
(auto-approve, approve with a note, hold, or reject), the reason, and who has to act on it.

## What it does

Each invoice runs through ten stages. You can watch them run in the UI.

1. **Intake**: fingerprint the file; check whether it has a text layer or is a scan/photo
2. **Extract**: pull header fields and line items, each with a confidence score and the text it was read from
3. **Normalise**: dates, amounts, and invoice numbers in a canonical form (`INV/0442` and `INV-0442` become the same thing)
4. **Validate**: line maths, totals, GSTIN checksum, CGST+SGST vs IGST against the place of supply
5. **Match vendor**: GSTIN first, then fuzzy name; compare bank details with the vendor master
6. **Find PO**: use the quoted PO, or infer it from the vendor's open POs if none is printed
7. **Match lines**: price vs PO (within tolerance), quantity vs goods received minus what's already been billed
8. **Check history**: duplicates, near-duplicates, and how much of the PO is already used up
9. **Decide**: a fixed precedence of rules picks the decision and the owner
10. **Record**: approved and held invoices go into the ledger, so the next invoice sees them

## The one design decision that matters

**The model reads; the code decides.** An LLM (Gemini or Claude) is only used to turn a messy PDF into
fields. Every check and every decision is plain Python in `checks.py` and `rules.py`. The same invoice
always gets the same answer, and every answer points to the rule that produced it. I don't think a
finance controller would accept anything else.

If there's no API key, or the call fails, a rules parser reads the PDF text layer. Scans go through
tesseract OCR. OCR'd values get lower confidence, and if a critical field (invoice number, date,
total, GSTIN) falls below the confidence floor, the invoice is held for a person to confirm. It never
guesses. The clerk corrects the value and re-runs, and the re-run replaces the earlier booking.

## Test invoices (`samples/`)

| File | What's going on | Expected |
|---|---|---|
| 01 Shree Ganesh | Clean; PO quoted; goods received | Auto-approve |
| 02 Coimbatore Bearings | Unit price 1.21% over PO; tolerance is 2% | Approve with note (hold if tolerance set to 1%) |
| 03 Precision Castings | Second invoice on a split PO: 240 already billed, 400 received, this one bills 192 | Hold: 32 units / ₹40,000 with no receipt behind them |
| 04 Deccan Fasteners | `INV/0442`, but `INV-0442` was paid on 3 Nov | Reject: duplicate |
| 05 Bharat Electricals | Everything matches, but "our bank account has changed" | Hold for Treasury, whatever the match score |
| 06 Sai Lubricants | Phone photo, no PO number | OCR unsure of invoice no. → confirm → approved against inferred PO-2026-0420 |
| 07 Nexa Safety | Maharashtra vendor billing a Maharashtra buyer with IGST | Hold for Tax |

All of it is made up: vendors, GSTINs (with valid checksums), POs, GRNs and the ledger. Regenerate it with
`python tools/make_seed.py` and `python tools/make_invoices.py`.

## Running it

Windows: `run_local.bat`. Mac/Linux: `./run_local.sh`. Then open http://localhost:8000.

Needs Python 3.11+ and Node 18+. Copy `.env.example` to `.env` and add a `GEMINI_API_KEY` (the free tier
is enough) if you want LLM extraction. Without one, everything except the photo scan works out of the
box. For the scan you'll need either the key or tesseract installed.

Docker:

```
docker build -t matchpoint .
docker run -p 7860:7860 -e GEMINI_API_KEY=... matchpoint
```

The live version runs this same Dockerfile on Render's free tier, built from this repo's `main` branch,
with `GEMINI_API_KEY` set as an environment variable. Render sets `$PORT` and the container picks it up.
Free instances sleep when idle, so the first request after a while can take up to a minute.

Tests: `cd backend && python tests/test_scenarios.py` runs all seven invoices in order and checks each decision.

## Stack

FastAPI + SQLite, pdfplumber / pypdfium2, tesseract, rapidfuzz. React + Vite on the front end, with
hand-written CSS. The run view streams stages over server-sent events. It's the same shape as my oil
market dashboard, which I'd already deployed this way.

## How I built it

I started on paper: the process map, the decision rules and their order, the tolerances, and the edge cases
I wanted the demo to prove (the split PO, the disguised duplicate, the changed bank account, the scan with no PO).
Those are in `NOTES.md`. Then I built it with Claude as my coding assistant. The case brief encourages
using AI tools, and it let me spend the week on the logic instead of boilerplate. I've been through every
rule and threshold and can explain why each one is there.

## What I left out

Email intake, multi-currency, multi-page invoices with continued line tables, approval routing, ERP posting,
partial approval of an invoice. See `NOTES.md` for the assumptions behind each threshold.
