"""QA-09 — render orchestration coverage for content_machine/render.py.

Exercises the orchestration layer end-to-end with the real ffmpeg/ffprobe
encode STUBBED OUT (no subprocess is ever spawned):

  * probe_dims    — ffprobe CSV parse -> (w, h)
  * render_clip   — per-aspect outputs + thumbnail + transform/edit threading
  * render_job    — multi-clip x multi-aspect loop, render.json streaming,
                    progress callbacks (set_progress + on_aspect_done)
  * rerender_one  — partial (single-aspect) re-render, edit.json merge,
                    render.json patch that keeps other clips
  * _run_encode   — GPU -> x264 transparent fallback
  * audio_chain / build_overlay_cmd / build_thumbnail_cmd — command arrays

compute_crop / crop_scale_filter / normalize_transforms / build_render_cmd are
already covered by tests/test_render.py and are intentionally NOT duplicated.

BUG NOTE (characterized, not fixed): see
test_rerender_one_nonatomic_write_loses_concurrent_clip_update — render.json is
read-modified-written with no lock/re-read and a non-atomic write_text(), so a
concurrent update to a *different* clip is silently lost.
"""

from __future__ import annotations

import json
import subprocess
import types
from pathlib import Path

import pytest

from content_machine import config, hwaccel
from content_machine import render as r
from content_machine.jobs import Job


# --- helpers -----------------------------------------------------------------
def _touch_output(cmd) -> None:
    """Create the ffmpeg output file (always the last token of the command) so
    anything that later stats the rendered artifact sees it, like a real encode."""
    out = Path(str(cmd[-1]))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"\x00")


class EncodeRecorder:
    """Stand-in for render.stream_run / render.run: records the command, writes
    the expected output file, and reports success — without launching ffmpeg."""

    def __init__(self):
        self.stream_calls = []
        self.run_calls = []

    def stream_run(self, cmd, log=None, desc=None, on_line=None, **kw):
        self.stream_calls.append((list(cmd), desc))
        _touch_output(cmd)
        return 0

    def run(self, cmd, log=None, desc=None, **kw):
        self.run_calls.append((list(cmd), desc))
        _touch_output(cmd)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")


