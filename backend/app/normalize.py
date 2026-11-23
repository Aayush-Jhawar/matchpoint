import re
from datetime import date, datetime

from rapidfuzz import fuzz

_SUFFIXES = {"pvt", "private", "ltd", "limited", "llp", "co", "company", "corp", "inc", "the", "m/s", "ms"}


def canonical_invoice_no(s):
    """INV/0442, INV-0442, inv 442 -> INV442. Separators and leading zeros carry no meaning for duplicates."""
    if not s:
        return ""
    parts = re.findall(r"[A-Za-z]+|\d+", s.upper())
    return "".join(p.lstrip("0") or "0" if p.isdigit() else p for p in parts)


def vendor_key(name):
    n = (name or "").lower().replace("&", " and ")
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(w for w in n.split() if w not in _SUFFIXES)


def name_similarity(a, b):
    return fuzz.token_set_ratio(vendor_key(a), vendor_key(b))


def item_similarity(a, b):
    def clean(s):
        s = (s or "").lower()
        s = re.sub(r"\b(ltr|litre|liter|l)\b", "l", s)
        s = s.replace("brg", "bearing").replace("c.i.", "ci").replace("sq mm", "sqmm")
        return re.sub(r"[^a-z0-9 ]", " ", s)
    return fuzz.token_set_ratio(clean(a), clean(b))


def to_num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).replace(",", "").replace("Rs.", "").replace("INR", "").replace("₹", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


_DATE_FORMATS = ["%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%b %d, %Y", "%B %d, %Y", "%d/%m/%Y", "%d.%m.%Y",
                 "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%d/%m/%y"]


def parse_date(s):
    if not s:
        return None
    if isinstance(s, date):
        return s
    s = s.strip().rstrip(".")
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def fmt_inr(x):
    if x is None:
        return "-"
    neg = x < 0
    whole, dec = f"{abs(x):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return ("-" if neg else "") + "₹" + whole + "." + dec
