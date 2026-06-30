---
phase: 23
name: Test Harness & CI Foundation
wave: 1
requirements: [QA-01, QA-02, QA-03, QA-04, QA-05]
autonomous: true
---

# Phase 23 — Test Harness & CI Foundation

**Goal:** Stand up the testing foundation everything else in v6 depends on — coverage measurement, an HTTP-layer test client, a headless Playwright-able seeded-job harness, a lint gate, and CI. Derived from `.planning/v6-DISCOVERY.md` §(c).

## Tasks

1. **QA-01 coverage** — add `pytest-cov` (+ `httpx`, `ruff`) to `[project.optional-dependencies].dev`; configure `[tool.coverage.run]` (source=`content_machine`) and pytest `addopts`. Record a baseline coverage number in the SUMMARY.
2. **QA-02 TestClient fixture** — `tests/conftest.py`: a `client` fixture that points `CM_DATA_DIR` at a tmp dir, reloads `config`+`app`, and yields a `starlette.testclient.TestClient`; plus a `seed_job()` helper + `seeded_job` fixture that writes a completed job (job.json all-stages-done, clips/render.json with outputs, transcript.json, clips.json, edit.json) with tiny real mp4s.
3. **QA-03 Playwright harness** — `scripts/seed_fixture.py`: seeds a completed job into the live `DATA_DIR` with real 1s mp4s (vendored ffmpeg lavfi) so `/job/{id}` + the editor render with no pipeline run; documented via `make e2e-seed`. Verify live by driving it with the Playwright browser.
4. **QA-04 ruff** — `[tool.ruff]` config; run `ruff check` on `content_machine/` + `tests/` and make it green (fix or scope ignores with rationale).
5. **QA-05 CI** — `.github/workflows/test.yml`: on push/PR, install dev deps, `ruff check`, `pytest -m "not e2e and not slow"` on Python 3.11 (ubuntu; binary-dependent tests skip cleanly).

## Verify (exit criteria)
- `pytest -q` still green (was 58) + coverage reported with a baseline number.
- `client` fixture smoke test passes (`GET /` 200); `seeded_job` renders clips via `/api/job/{id}` + `/job/{id}` 200.
- `ruff check content_machine tests` exits 0.
- Seed script produces a job the live UI shows clips for (Playwright-verified).
- CI workflow file present and internally consistent (lint + tests).

## Notes
- Windows venv is `.venv/Scripts/`; Makefile POSIX targets mirror with a note.
- E2E/real-render tests carry `@pytest.mark.e2e`/`slow` and are excluded from the default CI run.