def _seed_job_inputs(data_dir, job_id, *, n_clips=2,
                     aspects=("9:16", "1:1", "16:9"), with_render_json=False):
    """Write the minimal inputs the render_* functions read: source.*,
    transcript.json, clips.json (+ optionally a prior clips/render.json that
    already carries per-aspect outputs, as rerender_one expects)."""
    d = data_dir / job_id
    (d / "clips").mkdir(parents=True, exist_ok=True)
    (d / "source.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16)

    segments, t = [], 0.0
    for i in range(6):
        segments.append({"start": round(t, 3), "end": round(t + 3.0, 3),
                         "text": f"Sentence {i} here.", "words": []})
        t += 3.2
    (d / "transcript.json").write_text(json.dumps(
        {"language": "en", "duration": round(t, 3), "segments": segments}))

    clips = []
    for i in range(n_clips):
        s = round(i * 3.2, 3)
        clips.append({"start": s, "end": round(s + 3.0, 3),
                      "title": f"Clip {i + 1}", "score": round(0.9 - 0.1 * i, 3)})
    (d / "clips.json").write_text(json.dumps({"clips": clips}))

    if with_render_json:
        render_clips = []
        for i, c in enumerate(clips, start=1):
            cdir = d / "clips" / f"clip{i:02d}"
            cdir.mkdir(parents=True, exist_ok=True)
            outputs = {}
            for a in aspects:
                f = cdir / f"{r.ASPECT_SLUG[a]}.mp4"
                f.write_bytes(b"old")
                outputs[a] = str(f)
            (cdir / "thumb.jpg").write_bytes(b"\xff\xd8\xff\xd9")
            render_clips.append({
                "index": i, "dir": str(cdir), "outputs": outputs,
                "thumb": str(cdir / "thumb.jpg"), "captions": "overlay",
                "title": c["title"], "score": c["score"],
                "transforms": r.normalize_transforms(None),
                "start": c["start"], "end": c["end"],
                "audio": {"mute": False, "volume": 1.0},
            })
        (d / "clips" / "render.json").write_text(
            json.dumps({"clips": render_clips}, indent=2))
    return d


def _make_job(data_dir, job_id):
    return Job(job_id=job_id, source_name="source.mp4", data_dir=data_dir / job_id)


@pytest.fixture
def stub_encode(tmp_path, monkeypatch):
    """Neutralize every real subprocess in the render path and point DATA_DIR at
    tmp_path. Returns the EncodeRecorder so tests can introspect encode calls."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(r.config, "require_tool", lambda *a, **k: None)
    monkeypatch.setattr(r, "probe_dims", lambda src: (1920, 1080))
    monkeypatch.setattr(r.hwaccel, "select_encoder", lambda *a, **k: r.hwaccel.X264)

    def fake_pngs(events, w, h, outdir, font=None):
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        png = outdir / "cap_000.png"
        png.write_bytes(b"\x89PNG")
        return [{"png": png, "start": 0.0, "end": 1.0}]
    monkeypatch.setattr(r.captions, "render_caption_pngs", fake_pngs)

    rec = EncodeRecorder()
    monkeypatch.setattr(r, "stream_run", rec.stream_run)
    monkeypatch.setattr(r, "run", rec.run)
    return rec


# --- probe_dims --------------------------------------------------------------
def test_probe_dims_parses_ffprobe_csv(monkeypatch):
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return types.SimpleNamespace(stdout="1920x1080\n", stderr="", returncode=0)
    monkeypatch.setattr(r.subprocess, "run", fake_run)

    assert r.probe_dims(Path("video.mp4")) == (1920, 1080)
    # shells out to ffprobe for the v:0 width,height in csv form
    assert config.FFPROBE in captured["cmd"]
    assert "stream=width,height" in captured["cmd"]
    assert "csv=p=0:s=x" in captured["cmd"]


# --- render_clip -------------------------------------------------------------
def test_render_clip_produces_all_aspects_thumb_and_threads_transforms(stub_encode, tmp_path):
    d = _seed_job_inputs(tmp_path, "jobclip0001", n_clips=1)
    job = _make_job(tmp_path, "jobclip0001")
    clips = json.loads((d / "clips.json").read_text())["clips"]
    segments = json.loads((d / "transcript.json").read_text())["segments"]

    fired = []
    aspects = ("9:16", "1:1", "16:9")
    result = r.render_clip(job, clips[0], 1, segments, aspects=aspects,
                           transforms={"1:1": {"zoom": 1.8}},
                           on_aspect_done=lambda a, p: fired.append((a, p)))

    # outputs dict keys == requested aspects, each an existing rendered file
    assert set(result["outputs"]) == set(aspects)
    for a in aspects:
        out = Path(result["outputs"][a])
        assert out.exists() and out.name == f"{r.ASPECT_SLUG[a]}.mp4"
    # thumbnail rendered next to the clip outputs
    assert Path(result["thumb"]).exists() and result["thumb"].endswith("thumb.jpg")
    # transforms threaded through, per-aspect normalized; the 1:1 zoom survived
    assert set(result["transforms"]) == set(aspects)
    assert result["transforms"]["1:1"]["zoom"] == 1.8
    # on_aspect_done fired once per aspect, in order
    assert [a for a, _ in fired] == list(aspects)
    # metadata carried through from the clip + defaults
    assert result["index"] == 1
    assert result["captions"] == "overlay"
    assert result["start"] == clips[0]["start"] and result["end"] == clips[0]["end"]
    assert result["audio"] == {"mute": False, "volume": 1.0}
    # one streamed encode per aspect + one (non-streamed) thumbnail run
    assert len(stub_encode.stream_calls) == 3
    assert len(stub_encode.run_calls) == 1


def test_render_clip_edit_overrides_trim_captions_audio(stub_encode, tmp_path):
    d = _seed_job_inputs(tmp_path, "jobclip0002", n_clips=1)
    job = _make_job(tmp_path, "jobclip0002")
    clips = json.loads((d / "clips.json").read_text())["clips"]
    segments = json.loads((d / "transcript.json").read_text())["segments"]

    edit = {"start": 1.0, "end": 2.5,
            "audio": {"mute": True, "volume": 0.5},
            "captions": {"mode": "none"}}
    result = r.render_clip(job, clips[0], 1, segments, aspects=("9:16",), edit=edit)

    assert result["start"] == 1.0 and result["end"] == 2.5
    assert result["audio"] == {"mute": True, "volume": 0.5}
    assert result["captions"] == "none"           # edit captions mode wins
    assert set(result["outputs"]) == {"9:16"}


def test_render_clip_edit_custom_caption_segments_drive_events(stub_encode, tmp_path, monkeypatch):
    d = _seed_job_inputs(tmp_path, "jobclip0004", n_clips=1)
    job = _make_job(tmp_path, "jobclip0004")
    clips = json.loads((d / "clips.json").read_text())["clips"]
    segments = json.loads((d / "transcript.json").read_text())["segments"]

    seen_events = []

    def recording_pngs(events, w, h, outdir, font=None):
        seen_events.append(events)
        return [{"png": Path(outdir) / "c.png", "start": 0.0, "end": 1.0}]
    monkeypatch.setattr(r.captions, "render_caption_pngs", recording_pngs)

    edit = {"captions": {"segments": [
        {"start": 0.0, "end": 1.0, "text": "custom one"},
        {"start": 1.0, "end": 2.0, "text": "  "},        # blank text -> filtered out
        {"start": 2.0, "end": 3.0, "text": "custom two"},
    ]}}
    result = r.render_clip(job, clips[0], 1, segments, aspects=("9:16",), edit=edit)

    # explicit edit segments win over auto-derived transcript captions; blanks dropped
    assert [e["text"] for e in seen_events[0]] == ["custom one", "custom two"]
    assert result["captions"] == "overlay"


def test_render_clip_prev_outputs_preserves_untouched_aspects(stub_encode, tmp_path):
    d = _seed_job_inputs(tmp_path, "jobclip0003", n_clips=1)
    job = _make_job(tmp_path, "jobclip0003")
    clips = json.loads((d / "clips.json").read_text())["clips"]
    segments = json.loads((d / "transcript.json").read_text())["segments"]

    prev = {"1:1": "/old/1x1.mp4", "16:9": "/old/16x9.mp4"}
    fired = []
    result = r.render_clip(job, clips[0], 1, segments, aspects=("9:16",),
                           prev_outputs=prev,
                           on_aspect_done=lambda a, p: fired.append(a))

    # only 9:16 re-encoded; 1:1 & 16:9 carried over untouched from prev_outputs
    assert result["outputs"]["1:1"] == "/old/1x1.mp4"
    assert result["outputs"]["16:9"] == "/old/16x9.mp4"
    assert Path(result["outputs"]["9:16"]).exists()
    assert fired == ["9:16"]                       # callback fires only for rendered aspect


def test_render_clip_hyperframes_path(stub_encode, tmp_path, monkeypatch):
    d = _seed_job_inputs(tmp_path, "jobhf0001", n_clips=1)
    job = _make_job(tmp_path, "jobhf0001")
    clips = json.loads((d / "clips.json").read_text())["clips"]
    segments = json.loads((d / "transcript.json").read_text())["segments"]

    monkeypatch.setattr(r.captions, "hyperframes_available", lambda: True)

    def fake_overlay(events, w, h, out_path, *a, **k):
        mov = Path(str(out_path)).with_suffix(".mov")
        mov.parent.mkdir(parents=True, exist_ok=True)
        mov.write_bytes(b"mov")
        return mov
    monkeypatch.setattr(r.captions, "render_hyperframes_overlay", fake_overlay)

    fired = []
    result = r.render_clip(job, clips[0], 1, segments, aspects=("9:16",),
                           caption_mode="hyperframes",
                           on_aspect_done=lambda a, p: fired.append(a))

    assert result["captions"] == "hyperframes"
    assert Path(result["outputs"]["9:16"]).exists()
    assert fired == ["9:16"]
    # hyperframes uses the non-streamed `run` path: base render + composite + thumb
    assert len(stub_encode.run_calls) == 3
    assert len(stub_encode.stream_calls) == 0


def test_render_clip_hyperframes_failure_falls_back_to_overlay(stub_encode, tmp_path, monkeypatch):
    d = _seed_job_inputs(tmp_path, "jobhf0002", n_clips=1)
    job = _make_job(tmp_path, "jobhf0002")
    clips = json.loads((d / "clips.json").read_text())["clips"]
    segments = json.loads((d / "transcript.json").read_text())["segments"]

    monkeypatch.setattr(r.captions, "hyperframes_available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("hyperframes exploded")
    monkeypatch.setattr(r.captions, "render_hyperframes_overlay", boom)

    result = r.render_clip(job, clips[0], 1, segments, aspects=("9:16",),
                           caption_mode="hyperframes")

    # transparently degraded to the Pillow overlay caption path
    assert result["captions"] == "overlay"
    assert Path(result["outputs"]["9:16"]).exists()


# --- render_job --------------------------------------------------------------
def test_render_job_full_loop_writes_manifest_and_streams_progress(stub_encode, tmp_path, monkeypatch):
    _seed_job_inputs(tmp_path, "jobfull0001", n_clips=2)
    job = _make_job(tmp_path, "jobfull0001")
    aspects = ("9:16", "1:1")
    manifest_path = job.clips_dir / "render.json"

    # spy on set_progress to confirm it fires and clips_done advances
    progress_calls = []
    orig_set_progress = job.set_progress

    def spy_progress(stage, progress=None, **extra):
        progress_calls.append((stage, progress, extra.get("clips_done")))
        return orig_set_progress(stage, progress, **extra)
    monkeypatch.setattr(job, "set_progress", spy_progress)

    # on_aspect_done observes how many clips are already streamed to render.json
    stream_obs = []

    def on_done(clip_no, aspect, path):
        n = len(json.loads(manifest_path.read_text())["clips"]) if manifest_path.exists() else 0
        stream_obs.append((clip_no, aspect, n))

    out = r.render_job(job, aspects=aspects, on_aspect_done=on_done)

    assert out == manifest_path and out.exists()
    manifest = json.loads(out.read_text())
    assert [c["index"] for c in manifest["clips"]] == [1, 2]
    for c in manifest["clips"]:
        assert set(c["outputs"]) == set(aspects)
        assert Path(c["thumb"]).exists()

    # on_aspect_done fired once per (clip, aspect)
    assert [(cn, a) for cn, a, _ in stream_obs] == [
        (1, "9:16"), (1, "1:1"), (2, "9:16"), (2, "1:1")]
    # streaming: clip 1's callbacks see no manifest yet; by clip 2, clip 1 is written
    assert [n for cn, _, n in stream_obs if cn == 1] == [0, 0]
    assert [n for cn, _, n in stream_obs if cn == 2] == [1, 1]

    # set_progress fired with a non-decreasing clips_done that reaches n_clips
    clips_done_seq = [cd for _, _, cd in progress_calls if cd is not None]
    assert clips_done_seq and clips_done_seq == sorted(clips_done_seq)
    assert max(clips_done_seq) == 2

    # final job manifest reflects completion
    stage = job.load_manifest()["stages"]["render"]
    assert stage["status"] == "done" and stage["progress"] == 1.0
    assert stage["clips"] == 2 and stage["aspects"] == list(aspects)
    assert stage["captions"] == "overlay"


def test_render_job_raises_when_no_clips(stub_encode, tmp_path):
    d = tmp_path / "jobempty01"
    (d / "clips").mkdir(parents=True)
    (d / "source.mp4").write_bytes(b"x")
    (d / "clips.json").write_text(json.dumps({"clips": []}))
    (d / "transcript.json").write_text(json.dumps({"segments": []}))
    job = _make_job(tmp_path, "jobempty01")

    with pytest.raises(ValueError, match="No clips"):
        r.render_job(job)


# --- rerender_one ------------------------------------------------------------
def test_rerender_one_reencodes_only_requested_aspect_preserves_others(stub_encode, tmp_path):
    _seed_job_inputs(tmp_path, "jobre0001", n_clips=2, with_render_json=True)
    job = _make_job(tmp_path, "jobre0001")
    manifest_path = job.clips_dir / "render.json"
    before = json.loads(manifest_path.read_text())
    clip1_before = next(c for c in before["clips"] if c["index"] == 1)
    clip2_before = next(c for c in before["clips"] if c["index"] == 2)

    fired = []
    result = r.rerender_one(job, 1, aspects=("9:16",),
                            transforms={"9:16": {"zoom": 1.5}},
                            on_aspect_done=lambda a, p: fired.append(a))

    # only the requested aspect was re-encoded
    assert fired == ["9:16"]
    # untouched aspects preserved from the prior render manifest
    assert result["outputs"]["1:1"] == clip1_before["outputs"]["1:1"]
    assert result["outputs"]["16:9"] == clip1_before["outputs"]["16:9"]
    assert Path(result["outputs"]["9:16"]).exists()

    # render.json patched for clip 1 WITHOUT clobbering clip 2
    after = json.loads(manifest_path.read_text())
    assert [c["index"] for c in after["clips"]] == [1, 2]
    assert next(c for c in after["clips"] if c["index"] == 2) == clip2_before
    clip1_after = next(c for c in after["clips"] if c["index"] == 1)
    assert clip1_after["transforms"]["9:16"]["zoom"] == 1.5


def test_rerender_one_merges_edit_json_over_prior(stub_encode, tmp_path):
    _seed_job_inputs(tmp_path, "jobre0002", n_clips=1, with_render_json=True)
    job = _make_job(tmp_path, "jobre0002")
    edit_path = job.clips_dir / "clip01" / "edit.json"
    # prior persisted edit: a volume bump + a 1:1 zoom
    edit_path.write_text(json.dumps({
        "audio": {"mute": False, "volume": 2.0},
        "transforms": {"1:1": {"zoom": 1.3}},
    }))

    result = r.rerender_one(job, 1, aspects=("9:16",),
                            edit={"start": 1.0, "end": 2.0},
                            transforms={"9:16": {"zoom": 1.7}})

    stored = json.loads(edit_path.read_text())
    # new trim merged in; prior audio preserved
    assert stored["start"] == 1.0 and stored["end"] == 2.0
    assert stored["audio"] == {"mute": False, "volume": 2.0}
    # transforms merged: prior 1:1 kept, new 9:16 added
    assert stored["transforms"]["1:1"] == {"zoom": 1.3}
    assert stored["transforms"]["9:16"] == {"zoom": 1.7}
    # the merged edit actually drove the render
    assert result["start"] == 1.0 and result["end"] == 2.0
    assert result["audio"]["volume"] == 2.0


def test_rerender_one_out_of_range_raises(stub_encode, tmp_path):
    _seed_job_inputs(tmp_path, "jobre0003", n_clips=2, with_render_json=True)
    job = _make_job(tmp_path, "jobre0003")
    with pytest.raises(IndexError):
        r.rerender_one(job, 5)
    with pytest.raises(IndexError):
        r.rerender_one(job, 0)


def test_rerender_one_nonatomic_write_loses_concurrent_clip_update(stub_encode, tmp_path):
    """QA finding (characterization, NOT a fix).

    rerender_one does a read-modify-write of clips/render.json with no locking,
    no re-read before write, and a non-atomic write_text(). Any update to a
    *different* clip that lands after rerender_one has read the manifest but
    before it writes is silently lost.

    Simulated deterministically: an on_aspect_done hook (which fires DURING
    render_clip — after rerender_one has already read the manifest into memory)
    rewrites clip 2 on disk. rerender_one then overwrites render.json from its
    STALE in-memory copy, clobbering that concurrent change.
    """
    _seed_job_inputs(tmp_path, "jobre0004", n_clips=2, with_render_json=True)
    job = _make_job(tmp_path, "jobre0004")
    manifest_path = job.clips_dir / "render.json"

    def concurrent_writer(aspect, path):
        m = json.loads(manifest_path.read_text())
        for c in m["clips"]:
            if c["index"] == 2:
                c["title"] = "CONCURRENTLY UPDATED"
        manifest_path.write_text(json.dumps(m, indent=2))

    r.rerender_one(job, 1, aspects=("9:16",), on_aspect_done=concurrent_writer)

    after = json.loads(manifest_path.read_text())
    clip2 = next(c for c in after["clips"] if c["index"] == 2)
    # CURRENT (buggy) behavior: the concurrent update is lost. A correct,
    # atomic/locked implementation would instead preserve "CONCURRENTLY UPDATED".
    assert clip2["title"] != "CONCURRENTLY UPDATED"


# --- command builders (not covered by test_render.py) ------------------------
def test_audio_chain_loudnorm_only_when_no_volume():
    assert r.audio_chain(None) == r.AUDIO_FILTER


def test_audio_chain_prepends_volume_scale():
    chain = r.audio_chain(1.5)
    assert chain == f"volume=1.500,{r.AUDIO_FILTER}"
    assert chain.startswith("volume=1.500,") and "loudnorm" in chain


def test_build_thumbnail_cmd_single_frame_input_seek():
    cmd = r.build_thumbnail_cmd(Path("s.mp4"), 12.0, Path("t.jpg"))
    assert cmd.index("-ss") < cmd.index("-i")      # input seek (fast + frame-accurate)
    assert "12.000" in cmd
    assert cmd[cmd.index("-frames:v") + 1] == "1"
    assert cmd[cmd.index("-q:v") + 1] == "3"
    assert cmd[-1] == "t.jpg"


def test_build_overlay_cmd_composites_overlay_with_audio_normalize():
    cmd = r.build_overlay_cmd(Path("base.mp4"), Path("ov.mov"), Path("out.mp4"))
    assert cmd[cmd.index("-filter_complex") + 1] == "[0:v][1:v]overlay=0:0:format=auto[v]"
    assert cmd[cmd.index("-map") + 1] == "[v]"
    assert "0:a?" in cmd
    assert cmd[cmd.index("-af") + 1] == r.AUDIO_FILTER
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert "libx264" in cmd                         # defaults to the x264 profile
    assert cmd[-3:] == ["-movflags", "+faststart", "out.mp4"]


def test_build_overlay_cmd_uses_given_encoder():
    cmd = r.build_overlay_cmd(Path("b.mp4"), Path("o.mov"), Path("out.mp4"),
                              encoder=hwaccel.PROFILES["nvenc"])
    assert "h264_nvenc" in cmd and "libx264" not in cmd


# --- _run_encode GPU -> x264 fallback ----------------------------------------
def test_run_encode_x264_path_skips_gpu(stub_encode, tmp_path):
    out = tmp_path / "x.mp4"
    built = []

    def build(enc):
        built.append(enc["key"])
        return [config.FFMPEG, "-i", "in", *enc["args"], str(out)]

    used = r._run_encode(build, hwaccel.X264, r.log, "direct")
    assert used is hwaccel.X264
    assert built == ["x264"]                        # built once, straight on x264
    assert out.exists()


def test_run_encode_gpu_success_returns_gpu_profile(stub_encode, tmp_path):
    out = tmp_path / "g.mp4"
    nvenc = hwaccel.PROFILES["nvenc"]
    used = r._run_encode(lambda e: [config.FFMPEG, *e["args"], str(out)],
                         nvenc, r.log, "gpu ok")
    assert used is nvenc
    assert out.exists()


def test_run_encode_gpu_failure_falls_back_to_x264(stub_encode, tmp_path, monkeypatch):
    out = tmp_path / "fb.mp4"
    nvenc = hwaccel.PROFILES["nvenc"]
    seen = []

    def flaky_stream(cmd, log=None, desc=None, on_line=None, **kw):
        seen.append(desc)
        if "x264 fallback" not in (desc or ""):     # first (GPU) attempt fails
            raise subprocess.CalledProcessError(1, cmd)
        Path(str(cmd[-1])).write_bytes(b"\x00")      # fallback succeeds + writes output
        return 0
    monkeypatch.setattr(r, "stream_run", flaky_stream)

    used = r._run_encode(lambda e: [config.FFMPEG, *e["args"], str(out)],
                         nvenc, r.log, "gpu boom")
    assert used is hwaccel.X264                       # transparently fell back to CPU
    assert out.exists()
    assert any("x264 fallback" in (d or "") for d in seen)
