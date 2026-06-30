---
phase: 28
name: Input Validation & Hardening
status: complete
requirements: [VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06]
completed: 2026-06-30
---

# Phase 28 — Input Validation & Hardening — SUMMARY

**Outcome:** Inputs are bounded, `claude -p` selection is resilient, and the portability/security sharp edges are closed. **196 tests pass; ruff clean; coverage 92.4%.** Clears bug-ledger #2/#3/#4/#7; #8 noted (harmless dead guard left).

## Changes (product code)
- **VAL-02** (`select.py`) — `run_claude` rewritten: guarded stdout parse (chatty/non-JSON → clear `RuntimeError`, never a raw `JSONDecodeError`), None-safe `stderr`, **retry×3 with `1.5**attempt` backoff** on timeout/non-zero/non-JSON (`is_error` stays a hard non-retry), prompt-scaled default timeout (`min(600, 120+len//100)`). `select_clips` skips a failing chunk (logs, continues) and only raises if **all** chunks fail with no clips.
- **VAL-01** — `save_clip_edit` (`app.py`) clamps `start>=0` / `end<=duration` (from transcript); `render.normalize_transforms` caps `zoom` at `MAX_ZOOM=5.0`.
- **VAL-03** — `/upload` stages to `UPLOADS/{uuid}_{name}` so concurrent same-name uploads don't collide.
- **VAL-04** — `_run_pipeline` detects an empty/silent transcript and surfaces the friendly "No clip-worthy moments found…" message instead of a raw `ValueError`.
- **VAL-05** — `MediaFiles(StaticFiles)` subclass serves only `{.mp4,.mov,.webm,.m4v,.jpg,.jpeg,.png,.gif}` and 404s everything else; `/media/{job}/job.json` no longer leaks the manifest.
- **VAL-06** — `config.ffmpeg_hint()`/`whisper_hint()` give platform-correct install hints (Windows → `scripts/setup.ps1`, not `brew`); wired into `transcribe.py` + `render.py`.

## Tests
- **Flipped** (old buggy → correct): 3 `run_claude` tests in `test_select_transcribe.py` (timeout/non-zero now retry-then-raise; chatty stdout → clear RuntimeError); `test_api.py` `/media` test (job.json → 404, source.mp4 → 200).
- **Added**: `test_select_transcribe.py` (+3: None-stderr safe, chunk-skip keeps partial, all-fail raises); new `tests/test_validation.py` (zoom cap+floor, trim clamping, upload-collision distinct jobs, empty-transcript friendly via `_run_pipeline`, platform hint strings).

## Verification
- `pytest -q` → **196 passed**, coverage 92.4%; `ruff check` clean.
- Bug ledger **#2, #3, #4 (run_claude), #7 (VAL-05 /media) — FIXED**; **#8** (dead empty-filename guard) left as a harmless no-op (documented).

## Improvement criteria applied
**Reliability** (selection survives transient/partial failures), **Correctness** (bounded trims/zoom, friendly empty path), **Error-handling** (clear messages, no raw exceptions), **Security** (media-only mount), **Code quality** (platform hints). All covered by tests.
