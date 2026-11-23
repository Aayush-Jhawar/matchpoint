import re

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")

STATES = {
    "03": "Punjab", "07": "Delhi", "24": "Gujarat", "27": "Maharashtra",
    "29": "Karnataka", "33": "Tamil Nadu", "36": "Telangana",
}


def checksum_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        prod = CHARS.index(ch) * (2 if i % 2 else 1)
        total += prod // 36 + prod % 36
    return CHARS[(36 - total % 36) % 36]


def make_gstin(state: str, pan: str, entity: str = "1") -> str:
    base = f"{state}{pan}{entity}Z"
    return base + checksum_char(base)


def check(gstin: str) -> list[str]:
    """Returns a list of problems, empty if the GSTIN looks fine."""
    problems = []
    g = (gstin or "").strip().upper()
    if len(g) != 15 or not GSTIN_RE.fullmatch(g):
        return ["format is not a valid GSTIN"]
    if g[:2] not in STATES:
        problems.append(f"unknown state code {g[:2]}")
    if not PAN_RE.match(g[2:12]):
        problems.append("embedded PAN is malformed")
    if checksum_char(g[:14]) != g[14]:
        problems.append("checksum digit does not match")
    return problems


def state_of(gstin: str) -> str:
    return (gstin or "")[:2]
