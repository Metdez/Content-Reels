---
phase: 23
name: Test Harness & CI Foundation
status: complete
requirements: [QA-01, QA-02, QA-03, QA-04, QA-05]
completed: 2026-06-30
---

# Phase 23 — Test Harness & CI Foundation — SUMMARY

**Outcome:** The v6 testing foundation is in place. All 14 later phases now have coverage measurement, an HTTP-layer client, a seeded-job harness, a lint gate, and CI to build on.

## What shipped

- **QA-01 — Coverage.** Added `pytest-cov` (+ `httpx`, `ruff`) to `[project.optional-dependencies].dev`; `[tool.coverage.run]` (source=`content_machine`) + pytest `addopts="--cov ... --cov-report=term-missing"`. **Baseline: 64.2% overall** (app 74.5, jobs 96.3, transcribe 78.7, config 81.8, select 62.4, captions 66.0, hwaccel 60.3, render 46.2, logging_setup 45.7, **cli 0.0**). cli/logging_setup/render are the Phase 24 targets.
- **QA-02 — TestClient fixture.** `tests/conftest.py`: a `client` fixture that sets `CM_DATA_DIR` to a tmp dir and reloads `config`+`app` (so the import-time `/media` mount + `UPLOADS` rebind), yielding a `starlette.testclient.TestClient`. Plus `seed_job()` + `seeded_job` fixture writing a complete rendered job (manifest all-stages-done, transcript w/ words, clips.json, clips/render.json, per-aspect mp4s, edit.json) matching the exact shapes `_job_payload`/`_clip_editor_payload` consume. `tests/test_harness.py` adds 6 first-ever HTTP-boundary tests.
- **QA-03 — Playwright harness.** `scripts/seed_fixture.py` seeds a job into the live `DATA_DIR` with **real** playable mp4s (vendored ffmpeg `testsrc`+`sine`, correct per-aspect dims) so `/job/{id}` + the editor render with no pipeline run. **Verified live via Playwright**: review grid shows "Complete 🎉 100%", all stages done, 2 clips with aspect tabs + edit/quick-crop/download; ffprobe confirms 9x16=1080×1920 h264; **0 console errors**.
- **QA-04 — ruff.** `[tool.ruff]` config (line-length 100, py311, `select=F,E,W,I,UP,B`). Auto-fixed 15 (imports/unused/pyupgrade); fixed 1 real nit (`raise ... from e` in `upload`); scoped B023 with a documented rationale (every flagged closure is created+consumed in one loop iteration — no late-binding escape) and test-only E702/E731. `ruff check content_machine tests` → **clean**.
- **QA-05 — CI.** `.github/workflows/test.yml`: on push/PR, py3.11, `pip install -e ".[dev]"`, `ruff check`, then `pytest -m "not e2e and not slow"`. `Makefile` gained `lint`/`cov`/`e2e-seed`.

## Verification
- `pytest -q` → **64 passed** (58 prior + 6 new), coverage 64.2%.
- `ruff check content_machine tests` → exit 0.
- CI-equivalent (`ruff` + `pytest -m "not e2e and not slow"`) green locally.
- Seeded job driven live in the browser — full review grid, no errors.

## Notes / fixes during the phase
- `seed_fixture.py` first failed because the drawtext label `Clip 1 9:16` contains a colon (ffmpeg's option separator) — fixed by stripping `:` from labels.
- Known cosmetic: Starlette warns `httpx`+TestClient is deprecated in favor of `httpx2`; harmless, TestClient works. Fontconfig warnings from ffmpeg drawtext are non-fatal (outputs valid).
- "Better" criteria touched: **Test coverage** (foundation), **Reliability** (CI gate), small **Error-handling** improvement (`raise from`).

## Improvement criteria applied
Per the v6 standard, this phase advances **Test coverage** (measurement + HTTP/E2E harness) and **Reliability** (lint + CI gate) with no behavior regression (64/64 green).
