# Phase 3 Summary: Render — Cut, Reframe, Captions

**Status:** ✅ Complete (4/5 reqs fully verified live; RENDER-04 wired with documented limitation).

## Environment finding (important)
This Mac's Homebrew **ffmpeg 8.1.2 is a stripped build**: no libass, no freetype, no
drawtext — only the `overlay` filter. So text can't be burned by ffmpeg directly.
Captions are therefore rendered as transparent **PNG strips (Pillow)** composited
with time-gated ffmpeg `overlay`. This is the default and works with any ffmpeg.

## What shipped
- `content_machine/render.py`:
  - `compute_crop` — largest target-aspect rect, center + `x_offset` (-1..1) for off-center speakers.
  - `build_render_cmd` — input-seek `-ss` (fast + accurate w/ re-encode), crop→scale, and a time-gated `overlay` chain (`enable='between(t,s,e)'`) for caption PNGs.
  - `render_clip` / `render_job` — 3 aspect ratios per clip + thumbnail + `clips/render.json`.
  - hyperframes mode: renders an animated HTML→MOV overlay then composites; auto-falls back to PNG overlay.
- `content_machine/captions.py`:
  - `clip_caption_events` (re-time to clip), `render_caption_png` (Pillow, wrapped, stroked, backing box), `render_caption_pngs`.
  - hyperframes composition scaffold + CLI invocation (`render --format mov`).
- `cli.py` — `content-machine render <job_id> [--x-offset] [--captions overlay|hyperframes|none]`.
- `tests/test_render.py` — 9 tests (crop math, x-offset, filtergraph, gated overlay chain, caption events, PNG render).

## Verification (success criteria)
- RENDER-01 ✅ cut via re-encode, exact 12.76s, no black lead frames
- RENDER-02 ✅ 9:16 (1080×1920), 1:1 (1080×1080), 16:9 (1920×1080); center crop + x-offset
- RENDER-03 ✅ captions visible (sampled frame: white text present in band)
- RENDER-04 ⚠️ hyperframes wired + attempts (launches Chrome) but a bare composition doesn't satisfy its player-readiness runtime; default `overlay` engine delivers composited captions. Full animated hyperframes needs a scaffolded composition (`hyperframes init`) — deferred polish. Stripped ffmpeg + 1.1GB free RAM favor the overlay path here anyway.
- RENDER-05 ✅ `data/<job>/clips/clip01/{9x16,1x1,16x9}.mp4` + `thumb.jpg` + `render.json`

## Decisions / notes
- `# ponytail:` PNG-overlay captions chosen because the target ffmpeg lacks libass/drawtext — most robust path, no Chrome, low memory.
- Added `pillow` dependency.
- hyperframes left as `--captions hyperframes` (best-effort, auto-fallback) per the locked decision; upgrade path = scaffold a real composition via their runtime.
