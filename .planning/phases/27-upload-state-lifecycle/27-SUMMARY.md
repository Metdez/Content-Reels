---
phase: 27
name: Reliability — Non-blocking Upload + State Persistence + Lifecycle
status: complete
requirements: [REL-03, REL-04, REL-05]
completed: 2026-06-30
---

# Phase 27 — Non-blocking Upload + State Persistence + Lifecycle — SUMMARY

**Outcome:** Upload no longer blocks the event loop, in-flight failures survive a restart, concurrent encodes are bounded, shutdown is clean, and the `/upload` ingest-revert bug is fixed. **186 tests pass; ruff clean; coverage 91.4%; deprecation-free.**

## Changes (product code, `app.py`)
- **REL-03:** `upload` changed from `async def` → `def`, so FastAPI runs its synchronous whole-file SHA-256 + copy in the threadpool — a large upload no longer freezes the event loop and every in-flight progress poll.
- **bug #6 (Phase 25 finding):** `/upload` now `save_manifest(metadata)` **then** `update_stage("ingest","done")`. The old order saved a stale in-memory manifest after the stage update, silently reverting ingest to `pending` on disk.
- **REL-04 (error persistence):** `_job_payload` now falls back to the erroring stage's `error` message from the manifest when `RUNNING` has none — so a failure shown mid-run still shows after a server restart.
- **REL-04 (lifecycle):** replaced the deprecated `@app.on_event("shutdown")` with a modern `lifespan` context manager that sets `_SHUTTING_DOWN`; the re-render worker loop checks the flag and stops draining on shutdown.
- **REL-05 (concurrency cap):** a module-level `_RENDER_SLOTS = Semaphore(_MAX_RENDERS)` (default 1, override `CM_MAX_RENDERS`) wraps both `render_job` (in `_run_pipeline`) and `rerender_one` (in the worker), so simultaneous jobs / a job-render racing a clip re-render can't exhaust the GPU's NVENC session limit.

## Tests
- **Flipped:** `test_api.py` upload test → asserts `ingest == "done"` (was the bug-#6 characterization).
- **New `tests/test_lifecycle.py` (+4):** upload endpoint is sync (REL-03); in-flight error surfaces from the manifest with no `RUNNING` entry (REL-04); render cap defaults to 1, second non-blocking acquire fails (REL-05); leaving the lifespan sets `_SHUTTING_DOWN` (REL-04).

## Verification
- `pytest -q` → **186 passed**, coverage 91.4%; `ruff check` clean; no deprecation warnings.
- Bug ledger **#6 (ingest revert) — FIXED**.

## Improvement criteria applied
**Reliability** (no event-loop stalls, restart-survivable errors, bounded GPU sessions, clean shutdown), **Correctness** (ingest state), and **Code quality** (lifespan over deprecated on_event). New behavior is covered by tests.
