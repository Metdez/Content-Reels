---
phase: 27
name: Reliability — Non-blocking Upload + State Persistence + Lifecycle
wave: 1
requirements: [REL-03, REL-04, REL-05]
autonomous: true
---

# Phase 27 — Non-blocking Upload + State Persistence + Lifecycle

**Goal:** Keep the event loop responsive during uploads, make failure state survive a restart, bound concurrent encodes, and shut down cleanly. Also fix bug #6 (ingest reverts to pending in /upload).

## Tasks
1. **REL-03** — `/upload` becomes a sync `def` (Starlette threadpool) so its blocking hash/copy no longer stalls the event loop + polls.
2. **bug #6** — persist upload metadata first, then `update_stage("ingest","done")` (was clobbered by a trailing stale save).
3. **REL-04** — `_job_payload` surfaces the error from the manifest stage when `RUNNING` has none (survives restart); add a `lifespan` shutdown that sets `_SHUTTING_DOWN`; the re-render worker checks it.
4. **REL-05** — a global `_RENDER_SLOTS` semaphore (default 1, `CM_MAX_RENDERS`) around `render_job` and `rerender_one`.

## Verify (exit)
- Full `pytest -q` green; ruff clean. Flip bug-#6 test (ingest → done). New `tests/test_lifecycle.py`: upload is sync; error surfaces from manifest; render cap = 1; lifespan sets shutdown flag.
- Bug ledger #6 FIXED; deprecation-free (lifespan, not on_event).
