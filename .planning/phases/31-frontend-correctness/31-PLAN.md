---
phase: 31
name: Frontend Correctness — Captions, Audio, Validation
wave: 1
requirements: [FE-05, FE-06, FE-07, FE-08]
autonomous: true
---

# Phase 31 — Frontend Correctness: Captions, Audio, Validation

**Goal:** Make the editor's caption/audio editing actually correct + auditable, and cache-bust media consistently.

## Tasks
- **FE-05** — "Re-derive from transcript" is a no-op (fetches, never parses). Add a real backend endpoint `GET /api/job/{id}/clip/{idx}/captions?start=&end=` → `{segments: captions.clip_caption_events(transcript_segments, start, end)}`; the editor button calls it with the CURRENT trim window and replaces the caption rows. (Now it actually reflects a changed trim.)
- **FE-06** — the editor source `<video>` is `muted playsinline` with no controls → audio edits aren't auditionable. Add native `controls` (and/or a mute-toggle) so the user can scrub + hear audio before re-render.
- **FE-07** — caption time inputs (`parseFloat||0`) silently coerce junk → 0. Validate: numeric, `start<end`, within [trimIn,trimOut]; show an inline error + block a bad value.
- **FE-08** — output media isn't consistently cache-busted (reconcile-rebuilt cards lack `?t=`). Make `app.media_url` append `?v=<int file mtime>` so any output URL busts whenever the file content changes; simplify/keep the editor's manual bust. Update the one exact-match `media_url` unit test in `tests/test_app.py` to tolerate the `?v=` suffix.

## Verify (exit)
- `pytest -q` green (update media_url test); ruff clean.
- Playwright (live, seeded job editor): Re-derive after changing trim returns window-scoped caption rows; source video has controls; invalid caption time shows inline error + is blocked; an output URL carries `?v=`. 0 console errors on happy path.
