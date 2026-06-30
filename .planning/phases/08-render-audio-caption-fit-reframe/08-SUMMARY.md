# Phase 8: Render Audio + Caption Fit + Review Reframe — Summary

**Status:** Complete ✅
**Completed:** 2026-06-29

## What shipped

- **Audio everywhere:** the simple (no-caption) render branch now maps `-map 0:v:0 -map 0:a?`
  explicitly, matching the caption/overlay paths — audio can't be dropped on any path.
- **Caption fit across ratios:** rewrote sizing in `captions.py`. Font now keys off the
  **shorter side** (`min(w,h)*0.052`) so 9:16, 1:1, and 16:9 get the same perceptual size
  (was `height*0.045`, which made 9:16 ~2× bigger than 16:9). Text wraps to ~86% of the
  width (LinkedIn-safe column) via a new `fit_caption()` that shrinks only if a long caption
  would still be too tall; backing box clamped to the frame.
- **Review-time reframe:** per-clip "Adjust crop" modal reuses the crop-preview component —
  source video seeked to the clip start, crop box + slider + aspect toggle — then re-renders
  that one clip via `/clip/{i}/reframe` and hot-reloads the video.

## Verified live (real binaries + browser)

- ffprobe: 9:16/1:1/16:9 outputs are 1080×1920 / 1080×1080 / 1920×1080, each with an **aac**
  audio stream (24.6s).
- Extracted mid-clip frames per ratio: captions are a uniform 56px, wrap to fit, and sit in
  the bottom safe area in all three ratios (text width 76–79% of frame).
- Reframe modal: moved crop to −0.84 (left) → re-render updated the file, **audio intact**,
  output framed left; a control +1.0 re-render framed fully right — confirms offset flows
  through the real pipeline (and matches `compute_crop`: −1→x=0, +1→x=1312 for 9:16).

## Success criteria

1. ✅ Every rendered clip (all 3 ratios) contains an audio stream (ffprobe)
2. ✅ Re-rendered clips after a crop tweak still contain audio
3. ✅ Captions wrap, never overflow, and sit in the safe area in all 3 ratios (frame-verified)
4. ✅ Review-time crop slider shows a live box and re-renders with audio intact
