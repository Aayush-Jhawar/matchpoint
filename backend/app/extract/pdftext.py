import io

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")


def is_image(name):
    return name.lower().endswith(IMAGE_EXT)


def text_layer(data):
    """Layout-preserving text from a PDF. Empty string means it's a scan."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [p.extract_text(layout=True) or "" for p in pdf.pages[:3]]
        return "\n".join(pages)
    except Exception:
        return ""


def page_count(data, name):
    if is_image(name):
        return 1
    try:
        return len(pdfium.PdfDocument(data))
    except Exception:
        return 0


def to_image(data, name, dpi=300):
    if is_image(name):
        img = Image.open(io.BytesIO(data)).convert("RGB")
        # phone photos are often small; tesseract does much better at ~300 dpi equivalent
        if img.width < 2400:
            f = 2400 / img.width
            img = img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
        return img
    page = pdfium.PdfDocument(data)[0]
    return page.render(scale=dpi / 72).to_pil().convert("RGB")


def _tesseract():
    import os
    import pytesseract
    if os.getenv("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
    return pytesseract


def ocr(data, name):
    pytesseract = _tesseract()
    img = to_image(data, name).convert("L")
    return pytesseract.image_to_string(img, config="--psm 6 -c preserve_interword_spaces=1")


def ocr_available():
    try:
        _tesseract().get_tesseract_version()
        return True
    except Exception:
        return False
