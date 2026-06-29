"""Localhost web app: upload → pipeline → progress → review → re-frame → download.

Single-user, local-first. The pipeline (transcribe → select → render) runs in a
background thread; each stage writes its status into `data/<job_id>/job.json`, so
the browser just polls `/api/job/{id}`. The library is the filesystem itself —
`data/*/job.json` — no database needed for one local user (ponytail: a directory
glob is the index; the architecture research endorsed this).
"""

from __future__ import annotations

import json
import shutil
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from .jobs import Job, compute_job_id, STAGES
from . import transcribe, select, render

config.DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS = config.DATA_DIR / "_uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}


def safe_upload_name(filename: str) -> str:
    """Basename-only, dotfile-free, video-extension filename. Raises ValueError otherwise."""
    name = Path(filename or "").name
    if not name or name.startswith(".") or Path(name).suffix.lower() not in VIDEO_EXTS:
        raise ValueError(f"unsafe or unsupported filename: {filename!r}")
    if not (UPLOADS / name).resolve().is_relative_to(UPLOADS.resolve()):
        raise ValueError("filename escapes uploads dir")
    return name

# Drive Jinja2 directly with caching disabled — Starlette's Jinja2Templates hits
# a jinja2 LRUCache bug on Python 3.14 (unhashable dict in the cache key).
# ponytail: cache_size=0 sidesteps the broken cache path; templates are tiny.
_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]), cache_size=0,
)


def render_template(name: str, **ctx) -> HTMLResponse:
    return HTMLResponse(_env.get_template(name).render(**ctx))

app = FastAPI(title="Content Machine")
app.mount("/media", StaticFiles(directory=str(config.DATA_DIR)), name="media")

# job_id -> {"error": str|None} for surfacing background failures
RUNNING: dict[str, dict] = {}


def media_url(path: str | Path) -> str:
    rel = Path(path).resolve().relative_to(config.DATA_DIR.resolve())
    return f"/media/{rel.as_posix()}"


def _run_pipeline(temp_video: Path, model: str | None, max_clips: int,
                  x_offset: float, captions_mode: str) -> None:
    job = Job.for_video(temp_video)
    RUNNING[job.job_id] = {"error": None}
    try:
        transcribe.transcribe(temp_video, model=model)
        select.select_clips(job, max_clips=max_clips)
        render.render_job(job, x_offset=x_offset, caption_mode=captions_mode)
    except Exception as e:  # surface failure on whichever stage was running
        RUNNING[job.job_id]["error"] = str(e)
        manifest = job.load_manifest()
        for stage in STAGES:
            if manifest.get("stages", {}).get(stage, {}).get("status") == "running":
                job.update_stage(stage, "error", error=str(e))
        traceback.print_exc()


def list_jobs() -> list[dict]:
    jobs = []
    for mf in sorted(config.DATA_DIR.glob("*/job.json")):
        try:
            m = json.loads(mf.read_text())
        except Exception:
            continue
        stages = m.get("stages", {})
        done = stages.get("render", {}).get("status") == "done"
        jobs.append({
            "job_id": m.get("job_id", mf.parent.name),
            "source_name": m.get("source_name", ""),
            "created_at": m.get("created_at", 0),
            "status": "ready" if done else _overall_status(stages),
            "n_clips": stages.get("render", {}).get("clips")
                       or stages.get("select", {}).get("clips"),
        })
    return sorted(jobs, key=lambda j: j["created_at"], reverse=True)


def _overall_status(stages: dict) -> str:
    for s in STAGES:
        st = stages.get(s, {}).get("status", "pending")
        if st == "error":
            return f"error: {s}"
        if st == "running":
            return f"{s}…"
        if st in ("pending",) and s != "ingest":
            return f"{s} pending"
    return "working…"


def _job_payload(job: Job) -> dict:
    m = job.load_manifest()
    stages = {s: m.get("stages", {}).get(s, {"status": "pending"}) for s in STAGES}
    clips = []
    render_manifest = job.clips_dir / "render.json"
    if render_manifest.exists():
        for c in json.loads(render_manifest.read_text()).get("clips", []):
            clips.append({
                "index": c["index"],
                "title": c.get("title", ""),
                "score": c.get("score"),
                "captions": c.get("captions"),
                "thumb": media_url(c["thumb"]) if c.get("thumb") else None,
                "outputs": {a: media_url(p) for a, p in c.get("outputs", {}).items()},
            })
    # rationale lives in clips.json
    if job.clips_json_path.exists():
        rats = {i + 1: c.get("rationale", "")
                for i, c in enumerate(json.loads(job.clips_json_path.read_text()).get("clips", []))}
        for c in clips:
            c["rationale"] = rats.get(c["index"], "")
    return {"job_id": job.job_id, "source_name": m.get("source_name", ""),
            "stages": stages, "clips": clips,
            "error": RUNNING.get(job.job_id, {}).get("error")}


# --- routes ------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    return render_template("index.html", jobs=list_jobs())


@app.post("/upload")
async def upload(video: UploadFile = File(...), model: str = Form(""),
                 max_clips: int = Form(6), x_offset: float = Form(0.0),
                 captions: str = Form("overlay")):
    if not video.filename:
        raise HTTPException(400, "No file")
    try:
        safe_name = safe_upload_name(video.filename)  # blocks path traversal
    except ValueError as e:
        raise HTTPException(400, str(e))
    dest = UPLOADS / safe_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(video.file, f)
    job_id = compute_job_id(dest)
    # init manifest so polling works immediately
    job = Job(job_id=job_id, source_name=video.filename, data_dir=config.DATA_DIR / job_id)
    job.save_manifest(job.load_manifest())
    threading.Thread(target=_run_pipeline,
                     args=(dest, model or None, max_clips, x_offset, captions),
                     daemon=True).start()
    return RedirectResponse(f"/job/{job_id}", status_code=303)


@app.get("/job/{job_id}", response_class=HTMLResponse)
def job_page(job_id: str):
    if not (config.DATA_DIR / job_id / "job.json").exists():
        raise HTTPException(404, "Job not found")
    return render_template("job.html", job_id=job_id)


@app.get("/api/job/{job_id}")
def api_job(job_id: str):
    if not (config.DATA_DIR / job_id / "job.json").exists():
        raise HTTPException(404, "Job not found")
    return JSONResponse(_job_payload(Job.load(job_id)))


@app.post("/api/job/{job_id}/clip/{idx}/reframe")
def reframe(job_id: str, idx: int, x_offset: float = Form(0.0),
            captions: str = Form("overlay")):
    if not (config.DATA_DIR / job_id / "clips.json").exists():
        raise HTTPException(404, "Job/clips not found")
    result = render.rerender_one(job_id, idx, x_offset=x_offset, caption_mode=captions)
    return {"index": result["index"],
            "outputs": {a: media_url(p) for a, p in result["outputs"].items()}}


@app.get("/download/{job_id}/{idx}/{aspect}")
def download(job_id: str, idx: int, aspect: str):
    slug = {"9:16": "9x16", "1:1": "1x1", "16:9": "16x9"}.get(aspect, aspect)
    f = config.DATA_DIR / job_id / "clips" / f"clip{idx:02d}" / f"{slug}.mp4"
    if not f.exists():
        raise HTTPException(404, "Clip not found")
    return FileResponse(f, media_type="video/mp4",
                        filename=f"{job_id}_clip{idx:02d}_{slug}.mp4")
