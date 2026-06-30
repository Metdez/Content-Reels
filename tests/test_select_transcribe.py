"""QA-11 characterization tests for the impure layers of select.py / transcribe.py.

The pure parsers (prompt build, JSON extraction, index mapping, dedup, chunking,
whisper-JSON parse, silencedetect parse, VAD) are already covered in
test_select.py / test_pipeline.py — NOT duplicated here.

This file pins down the *subprocess-driven* layers with everything stubbed (no
real claude / ffmpeg / whisper binaries are launched):

  select.py     build_claude_cmd, run_claude (timeout / non-zero / chatty stdout /
                is_error / happy), select_clips multi-chunk merge+dedup + cache hit
  transcribe.py build_whisper_cmd (no-language branch), extract_audio, detect_silence,
                run_whisper progress-callback wiring + missing-model guard

These assert CURRENT behavior. Where current behavior is fragile (no retry, raw
JSONDecodeError leaking out of run_claude), the test name + comment flags it as a
Phase 28 fix target rather than asserting a "nicer" behavior that doesn't exist yet.
"""

import json
import subprocess
import types
from pathlib import Path

import pytest

from content_machine import select as s
from content_machine import transcribe as t
from content_machine.jobs import Job

# ---------------------------------------------------------------------------
# select.build_claude_cmd
# ---------------------------------------------------------------------------


def test_build_claude_cmd_is_subscription_json():
    cmd = s.build_claude_cmd()
    assert cmd[0] == s.config.CLAUDE
    assert cmd[1:] == ["-p", "--output-format", "json"]
    # subscription OAuth path, NOT --bare (which would force ANTHROPIC_API_KEY)
    assert "--bare" not in cmd


# ---------------------------------------------------------------------------
# select.run_claude — failure handling (subprocess stubbed)
# ---------------------------------------------------------------------------


def _stub_claude_proc(monkeypatch, *, returncode=0, stdout="", stderr=""):
    """Make config.require_tool a no-op and subprocess.run return a fake proc."""
    monkeypatch.setattr(s.config, "require_tool", lambda *a, **k: None)
    proc = types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(s.subprocess, "run", lambda *a, **k: proc)
    return proc


def test_run_claude_happy_path_extracts_clips_from_chatty_result(monkeypatch):
    # stdout is the --output-format json wrapper; its .result may be chatty,
    # and extract_json_object digs the JSON object out of it.
    wrapper = {
        "type": "result",
        "is_error": False,
        "result": 'Sure! Here you go:\n{"clips": [{"start_seg": 0, "end_seg": 2}]}',
    }
    _stub_claude_proc(monkeypatch, stdout=json.dumps(wrapper))
    out = s.run_claude("prompt")
    assert out["clips"][0]["end_seg"] == 2


def test_run_claude_propagates_timeout(monkeypatch):
    # CHARACTERIZATION: a timeout is re-raised verbatim — no retry/backoff.
    monkeypatch.setattr(s.config, "require_tool", lambda *a, **k: None)

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=k.get("timeout", 1))

    monkeypatch.setattr(s.subprocess, "run", boom)
    with pytest.raises(subprocess.TimeoutExpired):
        s.run_claude("prompt", timeout=1)


def test_run_claude_nonzero_exit_raises_runtimeerror(monkeypatch):
    # CHARACTERIZATION: non-zero exit -> RuntimeError carrying code + stderr; no retry.
    _stub_claude_proc(monkeypatch, returncode=2, stderr="boom: model overloaded")
    with pytest.raises(RuntimeError) as ei:
        s.run_claude("prompt")
    msg = str(ei.value)
    assert "claude -p failed (2)" in msg
    assert "boom: model overloaded" in msg


def test_run_claude_chatty_nonjson_stdout_raises_jsondecodeerror(monkeypatch):
    # BUG / Phase 28 target (select.py:130): run_claude assumes stdout is a JSON
    # wrapper and calls json.loads(proc.stdout) with NO guard. If claude emits
    # plain/chatty text on stdout (exit 0), this leaks a raw json.JSONDecodeError
    # instead of a graceful, typed failure.
    _stub_claude_proc(monkeypatch, stdout="Sure! Here are your clips, no JSON though.")
    with pytest.raises(json.JSONDecodeError):
        s.run_claude("prompt")


def test_run_claude_wrapper_is_error_raises(monkeypatch):
    # Wrapper parses fine but signals is_error -> RuntimeError with the message.
    wrapper = {"type": "result", "is_error": True, "result": "5-hour usage limit reached"}
    _stub_claude_proc(monkeypatch, stdout=json.dumps(wrapper))
    with pytest.raises(RuntimeError) as ei:
        s.run_claude("prompt")
    assert "5-hour usage limit reached" in str(ei.value)


