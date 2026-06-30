---
phase: 25
name: HTTP API Integration Tests
wave: 1
requirements: [API-01, API-02, API-03, API-04, API-05]
autonomous: true
---

# Phase 25 — HTTP API Integration Tests

**Goal:** Exercise every endpoint in `content_machine/app.py` at the request boundary via the `client` TestClient fixture (Phase 23), asserting status codes, validation, and error paths — closing the app.py coverage gap (74.5%) and surfacing wiring bugs unit tests miss.

## Tasks (one new file: `tests/test_api.py`)
- **API-01** `/upload` — valid video → 303 + manifest `awaiting_run` (+ source_dims if probe stubbed); reject missing file (400), bad extension, dotfile, traversal name (400).
- **API-02** `/api/job/{id}/run` — start (ok, pipeline thread stubbed), re-run already-started (409), unknown job (404), missing source (400).
- **API-03** `/api/job/{id}` + `/log` (+ `lines` param) + `/clip/{idx}` GET — seeded job 200 + shape; unknown job/idx → 404.
- **API-04** `/clip/{idx}/edit` — `<0.5s` trim → 400; valid → `{queued:true}` (enqueue stubbed so no real render); `/rerender-status` idle + shape.
- **API-05** `/download/{id}/{idx}/{aspect}` — present → 200 video/mp4; missing aspect → 404; `/media` scoping (currently serves job.json/transcript — characterize, note as VAL-05); legacy `/reframe` route behavior.

## Verify (exit criteria)
- `tests/test_api.py` green; full `pytest -q` green; app.py coverage materially up from 74.5%.
- ruff clean on the new file.
- Bugs/sharp-edges (e.g. `/media` serving manifests → VAL-05; any 500 instead of 4xx) logged in SUMMARY.

## Notes
- Stub the pipeline thread (`app.threading.Thread`) and `_enqueue_rerender`/probe so no real ffmpeg/whisper/claude runs (mirror test_app.py techniques).
- Pure tests; do NOT modify product code. Report bugs, don't fix.
