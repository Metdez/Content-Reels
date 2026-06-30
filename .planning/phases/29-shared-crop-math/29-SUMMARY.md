---
phase: 29
name: Shared Crop-Math Module + Parity Test
status: complete
requirements: [CROP-01, CROP-02]
completed: 2026-06-30
---

# Phase 29 — Shared Crop-Math Module + Parity Test — SUMMARY

**Outcome:** The crop math is now ONE shared JS module, sourced from server `source_dims`, and locked to the Python renderer by a 960-vector parity test. A real latent 1px drift was found and fixed. **197 tests pass; ruff clean; coverage 92.5%; verified live in-browser.**

## Changes
- **CROP-01** — `content_machine/static/crop.js` (`window.CMCrop = {computeCrop, drawBox, drawOut}`, also `module.exports` for Node). `job.html` + `editor.html` drop their inline duplicates, `<script src="/static/crop.js">`, and call `CMCrop.*`. `drawOut` unified to take explicit `srcW/srcH` + a `cap` param. **All crop calls now use server `source_dims`** (intrinsic-`<video>`-dims fallback inside `drawOut`). `/static` StaticFiles mount added to `app.py`.
- **CROP-02** — `tests/test_crop_parity.py`: 960 golden vectors (4 src dims × 3 aspects × 4 zooms × 5 x × 4 y) from Python `compute_crop`, compared to `crop.js` run in Node (subprocess; `shutil.which("node")` skip guard). CI gained `actions/setup-node@v4` so it runs there too.

## Latent bug found + fixed (the point of the parity test)
The verbatim JS diverged from Python on **150/960** vectors: Python `round()` is banker's rounding (half-to-even), JS `Math.round()` is half-up — so the preview crop box drifted 1px on `.5` boundaries (e.g. 1920×1080 9:16 @ zoom 1.5, x=0.4: Python x=1060, JS x=1061). Fixed by a Python-compatible `rnd()` (round-half-to-even) in `crop.js`; **Python math untouched**. Parity is now exact. (Inputs are bit-identical IEEE-754 doubles in V8 and CPython, so the exact compare is safe.)

## Verification
- `pytest -q` → **197 passed** (incl. 960-vector parity), coverage 92.5%; ruff clean.
- Server restarted: `GET /static/crop.js` → 200.
- **Playwright (live, seeded job editor):** `CMCrop` loaded (3 fns); in-browser `computeCrop(1920,1080,'9:16',0.4,1.5,0)` → x=**1060** (banker's value, matches Python, not the old 1061); full-frame crop box renders at 31.67% width (608/1920 ✓); canvas live; **0 console errors**.

## Improvement criteria applied
**Correctness** (preview now pixel-exact to the render — fixed a real 1px drift), **Code quality** (one crop module, three→one source of truth), **Test coverage** (parity locked in CI). The CROP-01 source_dims change removes a divergence class (decoded vs server dims).
