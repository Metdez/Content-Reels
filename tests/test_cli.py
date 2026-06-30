"""QA-07: CLI command coverage for content_machine/cli.py.

The CLI is a Typer app whose four commands (ingest/select/render/serve) each
delegate the heavy work to a lazily-imported stage function. We drive the app
through Typer's CliRunner and monkeypatch every heavy stage at its import site
(`content_machine.transcribe.transcribe`, `.select.select_clips`,
`.render.render_job`, and `uvicorn.run`) so NO real ffmpeg / whisper / claude /
HTTP server ever runs. Each test asserts the stage was invoked with the args the
CLI forwarded and that the command exits 0 (or errors cleanly).
"""

import json

from typer.testing import CliRunner

from content_machine import config
from content_machine.cli import app
from content_machine.jobs import Job

runner = CliRunner()


# --- ingest ------------------------------------------------------------------
def test_ingest_invokes_transcribe_and_exits_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import transcribe

    # Fake transcribe returns a real Job whose transcript.json exists on disk,
    # so the CLI's "if transcript.exists()" summary branch fully executes.
    job_dir = tmp_path / "ingestjob"
    job_dir.mkdir(parents=True, exist_ok=True)
    job = Job(job_id="ingestjob", source_name="talk.mp4", data_dir=job_dir)
    job.transcript_path.write_text(json.dumps({
        "language": "en", "duration": 12.34,
        "segments": [{"start": 0, "end": 2, "text": "hi"}],
        "vad_dropped": 1,
    }))

    captured = {}

    def fake_transcribe(video, **kwargs):
        captured["video"] = video
        captured["kwargs"] = kwargs
        return job

    monkeypatch.setattr(transcribe, "transcribe", fake_transcribe)

    video = tmp_path / "talk.mp4"
    video.write_bytes(b"\x00fakevideo")
    result = runner.invoke(app, ["ingest", str(video)])

    assert result.exit_code == 0, result.output
    assert captured, "transcribe was never invoked"
    assert str(captured["video"]).endswith("talk.mp4")
    # CLI forwards: model=None, vad=not no_vad (True), force=False, language=None
    assert captured["kwargs"] == {"model": None, "vad": True, "force": False, "language": None}
    assert "Job ingestjob" in result.output
    assert "language:   en" in result.output
    assert "VAD dropped 1" in result.output


