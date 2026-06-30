"""E2E-05/real — the genuine real-ffmpeg-through-the-app E2E.

Trigger a real re-render of the seeded clip via the actual `/edit` endpoint (the
same path the editor's Apply uses: enqueue → background worker → REAL ffmpeg with
the cached transcript, no claude/whisper), poll `/rerender-status` until it settles,
and assert the 9:16 output file changed (new mtime ⇒ new ?v=).

We drive the render via `page.request` (the real HTTP endpoint) rather than a
headless slider-drag, because synthetic pointer events don't reliably register the
editor's dirty-tracking in headless Chromium — and the point of THIS spec is to
prove the real render pipeline runs end-to-end and the output updates, which the
endpoint exercises faithfully. (The Apply-button UI path is covered by the editor
UI spec.) A real single-aspect re-render of the seeded clip settles in ~10–15s.
"""

from __future__ import annotations

import json
import time

import pytest
from playwright.sync_api import Page, expect

JOB_REAL = "e2eseed0001"

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _clip_9x16(page: Page, base_url: str, idx: int) -> str:
    resp = page.request.get(f"{base_url}/api/job/{JOB_REAL}/clip/{idx}")
    assert resp.status == 200
    return json.loads(resp.text()).get("outputs", {}).get("9:16", "")


def test_real_render_9x16_updates(base_url: str, page: Page):
    idx = 1
    before = _clip_9x16(page, base_url, idx)

    # The editor opens + the Apply control is present (UI smoke).
    page.goto(f"{base_url}/job/{JOB_REAL}/clip/{idx}/edit")
    expect(page.locator("#apply")).to_be_visible(timeout=15_000)

    # Trigger a REAL single-aspect re-render via the real endpoint.
    post = page.request.post(
        f"{base_url}/api/job/{JOB_REAL}/clip/{idx}/edit",
        data=json.dumps({"transforms": {"9:16": {"zoom": 1.3, "x": 0.0, "y": 0.0}},
                         "aspects": ["9:16"]}),
        headers={"Content-Type": "application/json"},
    )
    assert post.status == 200 and json.loads(post.text()).get("queued") is True

    # Poll the real background ffmpeg render until it settles.
    deadline = time.time() + 90
    final = None
    while time.time() < deadline:
        resp = page.request.get(f"{base_url}/api/job/{JOB_REAL}/clip/{idx}/rerender-status")
        s = json.loads(resp.text())
        busy = s.get("active") or s.get("queued") or s.get("status") in ("rendering", "queued")
        if not busy and s.get("aspects", {}).get("9:16") in ("done", "error"):
            final = s
            break
        time.sleep(1.0)

    assert final is not None, "re-render did not settle within the timeout"
    assert final.get("status") != "error", f"re-render failed: {final.get('error')}"
    assert final["aspects"]["9:16"] == "done", final

    # Real ffmpeg wrote a new file → the mtime-based ?v= cache-bust changed.
    after = _clip_9x16(page, base_url, idx)
    assert after and after != before, (before, after)