# ---------------------------------------------------------------------------
# select.select_clips — multi-chunk orchestration (run_claude + chunk stubbed)
# ---------------------------------------------------------------------------

# Six 15-second segments; chunk_segments is stubbed to split them 3+3 so we
# exercise the per-chunk loop + chunk-local->global index remap + cross-chunk merge.
_SEGMENTS = [
    {"start": 0.0, "end": 15.0, "text": "Segment zero hook.", "words": []},
    {"start": 15.0, "end": 30.0, "text": "Segment one body.", "words": []},
    {"start": 30.0, "end": 45.0, "text": "Segment two punch.", "words": []},
    {"start": 45.0, "end": 60.0, "text": "Segment three hook.", "words": []},
    {"start": 60.0, "end": 75.0, "text": "Segment four body.", "words": []},
    {"start": 75.0, "end": 90.0, "text": "Segment five punch.", "words": []},
]


def _make_job(tmp_path, transcript):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    job = Job(job_id="selecttest01", source_name="x.mp4", data_dir=job_dir)
    job.transcript_path.write_text(json.dumps(transcript))
    return job


def test_select_clips_multi_chunk_merges_dedups_and_writes(tmp_path, monkeypatch):
    transcript = {"segments": _SEGMENTS}
    job = _make_job(tmp_path, transcript)

    # force two chunks regardless of char budget
    monkeypatch.setattr(s, "chunk_segments", lambda segs, *a, **k: [[0, 1, 2], [3, 4, 5]])

    # run_claude returns CHUNK-LOCAL indices; select_clips remaps to global.
    #   chunk1 idxs [0,1,2]: a high-score clip + a lower-score clip overlapping it
    #   chunk2 idxs [3,4,5]: one disjoint clip
    responses = iter([
        {"clips": [
            {"start_seg": 0, "end_seg": 2, "score": 9, "title": "C1-high"},
            {"start_seg": 1, "end_seg": 2, "score": 5, "title": "C1-low-overlap"},
        ]},
        {"clips": [
            {"start_seg": 1, "end_seg": 2, "score": 8, "title": "C2"},
        ]},
    ])
    calls = []

    def fake_run_claude(prompt, timeout=180):
        calls.append(prompt)
        return next(responses)

    monkeypatch.setattr(s, "run_claude", fake_run_claude)

    out = s.select_clips(job, max_clips=6)

    # one claude call per chunk (no batching, no dedup of calls)
    assert len(calls) == 2
    assert out == job.clips_json_path

    payload = json.loads(job.clips_json_path.read_text())
    assert payload["transcript_hash"] == s.transcript_hash(transcript)
    # 3 raw candidates merged across chunks -> 2 after overlap dedup (lower-score dropped)
    assert len(payload["clips"]) == 2
    assert [(c["start"], c["end"]) for c in payload["clips"]] == [(0.0, 45.0), (60.0, 90.0)]
    # highest score within each kept region survives; ordered by timeline start
    assert [c["title"] for c in payload["clips"]] == ["C1-high", "C2"]

    assert job.stage_status("select") == "done"
    assert job.load_manifest()["stages"]["select"]["clips"] == 2


def test_select_clips_cache_hit_skips_claude(tmp_path, monkeypatch):
    transcript = {"segments": _SEGMENTS[:1]}
    job = _make_job(tmp_path, transcript)
    # pre-write a clips.json whose hash matches the transcript -> cache hit
    job.clips_json_path.write_text(json.dumps(
        {"transcript_hash": s.transcript_hash(transcript), "clips": []}))

    called = []
    monkeypatch.setattr(s, "run_claude", lambda *a, **k: called.append(1) or {"clips": []})

    out = s.select_clips(job)
    assert out == job.clips_json_path
    assert called == []  # cache hit -> claude never invoked
    assert job.load_manifest()["stages"]["select"].get("cached") is True


# ---------------------------------------------------------------------------
# transcribe.build_whisper_cmd — no-language branch (the language branch is
# already covered in test_pipeline.py)
# ---------------------------------------------------------------------------


def test_build_whisper_cmd_without_language_omits_lang_flag():
    cmd = t.build_whisper_cmd(Path("a.wav"), Path("m.bin"), Path("/out/pre"))
    assert "-l" not in cmd          # no language -> no -l pair
    assert "-pp" in cmd             # progress printing always on (feeds on_progress)
    assert "--output-json-full" in cmd
    assert cmd[0] == str(t.config.WHISPER_CLI)


