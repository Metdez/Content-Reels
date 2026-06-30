---
phase: 31
name: Frontend Correctness — Captions, Audio, Validation
status: complete
requirements: [FE-05, FE-06, FE-07, FE-08]
completed: 2026-06-30
---

# Phase 31 — Frontend Correctness: Captions, Audio, Validation — SUMMARY

**Outcome:** The editor's caption/audio editing is now correct + auditable, and media is cache-busted consistently. **201 tests pass; ruff clean; coverage 92.6%; all four live-verified.**

## Changes
- **FE-05** — new `GET /api/job/{id}/clip/{idx}/captions?start=&end=` → `{segments: clip_caption_events(segs,start,end)}` (404 on missing job/idx). The editor "Re-derive from transcript" button now calls it with the **current trim** and replaces the caption rows — previously a no-op that just reset to the loaded segments. (`app.py`, `editor.html`)
- **FE-06** — editor source `<video>` gained `controls` (kept `muted playsinline` for autoplay safety) so trims can be scrubbed + audio auditioned; existing track-scrub/playhead/preview still work. (`editor.html`)
- **FE-07** — caption time inputs validated: NaN/empty rejected, `start<end` enforced, bounded to the clip window; bad values show a per-row inline error, aren't written to the edit, and block Apply (`capBad` set) until fixed. (`editor.html`)
- **FE-08** — `app.media_url` appends `?v=<int mtime>` (guarded for missing file) so every output URL busts when content changes — reconcile-rebuilt cards + editor previews included. (`app.py`)

## Tests
- New in `test_api.py`: `/captions` window segments + 404s; `test_api_job_outputs_carry_cache_bust` (`?v=` present). Updated `test_app.py::test_media_url_*` to assert path + `?v=`.

## Verification
- `pytest -q` → **201 passed**, coverage 92.6%; ruff clean.
- Server restarted; **live:** `/captions?start=0&end=3` → window-scoped segment; `/api/job/...` output URL = `…/9x16.mp4?v=1782835624`; editor `<video controls muted>`; invalid caption times ("abc"/start≥end/"-5") → inline errors + Apply disabled, valid value clears it; editor loads with **0 console errors**.

## Improvement criteria applied
**Correctness** (re-derive actually reflects the trim; caption times validated; previews never stale), **UX clarity** (auditable audio, inline caption errors), **Reliability** (mtime cache-bust removes a stale-media class). Covered by tests + live checks.

## Open ledger note
Bug #5 (`stream_run` swallows `on_line` exceptions + `CalledProcessError` without output, `logging_setup.py`) remains — low severity (a progress-parse hiccup just skips a progress tick); will note/close in Phase 36.
