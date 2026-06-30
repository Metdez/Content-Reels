"""E2E-02 — job preview (awaiting_run): aspect tabs, zoom/X/Y, slack-disable, reset,
copy-to-all, Run."""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page, expect

JOB_AWAIT = "e2eawait0001"
JOB_RUN = "e2erun0001"

pytestmark = pytest.mark.e2e


def _open_preview(base_url: str, page: Page, job_id: str):
    page.goto(f"{base_url}/job/{job_id}")
    # buildPreview renders #pasps once the boot fetch resolves.
    expect(page.locator("#pasps .asp")).to_have_count(3)


def test_preview_aspect_tabs(base_url: str, page: Page):
    _open_preview(base_url, page, JOB_AWAIT)
    tabs = page.locator("#pasps .asp")
    expect(tabs.nth(0)).to_have_class(re.compile(r"\bactive\b"))
    expect(tabs.nth(0)).to_have_attribute("aria-pressed", "true")

    tabs.nth(2).click()  # 16:9
    expect(tabs.nth(2)).to_have_attribute("aria-pressed", "true")
    expect(tabs.nth(0)).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#ptag")).to_have_text("16:9")


def test_preview_zoom_and_position_update(base_url: str, page: Page):
    _open_preview(base_url, page, JOB_AWAIT)
    # 9:16 active. Bump zoom so both axes gain slack, then move X/Y.
    page.eval_on_selector("#pzoom", "el=>{el.value='1.5';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#pzval")).to_have_text("1.50×")

    box_before = page.eval_on_selector("#pbox", "el=>el.style.left")
    page.eval_on_selector("#poff", "el=>{el.value='0.5';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#pval")).not_to_have_text("center")
    box_after = page.eval_on_selector("#pbox", "el=>el.style.left")
    assert box_before != box_after  # crop box moved

    page.eval_on_selector("#poffy", "el=>{el.value='-0.5';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#pyval")).not_to_have_text("center")


def test_preview_slack_disable_at_zoom1(base_url: str, page: Page):
    _open_preview(base_url, page, JOB_AWAIT)
    # At zoom 1 for 9:16 on a 1920x1080 source the crop is width-limited: it spans
    # the full source height, so the Y axis has no slack (disabled) while X does.
    page.eval_on_selector("#pzoom", "el=>{el.value='1';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#poffy")).to_be_disabled()
    expect(page.locator("#poff")).to_be_enabled()
    # Zoom in → the crop shrinks vertically too → Y gains slack and re-enables.
    page.eval_on_selector("#pzoom", "el=>{el.value='1.5';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#poffy")).to_be_enabled()


def test_preview_reset_and_copy_to_all(base_url: str, page: Page):
    _open_preview(base_url, page, JOB_AWAIT)
    page.eval_on_selector("#pzoom", "el=>{el.value='2';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#pzval")).to_have_text("2.00×")
    # Copy this framing to all ratios, then switch tab → zoom carries over.
    page.click("#pcopy")
    page.locator("#pasps .asp").nth(1).click()  # 1:1
    expect(page.locator("#pzval")).to_have_text("2.00×")
    # Reset just this ratio.
    page.click("#preset")
    expect(page.locator("#pzval")).to_have_text("1.00×")


def test_preview_run_flips_to_progress(base_url: str, page: Page):
    _open_preview(base_url, page, JOB_RUN)
    # Stub the pipeline kickoff so we don't start a real (whisper/claude) render,
    # and make the follow-up poll report a running job so the progress shell mounts
    # deterministically. Routes are added AFTER the preview boots so the initial
    # boot fetch still receives the real awaiting_run payload.
    page.route(
        f"**/api/job/{JOB_RUN}/run",
        lambda route: route.fulfill(status=200, content_type="application/json",
                                    body=json.dumps({"ok": True})),
    )
    running = {
        "awaiting_run": False, "source_name": "run", "progress": 0.25,
        "stages": {"ingest": {"status": "done"}, "transcribe": {"status": "running", "progress": 0.5},
                   "select": {"status": "pending"}, "render": {"status": "pending"}},
        "clips": [], "error": None,
    }
    page.route(
        f"**/api/job/{JOB_RUN}",
        lambda route: route.fulfill(status=200, content_type="application/json",
                                    body=json.dumps(running)),
    )
    page.click("#runbtn")
    # After the POST resolves the preview is torn down and the progress shell mounts.
    expect(page.locator("#steps")).to_be_visible(timeout=10_000)
    expect(page.locator("#pasps")).to_have_count(0)
