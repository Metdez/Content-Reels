---
phase: 32
name: Accessibility Pass (WCAG 2.1 AA)
wave: 1
requirements: [A11Y-01, A11Y-02, A11Y-03, A11Y-04]
autonomous: true
---

# Phase 32 — Accessibility Pass (WCAG 2.1 AA where feasible)

**Goal:** Make all three pages keyboard- and screen-reader-operable and touch-friendly. Templates: `index.html`, `job.html`, `editor.html`.

## Tasks
- **A11Y-01** — aspect tabs (`.asp`), clip tabs (`.tab`), and the modal close `✕` become real keyboard-operable `<button>`s with roles/`aria-label`s (or proper `role="tab"` semantics). Currently `<span>`s with no keyboard handling.
- **A11Y-02** — Quick-crop modal: `role="dialog"` + `aria-modal="true"`, a focus trap, ESC-to-close, and focus return to the opener.
- **A11Y-03** — associate slider `<label for>`/`aria-label`; `aria-live="polite"` on the progress + live-log + status regions; convey state by text+icon, not color alone (pills/step-dots get text).
- **A11Y-04** — trim handles ≥24px hit area; wheel-zoom must not trap page scroll (only `preventDefault` when actually zooming the preview, or require focus/hover-intent); index drop enforces video type/size with a friendly rejection; unify the preview CAP base across modal/editor/card (keep the editor MAG multiplier).

## Verify (exit)
- Playwright (live): inject axe-core (CDN) and assert **no critical/serious violations** on `/`, `/job/{seeded}`, and the editor; if axe unreachable, do targeted assertions instead. Keyboard: Tab reaches aspect/clip tabs + activates with Enter/Space; ESC closes the modal and returns focus. 0 console errors.
- `pytest -q` green (no backend touched); ruff clean.
