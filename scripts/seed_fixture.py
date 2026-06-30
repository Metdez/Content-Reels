"""Seed a fully-rendered fixture job into the live DATA_DIR for Playwright / manual QA.

Unlike the unit-test ``seed_job`` fixture (placeholder bytes, instant), this writes
*real* short mp4s with the correct per-aspect dimensions using the vendored ffmpeg,
so ``/job/<id>`` renders a working review grid and ``/job/<id>/clip/<n>/edit`` loads a
real source video — with no transcribe/select/render pipeline run (seconds, not minutes).

Usage:
    python scripts/seed_fixture.py [--job-id e2eseed0001] [--clips 2] [--seconds 1]

Prints the job id and URLs. Idempotent: re-running overwrites the same job dir.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from content_machine import config

ASPECT_SLUG = {"9:16": "9x16", "1:1": "1x1", "16:9": "16x9"}
ASPECT_DIMS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
SRC_DIMS = (1920, 1080)


def _ffmpeg(*args: str) -> None:
    cmd = [config.FFMPEG, "-y", "-loglevel", "error", *args]
    subprocess.run(cmd, check=True)


def _make_clip(path: Path, w: int, h: int, seconds: float, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # drawtext uses ':' as its option separator — keep labels colon-free.
    safe = label.replace(":", " ").replace("'", "")
    _ffmpeg(
        "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=24:duration={seconds}",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=" + str(seconds),
        "-vf", f"drawtext=text='{safe}':fontcolor=white:fontsize={h // 12}:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        "-movflags", "+faststart", str(path),
    )


def _make_thumb(src: Path, thumb: Path) -> None:
    _ffmpeg("-i", str(src), "-frames:v", "1", "-q:v", "3", str(thumb))


def seed(job_id: str, n_clips: int, seconds: float) -> Path:
    d = config.DATA_DIR / job_id
    (d / "clips").mkdir(parents=True, exist_ok=True)

    # real source video at SRC_DIMS
    src = d / "source.mp4"
    _make_clip(src, SRC_DIMS[0], SRC_DIMS[1], max(seconds * n_clips, 2.0), "SOURCE")

    # transcript with word timing
    segments, t = [], 0.0
    for i in range(8):
        text = f"This is sentence number {i} in the talk."
        words, wt = [], t
        for w in text.split():
            words.append({"word": w, "start": round(wt, 3), "end": round(wt + 0.3, 3)})
            wt += 0.35
        segments.append({"start": round(t, 3), "end": round(wt, 3), "text": text, "words": words})
        t = round(wt + 0.2, 3)
    duration = t
    (d / "transcript.json").write_text(json.dumps(
        {"language": "en", "duration": duration, "segments": segments, "vad_dropped": 0}, indent=2))

    aspects = ("9:16", "1:1", "16:9")
    seg_per = max(1, len(segments) // n_clips)
    clips_meta, render_clips = [], []
    for i in range(n_clips):
        s_seg = i * seg_per
        e_seg = min(len(segments) - 1, s_seg + seg_per)
        cm = {"start": segments[s_seg]["start"], "end": segments[e_seg]["end"],
              "start_seg": s_seg, "end_seg": e_seg, "title": f"Clip {i + 1}",
              "rationale": f"Strong, self-contained hook {i + 1}", "score": round(0.92 - i * 0.07, 2)}
        clips_meta.append(cm)
        cdir = d / "clips" / f"clip{i + 1:02d}"
        outputs = {}
        for a in aspects:
            w, h = ASPECT_DIMS[a]
            f = cdir / f"{ASPECT_SLUG[a]}.mp4"
            _make_clip(f, w, h, seconds, f"Clip {i + 1} {a}")
            outputs[a] = str(f)
        thumb = cdir / "thumb.jpg"
        _make_thumb(cdir / "9x16.mp4", thumb)
        tf = {a: {"zoom": 1.0, "x": 0.0, "y": 0.0} for a in aspects}
        (cdir / "edit.json").write_text(json.dumps(
            {"start": cm["start"], "end": cm["end"], "transforms": tf,
             "audio": {"mute": False, "volume": 1.0}}, indent=2))
        render_clips.append({"index": i + 1, "dir": str(cdir), "outputs": outputs,
                             "thumb": str(thumb), "captions": "overlay", "title": cm["title"],
                             "score": cm["score"], "transforms": tf, "start": cm["start"],
                             "end": cm["end"], "audio": {"mute": False, "volume": 1.0}})
    (d / "clips.json").write_text(json.dumps(
        {"transcript_hash": "seedhash", "clips": clips_meta}, indent=2))
    (d / "clips" / "render.json").write_text(json.dumps({"clips": render_clips}, indent=2))
    (d / "job.json").write_text(json.dumps({
        "job_id": job_id, "source_name": "seed_talk.mp4", "created_at": time.time(),
        "content_id": job_id[:10], "source_ext": ".mp4", "source_dims": list(SRC_DIMS),
        "awaiting_run": False,
        "run_params": {"model": "base.en", "max_clips": n_clips, "captions": "overlay",
                       "transforms": {a: {"zoom": 1.0, "x": 0.0, "y": 0.0} for a in aspects}},
        "tools": {"whisper_model": "base.en"},
        "stages": {
            "ingest": {"status": "done", "source": "source.mp4"},
            "transcribe": {"status": "done", "segments": len(segments), "duration": duration},
            "select": {"status": "done", "clips": n_clips},
            "render": {"status": "done", "clips": n_clips, "aspects": len(aspects),
                       "clips_done": n_clips, "clips_total": n_clips},
        },
    }, indent=2))
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a rendered fixture job for E2E/manual QA.")
    ap.add_argument("--job-id", default="e2eseed0001")
    ap.add_argument("--clips", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=1.0)
    args = ap.parse_args()
    config.require_tool(config.FFMPEG, "Install ffmpeg or run scripts/setup.ps1 (vendored)")
    d = seed(args.job_id, args.clips, args.seconds)
    print(f"Seeded job {args.job_id} -> {d}")
    print(f"  Review grid: http://127.0.0.1:8000/job/{args.job_id}")
    print(f"  Clip editor: http://127.0.0.1:8000/job/{args.job_id}/clip/1/edit")


if __name__ == "__main__":
    main()
