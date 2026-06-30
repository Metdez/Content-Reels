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
from .logging_setup import get_logger, job_log, job_log_path, tail

log = get_logger(__name__)

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


def _run_pipeline(job_id: str, source: Path, model: str | None, max_clips: int,
                  x_offset: float, captions_mode: str,
                  transforms: dict | None = None) -> None:
    job = Job.load(job_id)
    RUNNING[job.job_id] = {"error": None}
    with job_log(job.job_id):
        log.info("=== pipeline start: %s (model=%s, max_clips=%d, captions=%s) ===",
                 job.job_id, model or config.DEFAULT_MODEL, max_clips, captions_mode)
        try:
            import json as _json
            transcribe.transcribe(source, model=model)
            clips_path = select.select_clips(job, max_clips=max_clips)
            n_clips = len(_json.loads(Path(clips_path).read_text()).get("clips", []))
            if n_clips == 0:
                msg = ("No clip-worthy moments found. Try a longer video, lower the "
                       "minimum clip length, or raise 'max clips'.")
                log.warning(msg)
                RUNNING[job.job_id]["error"] = msg
                job.update_stage("render", "error", error=msg)
                return
            render.render_job(job, x_offset=x_offset, caption_mode=captions_mode,
                              transforms=transforms)
            log.info("=== pipeline complete: %s ===", job.job_id)
        except Exception as e:  # surface failure on whichever stage was running
            RUNNING[job.job_id]["error"] = str(e)
            log.error("=== pipeline FAILED: %s ===\n%s", e, traceback.format_exc())
            manifest = job.load_manifest()
            marked = False
            for stage in STAGES:
                if manifest.get("stages", {}).get(stage, {}).get("status") == "running":
                    job.update_stage(stage, "error", error=str(e))
                    marked = True
            if not marked:  # failed before any stage started running
                job.update_stage("ingest", "error", error=str(e))


def list_jobs() -> list[dict]:
    jobs = []
    for mf in sorted(config.DATA_DIR.glob("*/job.json")):
        try:
            m = json.loads(mf.read_text())
        except Exception:
            continue
        stages = m.get("stages", {})
        done = stages.get("render", {}).get("status") == "done"
        if done:
            status = "ready"
        elif m.get("awaiting_run"):
            status = "awaiting run"
        else:
            status = _overall_status(stages)
        jobs.append({
            "job_id": m.get("job_id", mf.parent.name),
            "source_name": m.get("source_name", ""),
            "created_at": m.get("created_at", 0),
            "status": status,
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
                "transforms": c.get("transforms", {}),
            })
    # rationale + timing live in clips.json
    if job.clips_json_path.exists():
        src_clips = json.loads(job.clips_json_path.read_text()).get("clips", [])
        meta = {i + 1: c for i, c in enumerate(src_clips)}
        for c in clips:
            sc = meta.get(c["index"], {})
            c["rationale"] = sc.get("rationale", "")
            c["start"] = sc.get("start", 0)
            c["end"] = sc.get("end", 0)
    source = next(job.data_dir.glob("source.*"), None)
    return {"job_id": job.job_id, "source_name": m.get("source_name", ""),
            "stages": stages, "clips": clips,
            "awaiting_run": bool(m.get("awaiting_run")),
            "source_url": media_url(source) if source else None,
            "source_dims": m.get("source_dims", [0, 0]),
            "run_params": m.get("run_params", {}),
            "error": RUNNING.get(job.job_id, {}).get("error")}


# --- routes ------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    return render_template("index.html", jobs=list_jobs())


@app.post("/upload")
async def upload(video: UploadFile = File(...)):
    """Stage the upload for preview — does NOT start the pipeline.

    The source is moved into data/<job_id>/source<ext> (previewable via /media),
    its dimensions are probed for the crop overlay, and the manifest is marked
    `awaiting_run`. The user picks the crop + run options on the job page, then
    POSTs /api/job/{id}/run to actually start transcribe→select→render.
    """
    if not video.filename:
        raise HTTPException(400, "No file")
    try:
        safe_name = safe_upload_name(video.filename)  # blocks path traversal
    except ValueError as e:
        raise HTTPException(400, str(e))
    tmp = UPLOADS / safe_name
    with open(tmp, "wb") as f:
        shutil.copyfileobj(video.file, f)
    job_id = compute_job_id(tmp)
    ext = Path(safe_name).suffix
    job = Job(job_id=job_id, source_name=safe_name, data_dir=config.DATA_DIR / job_id)
    job.ensure_dirs()
    src = job.source_path(ext)
    # Move (not copy) the staged upload into the job dir so we don't keep two
    # copies of a multi-GB video; os.replace is atomic on the same volume.
    import os as _os
    if src.exists():
        tmp.unlink(missing_ok=True)
    else:
        _os.replace(tmp, src)
    try:
        w, h = render.probe_dims(src)
    except Exception as e:  # non-fatal — preview overlay just won't draw
        log.warning("probe_dims failed for %s: %s", src, e)
        w, h = 0, 0
    log.info("upload staged: %s (%.1f MB, %dx%d) -> job %s — awaiting run",
             safe_name, src.stat().st_size / 1e6, w, h, job_id)
    manifest = job.load_manifest()
    manifest["awaiting_run"] = True
    manifest["source_ext"] = ext
    manifest["source_dims"] = [w, h]
    job.update_stage("ingest", "done", source=str(src))  # source already on disk
    job.save_manifest(manifest)
    return RedirectResponse(f"/job/{job_id}", status_code=303)


def _parse_transforms(raw: str) -> dict | None:
    """Parse the per-aspect transforms JSON from a form field; tolerate junk."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    clean = {}
    for aspect, t in data.items():
        if aspect in config.ASPECT_RATIOS and isinstance(t, dict):
            clean[aspect] = {"zoom": t.get("zoom", 1.0), "x": t.get("x", 0.0),
                             "y": t.get("y", 0.0)}
    return clean or None


@app.post("/api/job/{job_id}/run")
def run_job(job_id: str, model: str = Form(""), max_clips: int = Form(6),
            x_offset: float = Form(0.0), captions: str = Form("overlay"),
            transforms: str = Form("")):
    """Start the pipeline for a staged job using the user-chosen framing + options."""
    if not (config.DATA_DIR / job_id / "job.json").exists():
        raise HTTPException(404, "Job not found")
    job = Job.load(job_id)
    manifest = job.load_manifest()
    if not manifest.get("awaiting_run"):
        raise HTTPException(409, "Job already started")
    src = next(job.data_dir.glob("source.*"), None)
    if src is None:
        raise HTTPException(400, "Source video missing")
    tf = _parse_transforms(transforms)
    manifest["awaiting_run"] = False
    manifest["run_params"] = {"model": model or None, "max_clips": max_clips,
                              "x_offset": x_offset, "captions": captions,
                              "transforms": tf}
    job.save_manifest(manifest)
    log.info("run requested: job %s (transforms=%s, x_offset=%.2f, max_clips=%d, captions=%s)",
             job_id, "yes" if tf else "no", x_offset, max_clips, captions)
    threading.Thread(target=_run_pipeline,
                     args=(job_id, src, model or None, max_clips, x_offset, captions, tf),
                     daemon=True).start()
    return {"ok": True}


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


@app.get("/api/job/{job_id}/log")
def api_job_log(job_id: str, lines: int = 200):
    if not (config.DATA_DIR / job_id / "job.json").exists():
        raise HTTPException(404, "Job not found")
    return JSONResponse({"log": tail(job_log_path(job_id), lines)})


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
