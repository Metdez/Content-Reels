"""Phase 4 self-checks: library listing, status rollup, media URLs, job payload."""

import json
import time

from content_machine import config


def _make_job(tmp, job_id, stages, source="talk.mp4"):
    d = tmp / job_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps({
        "job_id": job_id, "source_name": source, "created_at": time.time(),
        "stages": stages,
    }))
    return d


def test_overall_status_rollup(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    assert app._overall_status({"transcribe": {"status": "running"}}).startswith("transcribe")
    assert "error" in app._overall_status({"transcribe": {"status": "error"}})


def test_list_jobs_reads_filesystem(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    _make_job(tmp_path, "aaaa", {"render": {"status": "done", "clips": 3}})
    _make_job(tmp_path, "bbbb", {"transcribe": {"status": "running"}}, source="b.mov")
    jobs = app.list_jobs()
    by_id = {j["job_id"]: j for j in jobs}
    assert by_id["aaaa"]["status"] == "ready" and by_id["aaaa"]["n_clips"] == 3
    assert by_id["bbbb"]["status"].startswith("transcribe")


def test_media_url_is_relative_to_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    p = tmp_path / "job1" / "clips" / "clip01" / "9x16.mp4"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    assert app.media_url(p) == "/media/job1/clips/clip01/9x16.mp4"


def test_safe_upload_name_blocks_traversal_and_bad_ext(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    import importlib
    from content_machine import app as appmod
    importlib.reload(appmod)
    assert appmod.safe_upload_name("talk.mp4") == "talk.mp4"
    assert appmod.safe_upload_name("/some/dir/My Talk.MOV") == "My Talk.MOV"  # basename kept
    assert appmod.safe_upload_name("../escape.mp4") == "escape.mp4"           # traversal neutralized
    for bad in ["../../etc/passwd", ".hidden.mp4", "evil.sh", "no_ext", ""]:
        with __import__("pytest").raises(ValueError):
            appmod.safe_upload_name(bad)


def test_parse_transforms_filters_and_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    assert app._parse_transforms("") is None
    assert app._parse_transforms("not json") is None
    tf = app._parse_transforms(json.dumps({
        "9:16": {"zoom": 1.5, "x": -0.3, "y": 0.4},
        "1:1": {"zoom": 2.0},               # partial — missing axes default
        "bogus": {"zoom": 9},               # non-aspect dropped
    }))
    assert set(tf) == {"9:16", "1:1"}
    assert tf["9:16"] == {"zoom": 1.5, "x": -0.3, "y": 0.4}
    assert tf["1:1"] == {"zoom": 2.0, "x": 0.0, "y": 0.0}


def test_run_job_persists_transforms_to_run_params(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    from content_machine.jobs import Job
    # stage an awaiting-run job with a source file
    job = Job(job_id="dddd", source_name="t.mp4", data_dir=tmp_path / "dddd")
    job.ensure_dirs()
    (job.data_dir / "source.mp4").write_bytes(b"x")
    m = job.load_manifest(); m["awaiting_run"] = True; job.save_manifest(m)
    # stub the pipeline thread so nothing actually runs (no claude/ffmpeg)
    class _NoThread:
        def __init__(self, *a, **k): pass
        def start(self): pass
    monkeypatch.setattr(app.threading, "Thread", _NoThread)
    out = app.run_job("dddd", model="", max_clips=6, x_offset=0.0,
                      captions="overlay",
                      transforms=json.dumps({"9:16": {"zoom": 1.8, "x": -0.2, "y": 0.5}}))
    assert out == {"ok": True}
    rp = json.loads((job.data_dir / "job.json").read_text())["run_params"]
    assert rp["transforms"]["9:16"] == {"zoom": 1.8, "x": -0.2, "y": 0.5}
    assert rp["captions"] == "overlay"


def test_master_progress_weighted(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    stages = {"ingest": {"status": "done"}, "transcribe": {"status": "done"},
              "select": {"status": "done"}, "render": {"status": "running", "progress": 0.5}}
    # 0.02 + 0.40 + 0.08 + 0.50*0.5 = 0.75
    assert abs(app._master_progress(stages) - 0.75) < 1e-6
    pending = {s: {"status": "pending"} for s in ("ingest", "transcribe", "select", "render")}
    assert app._master_progress(pending) == 0.0
    alldone = {s: {"status": "done"} for s in ("ingest", "transcribe", "select", "render")}
    assert abs(app._master_progress(alldone) - 1.0) < 1e-6


def test_job_payload_includes_master_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    from content_machine.jobs import Job
    _make_job(tmp_path, "eeee", {"ingest": {"status": "done"},
              "transcribe": {"status": "running", "progress": 0.5},
              "select": {"status": "pending"}, "render": {"status": "pending"}})
    payload = app._job_payload(Job.load("eeee"))
    # 0.02 + 0.40*0.5 = 0.22
    assert abs(payload["progress"] - 0.22) < 1e-6


def test_job_payload_merges_clips_and_rationale(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from content_machine import app
    from content_machine.jobs import Job
    d = _make_job(tmp_path, "cccc", {"render": {"status": "done"}})
    (d / "clips").mkdir()
    (d / "clips" / "render.json").write_text(json.dumps({"clips": [
        {"index": 1, "title": "Hook", "score": 8.0, "captions": "overlay",
         "thumb": str(d / "clips" / "t.jpg"), "outputs": {"9:16": str(d / "clips" / "c.mp4")}}
    ]}))
    (d / "clips" / "t.jpg").write_bytes(b"x"); (d / "clips" / "c.mp4").write_bytes(b"x")
    (d / "clips.json").write_text(json.dumps({"clips": [{"rationale": "great hook"}]}))
    payload = app._job_payload(Job.load("cccc"))
    assert payload["clips"][0]["title"] == "Hook"
    assert payload["clips"][0]["rationale"] == "great hook"
    assert payload["clips"][0]["outputs"]["9:16"].startswith("/media/cccc/")
