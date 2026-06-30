---
phase: 35
name: Exhaustive Playwright E2E Suite
status: complete
requirements: [E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06]
completed: 2026-06-30
---

# Phase 35 — Exhaustive Playwright E2E Suite — SUMMARY

**Outcome:** A real, runnable pytest-playwright suite covering every page/interaction/edge state, plus a real-ffmpeg render through the app. **E2E UI suite: 34 passed (deterministic); slow real-render: passes in isolation (16s); default unit suite: 211 passed; ruff clean.** No app bugs found — two test-infra bugs fixed.

## Deliverables
- `pytest-playwright` + chromium installed; added to dev deps. `tests/e2e/conftest.py` — self-contained harness: seeds a real-media completed job (`seed_fixture.seed`) + placeholder jobs (awaiting-run, zero-dims, no-captions, dispose-404), launches its own uvicorn on a free port, yields `base_url`.
- 7 spec files (all `@pytest.mark.e2e`): `index` (E2E-01), `job_preview` (E2E-02), `progress_clips` (E2E-03), `quickcrop` (E2E-04), `editor` (E2E-05), `edge` (E2E-06), `real_render` (E2E-05/real, also `slow`).
- CI: added a separate `e2e` job (apt ffmpeg + fonts, playwright chromium, `pytest -m "e2e and not slow"`). Unit job unchanged (`-m "not e2e and not slow"`).

## Test-infra bugs found + fixed (NOT app bugs)
1. **Harness pipe deadlock** — the conftest launched uvicorn with `stdout=PIPE` and never drained it; a render logs hundreds of ffmpeg lines → the OS pipe buffer fills → the server blocks on `write()` → the render thread **deadlocks** (the real-render spec hung at 120s). Fixed: redirect server output to a log file (drainable). The app re-render itself was proven fast 4 independent ways (9.6s direct / 11s via :8000 HTTP / 10s subprocess-repro / 16s in-spec after the fix). Production uvicorn drains its own stdout, so this only affected the test harness.
2. **conftest import collision** — adding `tests/e2e/conftest.py` made the bare `from conftest import seed_job` in `test_api.py`/`test_validation.py` resolve to the e2e conftest (no `seed_job`), breaking the default collection. Fixed → `from tests.conftest import seed_job`.

## Resolution of the 7 initial failures
The first build had 27/34 passing; all 7 failures were test-side (strict-mode selector matching 2 elements, an impossible `.pill.run` assertion, a `route.abort` that wiped the DOM, an inverted slack-axis assertion, a real-pipeline Run that needed stubbing, synthetic-pointer trim-drag not driving `document`-bound handlers, a completed-job 404 that needed `page.route`). No app/template defect — verified against the source each time.

## Verification
- `pytest -m "e2e and not slow"` → **34 passed** (deterministic, ~77s).
- `pytest tests/e2e/test_e2e_real_render.py -m "e2e and slow"` → **1 passed** in 16s (real x264 re-render through `/edit`, output `?v=` changes). (Run in isolation; under a shared session it contends on the single per-clip render slot with the UI specs' renders — hence `slow` + separate.)
- `pytest -m "not e2e and not slow"` → 211 passed; ruff clean.

## Note (real pipeline)
The full transcribe→select→render isn't E2E-driven because `claude -p` (subscription CLI) + whisper aren't headlessly invocable here; that path is covered by unit/integration tests + the Phase 36 manual real run. The editor-Apply path is the genuine real-ffmpeg E2E.

## Improvement criteria applied
**Test coverage** (every page/flow/edge now has an automated browser check + a real-render check) and **Reliability** (the harness deadlock + collision fixes harden the test infra itself).
