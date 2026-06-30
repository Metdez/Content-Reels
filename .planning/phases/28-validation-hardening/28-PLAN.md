---
phase: 28
name: Input Validation & Hardening
wave: 1
requirements: [VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06]
autonomous: true
---

# Phase 28 — Input Validation & Hardening

**Goal:** Validate/bound user+edit inputs, make `claude -p` selection resilient, and clean up portability/security sharp edges. Clears bug-ledger items #2, #3, #4, #7, #8. Regression-first where a characterization test exists (flip it).

## Tasks
- **VAL-01** trim/zoom bounds: `save_clip_edit` (`app.py`) clamps `start>=0` / `end<=duration` (load transcript duration); `render.normalize_transforms` caps `zoom` at a `MAX_ZOOM` (e.g. 5.0) in addition to the `>=1.0` floor.
- **VAL-02** `select.run_claude` resilience (bugs #2/#3/#4): guard `json.loads(proc.stdout)` → clear `RuntimeError` (no raw `JSONDecodeError`); `(proc.stderr or "")[:500]`; add retry/backoff (≥2 retries) on timeout/non-zero/parse-fail; transcript-scaled timeout. `select_clips` wraps each chunk's `run_claude` so one bad chunk logs + is skipped (partial results) instead of aborting the whole stage; only raise if ALL chunks fail.
- **VAL-03** upload collision: stage to a unique temp name (nonce/uuid), not `UPLOADS/safe_name`, so concurrent same-name uploads don't clobber.
- **VAL-04** friendly empty/silent transcript: `_run_pipeline` (or `select_clips`) maps "no segments"/empty to the friendly "no clip-worthy moments" surface, not a raw `ValueError`.
- **VAL-05** `/media` scoping: serve only media extensions (allowlist `.mp4/.mov/.webm/.jpg/.jpeg/.png/.gif`); deny `.json/.log/.txt/.wav` (StaticFiles subclass → 404).
- **VAL-06** platform hints: `require_tool` hints platform-aware (Windows → setup.ps1, not `brew install`) in `transcribe.py:50/85`, `render.py:272`.
- **#8 (minor):** leave the dead empty-filename guard (harmless) — note only.

## Verify (exit)
- Full `pytest -q` green; ruff clean. Flip the run_claude characterization tests (#2/#3) to assert graceful handling/retry. Add tests: trim/zoom clamping, /media denies job.json (404) but serves mp4, upload collision, friendly empty transcript, platform hint string.
- Bug ledger #2/#3/#4/#7 FIXED; #8 noted.
