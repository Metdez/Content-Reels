---
phase: 32
name: Accessibility Pass (WCAG 2.1 AA)
status: complete
requirements: [A11Y-01, A11Y-02, A11Y-03, A11Y-04]
completed: 2026-06-30
---

# Phase 32 — Accessibility Pass (WCAG 2.1 AA) — SUMMARY

**Outcome:** All three pages are keyboard- and screen-reader-operable and touch-friendly. **axe-core: 0 critical/serious (and 0 total WCAG 2A/2AA) violations on `/`, the job page, and the editor.** Templates-only; 201 tests pass; ruff clean.

## Changes (`index.html`, `job.html`, `editor.html`)
- **A11Y-01** — aspect tabs (`.asp`), clip tabs (`.tab`), modal close → real `<button>`s with `aria-pressed`/`aria-label`, Tab-reachable + Enter/Space-activatable, wrapped in `role="group"`; icon buttons (`✂`/`✎`/`🔍`/`✕`) labeled. CSS resets keep the exact prior look.
- **A11Y-02** — Quick-crop modal: `role="dialog"` + `aria-modal` + `aria-labelledby`; on open focus moves into the dialog (remembering the opener), **Tab/Shift+Tab trapped**, **ESC closes**, focus returns to the opener.
- **A11Y-03** — every slider labeled (`aria-label` + `aria-describedby` value); `aria-live="polite"`/`role="status"` on progress, step list, live-log, status banners, modal render rows, editor summary + flow pill; tab state via `aria-pressed` (non-color); also fixed a caught axe-critical (15 unlabeled caption inputs).
- **A11Y-04** — trim handles 12→24px hit area; wheel-zoom only `preventDefault`s when the zoom actually changes (no scroll-trap at min/max); index drop enforces video type + 2GB with a `role="alert"` rejection; unified preview `PREVIEW_CAP=420` across modal/card (editor keeps `CAP*MAG`).

## Verification (Playwright, live, axe-core 4.10.2)
- axe critical+serious: `/`=0, `/job/{seeded}`=0, editor=0 (+ modal-open scan 0). Independent re-run on the job page: **0 total WCAG 2A/2AA violations**, clip tabs are `BUTTON`, `#mclose` has `aria-label`.
- Keyboard: clip tab Enter switches active + updates `aria-pressed`; editor tab Space switches; modal — Enter opens with focus on close, Shift+Tab wraps (trap), **ESC closes + focus returns to the ✂ opener**.
- 0 console errors on all three pages.
- `pytest -q` → 201 passed; ruff clean.

## Improvement criteria applied
**Accessibility** (WCAG 2.1 AA: keyboard, roles, labels, live regions, focus management, touch targets) — the headline; plus **UX clarity** (non-color state) and **Reliability** (no scroll-trap, drop validation). Zero visual/behavioral regression (axe + keyboard + console verified).
