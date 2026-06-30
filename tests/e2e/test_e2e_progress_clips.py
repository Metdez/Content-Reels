"""E2E-03 — completed job: 100%/done, all steps done, clip cards, aspect tab src swap,
download links resolve, live-log details present."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

JOB_REAL = "e2eseed0001"

pytestmark = pytest.mark.e2e


def test_progress_done_and_clips(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_REAL}")

    # Master bar reaches 100% and all four steps are done.
    expect(page.locator("#masterpct")).to_have_text("100%", timeout=10_000)
    expect(page.locator("#master")).to_have_class(re.compile(r"\bcomplete\b"))
    steps = page.locator("#steps .step.done")
    expect(steps).to_have_count(4)

    # Two clip cards render (seed_fixture seeded 2 clips).
    expect(page.locator(".clip")).to_have_count(2)

    # Live-log details present. Scope to the page log — the quick-crop modal also
    # carries a details.logs (#mlogwrap), so an unqualified selector is ambiguous.
    expect(page.locator("details.logs:not(#mlogwrap)")).to_be_visible()


def test_clip_aspect_tab_swaps_video_src(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_REAL}")
    expect(page.locator("#clip1")).to_be_visible(timeout=10_000)
    vid = page.locator("#vid1")
    src_before = vid.get_attribute("src")
    assert "9x16" in src_before  # first tab is 9:16

    # Click the 1:1 tab → the <video> src swaps to the 1x1 output.
    page.locator('#clip1 .tab[data-a="1:1"]').click()
    expect(page.locator('#clip1 .tab[data-a="1:1"]')).to_have_attribute("aria-pressed", "true")
    src_after = vid.get_attribute("src")
    assert src_after != src_before
    assert "1x1" in src_after


def test_clip_download_links_resolve(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_REAL}")
    expect(page.locator("#clip1")).to_be_visible(timeout=10_000)
    link = page.locator(f'#clip1 .dl a[href="/download/{JOB_REAL}/1/9:16"]')
    expect(link).to_be_visible()
    href = link.get_attribute("href")
    resp = page.request.get(base_url + href)
    assert resp.status == 200
    assert "video/mp4" in (resp.headers.get("content-type", ""))


def test_video_element_identity_preserved_across_poll(base_url: str, page: Page):
    """Reconcile-in-place: the same <video> element survives the 2.5s poll."""
    page.goto(f"{base_url}/job/{JOB_REAL}")
    expect(page.locator("#vid1")).to_be_visible(timeout=10_000)
    # Tag the element, wait past a poll cycle, confirm the SAME node is still there.
    page.eval_on_selector("#vid1", "el=>el.setAttribute('data-e2e-mark','1')")
    page.wait_for_timeout(3000)
    assert page.eval_on_selector("#vid1", "el=>el.getAttribute('data-e2e-mark')") == "1"
