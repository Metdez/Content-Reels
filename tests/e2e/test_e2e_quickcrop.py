"""E2E-04 — Quick crop modal: open/seed, aspect tabs, wheel-zoom (slider sync),
drag-pan, copy-to-all, ESC closes + focus returns. UI only — no real re-render."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

JOB_REAL = "e2eseed0001"

pytestmark = pytest.mark.e2e


def _open_modal(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_REAL}")
    expect(page.locator("#clip1")).to_be_visible(timeout=10_000)
    page.locator('#clip1 button.adjust[aria-label="Quick crop clip 1"]').click()
    expect(page.locator("#modal")).to_have_class("modal open")
    expect(page.locator("#masps .asp")).to_have_count(3)


def test_quickcrop_open_seeds_dialog(base_url: str, page: Page):
    _open_modal(base_url, page)
    dialog = page.locator('#modal [role="dialog"]')
    expect(dialog).to_be_visible()
    # Seeds from saved transforms (all zoom 1 in the fixture).
    expect(page.locator("#mzval")).to_have_text("1.00×")
    # Focus moved into the dialog (close button).
    assert page.evaluate("document.activeElement && document.activeElement.id") == "mclose"


def test_quickcrop_aspect_tabs_switch(base_url: str, page: Page):
    _open_modal(base_url, page)
    page.locator('#masps .asp[data-a="1:1"]').click()
    expect(page.locator('#masps .asp[data-a="1:1"]')).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#mtag")).to_have_text("1:1")
    expect(page.locator("#mouttag")).to_have_text("1:1")


def test_quickcrop_wheel_zooms_and_syncs_slider(base_url: str, page: Page):
    _open_modal(base_url, page)
    expect(page.locator("#mzval")).to_have_text("1.00×")
    # Native wheel over the output preview → zoom in (negative deltaY). mouse.wheel
    # is dispatched after hovering the frame so the page's wheel handler fires.
    page.locator("#moutframe").hover()
    page.mouse.wheel(0, -400)
    expect(page.locator("#mzval")).not_to_have_text("1.00×")
    # The zoom slider value reflects the new zoom (msync ran).
    zoom_val = page.eval_on_selector("#mzoom", "el=>parseFloat(el.value)")
    assert zoom_val > 1.0


def test_quickcrop_drag_pans(base_url: str, page: Page):
    _open_modal(base_url, page)
    # Zoom in first so there is pan slack on both axes.
    page.locator("#moutframe").hover()
    page.mouse.wheel(0, -600)
    expect(page.locator("#mzval")).not_to_have_text("1.00×")
    x_before = page.eval_on_selector("#moff", "el=>parseFloat(el.value)")
    y_before = page.eval_on_selector("#moffy", "el=>parseFloat(el.value)")
    # Drag across the preview.
    box = page.locator("#moutframe").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 - 60, box["y"] + box["height"] / 2 - 60, steps=6)
    page.mouse.up()
    x_after = page.eval_on_selector("#moff", "el=>parseFloat(el.value)")
    y_after = page.eval_on_selector("#moffy", "el=>parseFloat(el.value)")
    assert (x_after != x_before) or (y_after != y_before)


def test_quickcrop_copy_to_all(base_url: str, page: Page):
    _open_modal(base_url, page)
    page.eval_on_selector("#mzoom", "el=>{el.value='2';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    expect(page.locator("#mzval")).to_have_text("2.00×")
    page.click("#mcopy")
    page.locator('#masps .asp[data-a="16:9"]').click()
    expect(page.locator("#mzval")).to_have_text("2.00×")


def test_quickcrop_esc_closes_and_restores_focus(base_url: str, page: Page):
    page.goto(f"{base_url}/job/{JOB_REAL}")
    expect(page.locator("#clip1")).to_be_visible(timeout=10_000)
    opener = page.locator('#clip1 button.adjust[aria-label="Quick crop clip 1"]')
    opener.click()
    expect(page.locator("#modal")).to_have_class("modal open")
    page.keyboard.press("Escape")
    expect(page.locator("#modal")).not_to_have_class("modal open")
    # Focus returns to the opener button.
    assert page.evaluate(
        "el=>document.activeElement===el", opener.element_handle()) is True