# ---------------------------------------------------------------------------
# transcribe.extract_audio — run() stubbed
# ---------------------------------------------------------------------------


def test_extract_audio_invokes_ffmpeg_cmd_and_returns_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(t.config, "require_tool", lambda *a, **k: None)
    seen = {}

    def fake_run(cmd, log, desc, **kw):
        seen["cmd"] = cmd
        seen["desc"] = desc

    monkeypatch.setattr(t, "run", fake_run)

    out = tmp_path / "audio.wav"
    res = t.extract_audio(Path("video.mp4"), out)

    assert res == out
    assert seen["cmd"] == t.build_ffmpeg_audio_cmd(Path("video.mp4"), out)
    assert seen["cmd"][0] == t.config.FFMPEG
    assert "extract audio" in seen["desc"]


# ---------------------------------------------------------------------------
# transcribe.detect_silence — subprocess.run stubbed
# ---------------------------------------------------------------------------


def test_detect_silence_builds_cmd_and_parses_ranges(monkeypatch):
    fake_stderr = (
        "[silencedetect @ 0x1] silence_start: 1.0\n"
        "[silencedetect @ 0x1] silence_end: 4.0 | silence_duration: 3.0\n"
    )
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return types.SimpleNamespace(returncode=0, stdout="", stderr=fake_stderr)

    monkeypatch.setattr(t.subprocess, "run", fake_run)

    ranges = t.detect_silence(Path("a.wav"), noise_db=-30, min_silence=0.5)

    # parsed range = (end - duration, end)
    assert ranges == [(1.0, 4.0)]
    cmd = seen["cmd"]
    assert cmd[0] == t.config.FFMPEG
    assert "-i" in cmd
    af = cmd[cmd.index("-af") + 1]
    assert af == "silencedetect=noise=-30dB:d=0.5"   # params threaded into the filter
    assert cmd[-3:] == ["-f", "null", "-"]


# ---------------------------------------------------------------------------
# transcribe.run_whisper — stream_run stubbed; progress callback wiring
# ---------------------------------------------------------------------------


def test_run_whisper_feeds_parsed_progress_to_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(t.config, "require_tool", lambda *a, **k: None)
    model = tmp_path / "ggml-base.en.bin"
    model.write_bytes(b"x")  # must exist or run_whisper raises before streaming

    progress_lines = [
        "whisper_print_progress_callback: progress =  10%",
        "load time = 123 ms",                 # non-progress -> ignored
        "progress = 55%",
        "progress = 100%",
    ]
    seen = {}

    def fake_stream_run(cmd, log, desc, on_line=None, **kw):
        seen["cmd"] = cmd
        for ln in progress_lines:
            on_line(ln)
        return 0

    monkeypatch.setattr(t, "stream_run", fake_stream_run)

    got = []
    out_prefix = tmp_path / "whisper"
    res = t.run_whisper(tmp_path / "a.wav", model, out_prefix, language="en",
                        on_progress=lambda p: got.append(p))

    assert got == [10, 55, 100]   # non-progress line filtered by parse_whisper_progress
    assert res == out_prefix.with_suffix(".json")
    assert seen["cmd"] == t.build_whisper_cmd(tmp_path / "a.wav", model, out_prefix, "en")


def test_run_whisper_without_progress_callback_passes_none_on_line(tmp_path, monkeypatch):
    monkeypatch.setattr(t.config, "require_tool", lambda *a, **k: None)
    model = tmp_path / "ggml-base.en.bin"
    model.write_bytes(b"x")
    captured = {}

    def fake_stream_run(cmd, log, desc, on_line=None, **kw):
        captured["on_line"] = on_line
        return 0

    monkeypatch.setattr(t, "stream_run", fake_stream_run)

    out_prefix = tmp_path / "whisper"
    res = t.run_whisper(tmp_path / "a.wav", model, out_prefix)  # no on_progress
    assert res == out_prefix.with_suffix(".json")
    assert captured["on_line"] is None   # no callback wired when on_progress is absent


def test_run_whisper_missing_model_raises_with_download_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(t.config, "require_tool", lambda *a, **k: None)
    missing = tmp_path / "ggml-base.en.bin"  # intentionally NOT created
    with pytest.raises(FileNotFoundError) as ei:
        t.run_whisper(tmp_path / "a.wav", missing, tmp_path / "whisper")
    msg = str(ei.value)
    assert "download-ggml-model.sh" in msg
    assert "base.en" in msg   # ggml- prefix stripped from the model stem in the hint
