"""
Turns findings into one decision. Order matters: the first code in this list
that was raised becomes the headline, and its owner gets the item.
"""
PRECEDENCE = [
    "DUPLICATE_FILE", "DUPLICATE_INVOICE",
    "UNKNOWN_VENDOR", "VENDOR_INACTIVE", "GSTIN_NOT_MASTER",
    "BANK_CHANGED",                                   # outranks every matching problem on purpose
    "UNREADABLE", "MISSING_FIELD", "LOW_CONFIDENCE",
    "TOTAL_MISMATCH", "LINE_SUM_MISMATCH",
    "GSTIN_INVALID", "WRONG_TAX_TYPE", "GST_RATE_MISMATCH", "BILLED_TO_OTHER",
    "PO_NOT_FOUND", "PO_VENDOR_MISMATCH", "PO_CLOSED", "PO_AMBIGUOUS", "PO_NOT_IDENTIFIED",
    "NO_LINES", "LINE_NOT_ON_PO", "NO_GRN", "QTY_EXCEEDS_RECEIPT", "PRICE_OVER_TOLERANCE", "OVER_PO_BALANCE",
    "REUSED_NUMBER", "POSSIBLE_DUPLICATE", "FUTURE_DATE",
    # notes
    "PO_INFERRED", "PRICE_WITHIN_TOLERANCE", "NAME_DIFFERS",
]
RANK = {c: i for i, c in enumerate(PRECEDENCE)}

DECISION_LABEL = {
    "AUTO_APPROVE": "Auto-approved",
    "APPROVE_WITH_NOTE": "Approved with note",
    "HOLD": "On hold",
    "REJECT": "Rejected",
}


def decide(findings, ctx):
    ordered = sorted(findings, key=lambda f: (RANK.get(f["code"], 999)))
    rejects = [f for f in ordered if f["level"] == "reject"]
    holds = [f for f in ordered if f["level"] == "hold"]
    notes = [f for f in ordered if f["level"] == "note"]

    if rejects:
        top = rejects[0]
        decision, owner, headline, action = "REJECT", top["owner"], top["title"], top["action"]
    elif holds:
        top = holds[0]
        decision, owner, headline, action = "HOLD", top["owner"], top["title"], top["action"]
    elif notes:
        decision, owner = "APPROVE_WITH_NOTE", "AP team"
        headline = "Approved. " + notes[0]["title"]
        action = "Release for payment on the normal run. " + (notes[0]["action"] or "")
    else:
        po = ctx.get("po")
        decision, owner = "AUTO_APPROVE", "AP team"
        headline = f"Clean match to {po['po_no']}. Ready to pay." if po else "Clean. Ready to pay."
        action = "Release for payment on the normal run."

    others = len(rejects) + len(holds) - 1 if decision in ("REJECT", "HOLD") else 0
    return {"decision": decision, "label": DECISION_LABEL[decision], "owner": owner, "headline": headline,
            "action": action, "other_issues": max(others, 0), "reasons": ordered}


def vendor_message(result, ctx):
    """Draft email for when the vendor has to fix something. Kept short, the way AP actually writes."""
    inv, v = ctx.get("inv") or {}, ctx.get("vendor")
    d = result["decision"]
    vendor_codes = {"TOTAL_MISMATCH", "LINE_SUM_MISMATCH", "WRONG_TAX_TYPE", "GST_RATE_MISMATCH", "QTY_EXCEEDS_RECEIPT",
                    "OVER_PO_BALANCE", "DUPLICATE_INVOICE", "PRICE_OVER_TOLERANCE"}
    relevant = [f for f in result["reasons"] if f["code"] in vendor_codes]
    if not v or not relevant or d not in ("HOLD", "REJECT"):
        return None
    name = v["name"]
    no = inv["invoice_no"] or "your invoice"
    if relevant[0]["code"] == "DUPLICATE_INVOICE":
        body = (f"Dear {name} team,\n\nWe received invoice {no} again. It matches an invoice we have already settled: "
                f"{relevant[0]['detail']}\n\nWe won't be processing this copy. If you think a payment is still "
                "pending, please send the UTR or remittance reference you are missing and we'll check.\n\n"
                "Regards,\nAccounts Payable\nKaveri Auto Components Pvt. Ltd.")
        return {"subject": f"Invoice {no}: already paid", "body": body}
    points = "\n".join(f"- {f['detail']}" for f in relevant)
    body = (f"Dear {name} team,\n\nWe can't process invoice {no} in its current form:\n\n{points}\n\n"
            "Please send a revised invoice (or a credit note for the difference) and quote the PO number. "
            "We'll process it as soon as it arrives.\n\nRegards,\nAccounts Payable\nKaveri Auto Components Pvt. Ltd.")
    return {"subject": f"Invoice {no}: revision needed", "body": body}
