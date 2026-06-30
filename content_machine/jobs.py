"""Per-job storage layout + manifest.

A job is one source video. Its id is the content hash of the video bytes, so
re-ingesting the same file is idempotent and cache-keyed. Everything lives under
`data/<job_id>/`:

    data/<job_id>/
      job.json          # manifest: stage statuses, source path, tool versions
      source<ext>       # copy of the source video
      audio.wav         # 16kHz mono extract
      transcript.json   # segments + word timing
      clips.json        # selected clip candidates (phase 2)
      clips/            # rendered clips + thumbnails (phase 3)

`job.json` tracks per-stage completion so a crash resumes from the last good
stage and never re-does expensive work (transcribe / select / render).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path

from . import config

STAGES = ("ingest", "transcribe", "select", "render")


def compute_job_id(video_path: str | Path, length: int = 16) -> str:
    """Stable id = truncated sha256 of the file's bytes (streamed, any size)."""
    h = hashlib.sha256()
    with open(video_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


@dataclass
class Job:
    job_id: str
    source_name: str
    data_dir: Path

    @classmethod
    def for_video(cls, video_path: str | Path) -> "Job":
        video_path = Path(video_path)
        job_id = compute_job_id(video_path)
        return cls(job_id=job_id, source_name=video_path.name, data_dir=config.DATA_DIR / job_id)

    @classmethod
    def load(cls, job_id: str) -> "Job":
        d = config.DATA_DIR / job_id
        if not (d / "job.json").exists():
            raise FileNotFoundError(f"No job found: {job_id}")
        manifest = json.loads((d / "job.json").read_text())
        return cls(job_id=job_id, source_name=manifest.get("source_name", ""), data_dir=d)

    # --- paths ---------------------------------------------------------------
    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "job.json"

    def source_path(self, ext: str = "") -> Path:
        return self.data_dir / f"source{ext}"

    @property
    def audio_path(self) -> Path:
        return self.data_dir / "audio.wav"

    @property
    def transcript_path(self) -> Path:
        return self.data_dir / "transcript.json"

    @property
    def clips_json_path(self) -> Path:
        return self.data_dir / "clips.json"

    @property
    def clips_dir(self) -> Path:
        return self.data_dir / "clips"

    # --- manifest ------------------------------------------------------------
    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def load_manifest(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {
            "job_id": self.job_id,
            "source_name": self.source_name,
            "created_at": time.time(),
            "stages": {s: {"status": "pending"} for s in STAGES},
            "tools": {},
        }

    def save_manifest(self, manifest: dict) -> None:
        self.ensure_dirs()
        self.manifest_path.write_text(json.dumps(manifest, indent=2))

    def update_stage(self, stage: str, status: str, **extra) -> dict:
        """Set a stage's status (pending|running|done|error) + optional metadata."""
        if stage not in STAGES:
            raise ValueError(f"Unknown stage: {stage}")
        manifest = self.load_manifest()
        entry = {"status": status, "updated_at": time.time()}
        entry.update(extra)
        manifest.setdefault("stages", {})[stage] = entry
        self.save_manifest(manifest)
        return manifest

    def set_progress(self, stage: str, progress: float | None = None, **extra) -> dict:
        """Merge a progress fraction (0..1) + metadata into a stage WITHOUT
        touching its status — for frequent updates during a running stage."""
        if stage not in STAGES:
            raise ValueError(f"Unknown stage: {stage}")
        manifest = self.load_manifest()
        stages = manifest.setdefault("stages", {})
        entry = stages.get(stage) or {"status": "running"}
        if progress is not None:
            entry["progress"] = max(0.0, min(1.0, float(progress)))
        entry.update(extra)
        entry["updated_at"] = time.time()
        stages[stage] = entry
        self.save_manifest(manifest)
        return entry

    def stage_status(self, stage: str) -> str:
        return self.load_manifest().get("stages", {}).get(stage, {}).get("status", "pending")
