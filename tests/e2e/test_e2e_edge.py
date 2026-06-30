"""E2E-06 — edge/error states: zero source_dims (crop box hidden), missing-captions
payload (safe editor boot), invalid caption time blocked, 404 job (poll surfaces +
stops), 404 clip (boot error)."""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page, expect

JOB_REAL = "e2eseed0001"
JOB_ZERODIM = "e2ezerodim01"
JOB_NOCAPS = "e2enocaps001"
JOB_DISPOSE = "e2edispose01"

pytestmark = pytest.mark.e2e


def test_zero_source_dims_hides_crop_box(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_ZERODIM}")
    expect(page.locator("#pasps .asp")).to_have_count(3)  # preview still boots
    # drawBox hides the box when source dims are 0×0 — no crash, box not shown.
    expect(page.locator("#pbox")).to_be_hidden()
    # Moving a slider does not throw (preview still responsive).
    page.eval_on_selector("#pzoom", "el=>{el.value='1.5';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#pzval")).to_have_text("1.50×")


def test_missing_captions_payload_boots_safely(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_NOCAPS}/clip/1/edit")
    # Editor reaches a usable state — not stuck on "Loading editor…".
    expect(page.locator("#apply")).to_be_visible(timeout=10_000)
    expect(page.locator("#bootmsg")).to_have_count(0)
    # Empty caption list renders its safe placeholder.
    expect(page.locator("#caps")).to_contain_text("No caption segments")


def test_invalid_caption_time_inline_error(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_REAL}/clip/1/edit")
    expect(page.locator("#apply")).to_be_visible(timeout=10_000)
    start_input = page.locator('#caps .caprow input[data-k="start"]').first
    expect(start_input).to_be_visible()
    start_input.fill("999")  # beyond clip length
    expect(start_input).to_have_class(re.compile(r"\bbad\b"))
    expect(page.locator('#caps .caperr[data-err="0"]')).to_be_visible()
    expect(page.locator("#apply")).to_be_disabled()


def test_404_clip_surfaces_boot_error(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_REAL}/clip/999/edit")
    expect(page.locator("#bootmsg")).to_have_text("Clip not found", timeout=10_000)


def test_404_job_polling_surfaces_and_stops(base_url: str, page: Page):
    # A *completed* job stops polling after its first successful poll, so deleting
    # its manifest on disk would never trigger another fetch. Instead serve a
    # still-running job (polling stays active), then flip the API to 404 so the
    # next poll surfaces the fatal "no longer exists" banner and stops.
    state = {"gone": False}
    running = {
        "awaiting_run": False, "source_name": "dispose", "progress": 0.5,
        "stages": {"ingest": {"status": "done"}, "transcribe": {"status": "done"},
                   "select": {"status": "done"},
                   "render": {"status": "running", "clips_done": 0, "clips_total": 2}},
        "clips": [], "error": None,
    }

    def handle(route):
        if state["gone"]:
            route.fulfill(status=404, content_type="application/json",
                          body=json.dumps({"detail": "Job not found"}))
        else:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(running))

    page.route(f"**/api/job/{JOB_DISPOSE}", handle)
    page.goto(f"{base_url}/job/{JOB_DISPOSE}")
    expect(page.locator("#steps")).to_be_visible(timeout=10_000)
    # ...now make the job vanish → the next poll 404s.
    state["gone"] = True
    banner = page.locator("#connbar")
    expect(banner).to_be_visible(timeout=8_000)
    expect(banner).to_contain_text("no longer exists")
