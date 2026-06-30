---
phase: 30
name: Frontend Robustness — Error Surfacing + Polling
status: complete
requirements: [FE-01, FE-02, FE-03, FE-04]
completed: 2026-06-30
---

# Phase 30 — Frontend Robustness: Error Surfacing + Polling — SUMMARY

**Outcome:** No more silent hangs. Poll/edit failures surface a readable state, infinite polling stops (404 / retry-cap), edit intent survives a failed apply, and the editor boots safely on a bad payload. **Templates-only; 197 tests pass; ruff clean; Playwright-verified (5 failure scenarios + happy path).**

## Changes (`job.html`, `editor.html` — JS only)
- **FE-01** — `job.poll` + `editor.pollRender` wrapped in try/catch with a consecutive-failure counter (cap 5): a transient "⚠ Connection lost — retrying…" banner that clears on success; **stop** on 404 ("This job no longer exists.") or at the cap ("retrying paused — reload"). New `.connbar` element + CSS in job.html; editor surfaces via the flow pill + status. `pollLog`/`mPollLog` bounded too. The editor pill never spins forever.
- **FE-02** — pre-run Run `alert()` → inline `#runerr` `.err` banner.
- **FE-03** — editor Apply clears `dirtyClip`/`dirtyAspects` only in the `r.ok` branch; a failed apply keeps dirty + Apply enabled + "…your changes are kept, press Apply to retry."
- **FE-04** — editor boot wrapped in try/catch: a network/404/unusable-payload (missing core `start`/`end`) shows a red error state instead of a stuck "Loading editor…"; `captions`/`audio`/`transforms` are safely defaulted (`||{}`/`||[]`). Modal `mGo` failure tears down `#mprog` (reset + stop polls) and shows inline `#merr`.

## Verification (Playwright, live seeded job)
1. Job 404 → connbar "no longer exists", polling stopped ✓
2. Job network reject → warn banner for fails 1–4, "retrying paused" + stop at 5 ✓
3. Editor renderer reject → pill "⚠ Connection lost" (not spinning), timer stopped ✓
4. Editor failed Apply (503) → dirty kept, Apply enabled, clear message ✓
5. Editor boot with unusable payload → red error state, no hang; safe-defaults path boots fine ✓
- Happy-path re-check (clean browser): job page 2 clips, polling stopped at "done", connbar present, **0 console errors**; editor loads clean.
- `pytest -q` → 197 passed (no backend regression); ruff clean.

## Note
- Interpretation call (FE-04): missing `captions`/`audio`/`transforms` are safe-defaulted (non-fatal); the hard error state is reserved for a payload missing core `start`/`end`. Reasonable — keeps a caption-less clip editable while still failing loudly on a truly broken payload.

## Improvement criteria applied
**Error-handling / UX clarity** (every failure now visible, no silent hangs), **Reliability** (bounded polling, no infinite loops), **Correctness** (dirty survives failed apply). All verified live.
