"""Render selected clips: cut + reframe (9:16/1:1/16:9) + captions + thumbnail.

ffmpeg does everything. We re-encode (crop forces it), so input-seek `-ss` before
`-i` is both fast AND frame-accurate here — the black-frame trap only bites
`-c copy`, which we never use.

Reframe = center crop to the target aspect with an adjustable horizontal offset
(`x_offset` in [-1,1]) for off-center speakers, then scale to a standard size.

Captions (this ffmpeg has no libass/drawtext, only `overlay`):
  - "overlay" (default): transparent caption PNGs (Pillow) composited with
    time-gated ffmpeg `overlay`. Works everywhere.
  - "hyperframes": animated HTML→MOV overlay; falls back to "overlay" on failure.
  - "none": no captions.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import config, captions
from .jobs import Job
from .logging_setup import get_logger, run, stream_run

log = get_logger(__name__)

OUTPUT_DIMS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
ASPECT_SLUG = {"9:16": "9x16", "1:1": "1x1", "16:9": "16x9"}

# Per-aspect framing transform. zoom>=1 (1.0 = max-fit crop, larger = tighter);
# x/y in [-1,1] pan across whatever horizontal/vertical slack the aspect+zoom create.
DEFAULT_TRANSFORM = {"zoom": 1.0, "x": 0.0, "y": 0.0}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def normalize_transforms(transforms: dict | None, x_offset: float = 0.0,
                         aspects: tuple[str, ...] = config.ASPECT_RATIOS) -> dict:
    """One clean {zoom,x,y} per aspect.

    `transforms` is an optional aspect -> {zoom,x,y} mapping (partial is fine).
    When an aspect is absent, it falls back to DEFAULT_TRANSFORM but with `x`
    seeded from the legacy scalar `x_offset` so old callers/run_params that only
    knew about a single horizontal offset keep working unchanged.
    """
    out = {}
    for a in aspects:
        t = (transforms or {}).get(a) or {}
        out[a] = {
            "zoom": max(1.0, float(t.get("zoom", DEFAULT_TRANSFORM["zoom"]))),
            "x": _clamp(float(t.get("x", x_offset)), -1.0, 1.0),
            "y": _clamp(float(t.get("y", DEFAULT_TRANSFORM["y"])), -1.0, 1.0),
        }
    return out


def probe_dims(src: Path) -> tuple[int, int]:
    out = subprocess.run(
        [config.FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(src)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True).stdout.strip()
    w, h = out.split("x")[:2]
    return int(w), int(h)


def compute_crop(src_w: int, src_h: int, aspect: str, x_offset: float = 0.0,
                 zoom: float = 1.0, y_offset: float = 0.0) -> tuple[int, int, int, int]:
    """Target-aspect crop rect inside the source: max-fit, then zoom + x/y pan.

    Returns (crop_w, crop_h, x, y).
      - zoom>=1 shrinks the crop window (1.0 = largest fitting rect, 2.0 = half
        as wide/tall = 2x tighter), which creates slack to pan in BOTH axes.
      - x_offset / y_offset in [-1,1] move the window across that slack
        (-1 = hard left/top, 0 = center, +1 = hard right/bottom).

    Back-compatible: with the default zoom=1.0, y_offset=0.0 this matches the
    original center-crop + horizontal-offset behavior exactly.
    """
    tw, th = (int(p) for p in aspect.split(":"))
    target_ar = tw / th
    src_ar = src_w / src_h
    if target_ar <= src_ar:                       # width-limited (e.g. 9:16 from 16:9)
        base_h = src_h
        base_w = round(src_h * target_ar)
    else:                                          # height-limited
        base_w = src_w
        base_h = round(src_w / target_ar)
    z = max(1.0, zoom)
    crop_w = min(src_w, round(base_w / z))
    crop_h = min(src_h, round(base_h / z))
    slack_x = src_w - crop_w
    slack_y = src_h - crop_h
    x = round(slack_x / 2 + _clamp(x_offset, -1.0, 1.0) * slack_x / 2)
    y = round(slack_y / 2 + _clamp(y_offset, -1.0, 1.0) * slack_y / 2)
    x = int(max(0, min(slack_x, x)))
    y = int(max(0, min(slack_y, y)))
    crop_w -= crop_w % 2                            # even dims for yuv420p
    crop_h -= crop_h % 2
    return crop_w, crop_h, x, y


def crop_scale_filter(src_w: int, src_h: int, aspect: str, x_offset: float = 0.0,
                      zoom: float = 1.0, y_offset: float = 0.0) -> str:
    cw, ch, x, y = compute_crop(src_w, src_h, aspect, x_offset, zoom, y_offset)
    ow, oh = OUTPUT_DIMS[aspect]
    return f"crop={cw}:{ch}:{x}:{y},scale={ow}:{oh}"


def build_render_cmd(src: Path, start: float, end: float, aspect: str, x_offset: float,
                     out: Path, src_w: int, src_h: int,
                     png_events: list[dict] | None = None,
                     zoom: float = 1.0, y_offset: float = 0.0) -> list[str]:
    """ffmpeg: cut + crop/scale, optionally compositing time-gated caption PNGs."""
    dur = max(0.1, end - start)
    cs = crop_scale_filter(src_w, src_h, aspect, x_offset, zoom, y_offset)
    cmd = [config.FFMPEG, "-y", "-ss", f"{start:.3f}", "-i", str(src)]

    png_events = png_events or []
    if not png_events:
        # explicit maps so the audio stream is always carried, never dropped
        cmd += ["-t", f"{dur:.3f}", "-vf", cs, "-map", "0:v:0", "-map", "0:a?"]
    else:
        for e in png_events:
            cmd += ["-loop", "1", "-i", str(e["png"])]
        parts = [f"[0:v]{cs}[base]"]
        prev = "base"
        for i, e in enumerate(png_events):
            nxt = f"v{i}"
            parts.append(
                f"[{prev}][{i + 1}:v]overlay=0:0:enable='between(t,{e['start']:.3f},{e['end']:.3f})'[{nxt}]"
            )
            prev = nxt
        cmd += ["-filter_complex", ";".join(parts), "-map", f"[{prev}]", "-map", "0:a?",
                "-t", f"{dur:.3f}"]

    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(out)]
    return cmd


def build_overlay_cmd(base: Path, overlay: Path, out: Path) -> list[str]:
    """Composite a transparent caption overlay video onto a rendered clip."""
    return [
        config.FFMPEG, "-y", "-i", str(base), "-i", str(overlay),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-movflags", "+faststart", str(out),
    ]


def build_thumbnail_cmd(src: Path, t: float, out: Path) -> list[str]:
    return [config.FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", str(src),
            "-frames:v", "1", "-q:v", "3", str(out)]


def render_clip(job: Job, clip: dict, idx: int, segments: list[dict],
                aspects: tuple[str, ...] = config.ASPECT_RATIOS,
                x_offset: float = 0.0, caption_mode: str = "overlay",
                transforms: dict | None = None,
                on_aspect_done=None, prev_outputs: dict | None = None) -> dict:
    """Render a clip in each aspect, each with its own {zoom,x,y} framing.

    `transforms` is an aspect -> {zoom,x,y} mapping (falls back to x_offset for
    any missing axis). `on_aspect_done(aspect, url_path)` is called as each
    aspect finishes so the UI can surface clips incrementally. `prev_outputs`
    seeds the returned outputs so a partial re-render (subset of `aspects`)
    keeps the untouched aspects.
    """
    config.require_tool(config.FFMPEG, "Install ffmpeg: brew install ffmpeg")
    src = next(job.data_dir.glob("source.*"))
    src_w, src_h = probe_dims(src)
    tf = normalize_transforms(transforms, x_offset)
    clip_dir = job.clips_dir / f"clip{idx:02d}"
    clip_dir.mkdir(parents=True, exist_ok=True)
    events = captions.clip_caption_events(segments, clip["start"], clip["end"])
    log.info("render clip %d (%.1f-%.1fs, %d caption events) -> %s",
             idx, clip["start"], clip["end"], len(events), ", ".join(aspects))

    outputs = dict(prev_outputs or {})
    captions_used = caption_mode
    for aspect in aspects:
        ow, oh = OUTPUT_DIMS[aspect]
        out = clip_dir / f"{ASPECT_SLUG[aspect]}.mp4"
        t = tf[aspect]

        # try hyperframes animated overlay first if requested
        if caption_mode == "hyperframes" and events and captions.hyperframes_available():
            try:
                overlay = captions.render_hyperframes_overlay(
                    events, ow, oh, clip_dir / f"hf_{ASPECT_SLUG[aspect]}")
                base = clip_dir / f"base_{ASPECT_SLUG[aspect]}.mp4"
                run(build_render_cmd(src, clip["start"], clip["end"], aspect, t["x"],
                    base, src_w, src_h, png_events=None, zoom=t["zoom"], y_offset=t["y"]),
                    log, f"render base {aspect}")
                run(build_overlay_cmd(base, overlay, out), log, f"composite hyperframes {aspect}")
                outputs[aspect] = str(out)
                if on_aspect_done:
                    on_aspect_done(aspect, str(out))
                continue
            except Exception as e:
                log.warning("hyperframes %s failed (%s) — falling back to overlay captions",
                            aspect, str(e)[:160])
                captions_used = "overlay"  # fall back

        # default: Pillow PNG overlays (or no captions)
        png_events = []
        if caption_mode != "none" and events:
            font = captions.find_font()
            png_events = captions.render_caption_pngs(
                events, ow, oh, clip_dir / f"pngs_{ASPECT_SLUG[aspect]}", font)
        stream_run(build_render_cmd(src, clip["start"], clip["end"], aspect, t["x"],
                   out, src_w, src_h, png_events=png_events, zoom=t["zoom"], y_offset=t["y"]),
                   log, f"render clip {idx} {aspect}", cwd=str(clip_dir))
        outputs[aspect] = str(out)
        if on_aspect_done:
            on_aspect_done(aspect, str(out))

    thumb = clip_dir / "thumb.jpg"
    run(build_thumbnail_cmd(src, clip["start"] + 0.5, thumb), log, f"thumbnail clip {idx}")
    return {"index": idx, "dir": str(clip_dir), "outputs": outputs,
            "thumb": str(thumb), "captions": captions_used,
            "title": clip.get("title", ""), "score": clip.get("score"),
            "transforms": tf}


def rerender_one(job_id_or_job, idx: int, x_offset: float = 0.0,
                 caption_mode: str = "overlay", transforms: dict | None = None,
                 aspects: tuple[str, ...] | None = None) -> dict:
    """Re-render a single clip after a UI tweak (framing / trim / captions).

    `transforms` carries per-aspect {zoom,x,y}; `aspects` (optional) limits the
    re-render to specific ratios so only the changed aspect re-encodes — the
    untouched aspects are preserved from the existing render manifest.
    """
    job = job_id_or_job if isinstance(job_id_or_job, Job) else Job.load(job_id_or_job)
    clips = json.loads(job.clips_json_path.read_text()).get("clips", [])
    segments = json.loads(job.transcript_path.read_text()).get("segments", [])
    if not 1 <= idx <= len(clips):
        raise IndexError(f"clip {idx} out of range (1..{len(clips)})")
    target_aspects = tuple(aspects) if aspects else config.ASPECT_RATIOS

    manifest_path = job.clips_dir / "render.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"clips": []}
    existing = next((c for c in manifest.get("clips", []) if c.get("index") == idx), None)
    prev_outputs = dict(existing.get("outputs", {})) if existing else {}
    # carry framing forward for aspects we're NOT re-rendering this time
    merged_tf = dict((existing or {}).get("transforms", {}))
    merged_tf.update(transforms or {})

    result = render_clip(job, clips[idx - 1], idx, segments, target_aspects,
                         x_offset, caption_mode, transforms=merged_tf,
                         prev_outputs=prev_outputs)
    # patch render.json for this clip so the library/UI reflect the re-render
    others = [c for c in manifest.get("clips", []) if c.get("index") != idx]
    manifest["clips"] = sorted(others + [result], key=lambda c: c["index"])
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return result


def render_job(job_id_or_job, aspects: tuple[str, ...] = config.ASPECT_RATIOS,
               x_offset: float = 0.0, caption_mode: str = "overlay",
               transforms: dict | None = None, on_aspect_done=None) -> Path:
    job = job_id_or_job if isinstance(job_id_or_job, Job) else Job.load(job_id_or_job)
    clips_data = json.loads(job.clips_json_path.read_text())
    transcript = json.loads(job.transcript_path.read_text())
    segments = transcript.get("segments", [])
    clips = clips_data.get("clips", [])
    if not clips:
        raise ValueError("No clips to render — run select first.")

    total_units = max(1, len(clips) * len(aspects))
    done_units = [0]
    job.update_stage("render", "running", progress=0.0,
                     clips_done=0, clips_total=len(clips))
    log.info("render: %d clip(s) x %d aspect(s), captions=%s",
             len(clips), len(aspects), caption_mode)
    manifest_path = job.clips_dir / "render.json"
    rendered = []

    def make_cb(clip_no):
        def cb(aspect, path):
            done_units[0] += 1
            job.set_progress("render", done_units[0] / total_units,
                             clips_done=len(rendered), clips_total=len(clips))
            if on_aspect_done:
                on_aspect_done(clip_no, aspect, path)
        return cb

    for i, c in enumerate(clips):
        rendered.append(render_clip(job, c, i + 1, segments, aspects, x_offset,
                                    caption_mode, transforms=transforms,
                                    on_aspect_done=make_cb(i + 1)))
        # incremental manifest so the UI surfaces each clip the moment it's ready
        manifest_path.write_text(json.dumps({"clips": rendered}, indent=2))
        job.set_progress("render", done_units[0] / total_units,
                         clips_done=len(rendered), clips_total=len(clips))
    log.info("render: done — %d clip(s)", len(rendered))
    job.update_stage("render", "done", clips=len(rendered),
                     aspects=list(aspects), captions=caption_mode, progress=1.0)
    return manifest_path
