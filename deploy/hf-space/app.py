"""
Hugging Face Space entry point.

Gradio Spaces just run `python app.py` and expect a web server on port 7860.
Instead of a Gradio UI, this downloads Matchpoint from GitHub and serves its own
FastAPI app (API + prebuilt React UI) on that port. GitHub stays the only copy of the code.
"""
import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import httpx
import uvicorn

REPO_ZIP = os.getenv("MATCHPOINT_ZIP", "https://codeload.github.com/Aayush-Jhawar/matchpoint/zip/refs/heads/main")
SRC = Path(os.getenv("MATCHPOINT_SRC", "/tmp/matchpoint-src"))


def fetch_source():
    if (SRC / "backend").exists() and os.getenv("MATCHPOINT_SRC"):
        return SRC  # local testing against an existing checkout
    try:
        r = httpx.get(REPO_ZIP, follow_redirects=True, timeout=60)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            root = z.namelist()[0].split("/")[0]  # e.g. matchpoint-main
            z.extractall(SRC.parent)
        return SRC.parent / root
    except Exception as e:
        print(f"zip download failed ({e}), trying git clone")
        dest = SRC.parent / "matchpoint-git"
        if not dest.exists():
            subprocess.run(["git", "clone", "--depth", "1", "https://github.com/Aayush-Jhawar/matchpoint.git",
                            str(dest)], check=True)
        return dest


src = fetch_source()
os.environ.setdefault("MATCHPOINT_DATA", "/tmp/matchpoint-data")
os.environ.setdefault("STAGE_DELAY_MS", "450")
sys.path.insert(0, str(src / "backend"))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
