---
phase: 35
name: Exhaustive Playwright E2E Suite
wave: 1
requirements: [E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06]
autonomous: true
---

# Phase 35 — Exhaustive Playwright E2E Suite

**Goal:** Codify every page/interaction/edge state from discovery as repeatable `pytest-playwright` specs, plus one real ffmpeg render through the UI.

## Harness
- `pip install pytest-playwright` + `playwright install chromium`; add to dev deps; add browser install to CI (e2e job).
- `tests/e2e/conftest.py`: session fixture seeds a temp `CM_DATA_DIR` (real-media job via `scripts/seed_fixture.seed`), launches `uvicorn` on a free port, yields `base_url`; teardown stops it. All specs `@pytest.mark.e2e` (excluded from the default unit CI run; run in a dedicated e2e job).

## Specs
- **E2E-01** index: submit enable/disable, drag/drop highlight, library pills, submit→uploading.
- **E2E-02** job preview (awaiting_run fixture): aspect tabs, zoom/X/Y, slack-disable, reset, copy-to-all, Run.
- **E2E-03** progress+clips (completed fixture): master/step bars, log, clip aspect tabs swap, downloads resolve, done state; reconcile-in-place (video element identity preserved).
- **E2E-04** Quick-crop modal: open/seed, tabs, scroll-zoom, drag-pan, slider sync, copy-to-all, ESC/focus.
- **E2E-05** editor: reframe (slider+scroll+drag), magnifier cycle, trim drag + word-snap, playhead/preview, caption toggle/edit/validate, audio mute/volume, Apply→flow pill, resume.
- **E2E-06** edge/error: zero source_dims, missing captions payload (safe boot), invalid caption time blocked, 404 job → polling stops + surface.
- **Real render (E2E + slow):** open editor on seeded clip → nudge framing → Apply → wait for the background re-render (REAL ffmpeg) to settle → assert the output updates (new `?v=`). (Full transcribe→select→render needs `claude -p`/whisper which aren't headlessly invocable here — exercised by unit/integration + Phase 36 manual; the editor Apply path is the real-ffmpeg E2E.)

## Verify (exit)
- `pytest -m e2e` green locally (report counts). Default `pytest -m "not e2e and not slow"` still green. ruff clean. CI e2e job added.
