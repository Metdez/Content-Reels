"""Phase 27 — non-blocking upload, persistent error state, render concurrency cap.

REL-03: /upload runs off the event loop (sync endpoint → Starlette threadpool).
REL-04: an in-flight failure survives a restart (surfaced from the manifest, not
        only the in-memory RUNNING dict); the shutdown hook signals workers.
REL-05: a global semaphore bounds concurrent GPU encodes.
"""

from __future__ import annotations

import asyncio
import json

from tests.conftest import seed_job


def test_upload_endpoint_is_sync_offloaded(client):
    """REL-03: upload is a plain `def` so FastAPI runs its blocking hash/copy in the
    threadpool — not `async def`, which would block the event loop + every poll."""
    assert not asyncio.iscoroutinefunction(client.app_module.upload)


def test_inflight_error_surfaces_from_manifest(client):
    """REL-04: with no in-memory RUNNING entry (simulating a restart), a stage error
    recorded on disk is still surfaced in the job payload."""
    job_dir = seed_job(client.data_dir, "errjob0001")
    mf = json.loads((job_dir / "job.json").read_text())
    mf["stages"]["render"] = {"status": "error", "error": "ffmpeg exploded"}
    (job_dir / "job.json").write_text(json.dumps(mf))
    # ensure nothing in the in-memory tracker
    client.app_module.RUNNING.pop("errjob0001", None)

    data = client.get("/api/job/errjob0001").json()
    assert data["error"] == "ffmpeg exploded"


def test_render_concurrency_cap_default_one(client):
    """REL-05: the global render-slot semaphore defaults to 1 (fully serial)."""
    app = client.app_module
    assert app._MAX_RENDERS == 1
    assert app._RENDER_SLOTS.acquire(blocking=False) is True
    try:
        # second non-blocking acquire fails — only one render slot
        assert app._RENDER_SLOTS.acquire(blocking=False) is False
    finally:
        app._RENDER_SLOTS.release()


def test_shutdown_lifespan_signals_workers(client):
    """REL-04: leaving the app lifespan (server shutdown) flips the flag the
    background workers watch."""
    from starlette.testclient import TestClient
    app = client.app_module
    app._SHUTTING_DOWN.clear()
    with TestClient(app.app):  # enter → startup; exit → lifespan shutdown
        pass
    assert app._SHUTTING_DOWN.is_set()
    app._SHUTTING_DOWN.clear()  # reset so other tests/threads aren't affected
