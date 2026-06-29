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
