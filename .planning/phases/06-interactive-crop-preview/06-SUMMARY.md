# Phase 6: Interactive Crop Preview Before Run — Summary

**Status:** Complete ✅
**Completed:** 2026-06-29

## What shipped

Upload no longer auto-starts the pipeline. Instead it stages the source and lands the
user on a preview page where they position the crop and choose options, then click Run.

- **`/upload`** now moves the file into `data/<id>/source<ext>`, probes dimensions, writes
  the manifest with `awaiting_run: true` + `source_dims`, marks `ingest` done, and redirects
  — no pipeline thread.
- **`/api/job/{id}/run`** (new) receives `x_offset` + run options, flips `awaiting_run` off,
  records `run_params`, and starts the background pipeline against the staged source.
- **`_run_pipeline`** reworked to take `(job_id, source, …)` and load the existing job
  (transcribe cache-hits on the already-staged source).
- **Job payload** exposes `awaiting_run`, `source_url`, `source_dims`, `run_params`, and each
  clip's `start` (for the reframe modal seek).
- **Preview UI** (`job.html`): `<video>` of the source with a live crop-box overlay sized in
  % of source dims, an aspect toggle (9:16/1:1/16:9), and an x_offset slider. Browser
  `computeCrop()` mirrors `render.compute_crop` exactly. Run options (max_clips, model,
  captions) live here.

## Verified live (browser, real binaries)

- Uploaded a 90s slice → landed on preview (pipeline did NOT auto-start).
- Crop slider at 0.7 → box at left 58.07%, width 31.67% — matches `compute_crop` (608px, x=1115).
- Aspect toggle moves the box; 16:9 disables the slider (full-width, no horizontal slack).
- Clicked Run → pipeline started; `run_params.x_offset=0.7` propagated to the render
  (9:16/1:1 outputs visibly right-shifted; ffprobe-confirmed dims + audio).
- Repeated end-to-end on the full **EnlayeParis.mp4** (13:39): preview scrubs the 1.17 GB
  source via range requests; Run starts transcribe→select→render.

## Success criteria

1. ✅ Upload stages source + shows preview; no auto-start
2. ✅ Crop-box overlay moves live with the slider (9:16 + 1:1)
3. ✅ Run starts the pipeline with the chosen x_offset; progress displays as before
4. ✅ Browser crop math matches `render.compute_crop`
