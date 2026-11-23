import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# tiny .env reader so I don't need python-dotenv just for two keys
_env = ROOT.parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
SEED_DIR = ROOT / "seed"
DATA_DIR = Path(os.getenv("MATCHPOINT_DATA", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "matchpoint.db"
SAMPLES_DIR = ROOT.parent / "samples"
STATIC_DIR = ROOT.parent / "frontend" / "dist"

# Small pause between stages so the run view is watchable in a demo.
# Set to 0 for real use. Nothing else in the pipeline is slowed down.
STAGE_DELAY_MS = int(os.getenv("STAGE_DELAY_MS", "450"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

DEFAULT_SETTINGS = {
    "price_tolerance_pct": 2.0,      # unit price over PO, per line
    "line_variance_cap": 5000.0,     # and never more than this many rupees on one line
    "total_rounding": 1.0,           # rupees allowed between computed and printed total
    "duplicate_window_days": 30,
    "confidence_floor": 0.75,        # below this a critical field is not trusted
    "po_inference_min_score": 70,
    "po_inference_margin": 12,
    "use_llm": True,
}

for d in (DATA_DIR, UPLOAD_DIR):
    d.mkdir(parents=True, exist_ok=True)
