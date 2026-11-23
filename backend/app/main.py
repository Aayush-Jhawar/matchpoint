import asyncio
import json
import threading
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, pipeline
from .extract import llm, pdftext

app = FastAPI(
    title="Matchpoint",
    description="Vendor invoice in, AP decision out. Zamp ASA case study (PS-1) by Aayush Jhawar.",
    version="0.1.0",
    contact={"name": "Aayush Jhawar", "url": "https://github.com/Aayush-Jhawar"},
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
db.init()

SAMPLE_NOTES = {
    "01": "Clean invoice, PO quoted, goods received",
    "02": "Unit price a little above PO",
    "03": "Second invoice on a split PO",
    "04": "Invoice number looks familiar",
    "05": "Everything matches, bank details on the invoice are new",
    "06": "Phone photo, no PO number",
    "07": "Local vendor, check the tax",
}


def _start(data, name, overrides=None, parent=None):
    run_id = pipeline.new_run(name, "", parent)
    path = config.UPLOAD_DIR / f"{run_id}__{Path(name).name}"
    path.write_bytes(data)
    db.ex("UPDATE runs SET file_path=? WHERE id=?", (str(path), run_id))
    threading.Thread(target=pipeline.execute, args=(run_id, data, name, overrides, parent), daemon=True).start()
    return run_id


@app.get("/api/health")
def health():
    provider = None
    if llm.available():
        provider = config.GEMINI_MODEL if config.GEMINI_API_KEY else config.ANTHROPIC_MODEL
    return {"llm": provider, "ocr": pdftext.ocr_available(), "stage_delay_ms": config.STAGE_DELAY_MS}


@app.get("/api/samples")
def samples():
    out = []
    for p in sorted(config.SAMPLES_DIR.glob("*")):
        if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg"):
            out.append({"name": p.name, "note": SAMPLE_NOTES.get(p.name[:2], ""), "size": p.stat().st_size})
    return out


@app.get("/api/samples/{name}")
def sample_file(name: str):
    p = config.SAMPLES_DIR / Path(name).name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/runs")
async def create_run(file: UploadFile = File(None), sample: str = None):
    if sample:
        p = config.SAMPLES_DIR / Path(sample).name
        if not p.exists():
            raise HTTPException(404, "no such sample")
        data, name = p.read_bytes(), p.name
    elif file is not None:
        data, name = await file.read(), file.filename or "upload.pdf"
    else:
        raise HTTPException(400, "send a file or a sample name")
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "file too large")
    return {"id": _start(data, name)}


