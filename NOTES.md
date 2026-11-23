# Assumptions and decisions

Aayush Jhawar · Matchpoint (Zamp ASA case study, PS-1)

My log of the calls I made where the problem statement was open. Most of these are things I'd ask a
real AP team on day one.

## Assumptions

- The buyer is an Indian mid-size manufacturer (Kaveri Auto Components, Pune) under GST. INR only.
  A foreign-currency invoice would need FX rules I haven't built, so it isn't handled.
- PO, GRN and vendor master come from an ERP export. Here they're CSVs loaded into SQLite on reset.
- PO values and PO-balance checks use the **taxable value** (before GST). Tax is checked separately.
- One invoice maps to one PO. An invoice covering two POs is rare enough in this kind of business to leave out for now.
- "Approved" means released to the normal payment run. Actually paying is out of scope.
- Held invoices are booked as `on_hold`. They don't use up PO balance, but they do count for duplicate checks.
  So a vendor who resends a held invoice gets caught.

## Thresholds and why

| Setting | Value | Why |
|---|---|---|
| Price tolerance | 2% per line | Common in Indian manufacturing for commodity-linked items; can be changed in Settings |
| Line variance cap | ₹5,000 | 2% of a big line is real money. The cap stops tolerance from hiding large amounts |
| Total rounding | ₹1 | Tally rounds totals to the rupee |
| Qty vs GRN | zero tolerance | You pay for what you received, not for what was billed |
| Duplicate window | 30 days | Same vendor + same amount + different number inside a month: worth a look, not a rejection |
| Confidence floor | 0.75 | Below this I'd rather a person spends 20 seconds confirming |
| PO inference | score ≥ 70 and 12 clear of the next | When two POs look alike it should ask, not pick |

## Rule order (top wins)

Duplicate > unknown vendor > **bank change** > unreadable / low confidence > maths > tax > PO problems >
quantity > price > balance > possible duplicate.

Bank change sits above all matching problems on purpose. A fraudulent invoice is built to match the PO
perfectly, so the match score is exactly the wrong signal to trust there.

Duplicate vs reused number: same vendor + same canonical number + same amount is a duplicate and gets
rejected. Same number with a different amount is held, because it could be a revised invoice.

## Things I'd do next

- Read invoices from a mailbox and reply to the vendor from the same thread (the vendor draft is already generated)
- Learn each vendor's invoice-number pattern, so OCR mistakes like `SIL/S83` get caught as "doesn't fit this vendor's pattern"
- Partial approval: approve the 160 received units and hold 32 instead of holding the whole invoice
- Multi-page invoices, credit notes, TDS deduction
- Approval matrix by amount, and an audit export
