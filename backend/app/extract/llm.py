"""
LLM extraction. The model only reads the document and fills a fixed shape;
it never sees the PO data and never makes the decision.
"""
import base64
import json
import re

import httpx

from .. import config

PROMPT = """You are reading one vendor invoice issued to an Indian company. Extract what is printed.
Do not calculate or infer missing values; use null when a field is not on the document.
Return only JSON in exactly this shape:
{
 "fields": {
  "vendor_name": {"value": str|null, "confidence": 0-1, "source": "exact text you read it from"},
  "vendor_gstin": {...}, "buyer_gstin": {...}, "invoice_no": {...},
  "invoice_date": {"value": "YYYY-MM-DD"|null, ...}, "po_ref": {...},
  "taxable_value": {"value": number|null, ...}, "cgst": {...}, "sgst": {...}, "igst": {...},
  "round_off": {...}, "total": {...},
  "bank_name": {...}, "bank_account": {...}, "ifsc": {...},
  "remarks": {"value": "any note about changed bank details, credit notes or disputes"|null, ...}
 },
 "lines": [{"description": str, "hsn": str|null, "qty": number, "unit": str|null, "rate": number,
            "amount": number, "confidence": 0-1, "source": "the row as printed"}]
}
Rules: amounts are plain numbers without commas or currency. Confidence below 0.7 means you are
guessing (blurry, cut off, ambiguous). buyer_gstin is the GSTIN of the company being billed,
vendor_gstin is the issuer's. po_ref is the buyer's purchase order number if printed."""


def _mime(name):
    n = name.lower()
    if n.endswith(".pdf"):
        return "application/pdf"
    if n.endswith(".png"):
        return "image/png"
    if n.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _json_from(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def gemini(data, name):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
           f"?key={config.GEMINI_API_KEY}")
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": _mime(name), "data": base64.b64encode(data).decode()}},
            {"text": PROMPT}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    r = httpx.post(url, json=body, timeout=60)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _json_from(text), f"llm:{config.GEMINI_MODEL}"


def anthropic(data, name):
    mime = _mime(name)
    block_type = "document" if mime == "application/pdf" else "image"
    body = {
        "model": config.ANTHROPIC_MODEL, "max_tokens": 2000, "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": block_type, "source": {"type": "base64", "media_type": mime,
                                            "data": base64.b64encode(data).decode()}},
            {"type": "text", "text": PROMPT}]}],
    }
    r = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=60,
                   headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    return _json_from(text), f"llm:{config.ANTHROPIC_MODEL}"


def available():
    return bool(config.GEMINI_API_KEY or config.ANTHROPIC_API_KEY)


def extract(data, name):
    if config.GEMINI_API_KEY:
        return gemini(data, name)
    return anthropic(data, name)
