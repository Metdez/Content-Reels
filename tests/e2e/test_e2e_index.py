"""E2E-01 — index page: upload enable/disable, drag highlight, library pills, submit."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_index_submit_enables_on_file(base_url: str, page: Page, tmp_path: Path):
    page.goto(base_url + "/")
    submit = page.locator("#submit")
    expect(submit).to_be_disabled()

    # Set a file on the (hidden) input → submit enables + filename shows.
    f = tmp_path / "my_talk.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32)
    page.set_input_files("#file", str(f))

    expect(submit).to_be_enabled()
    expect(page.locator("#fname")).to_have_text("my_talk.mp4")
    expect(page.locator("#chosen")).to_be_visible()


def test_index_drag_toggles_highlight(base_url: str, page: Page):
    page.goto(base_url + "/")
    drop = page.locator("#drop")
    assert "drag" not in (drop.get_attribute("class") or "")
    page.dispatch_event("#drop", "dragenter")
    assert "drag" in (drop.get_attribute("class") or "")
    page.dispatch_event("#drop", "dragleave")
    assert "drag" not in (drop.get_attribute("class") or "")


def test_index_library_pills(base_url: str, page: Page):
    page.goto(base_url + "/")
    jobs = page.locator(".lib .job")
    expect(jobs.first).to_be_visible()
    # Every job in the library renders a status pill; the seeded jobs are all fully
    # rendered, so at least one shows the "ready" pill (the app reports a job as
    # ready whenever its render stage is done, regardless of awaiting_run).
    assert page.locator(".lib .job .pill").count() == jobs.count()
    assert page.locator(".pill.ready").count() >= 1
    # Each row links to its job page.
    assert page.locator('.job a.open[href^="/job/"]').count() >= 1


def test_index_submit_shows_uploading(base_url: str, page: Page, tmp_path: Path):
    page.goto(base_url + "/")
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32)
    page.set_input_files("#file", str(f))
    expect(page.locator("#submit")).to_be_enabled()
    # Suppress the real form navigation so the transient button state stays
    # readable (aborting the POST instead would navigate to a browser error page
    # and wipe the DOM before we can assert).
    page.evaluate("document.getElementById('form').addEventListener('submit', e => e.preventDefault())")
    page.click("#submit")
    expect(page.locator("#submit")).to_have_text("Uploading…")
    expect(page.locator("#submit")).to_be_disabled()