def test_ingest_forwards_options_to_transcribe(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import transcribe

    job_dir = tmp_path / "optjob"
    job_dir.mkdir(parents=True, exist_ok=True)
    job = Job(job_id="optjob", source_name="talk.mp4", data_dir=job_dir)
    # No transcript file written -> exercises the "transcript missing" path too.

    captured = {}

    def fake_transcribe(video, **kwargs):
        captured["kwargs"] = kwargs
        return job

    monkeypatch.setattr(transcribe, "transcribe", fake_transcribe)

    video = tmp_path / "talk.mp4"
    video.write_bytes(b"\x00fakevideo")
    result = runner.invoke(app, [
        "ingest", str(video),
        "--model", "small.en", "--no-vad", "--force", "--language", "en",
    ])

    assert result.exit_code == 0, result.output
    assert captured["kwargs"] == {
        "model": "small.en", "vad": False, "force": True, "language": "en",
    }


def test_ingest_missing_file_errors_cleanly(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import transcribe

    called = {"n": 0}

    def fake_transcribe(*a, **k):
        called["n"] += 1
        return None

    monkeypatch.setattr(transcribe, "transcribe", fake_transcribe)

    missing = tmp_path / "does_not_exist.mp4"
    result = runner.invoke(app, ["ingest", str(missing)])

    # Typer's `exists=True` rejects the arg before the command body runs: a clean
    # non-zero usage error, no traceback, and transcribe is never called.
    assert result.exit_code != 0
    assert called["n"] == 0


# --- select ------------------------------------------------------------------
def test_select_invokes_select_clips_and_exits_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import select as select_mod

    clips_path = tmp_path / "clips.json"
    clips_path.write_text(json.dumps({"clips": [
        {"start": 10.0, "end": 25.0, "score": 8.5, "title": "Strong hook"},
        {"start": 40.0, "end": 70.0, "score": 7.0, "title": "Second clip"},
    ]}))

    captured = {}

    def fake_select_clips(job_id, **kwargs):
        captured["job_id"] = job_id
        captured["kwargs"] = kwargs
        return clips_path

    monkeypatch.setattr(select_mod, "select_clips", fake_select_clips)

    result = runner.invoke(app, ["select", "abcd1234"])

    assert result.exit_code == 0, result.output
    assert captured["job_id"] == "abcd1234"
    assert captured["kwargs"] == {"max_clips": 6, "force": False}
    assert "2 clips" in result.output
    assert "Strong hook" in result.output


def test_select_forwards_options_to_select_clips(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import select as select_mod

    clips_path = tmp_path / "clips.json"
    clips_path.write_text(json.dumps({"clips": []}))

    captured = {}

    def fake_select_clips(job_id, **kwargs):
        captured["job_id"] = job_id
        captured["kwargs"] = kwargs
        return clips_path

    monkeypatch.setattr(select_mod, "select_clips", fake_select_clips)

    result = runner.invoke(app, ["select", "job99", "--max-clips", "3", "--force"])

    assert result.exit_code == 0, result.output
    assert captured["job_id"] == "job99"
    assert captured["kwargs"] == {"max_clips": 3, "force": True}
    assert "0 clips" in result.output


# --- render ------------------------------------------------------------------
def test_render_invokes_render_job_and_exits_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import render as render_mod

    render_path = tmp_path / "render.json"
    render_path.write_text(json.dumps({"clips": [
        {"index": 1, "outputs": {"9:16": "/x/9x16.mp4", "1:1": "/x/1x1.mp4"},
         "captions": "overlay"},
    ]}))

    captured = {}

    def fake_render_job(job_id, **kwargs):
        captured["job_id"] = job_id
        captured["kwargs"] = kwargs
        return render_path

    monkeypatch.setattr(render_mod, "render_job", fake_render_job)

    result = runner.invoke(app, ["render", "abcd1234"])

    assert result.exit_code == 0, result.output
    assert captured["job_id"] == "abcd1234"
    assert captured["kwargs"] == {"x_offset": 0.0, "caption_mode": "overlay"}
    assert "Rendered 1 clips" in result.output
    assert "clip01:" in result.output


def test_render_forwards_options_to_render_job(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import render as render_mod

    render_path = tmp_path / "render.json"
    render_path.write_text(json.dumps({"clips": []}))

    captured = {}

    def fake_render_job(job_id, **kwargs):
        captured["job_id"] = job_id
        captured["kwargs"] = kwargs
        return render_path

    monkeypatch.setattr(render_mod, "render_job", fake_render_job)

    result = runner.invoke(app, [
        "render", "job42", "--x-offset", "0.5", "--captions", "none",
    ])

    assert result.exit_code == 0, result.output
    assert captured["job_id"] == "job42"
    assert captured["kwargs"] == {"x_offset": 0.5, "caption_mode": "none"}
    assert "Rendered 0 clips" in result.output


# --- serve -------------------------------------------------------------------
def test_serve_calls_uvicorn_without_starting_server(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    import uvicorn

    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    # cli.py does `import uvicorn; uvicorn.run(...)`, so patch the attr on the
    # uvicorn module — the real server never starts.
    monkeypatch.setattr(uvicorn, "run", fake_run)

    result = runner.invoke(app, ["serve", "--host", "0.0.0.0", "--port", "9123"])

    assert result.exit_code == 0, result.output
    assert captured["args"][0] == "content_machine.app:app"
    assert captured["kwargs"]["host"] == "0.0.0.0"
    assert captured["kwargs"]["port"] == 9123


def test_serve_uses_localhost_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    import uvicorn

    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(uvicorn, "run", fake_run)

    result = runner.invoke(app, ["serve"])

    assert result.exit_code == 0, result.output
    assert captured["kwargs"]["host"] == "127.0.0.1"
    assert captured["kwargs"]["port"] == 8000
