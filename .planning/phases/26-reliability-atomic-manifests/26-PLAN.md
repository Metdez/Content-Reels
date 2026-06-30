---
phase: 26
name: Reliability — Atomic Manifests + Locking
wave: 1
requirements: [REL-01, REL-02]
autonomous: true
---

# Phase 26 — Reliability: Atomic Manifests + Locking

**Goal:** Fix the truncated-read 500s and cross-clip `render.json` lost-update (bug ledger #1) found in Phase 24/25. Regression-first: the lost-update characterization test already pins the bug; flip it on fix.

## Tasks
1. **REL-01 atomic writes** — `jobs.atomic_write_text` (temp + `os.replace`, Windows sharing-violation retry); use in `Job.save_manifest` and the `render.json` writes.
2. **REL-01 tolerant reads** — `jobs.read_json` (retry on transient `PermissionError`/`JSONDecodeError`); use in `Job.load_manifest`/`Job.load`, `render` manifest reads, and `app` poll reads (`_job_payload`/`_clip_editor_payload`).
3. **REL-02 locked upsert** — `render._upsert_render_clips` (per-job lock, fresh re-read, upsert-by-index, atomic write); route `render_job` + `rerender_one` through it.
4. Flip `test_rerender_one_*` to assert the concurrent update survives; add `tests/test_reliability.py` (atomic write, no-torn-read under threads, concurrent-upsert, save_manifest atomic).

## Verify (exit)
- Full `pytest -q` green; ruff clean; the flipped + new tests pass; coverage steady/up.
- Bug ledger #1 marked FIXED.
