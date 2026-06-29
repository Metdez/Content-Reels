"""Phase 1 self-checks: job layout + transcription parsing/VAD (no binaries needed)."""

import json
from pathlib import Path

from content_machine import config
from content_machine.jobs import Job, compute_job_id, STAGES
from content_machine import transcribe as t


def test_job_id_deterministic_and_content_based(tmp_path):
    a = tmp_path / "a.mp4"; a.write_bytes(b"hello video")
    b = tmp_path / "b.mp4"; b.write_bytes(b"hello video")     # same bytes
    c = tmp_path / "c.mp4"; c.write_bytes(b"different bytes")
    assert compute_job_id(a) == compute_job_id(b)             # idempotent by content
    assert compute_job_id(a) != compute_job_id(c)
    assert len(compute_job_id(a)) == 16


def test_manifest_roundtrip_and_stage_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    vid = tmp_path / "talk.mov"; vid.write_bytes(b"xyz")
    job = Job.for_video(vid)
    job.update_stage("ingest", "done", source="src")
    job.update_stage("transcribe", "running")
    assert job.stage_status("ingest") == "done"
    assert job.stage_status("transcribe") == "running"
    assert job.stage_status("render") == "pending"
    # manifest persisted and reloadable
    reloaded = Job.load(job.job_id)
    assert reloaded.job_id == job.job_id
    assert set(json.loads(job.manifest_path.read_text())["stages"]) == set(STAGES)


def test_ffmpeg_audio_cmd_is_16k_mono():
    cmd = t.build_ffmpeg_audio_cmd(Path("in.mp4"), Path("out.wav"))
    assert "-ar" in cmd and "16000" in cmd
    assert "-ac" in cmd and "1" in cmd
    assert cmd[-1] == "out.wav"


def test_whisper_cmd_requests_full_json():
    cmd = t.build_whisper_cmd(Path("a.wav"), Path("m.bin"), Path("/out/pre"), language="en")
    assert "--output-json-full" in cmd
    assert "-of" in cmd and "/out/pre" in cmd
    assert "-l" in cmd and "en" in cmd


def test_parse_whisper_json_extracts_segments_and_words():
    raw = {
        "result": {"language": "en"},
        "transcription": [
            {"offsets": {"from": 0, "to": 2000}, "text": " Hello world",
             "tokens": [
                 {"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}},
                 {"text": " Hello", "offsets": {"from": 0, "to": 900}},
                 {"text": " world", "offsets": {"from": 900, "to": 2000}},
             ]},
        ],
    }
    out = t.parse_whisper_json(raw)
    assert out["language"] == "en"
    assert out["duration"] == 2.0
    assert len(out["segments"]) == 1
    seg = out["segments"][0]
    assert seg["start"] == 0.0 and seg["end"] == 2.0
    assert [w["word"] for w in seg["words"]] == ["Hello", "world"]   # special token filtered


def test_parse_silencedetect():
    stderr = (
        "[silencedetect @ 0x1] silence_start: 0\n"
        "[silencedetect @ 0x1] silence_end: 3.5 | silence_duration: 3.5\n"
    )
    ranges = t.parse_silencedetect(stderr)
    assert ranges == [(0.0, 3.5)]


def test_vad_filter_drops_hallucination_in_silence_keeps_real_speech():
    segments = [
        {"start": 0.0, "end": 3.0, "text": "Thanks for watching", "words": []},  # in silence
        {"start": 4.0, "end": 7.0, "text": "Real content here", "words": []},     # speech
    ]
    silence = [(0.0, 3.2)]
    kept = t.vad_filter(segments, silence)
    assert len(kept) == 1
    assert kept[0]["text"] == "Real content here"


def test_vad_filter_keeps_real_phrase_even_if_silent():
    # a non-blocklist phrase inside silence is kept (don't nuke real speech)
    segments = [{"start": 0.0, "end": 2.0, "text": "The quarterly numbers", "words": []}]
    kept = t.vad_filter(segments, [(0.0, 2.0)])
    assert len(kept) == 1
