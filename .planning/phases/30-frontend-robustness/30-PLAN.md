---
phase: 30
name: Frontend Robustness — Error Surfacing + Polling
wave: 1
requirements: [FE-01, FE-02, FE-03, FE-04]
autonomous: true
---

# Phase 30 — Frontend Robustness: Error Surfacing + Polling

**Goal:** No more silent hangs — every poll/edit failure surfaces a readable state, infinite loops stop, and edit intent survives a failed apply. Templates: `job.html`, `editor.html`.

## Tasks
- **FE-01** — `job.poll` (`if(!r.ok)return;`) and `editor.pollRender` (`.catch(()=>{})`) currently swallow failures and poll forever. Add: a visible "⚠ Connection lost — retrying…" surface; stop polling on 404 (job/clip deleted) with a clear message; a consecutive-failure retry cap (e.g. 5) that stops + surfaces instead of looping. `pollLog`/`mPollLog` failures likewise non-fatal but not infinite.
- **FE-02** — replace the pre-run Run `alert()` (job.html) with an inline error surface consistent with the rest of the UI.
- **FE-03** — editor Apply clears `dirtyClip`/`dirtyAspects` BEFORE the POST resolves; move the clear into the `r.ok` branch so a failed apply keeps the dirty markers (retryable without re-nudging).
- **FE-04** — guard editor boot when `D.captions`/`D.audio`/`D.transforms` are missing/null (real error state, not a stuck "Loading editor…"); the modal `mGo` failure path must tear down / not leave a half-open `#mprog` progress UI.

## Verify (exit)
- Playwright (live, seeded job): simulate a failed poll (stub fetch to reject/404) → banner appears, polling stops within the cap; Run error shows inline (no alert dialog); a failed Apply keeps Apply enabled with dirty intact; editor boots to an error state when the clip payload lacks captions. 0 unexpected console errors.
- `pytest -q` still green (no backend regressions). ruff clean.