@app.post("/api/runs/{run_id}/rerun")
def rerun(run_id: str, body: dict = Body(default={})):
    run = db.q1("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        raise HTTPException(404)
    data = Path(run["file_path"]).read_bytes()
    overrides = {k: v for k, v in (body.get("overrides") or {}).items() if v not in (None, "")}
    return {"id": _start(data, run["file_name"], overrides, run_id)}


def _run_row(r):
    keys = ["id", "created_at", "finished_at", "file_name", "state", "decision", "owner", "headline", "vendor_name",
            "invoice_no", "po_no", "total", "method", "duration_ms", "parent_run"]
    return {k: r[k] for k in keys}


@app.get("/api/runs")
def list_runs():
    return [_run_row(r) for r in db.q("SELECT * FROM runs ORDER BY created_at DESC, rowid DESC")]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    r = db.q1("SELECT * FROM runs WHERE id=?", (run_id,))
    if not r:
        raise HTTPException(404)
    out = _run_row(r)
    out["payload"] = json.loads(r["payload"]) if r["payload"] else None
    out["events"] = [{"seq": e["seq"], "stage": e["stage"], "status": e["status"], "data": json.loads(e["data"])}
                     for e in db.q("SELECT * FROM run_events WHERE run_id=? ORDER BY seq", (run_id,))]
    out["children"] = [c["id"] for c in db.q("SELECT id FROM runs WHERE parent_run=?", (run_id,))]
    return out


@app.get("/api/runs/{run_id}/file")
def run_file(run_id: str):
    r = db.q1("SELECT file_path, file_name FROM runs WHERE id=?", (run_id,))
    if not r or not r["file_path"] or not Path(r["file_path"]).exists():
        raise HTTPException(404)
    return FileResponse(r["file_path"], filename=r["file_name"], content_disposition_type="inline")


@app.get("/api/runs/{run_id}/preview.png")
def run_preview(run_id: str, page: int = 0):
    r = db.q1("SELECT file_path, file_name FROM runs WHERE id=?", (run_id,))
    if not r or not r["file_path"] or not Path(r["file_path"]).exists():
        raise HTTPException(404)
    cache = Path(r["file_path"] + f".p{page}.png")
    if not cache.exists():
        img = pdftext.to_image(Path(r["file_path"]).read_bytes(), r["file_name"], dpi=110)
        img.save(cache, "PNG", optimize=True)
    return FileResponse(cache, media_type="image/png")


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str):
    async def gen():
        last = 0
        idle = 0
        while True:
            events = db.q("SELECT * FROM run_events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, last))
            for e in events:
                last = e["seq"]
                msg = {"seq": e["seq"], "stage": e["stage"], "status": e["status"], "data": json.loads(e["data"])}
                yield f"data: {json.dumps(msg)}\n\n"
            run = db.q1("SELECT state FROM runs WHERE id=?", (run_id,))
            if not run:
                break
            if run["state"] != "running" and not events:
                yield f"event: end\ndata: {json.dumps({'state': run['state']})}\n\n"
                break
            idle = 0 if events else idle + 1
            if idle > 600:  # ~2 minutes with nothing happening
                break
            await asyncio.sleep(0.2)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/stats")
def stats():
    runs = db.q("SELECT * FROM runs WHERE state='done'")
    latest = {}
    for r in runs:  # a re-run supersedes its parent in the numbers
        latest[r["id"]] = r
    for r in runs:
        if r["parent_run"] in latest:
            latest.pop(r["parent_run"], None)
    rs = list(latest.values())
    by = {d: [r for r in rs if r["decision"] == d] for d in ("AUTO_APPROVE", "APPROVE_WITH_NOTE", "HOLD", "REJECT")}
    owners = {}
    for r in by["HOLD"]:
        owners[r["owner"]] = owners.get(r["owner"], 0) + 1
    n = len(rs)
    return {
        "processed": n,
        "counts": {k: len(v) for k, v in by.items()},
        "value": {k: round(sum((r["total"] or 0) for r in v), 2) for k, v in by.items()},
        "touchless_rate": round((len(by["AUTO_APPROVE"]) + len(by["APPROVE_WITH_NOTE"])) / n * 100) if n else 0,
        "holds_by_owner": owners,
        "avg_ms": round(sum(r["duration_ms"] or 0 for r in rs) / n) if n else 0,
        "blocked_value": round(sum((r["total"] or 0) for r in by["REJECT"]), 2),
    }


@app.get("/api/pos")
def pos():
    out = []
    for po in db.q("SELECT p.*, v.name vendor FROM purchase_orders p JOIN vendors v USING (vendor_id) "
                   "WHERE p.status='open' ORDER BY p.po_no"):
        billed = db.q1("SELECT COALESCE(SUM(taxable_value),0) s FROM ledger WHERE po_no=? AND status IN ('paid','approved')",
                       (po["po_no"],))["s"]
        held = db.q1("SELECT COALESCE(SUM(taxable_value),0) s FROM ledger WHERE po_no=? AND status='on_hold'",
                     (po["po_no"],))["s"]
        rec = db.q1("SELECT COALESCE(SUM(g.qty_received*l.rate),0) s FROM grn g JOIN po_lines l "
                    "ON g.po_no=l.po_no AND g.line_no=l.line_no WHERE g.po_no=?", (po["po_no"],))["s"]
        out.append({"po_no": po["po_no"], "vendor": po["vendor"], "value": po["taxable_value"], "billed": billed,
                    "on_hold": held, "received_value": rec})
    return out


@app.get("/api/master")
def master():
    return {"vendors": db.q("SELECT * FROM vendors"), "buyer": db.buyer()}


@app.get("/api/settings")
def get_settings():
    return db.get_settings()


@app.put("/api/settings")
def put_settings(body: dict = Body(...)):
    db.save_settings(body)
    return db.get_settings()


@app.post("/api/reset")
def reset():
    db.reset(keep_cache=True)
    return {"ok": True}


@app.post("/api/cache/clear")
def clear_cache():
    db.ex("DELETE FROM extraction_cache")
    return {"ok": True}


if config.STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = config.STATIC_DIR / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.STATIC_DIR / "index.html")
