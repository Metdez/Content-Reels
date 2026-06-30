"""Self-contained Playwright E2E harness (Phase 35).

This package does NOT depend on the dev server on :8000. A single session-scoped
fixture:

* makes a throwaway ``CM_DATA_DIR`` temp dir and points the config at it;
* seeds a COMPLETED job with REAL playable media via ``scripts/seed_fixture.seed``
  (uses vendored ffmpeg) — used by the editor / progress / quick-crop / real-render
  specs;
* seeds several placeholder-media jobs via ``tests.conftest.seed_job`` for the
  preview / edge specs (no decode needed there);
* launches ``uvicorn content_machine.app:app`` on a FREE port in a subprocess with
  that ``CM_DATA_DIR`` in its env, waits until it answers, and yields ``base_url``;
* terminates uvicorn on teardown.

Every spec module marks itself ``pytestmark = pytest.mark.e2e`` so the whole package
is excluded from the default ``-m "not e2e and not slow"`` unit run.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Job ids seeded for the suite — referenced by the spec modules.
JOB_REAL = "e2eseed0001"      # real media, completed (editor / progress / quick-crop / real render)
JOB_AWAIT = "e2eawait0001"    # awaiting_run, placeholder (preview interactions, read-only)
JOB_RUN = "e2erun0001"        # awaiting_run, placeholder (Run-click mutates it)
JOB_ZERODIM = "e2ezerodim01"  # awaiting_run, placeholder, source_dims [0,0] (edge)
JOB_NOCAPS = "e2enocaps001"   # completed placeholder, transcript emptied (edge)
JOB_DISPOSE = "e2edispose01"  # completed placeholder, deleted mid-poll (edge 404)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def e2e_data_dir(tmp_path_factory) -> Path:
    """Create + seed a throwaway data dir; rebinds config.DATA_DIR to it."""
    data_dir = tmp_path_factory.mktemp("cm_e2e_data")
    os.environ["CM_DATA_DIR"] = str(data_dir)

    # Reload config so module-level DATA_DIR rebinds before seeding.
    from content_machine import config as cfg
    importlib.reload(cfg)

    # Real-media completed job (vendored ffmpeg). Short clips keep it fast.
    if str(REPO_ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import seed_fixture
    importlib.reload(seed_fixture)  # pick up the reloaded config.DATA_DIR
    seed_fixture.seed(JOB_REAL, 2, 1.0)

    # Placeholder-media jobs for preview + edge specs. Load seed_job directly from
    # the top-level tests/conftest.py by path so it works under any pytest import mode.
    _spec = importlib.util.spec_from_file_location(
        "_cm_tests_conftest", REPO_ROOT / "tests" / "conftest.py")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    seed_job = _mod.seed_job
    seed_job(data_dir, JOB_AWAIT, awaiting_run=True)
    seed_job(data_dir, JOB_RUN, awaiting_run=True)
    seed_job(data_dir, JOB_ZERODIM, awaiting_run=True, source_dims=(0, 0))

    nocaps = seed_job(data_dir, JOB_NOCAPS)
    # Strip the transcript so the editor must boot a clip with no caption events.
    (nocaps / "transcript.json").write_text(json.dumps(
        {"language": "en", "duration": 5.0, "segments": [], "vad_dropped": 0}))

    seed_job(data_dir, JOB_DISPOSE)
    return data_dir


@pytest.fixture(scope="session")
def base_url(e2e_data_dir) -> str:
    """Launch uvicorn against the seeded data dir; yield its base URL."""
    port = _free_port()
    env = dict(os.environ)
    env["CM_DATA_DIR"] = str(e2e_data_dir)
    # Force CPU (x264) encoding in the E2E server: the test drives a headless
    # chromium that also uses the GPU, so an NVENC ffmpeg render would contend with
    # the browser and slow to a crawl (~0.1x). x264 keeps the real-render spec fast
    # and deterministic, off the GPU the browser is using.
    env["CM_FORCE_CPU"] = "1"
    # Redirect the server's stdout/stderr to a LOG FILE, not an undrained PIPE.
    # A render logs hundreds of ffmpeg progress lines; an unread PIPE fills its OS
    # buffer (~64KB on Windows) and the server blocks on write() — which deadlocks
    # the render thread. A file sink never blocks the writer.
    log_path = e2e_data_dir / "_uvicorn.log"
    log_fh = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "content_machine.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(REPO_ROOT), env=env,
        stdout=log_fh, stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:  # uvicorn died — surface its output
            log_fh.flush()
            out = log_path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"uvicorn exited early (code {proc.returncode}):\n{out}")
        try:
            with urllib.request.urlopen(url + "/", timeout=2) as r:
                if r.status == 200:
                    ready = True
                    break
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    if not ready:
        proc.terminate()
        log_fh.close()
        raise RuntimeError("uvicorn did not become ready in time")
    try:
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fh.close()
