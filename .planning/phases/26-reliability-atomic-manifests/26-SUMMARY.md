---
phase: 26
name: Reliability — Atomic Manifests + Locking
status: complete
requirements: [REL-01, REL-02]
completed: 2026-06-30
---

# Phase 26 — Reliability: Atomic Manifests + Locking — SUMMARY

**Outcome:** The two highest-severity backend bugs (truncated-read 500s and cross-clip lost-updates on `render.json`) are fixed. Manifest writes are atomic, reads are tolerant, and concurrent clip re-renders merge under a per-job lock. **182 tests pass; ruff clean; coverage 91.6%.** The lost-update characterization test flipped to assert the corrected behavior; +4 new reliability regression tests.

## Changes (product code)
- **`jobs.atomic_write_text(path, text)`** — write to a temp file in the same dir + `os.replace`. On Windows, `os.replace` raises `PermissionError` (WinError 5, sharing violation) if a reader holds the destination open; retry up to 20×5ms. (`jobs.py`)
- **`jobs.read_json(path, default=...)`** — the read side: tolerate the transient `PermissionError` (Windows mid-replace open) AND `JSONDecodeError` (partial read), retrying briefly. Returns `default` when absent. (`jobs.py`)
- **`Job.save_manifest`** now uses `atomic_write_text`; **`Job.load_manifest`/`Job.load`** use `read_json` (REL-01).
- **`render._upsert_render_clips(job, entries, reset=)`** — a per-job-locked, fresh-reread, upsert-by-index, atomic write of `clips/render.json`. Both `render_job` (resets then upserts each clip incrementally) and `rerender_one` (upserts its one clip) go through it, so a concurrent clip's entry is never clobbered (REL-02). (`render.py`)
- **`app._job_payload` / `_clip_editor_payload`** read `render.json` via `read_json` so a poll landing mid-write returns data, not a 500 (REL-01).

## Tests
- **Flipped:** `test_rerender_one_*` characterization → `test_rerender_one_preserves_concurrent_clip_update` (REL-02 regression: a concurrent clip-2 update during clip-1 re-render now survives).
- **New `tests/test_reliability.py` (+4):** atomic replace + no temp leftover; **no torn read under concurrent reader/writer threads** (resilient `read_json` tolerates the Windows replace window — the production poll path); concurrent upserts of different indices all survive (REL-02); `save_manifest` atomic.

## Verification
- `pytest -q` → **182 passed**, coverage 91.6%; `ruff check` clean.
- Bug ledger item **#1 (render.json non-atomic RMW) — FIXED**.

## Notes / discoveries
- Windows `os.replace` is atomic but not sharing-violation-proof — the write-retry + tolerant-read pair is required on this platform (surfaced by the concurrency test, now both sides handled).
- The running dev server (PID from session start) is pre-P23 code; these fixes take effect on restart (will be re-verified live in Phases 35–36).

## Improvement criteria applied
**Reliability** (no torn reads, no lost updates) and **Correctness** (manifest integrity under concurrency), with **Test coverage** regressions locking it in. No user-facing behavior change except the absence of intermittent failures.
