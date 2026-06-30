---
phase: 29
name: Shared Crop-Math Module + Parity Test
wave: 1
requirements: [CROP-01, CROP-02]
autonomous: true
---

# Phase 29 — Shared Crop-Math Module + Parity Test

**Goal:** Collapse the 3 copies of the crop math (job.html JS + editor.html JS + Python) to ONE shared JS module sourced from server `source_dims`, locked to the Python renderer by a golden-vector parity test.

## Tasks
1. **CROP-01** — extract `computeCrop`/`drawBox`/`drawOut` into `content_machine/static/crop.js` (no build; expose as `window.CMCrop`). Add a `/static` StaticFiles mount in `app.py`. Refactor `job.html` + `editor.html` to `<script src="/static/crop.js">` and call `CMCrop.*`; pass server `source_dims` (not the `<video>` intrinsic dims) into the crop math. Preserve exact current behavior/values.
2. **CROP-02** — `tests/test_crop_parity.py`: generate golden vectors from Python `render.compute_crop` over a grid of (src dims, aspect, zoom, x, y), run `crop.js`'s `computeCrop` in Node, assert exact `(x,y,w,h)` match. Add Node setup to CI so it runs there too.

## Verify (exit)
- `pytest -q` green incl. parity test; ruff clean.
- `GET /static/crop.js` → 200; `/job/{id}` + editor still draw crop boxes correctly — **Playwright pixel-parity check** (preview box matches a known computeCrop result).
- No visual regression on the seeded job.
