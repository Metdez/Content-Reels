"""Phase 28 (VAL-01/03/04/06): input-validation & hardening tests.

VAL-02 (run_claude resilience / chunk-skip) lives in test_select_transcribe.py and
VAL-05 (/media scoping) in test_api.py, next to their characterization siblings.
"""

from __future__ import annotations

import json

from conftest import seed_job

from content_machine import config, render

_MP4 = bytes.fromhex("0000001c66747970697336300000020069736f6d69736f3261766331") + b"\x00" * 16


# --- VAL-01: zoom cap --------------------------------------------------------
def test_normalize_transforms_caps_zoom_at_max():
    out = render.normalize_transforms({"9:16": {"zoom": 100}}, aspects=("9:16",))
    assert out["9:16"]["zoom"] == render.MAX_ZOOM == 5.0


def test_normalize_transforms_zoom_floor_still_one():
    out = render.normalize_transforms({"9:16": {"zoom": 0.1}}, aspects=("9:16",))
    assert out["9:16"]["zoom"] == 1.0


# --- VAL-01: trim clamping ---------------------------------------------------
def test_edit_trim_clamped_to_source_bounds(seeded_job, monkeypatch):
    client, job_id, job_dir = seeded_job
    duration = json.loads((job_dir / "transcript.json").read_text())["duration"]
    captured = {}
    monkeypatch.setattr(client.app_module, "_enqueue_rerender",
                        lambda jid, idx, edit, aspects: captured.update(edit=edit))
    # start < 0 and end far past the source duration -> both get clamped
    resp = client.post(f"/api/job/{job_id}/clip/1/edit",
                       json={"start": -5.0, "end": duration + 100.0})
    assert resp.status_code == 200
    assert captured["edit"]["start"] == 0.0
    assert captured["edit"]["end"] == duration


# --- VAL-03: upload collision ------------------------------------------------
def test_two_same_name_uploads_produce_distinct_jobs(client, monkeypatch):
    monkeypatch.setattr(client.app_module.render, "probe_dims", lambda src: (1920, 1080))
    ids = []
    for _ in range(2):
        resp = client.post("/upload", files={"video": ("talk.mp4", _MP4, "video/mp4")},
                           follow_redirects=False)
        assert resp.status_code == 303
        ids.append(resp.headers["location"].rsplit("/", 1)[-1])
    assert ids[0] != ids[1]                       # no collision -> two separate jobs
    for jid in ids:
        assert (client.data_dir / jid / "source.mp4").exists()


# --- VAL-04: friendly empty/silent transcript --------------------------------
def test_empty_transcript_surfaces_friendly_message(client, monkeypatch):
    job_id = "emptyjob01"
    job_dir = seed_job(client.data_dir, job_id)
    appmod = client.app_module

    def fake_transcribe(source, model=None, job=None):
        job.transcript_path.write_text(json.dumps({"segments": [], "duration": 0}))
        return job

    def fail_select(*a, **k):
        raise AssertionError("select_clips must not run on an empty transcript")

    monkeypatch.setattr(appmod.transcribe, "transcribe", fake_transcribe)
    monkeypatch.setattr(appmod.select, "select_clips", fail_select)

    source = next(job_dir.glob("source.*"))
    appmod._run_pipeline(job_id, source, None, 6, 0.0, "overlay")

    assert "No clip-worthy moments" in appmod.RUNNING[job_id]["error"]
    manifest = json.loads((job_dir / "job.json").read_text())
    assert manifest["stages"]["select"]["status"] == "error"
    assert "No clip-worthy moments" in manifest["stages"]["select"]["error"]


# --- VAL-06: platform-aware tool hints ---------------------------------------
def test_tool_hints_windows_point_to_setup_ps1(monkeypatch):
    monkeypatch.setattr(config.os, "name", "nt")
    assert "setup.ps1" in config.ffmpeg_hint()
    assert "setup.ps1" in config.whisper_hint()
    assert "brew" not in config.ffmpeg_hint()


def test_tool_hints_posix_keep_brew(monkeypatch):
    monkeypatch.setattr(config.os, "name", "posix")
    assert "brew install ffmpeg" in config.ffmpeg_hint()
    assert "setup.sh" in config.whisper_hint()
