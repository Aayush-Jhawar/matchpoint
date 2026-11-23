"""
Hugging Face Space entry point.

Free Spaces now run on ZeroGPU, which only starts an app that registers at least
one @spaces.GPU function, so `spaces` is imported first, before anything else.
Matchpoint itself never needs a GPU: the probe below is only wired to a small
Gradio page at /gradio so ZeroGPU can see it.

The app is downloaded from GitHub at startup (GitHub stays the only copy of the
code) and its FastAPI server, API plus prebuilt React UI, is served on port 7860.
"""
try:
    import spaces  # must come before other imports on ZeroGPU

    @spaces.GPU(duration=10)
    def gpu_probe() -> str:
        return "ok"
except ImportError:  # running locally / on CPU hardware
    def gpu_probe() -> str:
        return "ok"

import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import gradio as gr
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

with gr.Blocks(title="Matchpoint runtime") as probe_page:
    gr.Markdown("Matchpoint runs at the [root of this Space](/). This page only exists for the ZeroGPU runtime check.")
    out = gr.Textbox(label="GPU probe")
    gr.Button("Run GPU probe").click(gpu_probe, outputs=out)

app = gr.mount_gradio_app(app, probe_page, path="/gradio")
# Matchpoint has a catch-all route for its single-page UI; put the Gradio mount ahead of it
app.router.routes.insert(0, app.router.routes.pop())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
