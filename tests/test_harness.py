"""Phase 23 — proves the v6 test harness works: TestClient fixture + seeded job.

These are the first tests that hit the FastAPI app through the HTTP layer (via
``starlette.testclient``) rather than calling functions directly, and the first
to drive a fully-rendered job without running the pipeline.
"""

from __future__ import annotations


def test_client_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_seeded_job_payload_has_clips(seeded_job):
    client, job_id, _ = seeded_job
    r = client.get(f"/api/job/{job_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["job_id"] == job_id
    assert data["awaiting_run"] is False
    assert len(data["clips"]) == 2
    c0 = data["clips"][0]
    assert set(c0["outputs"]) == {"9:16", "1:1", "16:9"}
    assert all(u.startswith("/media/") for u in c0["outputs"].values())
    assert c0["title"] == "Clip 1"
    # rationale/timing folded in from clips.json
    assert c0["rationale"] == "Strong hook 1"
    assert data["progress"] == 1.0  # all stages done → master bar full


def test_seeded_job_page_html(seeded_job):
    client, job_id, _ = seeded_job
    r = client.get(f"/job/{job_id}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_seeded_clip_editor_payload(seeded_job):
    client, job_id, _ = seeded_job
    r = client.get(f"/api/job/{job_id}/clip/1")
    assert r.status_code == 200
    d = r.json()
    assert d["index"] == 1
    assert set(d["transforms"]) == {"9:16", "1:1", "16:9"}
    assert d["captions"]["mode"] in ("overlay", "none")
    assert isinstance(d["captions"]["segments"], list)
    assert isinstance(d["boundaries"], list) and d["boundaries"][0] == 0.0
    assert set(d["outputs"]) == {"9:16", "1:1", "16:9"}


def test_seeded_download_and_missing_aspect(seeded_job):
    client, job_id, _ = seeded_job
    ok = client.get(f"/download/{job_id}/1/9:16")
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "video/mp4"
    missing = client.get(f"/download/{job_id}/9/9:16")
    assert missing.status_code == 404


def test_media_mount_serves_seeded_source(seeded_job):
    client, job_id, _ = seeded_job
    r = client.get(f"/media/{job_id}/source.mp4")
    assert r.status_code == 200
