# Roadmap: Content Machine — LinkedIn Video Clipper

## Overview

Content Machine is a local-first batch pipeline: one Mac, one video at a time, four ordered stages — **ingest → transcribe → select → render** — wrapped last in a localhost UI. The build order *is* the artifact dependency chain: you can't select clips without a transcript, can't render without a clip list, and the UI is a thin wrapper over a pipeline that already works headlessly. Phases 1–3 are a CLI pipeline that solves every real risk (whisper.cpp Metal build, the `claude -p` subscription contract, ffmpeg reframing + caption legibility) before any HTTP code exists; Phase 4 wraps it. Locked engine: whisper.cpp (transcribe) + ffmpeg (cut/crop/assemble) + hyperframes (animated captions); clip selection via non-bare `claude -p` on the subscription, cached by transcript hash, no API-key fallback in v1.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Pipeline Spine — Ingest + Transcribe** - Drop a video on the CLI, get `data/<job_id>/` with audio + word-level transcript JSON
- [ ] **Phase 2: Clip Selection via Claude** - Transcript → cached, validated `clips.json` from non-bare `claude -p` on the subscription
- [ ] **Phase 3: Render — Cut, Reframe, Captions** - Each selected clip → 9:16/1:1/16:9 with snapped boundaries, burned captions, hyperframes overlay, thumbnail
- [ ] **Phase 4: Localhost UI + Job Runner** - Browser: upload → progress → review → adjust crop → download → local library

## Phase Details

### Phase 1: Pipeline Spine — Ingest + Transcribe
**Goal**: From the command line, turn a local video file into staged artifacts under `data/<job_id>/` — extracted audio plus a clean, timestamped transcript. This de-risks the whisper.cpp Metal build and establishes the staged-artifact layout every later stage and crash-recovery path depends on.
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04
**Success Criteria** (what must be TRUE):
  1. Running the CLI against a real mp4/mov produces `data/<job_id>/` containing `source`, `audio.wav` (16kHz mono), and `transcript.json`
  2. `transcript.json` holds segment-level text with word timing where available, anchored to real audio (correct on a known-content test video)
  3. A clip of silence/empty audio produces no phantom text — VAD suppresses whisper hallucinations like "Thanks for watching"
  4. Re-running on the same video reuses the cached transcript instead of re-transcribing (keyed by video hash)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD

**Pitfalls to bake in**: P8 whisper silence hallucination + ~±300ms word-timing drift (VAD model, deliberate small/medium model choice, pad on snaps later); whisper.cpp Metal/Core ML build on Apple Silicon; P9 staged-artifact layout established here (`data/<job_id>/` + `job.json`) so later crashes resume from the last completed stage and never re-transcribe.

### Phase 2: Clip Selection via Claude
**Goal**: Turn the transcript into a vetted list of post-worthy clip candidates by calling non-bare `claude -p` on the subscription, with output cached by transcript hash and validated against a strict schema. This is where the product lives or dies and where the locked subscription risk concentrates — so it is metered, cached, and validated, not just "call Claude."
**Depends on**: Phase 1
**Requirements**: SELECT-01, SELECT-02, SELECT-03, SELECT-04, SELECT-05
**Success Criteria** (what must be TRUE):
  1. Running selection on a real transcript yields `clips.json` — a structured list of `{start, end, title, rationale, score}` candidates, all 15–90s and distributed across the full timeline (not clustered in the first quartile)
  2. Every clip's start/end snaps to a sentence/silence boundary from the local word times, so no clip opens or closes mid-sentence
  3. Re-running selection on an unchanged transcript hits the cache and makes zero new Claude calls; Claude is invoked at most once per video
  4. Malformed, out-of-range, or end-before-start output is rejected (schema-validated, one repair retry, then fail loud) — never passed downstream
  5. A transcript too long for one pass is chunked/two-passed instead of being silently truncated
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

**Pitfalls to bake in**: P1 subscription-limit burn (one cached call per video, sentence-level input not word-level, log `total_cost_usd`, `--max-turns 1`, tools off); P2 context overflow / front-loaded picks (downsample to sentence level, reject single-quartile output, chunk only if a single pass overflows); P3 malformed/hallucinated timestamps (strict `--json-schema`, validate `0 ≤ start < end ≤ duration` and clip length, one repair retry); P4 mid-sentence cuts — snapping logic lands here on the P2→P3 boundary (Claude's seconds are *intent*, whisper word times are *ground truth*); P10 boring/wrong-length picks (criteria-driven prompt: hook in first ~3s, self-contained value, no off-screen references, ask for 6–8 candidates with a `reason` to audit). Keep selection behind a swappable `select_clips()` seam even with no v1 fallback.

### Phase 3: Render — Cut, Reframe, Captions
**Goal**: Turn each selected clip into watchable, captioned files in all three aspect ratios, saved locally under their source video. ffmpeg does all the cutting, cropping, and caption burn-in via output-seek re-encode; hyperframes renders the animated caption overlay composited over the cropped clip.
**Depends on**: Phase 1 (source + word timing), Phase 2 (clip list + snapped boundaries)
**Requirements**: RENDER-01, RENDER-02, RENDER-03, RENDER-04, RENDER-05
**Success Criteria** (what must be TRUE):
  1. Each selected clip renders to 9:16, 1:1, and 16:9 files with accurate starts — no black, smeared, or garbled lead frames, and no clip starts before its chosen moment
  2. The 9:16/1:1 crop is a center crop with an adjustable horizontal offset, and a crop-region preview is available before committing the full encode (so an off-center speaker isn't silently decapitated)
  3. Captions are generated per-clip from transcript timing, grouped into short phrases (not one-word strobe), and are legible over a bright frame and inside the LinkedIn safe area in every ratio
  4. Animated captions render via hyperframes as a transparent overlay and composite correctly over the cropped clip per ratio (ffmpeg ASS burn-in is the proven fallback if hyperframes proves heavy — segment-level captions still ship)
  5. Rendered clips and a per-clip thumbnail persist under `data/<job_id>/`, organized by source video; re-rendering skips files that already exist
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

**UI hint**: no (CLI render stage; visual review surfaces in Phase 4)

**Pitfalls to bake in**: P4 mid-sentence cuts — apply the snapped boundaries from P2 with ~0.2–0.4s pre-roll padding to absorb whisper drift; P5 center-crop slices the speaker out (manual x-offset parameter + crop-region preview thumbnail before full encode); P6 ffmpeg input-seek black/garbled frames (use output-seek + re-encode — required anyway for crop + captions); P5/P6 multi-pass blowup (one filtergraph per output, one encode pass; idempotent renders skip existing files); P7 caption legibility (ASS `force_style` BorderStyle=3, bold/large, high `MarginV`, per-ratio styling, eyeball one clip per ratio). hyperframes overlay-compositing is the freshest unknown — flag for `--research-phase` at planning.

### Phase 4: Localhost UI + Job Runner
**Goal**: Wrap the working headless pipeline in a localhost web UI and a serial in-process job runner: upload a video, watch per-stage progress, review candidates, nudge the crop and re-render, and download the clips you want — with everything persisting in a browsable local library. Built last by design: it is a thin wrapper over a pipeline whose every hard problem is already solved.
**Depends on**: Phase 1, Phase 2, Phase 3 (wraps the whole pipeline)
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06
**Success Criteria** (what must be TRUE):
  1. The user can upload a local video in the browser and start a clipping job
  2. The UI shows job progress through the pipeline stages (transcribe → select → render, including clip i of N) for long-running jobs
  3. The user can review each suggested clip — preview, title, score, rationale — before deciding what to keep
  4. The user can adjust a clip's crop offset and re-render just that clip without re-transcribing or re-calling Claude (re-renders from cached transcript + selection)
  5. The user can download selected clips per aspect ratio
  6. All transcripts and clips persist in a local library browsable by source video; killing the app mid-job and restarting resumes from the last completed stage rather than starting over
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

**UI hint**: yes

**Pitfalls to bake in**: P9 long-job UX + crash recovery (per-stage progress parsed from whisper/ffmpeg stderr; serial runner + `job.json` written after every stage; resume-from-stage; stream finished clips into the review grid as they render; idempotent renders); security (bind `127.0.0.1` only, pass ffmpeg args as an array not a shell string, validate/normalize file paths, keep all artifacts in a local non-cloud-synced dir); SQLite metadata + files-on-disk for the browsable library. Progress via polling first (lazy default), upgrade to SSE only if it feels laggy.

---

## Milestone v2 — Cross-Platform + Interactive Crop Preview

v1.0 shipped on macOS. v2 makes the app run on **Windows** (no Homebrew/Metal — vendored static
ffmpeg + prebuilt whisper.cpp), adds an **interactive crop-preview step before the pipeline runs**
(upload → preview the 9:16/1:1 crop with a live slider → Run), polishes the UI, and guarantees the
rendered clips carry **audio**. Driven by the author's switch to a Windows machine.

- [x] **Phase 5: Windows Cross-Platform Port** - App runs end-to-end on Windows: vendored ffmpeg/ffprobe + prebuilt `whisper-cli.exe` + model, OS-agnostic binary/font resolution, `setup.ps1`
- [x] **Phase 6: Interactive Crop Preview Before Run** - Upload no longer auto-starts; a preview page shows the source video with a draggable crop-box overlay (9:16/1:1) and a Run button that starts the pipeline with the chosen offset
- [x] **Phase 7: UI Polish + Live Logs** - Cleaner, more legible index + job pages; clear stage progress; readable live log panel
- [x] **Phase 8: Render Audio + Caption Fit + Review Reframe** - Every rendered clip keeps its audio in all 3 ratios and after re-frame; captions fit + sit in the safe area in 9:16/1:1/16:9; review-time crop slider (live box + re-render) works reliably

### Phase 5: Windows Cross-Platform Port
**Goal**: The full upload→transcribe→select→render→download flow works on Windows 11 with no package manager: static ffmpeg/ffprobe and prebuilt whisper.cpp vendored under `vendor/`, `config.py` resolves `.exe` binaries + vendored paths, captions fall back to Windows fonts, and `scripts/setup.ps1` reproduces the toolchain.
**Depends on**: v1.0 (whole pipeline)
**Success Criteria**:
  1. `whisper-cli.exe` + `ffmpeg.exe`/`ffprobe.exe` resolve via `config.py` on Windows (env → PATH → `vendor/bin`)
  2. Captions render with a real font on Windows (no Mac-only font path crash)
  3. `scripts/setup.ps1` downloads ffmpeg + whisper + model + venv idempotently
  4. `pytest` green on Windows

### Phase 6: Interactive Crop Preview Before Run
**Goal**: After upload, the user lands on a preview page with the source video and a live crop-box overlay they can position with a slider (per the 9:16 and 1:1 crops), then clicks **Run** to start the pipeline with that offset — instead of the pipeline auto-starting with a blind numeric offset.
**Depends on**: Phase 5
**Success Criteria**:
  1. Upload stores the source and shows a preview page; the pipeline does NOT auto-start
  2. The preview shows the source video with a crop-box overlay that moves live as the slider changes, for 9:16 and 1:1
  3. A Run button starts transcribe→select→render with the chosen x_offset; progress then displays as today
  4. Crop math in the browser matches `render.compute_crop`

### Phase 7: UI Polish + Live Logs
**Goal**: Both pages look intentional and legible — clearer upload form, library, stage chips, and a live log panel that's easy to read while a job runs.
**Depends on**: Phase 6
**Success Criteria**:
  1. Index + job pages restyled cohesively (spacing, type, states) and responsive
  2. Stage progress is obvious at a glance (pending/running/done/error)
  3. Live log panel is readable, auto-scrolls, and is clearly labeled

### Phase 8: Render Audio + Caption Fit + Review Reframe
**Goal**: Guarantee audio in every rendered output (all ratios, simple + caption + re-frame paths); make captions fit and sit in the LinkedIn safe area in each aspect ratio (per-ratio font size, wrap width, bottom margin — not the same absolute size across a tall 9:16 and a wide 16:9); and make the review-time crop slider re-render reliably with a live box preview.
**Depends on**: Phase 6, Phase 7
**Success Criteria**:
  1. Every rendered clip (9:16/1:1/16:9) contains an audio stream — verified with ffprobe
  2. Re-rendered clips after a crop tweak still contain audio
  3. Captions wrap to the frame width, never overflow horizontally, and sit inside the safe area in all 3 ratios (visually verified on the test video)
  4. The review-time crop slider shows a live crop box and re-renders the clip, reloading it with audio intact

---

## Milestone v3 — Per-Aspect Zoom/Crop + Clip Editor + Progress Bars

v2 shipped cross-platform with an interactive crop preview and guaranteed audio. v3 gives the user
real creative control: framing stops being a single horizontal nudge and becomes a full per-aspect
transform `{zoom≥1, x∈[-1,1], y∈[-1,1]}` — dialed in live before the run AND inside a focused
non-destructive per-clip editor — while an honest master + per-section progress system replaces the
"stuck waiting on a black screen" wait. The transform model (Phase 9) is the spine: the pre-run
preview (Phase 10) and the clip editor (Phase 12) are both live-preview surfaces over the same crop
math, and the progress system (Phase 11) runs orthogonally over the existing job runner. Scope is
locked: a focused per-clip tool, not a multi-track NLE.

- [x] **Phase 9: Per-Aspect Transform Model + Crop Math** - Replace scalar `x_offset` with a per-aspect `{zoom, x, y}` transform; `compute_crop` gains zoom + vertical pan; old `x_offset` runs still render; unit tests
- [x] **Phase 10: Pre-Run Preview Upgrade (live per-aspect zoom/pan)** - Per-aspect zoom + x/y pan controls on the preview page with instant CSS-transform preview mirroring the Python crop math; chosen transforms become the job's run defaults
- [x] **Phase 11: Progress System (master + per-section bars)** - Real backend progress numbers (transcribe % from whisper-cli, render per-aspect-per-clip counts); weighted master + per-section bars; clips surface as each finishes; Playwright-verified
- [x] **Phase 12: Focused Clip Editor** - Full-screen `/job/{id}/clip/{idx}/edit`: trim (snap-to-sentence), per-aspect reframe (+copy-to-all), caption text/timing + toggle, audio keep/mute/volume; non-destructive `edit.json`; per-aspect re-render; back-to-grid

### Phase 9: Per-Aspect Transform Model + Crop Math
**Goal**: Replace the single scalar `x_offset` with a per-aspect transform `{zoom≥1, x∈[-1,1], y∈[-1,1]}` and teach `render.compute_crop` to apply zoom (a tighter-than-fit crop window) plus vertical pan, while still accepting old `x_offset` run params so existing jobs and manifests keep rendering. This is the data-model + math foundation that the live previews in Phases 10 and 12 build on — get the crop arithmetic right once, in Python, with tests.
**Depends on**: v2.0 (Phase 8 — existing render pipeline: `compute_crop`/`build_render_cmd`/`run_params`)
**Requirements**: ZOOM-01, ZOOM-02, ZOOM-03
**Success Criteria** (what must be TRUE):
  1. `compute_crop` accepts a `{zoom, x, y}` transform and, at `zoom=1.0`, returns exactly today's max-fit center crop for 9:16/1:1/16:9 on EnlayeParis.mp4 (regression-locked); at `zoom=2.0` it returns a half-size crop window (a tighter framing)
  2. Panning `x` and `y` in [-1,1] moves the crop window across the real horizontal AND vertical slack the zoom creates, clamped so the window never leaves the source frame (no out-of-bounds crop at any aspect on the test video)
  3. Each aspect ratio carries its own independent `{zoom, x, y}`; a run stores three transforms as run-wide defaults, and a single aspect can be overridden without disturbing the other two
  4. A job whose run params still use the old scalar `x_offset` renders byte-for-byte as before (back-compat shim maps `x_offset` → `{zoom:1, x:x_offset, y:0}`); old `render.json` manifests load without error
  5. `pytest` covers the crop math — `zoom=1` parity with the current center crop, `zoom>1` window sizing, x/y clamping at the edges, and the `x_offset` back-compat path — and is green on Windows + macOS
**Plans**: TBD

Plans:
- [ ] 09-01: TBD

**Pitfalls to bake in**: keep `compute_crop`'s return signature `(crop_w, crop_h, x, y)` stable so `crop_scale_filter`/`build_render_cmd` keep working; do the even-dimension rounding (`% 2`) AFTER applying zoom so yuv420p stays happy; clamp `zoom≥1.0` (zoom<1 would crop outside the frame); height-limited aspects (16:9 from a 16:9-ish source) have little/no slack — clamp pan to 0 there rather than erroring; the back-compat shim is load-bearing — there are live v2 jobs with scalar `x_offset` in `render.json` run_params.

### Phase 10: Pre-Run Preview Upgrade (live per-aspect zoom/pan)
**Goal**: Upgrade the existing pre-run preview page so the user dials in per-aspect **zoom + x/y pan** with an instant CSS-transform preview (no ffmpeg) that mirrors the Phase 9 Python crop math, then commits those three transforms as the job's default framing for the run — replacing the single horizontal x-offset slider.
**Depends on**: Phase 9 (transform model + crop math)
**Requirements**: ZOOM-04, ZOOM-05
**Success Criteria** (what must be TRUE):
  1. The preview page shows zoom + horizontal + vertical pan controls for each of 9:16, 1:1, and 16:9, replacing the single x-offset slider
  2. Dragging zoom or pan updates the framed crop-box preview instantly via CSS transform, deferring all ffmpeg work until **Run** is clicked (no render request fires while the user is adjusting)
  3. The live browser preview crop agrees with `render.compute_crop` for the same `{zoom, x, y}` — box position and size match within a pixel on EnlayeParis.mp4 across all three aspects
  4. Clicking **Run** starts transcribe→select→render with the three chosen per-aspect transforms persisted as the job's run defaults (visible in `render.json` run_params), and the rendered clips reflect that exact framing
**Plans**: TBD

Plans:
- [ ] 10-01: TBD

**UI hint**: yes

**Pitfalls to bake in**: the CSS-transform preview and the ffmpeg crop must share ONE math definition (port `compute_crop` to JS or expose it via an endpoint) or they will silently diverge — this was already a Phase 6 success criterion for x_offset, now multiplied by zoom+y; defer all encoding to Run (the whole point is no ffmpeg until commit); persist transforms into the same `run_params` seam the `/run` route already writes (extend, don't replace, so the back-compat shim still applies).

### Phase 11: Progress System (master + per-section bars)
**Goal**: Make a running job honest. The backend emits real progress numbers — transcribe % parsed from whisper-cli output, render advanced per-aspect-per-clip — and the job page shows a per-section bar for each stage plus a weighted master bar, with each clip/aspect appearing in the review grid the instant it finishes encoding instead of all at once at the end. Verified visually with Playwright screenshots at multiple progress states.
**Depends on**: Phase 4 (job runner + render loop / `update_stage`) — orthogonal to the zoom/editor track, can be built in parallel with Phases 9–10
**Requirements**: PROG-01, PROG-02, PROG-03, PROG-04
**Success Criteria** (what must be TRUE):
  1. The job page shows a separate progress bar for transcribe (driven by a real % parsed from whisper-cli output), select, and render (advancing per aspect-per-clip — e.g. 14/18 on a 6-clip × 3-aspect job)
  2. A master bar shows weighted overall completion that moves monotonically from 0→100% across the three stages and reaches 100% exactly when the job finishes
  3. Each clip/aspect tile appears in the review grid the moment that file finishes encoding — not only at the end (observable on the 6-clip EnlayeParis.mp4 run)
  4. Playwright captures screenshots at multiple progress states (mid-transcribe, mid-render, complete) and the master + per-section bars render correctly and look good at each
**Plans**: TBD

Plans:
- [ ] 11-01: TBD

**UI hint**: yes

**Pitfalls to bake in**: whisper-cli prints progress to stderr in a parseable form — drive the transcribe bar off that, don't fake a timer; render count is deterministic (`len(clips) × len(aspects)`) so the render bar can be exact; `select` has no natural %, treat it as an indeterminate/at-stage-boundary step in the weighting; reuse the existing polling-over-`job.json` mechanism (stages already tracked via `update_stage`) before reaching for SSE; stream finished clips into the grid by writing each clip's manifest entry as it completes, not only the final `render.json` flush.

### Phase 12: Focused Clip Editor
**Goal**: A focused, full-screen, non-destructive editor at `/job/{id}/clip/{idx}/edit` where the user trims (snap-to-sentence), reframes each aspect (zoom/pan with a copy-to-all action), edits caption text/timing and toggles captions, and sets audio keep/mute/volume — all saved to a per-clip `edit.json` and applied by a per-aspect re-render that only re-encodes the aspects that changed — then returns to the grid with the edits reflected. A per-clip tool, explicitly not a multi-track NLE.
**Depends on**: Phase 9 (transform model — reframe writes `{zoom, x, y}` per aspect), Phase 10 (reuses the live-preview JS for in-editor reframe)
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-05, EDIT-06
**Success Criteria** (what must be TRUE):
  1. Opening `/job/{id}/clip/{idx}/edit` for any rendered EnlayeParis.mp4 clip loads a full-screen editor; saving returns to the review grid with that clip's changes reflected
  2. The trim scrubber sets in/out points that snap to sentence boundaries from word timings, and the reframe controls set per-aspect zoom/pan with a "copy this framing to all aspects" action
  3. Caption text and per-segment timing are editable and captions can be toggled on/off; the clip's audio can be kept, muted, or set to a chosen volume — and every one of these changes is visible/audible in the re-rendered clip
  4. Edits persist to a per-clip `edit.json` (non-destructive — the source and other clips are untouched); re-render applies them and only re-encodes the aspects that actually changed, leaving unchanged aspect files in place
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

**UI hint**: yes

**Pitfalls to bake in**: non-destructive means `edit.json` is the source of truth and re-render derives outputs from it (never mutate `source` or the original `clips.json`); reuse Phase 9's snap-to-sentence logic from selection rather than re-implementing it; trim must re-derive caption events for the new in/out window; per-aspect dirty-tracking (which aspects' `{zoom,x,y}`/trim/captions/audio changed) drives the "only changed aspects re-encode" rule — get this wrong and you either re-encode everything or serve stale files; audio mute/volume rides the existing `-map 0:a?` + `-c:a aac` path (a volume filter or `-an`), keeping the Phase 8 "always has audio" guarantee unless explicitly muted; the in-editor reframe preview must reuse Phase 10's shared crop math, not a second copy.

---

## Milestone v4 — Cross-Platform Hardware Acceleration

v3 gave creative control; v4 makes it fast. The two slow stages — render (~50% of the wait) and
transcribe (~40%) — leave the GPU idle on both OSes (`render.py` hardcodes `libx264`; Windows whisper
is a CPU BLAS build). v4 offloads **encode** to the GPU (NVENC on Windows / VideoToolbox on Mac) and
**transcription** to the GPU (CUDA whisper on Windows; Mac is already Metal), behind a startup
**probe + automatic CPU fallback** so it is structurally impossible to break. The spine is a shared
auto-detecting `hwaccel` core (Phase 13), enabled and benchmarked on Windows (Phase 14), tuned for
macOS via the same probe/fallback (Phase 15), then split into two thin platform branches (Phase 16).
"Must not break" outranks raw speed throughout: encode-only (no hw-decode), serial GPU sessions,
libx264 fallback on any failure.

- [x] **Phase 13: Shared Hardware-Accel Core + Render Encoder Fallback** - `hwaccel.py` probes encoders once and returns the best profile; `render.py` encodes with it and transparently falls back to `libx264` on any failure; NVENC-verified on Windows, x264 parity preserved ✓ (41156e2; NVENC 1.36× on 60s clip; 53 tests)
- [x] **Phase 14: Windows GPU Enablement + Benchmark Harness** - `setup.ps1` pins NVENC-capable ffmpeg 7.1; benchmark harness records CPU-vs-GPU deltas + ffprobe validation. ⚠ CUDA whisper DROPPED (data-driven): prebuilt cuBLAS 12.4 is ~40× slower than CPU on Blackwell — Windows transcribe stays fast CPU BLAS (ACCEL-02/SAFE-02 deferred, see BENCHMARKS.md) ✓ (e81618b)
- [x] **Phase 15: macOS Tuning (VideoToolbox + Metal defaults)** - VideoToolbox encode profile in `hwaccel` + Metal whisper + `setup.sh` note; probe + fallback unit-tested with a stubbed Mac (selects videotoolbox on darwin, falls back to x264 if absent) so the untestable Mac path cannot break ✓
- [x] **Phase 16: Branch Split + READMEs + Push** - Forked `windows-optimized` + `mac-optimized` off the shared core (differ only in the README platform banner), each with a dead-simple quickstart; both pushed to github.com/Metdez/Content-Reels ✓ (5280b0a / 540b582)

### Phase 13: Shared Hardware-Accel Core + Render Encoder Fallback
**Goal**: Introduce `content_machine/hwaccel.py` that probes the available video encoders once at startup (lavfi null-encode, exit-code verdict, cached) and returns the best encoder profile (codec + quality-matched flags); wire `render.py` to encode with the chosen profile on every render path and transparently fall back to `libx264` on any failure. Encode-only — `compute_crop` and all CPU filters are untouched. Verified live on Windows with NVENC; x264 output parity preserved when the GPU path is disabled.
**Depends on**: v3 (existing render pipeline: `build_render_cmd`/`render_clip`)
**Requirements**: ACCEL-01, SAFE-01, SAFE-03
**Success Criteria** (what must be TRUE):
  1. `hwaccel` probes `h264_nvenc`/`h264_videotoolbox` via a cached lavfi null-encode and returns a profile object (codec + flags); on this Windows machine it selects the `nvenc` profile (`-preset p5 -rc vbr -cq 21 -b:v 0 -pix_fmt yuv420p`)
  2. `build_render_cmd` emits the selected encoder's flags on BOTH the no-caption path and the `filter_complex` caption path (and `build_overlay_cmd`); a real EnlayeParis clip renders in all 3 aspects via NVENC with valid h264 + an audio stream + `+faststart` (ffprobe-verified)
  3. A forced encoder failure (unavailable/bogus encoder) makes the render transparently re-run the SAME filtergraph with `libx264`, producing a valid output — never missing, silent, or corrupt
  4. With the GPU path disabled (env/flag), output matches today's `libx264 -preset veryfast -crf 20` behavior; all existing render tests stay green; new unit tests cover profile selection + the fallback wrapper
  5. `pytest` green on Windows
**Plans**: TBD

Plans:
- [ ] 13-01: TBD

**UI hint**: no (engine/CLI change; speed shows up in the existing progress bars)

**Pitfalls to bake in**: nvenc has no `-crf`/`-preset veryfast` — use `-rc vbr -cq`; the probe MUST be cached (don't spawn an ffmpeg probe per clip); keep the Phase 8 audio guarantee — the fallback must re-run the SAME filtergraph (captions + `-map 0:a?` + volume) with x264, not silently drop captions or audio; `-af volume` stays illegal with `-filter_complex` (existing handling preserved); detect mid-encode failure by nonzero exit, not just probe; leave decode + all filters on CPU (encode-only).

### Phase 14: Windows GPU Enablement + Benchmark Harness
**Goal**: Make Windows actually use the GPU end-to-end and prove it. `setup.ps1` vendors the pinned NVENC-capable ffmpeg 7.1 (verified to init NVENC on driver 591.74, unlike the master build) and the CUDA cuBLAS whisper build (self-bundled DLLs), keeping the BLAS build as a fallback; `transcribe` uses the CUDA whisper when the GPU initializes and falls back to CPU otherwise; and a benchmark harness records CPU-vs-GPU wall-time for render and transcribe with ffprobe validation of every output.
**Depends on**: Phase 13
**Requirements**: ACCEL-02, SAFE-02, BENCH-01, BENCH-02, PLAT-01
**Success Criteria** (what must be TRUE):
  1. `setup.ps1` idempotently vendors BtbN ffmpeg 7.1 (NVENC works on the installed driver) and `whisper-cublas-12.4.0` binaries alongside the BLAS fallback; re-running setup is a no-op
  2. Transcription runs on the RTX 5060 via CUDA whisper (`ggml_cuda_init` logs a CUDA device); if CUDA init is absent/fails, it falls back to the CPU whisper build automatically
  3. A benchmark script reports render + transcribe wall-time for CPU vs GPU on a known input and prints the before/after deltas (GPU faster for both)
  4. The benchmark validates every output with ffprobe (codec, dimensions, audio stream present, not corrupt) and confirms GPU and CPU outputs are equivalently valid
  5. The recorded before/after numbers are committed; `pytest` green
**Plans**: TBD

Plans:
- [ ] 14-01: TBD

**UI hint**: no

**Pitfalls to bake in**: the cuBLAS zip bundles `cudart`/`cublas` DLLs — flatten them next to `whisper-cli.exe`; Blackwell PTX-JIT adds a one-time warmup — measure steady-state, not first-run; iterate benchmarks on a short slice but validate full-res outputs; make sure `config.WHISPER_CLI` resolves the CUDA binary and the CUDA DLLs don't collide with the BLAS build; the ffmpeg pin is load-bearing (master fails NVENC on driver 591.74).

### Phase 15: macOS Tuning (VideoToolbox + Metal defaults)
**Goal**: Tune the shared core for Apple Silicon — add the VideoToolbox encode profile and confirm Metal whisper defaults, with `setup.sh`/README adjustments — relying entirely on the Phase 13 probe + fallback so the Mac path (untestable here) cannot break: worst case it runs `libx264`/CPU exactly like today.
**Depends on**: Phase 13 (core), Phase 14 (benchmark harness reused)
**Requirements**: ACCEL-03, PLAT-02
**Success Criteria** (what must be TRUE):
  1. The encoder profile table includes a `videotoolbox` profile (`h264_videotoolbox -q:v 62 -b:v 0 -allow_sw 1`) selected when the probe detects it on macOS
  2. `setup.sh` idempotently provides VideoToolbox-capable ffmpeg (Homebrew) + Metal whisper (already `-DGGML_METAL=1`)
  3. The probe + fallback are platform-agnostic and unit-tested with a stubbed probe (no Mac hardware needed); a Mac with absent/failed VideoToolbox falls back to `libx264`
  4. Code-reviewed for Windows-only assumptions (paths, `.exe`, env); `pytest` green (cross-platform tests don't assume a GPU)
**Plans**: TBD

Plans:
- [ ] 15-01: TBD

**UI hint**: no

**Pitfalls to bake in**: can't run on Mac here — rely on the probe's exit-code contract + stubbed unit tests; `-q:v` constant quality is Apple-Silicon-only (the probe covers Intel/absence); `-allow_sw 1` lets VideoToolbox fall back to its SW encoder before our libx264 fallback even triggers; don't hardcode `/opt/homebrew` beyond what `setup.sh` already does; keep all platform divergence behind the profile table + setup script, not scattered conditionals.

### Phase 16: Branch Split + READMEs + Push
**Goal**: Split the tested shared core into the two thin platform branches — `windows-optimized` and `mac-optimized` — differing only in platform defaults, setup script, and README, each with a dead-simple one-command quickstart, and push both to `origin`. Branch from the current working branch (latest code), not stale `main`; do not merge to `main`.
**Depends on**: Phase 14 (Windows verified), Phase 15 (Mac tuned)
**Requirements**: PLAT-03, PLAT-04
**Success Criteria** (what must be TRUE):
  1. `windows-optimized` and `mac-optimized` branches exist off the shared core; the diff between them is limited to platform defaults + setup script + README
  2. Each branch's README has a one-command setup and a one-command run for that platform, accurate to that branch
  3. Both branches are pushed to `origin` (github.com/Metdez/Content-Reels) and visible on GitHub
  4. A clean checkout of each branch sets up and runs per its README (Windows verified locally; Mac steps dry-validated for correctness)
**Plans**: TBD

Plans:
- [ ] 16-01: TBD

**UI hint**: no

**Pitfalls to bake in**: do NOT merge to `main` (standing constraint); fork from the current working branch (`feat/windows-port-crop-preview`, latest code), not stale `main`; keep the shared core byte-identical on both branches so future fixes cherry-pick cleanly; the README must match what `setup` actually does — test the Windows one end-to-end; push uses `origin` over HTTPS (the user is authenticated).

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16

**Active milestone: v4 (Phases 13–16).** Phases 1–12 complete (v1.0 + v2.0 + v3, verified live).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Spine — Ingest + Transcribe | 0/TBD | Not started | - |
| 2. Clip Selection via Claude | 0/TBD | Not started | - |
| 3. Render — Cut, Reframe, Captions | 0/TBD | Not started | - |
| 4. Localhost UI + Job Runner | 0/TBD | Not started | - |
| 9. Per-Aspect Transform Model + Crop Math | 0/TBD | Not started | - |
| 10. Pre-Run Preview Upgrade | 0/TBD | Not started | - |
| 11. Progress System | 0/TBD | Not started | - |
| 12. Focused Clip Editor | 0/TBD | Not started | - |

---

## Coverage

All 20 v1 requirements mapped to exactly one phase. No orphans, no duplicates.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1. Pipeline Spine | INGEST-01, INGEST-02, INGEST-03, INGEST-04 | 4 |
| 2. Clip Selection | SELECT-01, SELECT-02, SELECT-03, SELECT-04, SELECT-05 | 5 |
| 3. Render | RENDER-01, RENDER-02, RENDER-03, RENDER-04, RENDER-05 | 5 |
| 4. UI + Storage | UI-01, UI-02, UI-03, UI-04, UI-05, UI-06 | 6 |

**Total: 20/20 mapped ✓**

### v3 Coverage

All 15 v3 requirements mapped to exactly one phase. No orphans, no duplicates.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 9. Per-Aspect Transform Model + Crop Math | ZOOM-01, ZOOM-02, ZOOM-03 | 3 |
| 10. Pre-Run Preview Upgrade | ZOOM-04, ZOOM-05 | 2 |
| 11. Progress System | PROG-01, PROG-02, PROG-03, PROG-04 | 4 |
| 12. Focused Clip Editor | EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-05, EDIT-06 | 6 |

**Total: 15/15 mapped ✓**

## Research Flags (carry into planning)

- **Phase 2:** The non-bare `claude -p` subscription invocation contract (OAuth/keychain behavior, `--json-schema` stability across versions, structured-output parsing) and the selection prompt design are load-bearing unknowns. Worth `--research-phase`.
- **Phase 3:** hyperframes integration is the freshest unknown — authoring segment-timed transparent caption overlays and compositing them over an ffmpeg-cropped clip per aspect ratio is under-researched. Flag for research; ffmpeg ASS captions are the proven fallback.
- **Phases 1 & 4:** standard patterns (whisper.cpp CLI + ffmpeg audio extraction; localhost upload→progress→download) — skip `--research-phase`.
- **Phase 9 (v3):** mostly deterministic crop arithmetic — skip research; the only subtlety is the `x_offset` back-compat shim, covered by tests.
- **Phase 10 (v3):** standard pattern (CSS-transform live preview over shared crop math, already proven for x_offset in Phase 6) — skip research; the risk is JS↔Python math divergence, handled by the pixel-parity criterion.
- **Phase 11 (v3):** whisper-cli stderr progress-format parsing is the one unknown — a quick spike, not a full research phase.
- **Phase 12 (v3):** the per-aspect dirty-tracking / "only changed aspects re-encode" design is the load-bearing unknown — worth a short `--research-phase` or spike on the `edit.json` schema before planning.

## v5 Phases — Editing UX Revamp (Phases 17–19)

Continues numbering after v4 (Phases 13–16). Sequential; 17 → 18 → 19.

### Phase 17 — Background Re-render + Live Editor Progress

**Goal:** A clip re-render runs in the background; the editor stays interactive and shows live per-aspect progress; edits made mid-render queue.

**Requirements:** EDITUX-01, EDITUX-02, EDITUX-03, EDITUX-04

**Success criteria:**
1. Clicking "Apply & re-render" returns immediately; the page is interactive (scrub, switch aspects, adjust framing) while ffmpeg runs in the background.
2. The editor shows an overall + per-aspect progress indicator (queued / rendering / done / error) sourced from `job.json` render progress.
3. Each aspect's preview/thumbnail refreshes the instant that ratio finishes; a Playwright run on EnlayeParis.mp4 captures the mid-render interactive + per-aspect-update states.
4. Changing framing/trim again while a render is in flight queues a second render that runs after the first; both complete and `edit.json` reflects the final state.

**Research flag:** Reuse the P11 progress mechanism (`update_stage`/`set_progress` on `job.json`) — but the editor needs to distinguish *this clip's* re-render from a whole-job render; key the progress per-clip so concurrent reads don't cross-talk. Worth a quick design check before coding.

### Phase 18 — Direct-Manipulation Framing + Preview Magnifier

**Goal:** Set framing by scroll-zoom + drag-pan directly on each aspect's live preview, with a magnifier to inspect detail — pixel-accurate to the renderer.

**Requirements:** EDITUX-05, EDITUX-06

**Success criteria:**
1. Scroll-wheel over an aspect preview zooms its crop; dragging pans it; values stay clamped to valid `{zoom, x, y}` and update the sliders (kept as fallback).
2. The drawn crop matches `render.compute_crop` for the same transform (pixel-parity verified, as in v3) — a re-rendered output frames identically to the preview.
3. A magnifier control enlarges the preview canvas for inspection without altering `{zoom, x, y}` or the output; copy-to-all and reset still work.

**Research flag:** None — this is the proven CSS/canvas-over-shared-crop-math pattern from v3; the only risk is JS↔Python divergence, gated by pixel-parity.

### Phase 19 — Edit-Flow Polish + Live Verification

**Goal:** The whole edit→crop flow has clear, always-visible states and is verified end-to-end in the browser.

**Requirements:** EDITUX-07

**Success criteria:**
1. The editor always shows an unambiguous state (idle / unsaved changes / rendering / done / error); a render failure surfaces a readable message, not a silent hang.
2. Full Playwright walkthrough on EnlayeParis.mp4 (open editor → reframe by drag/scroll → trim → apply → watch progress → confirm updated outputs) passes; ffprobe validates the re-rendered clips; pytest is green.

**Research flag:** None — integration/polish phase.

## v5 Coverage

All 7 v5 requirements mapped to exactly one phase. No orphans, no duplicates.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 17. Background Re-render + Live Progress | EDITUX-01, EDITUX-02, EDITUX-03, EDITUX-04 | 4 |
| 18. Direct-Manipulation Framing + Magnifier | EDITUX-05, EDITUX-06 | 2 |
| 19. Edit-Flow Polish + Verification | EDITUX-07 | 1 |

**Total: 7/7 mapped ✓**

## v5.1 Phases — Quick-Crop Parity & Render Visibility (Phases 20–22)

Continues numbering after v5 (Phases 17–19). Recorded retroactively — all three phases shipped 2026-06-30. Pure frontend; reuses the v5 `/edit` + `/rerender-status` + `/log` pipeline (no backend change).

### Phase 20 — Poll-in-place Hardening ✓ Complete

**Goal:** Finished render previews stop re-buffering forever; polls update the DOM in place instead of rebuilding `<video>` elements every tick.

**Requirements:** EDITUX-12 (partial — poll-in-place portion)

**Success criteria:**
1. The 600ms editor re-render poll patches per-aspect status/preview in place; a finished ratio's `<video>` is created once and never refetched, so it doesn't spin forever. ✓
2. The 2.5s job-page poll reconciles the clips grid in place (append/rebuild-on-change), preserving loaded videos and the active aspect tab. ✓

**Commit:** `6f94246`

### Phase 21 — Quick-Crop Full Framing + Non-blocking Render with Live Progress & Logs ✓ Complete

**Goal:** The Quick-crop modal matches the full editor — zoom + Y + X with a live preview — and re-renders non-blocking with a progress bar, per-aspect status, and a live log.

**Requirements:** EDITUX-08, EDITUX-10, EDITUX-11

**Success criteria:**
1. The modal exposes per-aspect zoom + Position-Y + Position-X with a live WYSIWYG output-preview canvas, seeded from saved transforms. ✓
2. Re-render posts per-aspect transforms to the non-blocking `/edit` endpoint and polls `/rerender-status`: progress bar + %, per-aspect queued/rendering/done rows; the button never freezes. ✓
3. A live `/api/job/{id}/log` tail streams inside the modal during the render. ✓
4. On done, the clip card + ratio tabs cache-bust (shared token, stable paths) to show the new framing; verified live on Windows with real NVENC; 58 tests pass. ✓

**Commit:** `fd5c298`

### Phase 22 — Quick-Crop Direct Manipulation ✓ Complete

**Goal:** Scroll-zoom + drag-pan on the Quick-crop preview, mirroring the full editor.

**Requirements:** EDITUX-09

**Success criteria:**
1. Scroll-wheel zooms (`zoom*exp(-deltaY*0.0016)`, clamped 1–3×) and dragging pans (grab-the-image mapping), mutating only `MTF.{zoom,x,y}` with the sliders kept synced. ✓
2. Verified live: wheel 1→1.60×, drag +60/+40px → x=−14% y=−36% with correct direction + slider sync. ✓

**Commit:** `148fa06`

## v5.1 Coverage

All 5 v5.1 requirements mapped to exactly one phase. No orphans, no duplicates.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 20. Poll-in-place Hardening | EDITUX-12 | 1 |
| 21. Quick-Crop Framing + Live Progress + Logs | EDITUX-08, EDITUX-10, EDITUX-11 | 3 |
| 22. Quick-Crop Direct Manipulation | EDITUX-09 | 1 |

**Total: 5/5 mapped ✓**

---

## Milestone v6 — Full Quality Pass: Test, Harden, Improve, Adopt (Phases 23–36)

Continues numbering after v5.1 (Phases 20–22). Derived from `.planning/v6-DISCOVERY.md`. A senior-engineer ownership pass: exhaustive automated + Playwright coverage, fix every defect surfaced, improve against an explicit "better" standard, and adopt the worthwhile repo features. Fix phases are **regression-first** (write the failing test → fix → confirm) so no phase ships red. Execution is sequential 23 → 36, but phases group into tracks: foundation (23) → coverage (24–25) → backend reliability (26–28) → frontend (29–32) → repo adoption (33–34) → capstone (35–36).

**"Better" criteria (priority order):** Correctness → Reliability → Error-handling/UX clarity → Accessibility (WCAG 2.1 AA) → Test coverage → Performance → Code quality. A change ships only if it improves ≥1 criterion without regressing another, and is covered by a test.

- [x] **Phase 23: Test Harness & CI Foundation** - pytest-cov baseline (64.2%), `TestClient` fixtures, Playwright seed harness, `ruff` (clean), CI workflow ✓ (64 tests pass)
- [x] **Phase 24: Backend Unit Coverage** - +92 tests; coverage 64.2%→89.2% (config/logging_setup 100%, cli 97.9, captions 98.9, render 98.6); 5 bugs logged for P26/P28/P30 ✓
- [x] **Phase 25: HTTP API Integration Tests** - tests/test_api.py (+22); app.py 74.5%→85.4%, overall 92.2%; 4 findings (ingest-revert→P27, VAL-05→P28) ✓
- [x] **Phase 26: Reliability — Atomic Manifests + Locking** - atomic_write_text + read_json (Windows-retry) + per-job locked upsert-by-index; bug #1 fixed; +4 tests, 182 pass ✓
- [x] **Phase 27: Reliability — Non-blocking Upload + State Persistence + Lifecycle** - sync upload (threadpool), manifest-backed error surfacing + lifespan shutdown, render semaphore (CM_MAX_RENDERS); bug #6 fixed; +4 tests, 186 pass ✓
- [x] **Phase 28: Input Validation & Hardening** - trim/zoom bounds, run_claude retry/backoff + per-chunk skip, uuid upload staging, friendly empty-transcript, MediaFiles allowlist, platform hints; bugs #2/#3/#4/#7 fixed; 196 pass ✓
- [ ] **Phase 29: Shared Crop-Math Module + Parity Test** - one `crop.js`, uses `source_dims`, golden-vector parity vs Python in CI
- [ ] **Phase 30: Frontend Robustness — Error Surfacing + Polling** - surface failures, stop 404 loops, retry cap, replace `alert()`, keep dirty until POST ok, safe boot
- [ ] **Phase 31: Frontend Correctness — Captions, Audio, Validation** - real re-derive-for-trim, source scrub + audition, caption time validation, consistent cache-busting
- [ ] **Phase 32: Accessibility Pass (WCAG 2.1 AA)** - real buttons, dialog focus-trap+ESC, labels+aria-live, touch targets, drop guard, CAP unification
- [ ] **Phase 33: Adopt — Word-level Timing → Cut-snapping** - consume `words[]` for word-boundary snap in selection + editor trim
- [ ] **Phase 34: Adopt — Word-level Karaoke Captions (hyperframes)** - finish hyperframes path with word-highlight; PNG fallback intact
- [ ] **Phase 35: Exhaustive Playwright E2E Suite** - every interaction/edge/error state across all 3 pages + one real short render
- [ ] **Phase 36: Final Integration Verification & Docs** - full real run, README/BENCHMARKS, document criteria, milestone audit

### Phase 23: Test Harness & CI Foundation
**Goal**: Stand up the testing foundation everything else depends on: coverage measurement, an HTTP-layer test client, a headless Playwright harness that drives the app against a pre-seeded job fixture (so E2E never waits on a 5-minute render), a lint gate, and CI.
**Depends on**: v5.1 (existing 58-test suite)
**Requirements**: QA-01, QA-02, QA-03, QA-04, QA-05
**Entry**: 58 tests pass.
**Success Criteria** (what must be TRUE):
  1. `pytest` reports line coverage with a committed baseline number; `pytest-cov` is a dev dependency.
  2. A reusable `TestClient` fixture exists and a smoke test exercises at least `GET /`.
  3. A seeded-job fixture (manifest + fake outputs on disk) lets a Playwright spec load `/job/{id}` and the editor without running the pipeline; the harness is documented (`make e2e` or equivalent).
  4. `ruff` is configured and green on `content_machine/` + `tests/`; a CI workflow runs lint + tests on push.
**Plans**: TBD
**UI hint**: no
**Exit**: coverage baseline + TestClient + Playwright harness + ruff + CI all committed and green.

### Phase 24: Backend Unit Coverage
**Goal**: Close the unit-test gaps on the modules with zero/low coverage, with external binaries stubbed so tests stay fast and deterministic.
**Depends on**: Phase 23
**Requirements**: QA-06, QA-07, QA-08, QA-09, QA-10, QA-11
**Success Criteria**:
  1. `config.py` (binary/model resolution, `require_tool` error), `cli.py` (all 4 commands via Typer runner), and `logging_setup.py` (`stream_run`/`run`/`tail`/`job_log` against a trivial real subprocess) have passing tests.
  2. Render orchestration (`render_clip`/`render_job`/`rerender_one`) is tested with the encode layer stubbed, asserting manifest shape + progress callbacks.
  3. `captions.fit_caption` and the hyperframes-gated composition path, plus `select.run_claude` failure handling and transcribe parsing, are tested (binary-dependent tests skip cleanly when absent).
  4. Coverage rises measurably over the Phase 23 baseline.
**Plans**: TBD
**UI hint**: no

### Phase 25: HTTP API Integration Tests
**Goal**: Exercise every endpoint at the request boundary via `TestClient`, asserting status codes, validation, and error paths — surfacing any wiring bugs that unit tests miss.
**Depends on**: Phase 23
**Requirements**: API-01, API-02, API-03, API-04, API-05
**Success Criteria**:
  1. `/upload` accepts a valid video (303 + manifest `awaiting_run`) and rejects missing file / bad extension / dotfile / traversal name (400).
  2. `/run` returns ok on start, 409 on re-run, 404 on unknown job, 400 on missing source; `/api/job/{id}`, `/log` (with `lines`), and `/clip/{idx}` GET handle unknown job/idx with 404.
  3. `/clip/{idx}/edit` rejects <0.5s trim (400) and queues a valid edit; `/rerender-status` returns the expected shape; `/download` 200s a present aspect and 404s a missing one.
  4. `/media` scoping and the legacy `/reframe` route have explicit tests (documenting current behavior before any change).
**Plans**: TBD
**UI hint**: no

### Phase 26: Reliability — Atomic Manifests + Locking
**Goal**: Eliminate the truncated-read 500s and cross-clip lost-updates: make all manifest writes atomic (temp file + `os.replace`) and serialize read-modify-write behind a per-job lock.
**Depends on**: Phase 25 (regression tests land here)
**Requirements**: REL-01, REL-02
**Success Criteria**:
  1. `job.json` and `render.json` are written atomically; a stress test polling while progress writes fire at high frequency never observes a JSON parse error.
  2. Two clips of one job re-rendering concurrently both retain their `render.json` entries (no clobber) — proven by a regression test that previously failed.
  3. Reads tolerate a momentary missing/temp file (retry/last-good) rather than 500ing; existing tests stay green.
**Plans**: TBD
**UI hint**: no

### Phase 27: Reliability — Non-blocking Upload + State Persistence + Lifecycle
**Goal**: Keep the event loop responsive during uploads, make failure state survive restarts, and shut down background work cleanly.
**Depends on**: Phase 26
**Requirements**: REL-03, REL-04, REL-05
**Success Criteria**:
  1. `/upload` no longer performs synchronous whole-file hashing/copy on the async path; a test confirms a concurrent request is served while a large upload is in flight.
  2. An in-flight pipeline error is persisted to the manifest and is still surfaced after a simulated restart; `_RERENDER` reconciles from `render.json` on startup.
  3. A render concurrency cap (semaphore/queue) bounds simultaneous encodes; shutdown stops daemon work without leaving the manifest mid-write.
**Plans**: TBD
**UI hint**: no

### Phase 28: Input Validation & Hardening
**Goal**: Validate and bound all user/edit inputs, make selection resilient, and clean up small correctness/portability issues.
**Depends on**: Phase 26
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06
**Success Criteria**:
  1. Trim clamps `start≥0`/`end≤duration` and `zoom` is upper-bounded (no tiny-crop blur); invalid edits are rejected with a clear error.
  2. `claude -p` selection retries transient failures with backoff and a transcript-scaled timeout; one failed chunk degrades gracefully instead of failing the whole stage.
  3. Concurrent same-name uploads no longer collide; a silent/empty transcript yields the friendly "no clip-worthy moments" message; `require_tool` hints are platform-correct; `/media` no longer serves manifests/transcripts/audio.
**Plans**: TBD
**UI hint**: no

### Phase 29: Shared Crop-Math Module + Parity Test
**Goal**: Collapse the three copies of the crop math to one shared JS module sourced from `source_dims`, locked to the Python renderer by a golden-vector parity test in CI.
**Depends on**: Phase 23 (harness)
**Requirements**: CROP-01, CROP-02
**Success Criteria**:
  1. `computeCrop`/`drawBox`/`drawOut` live in one module imported by `job.html` and `editor.html`; both use server `source_dims`, not the `<video>` intrinsic dims.
  2. A golden-vector fixture generated from Python `render.compute_crop` asserts JS parity (pixel-exact) across all three aspects and a range of `{zoom,x,y}`; it runs in CI.
  3. Existing framing behavior is unchanged (preview still matches a re-rendered frame) — verified live.
**Plans**: TBD
**UI hint**: yes

### Phase 30: Frontend Robustness — Error Surfacing + Polling
**Goal**: No more silent hangs — every poll/edit failure surfaces a readable state, infinite loops stop, and dirty intent survives a failed apply.
**Depends on**: Phase 29
**Requirements**: FE-01, FE-02, FE-03, FE-04
**Success Criteria**:
  1. A failed `/api/job`/`rerender-status`/`/log` poll shows a "connection lost / retrying" surface; polling stops on 404 with a retry cap; the pill never stays "⟳ Rendering…" forever on a transient error.
  2. The pre-run Run error is inline (no blocking `alert()`); editor dirty markers clear only after the edit POST is confirmed `ok`.
  3. The editor boots to a real error state (not a stuck "Loading editor…") when `captions`/`audio`/`transforms` are missing; a failed modal edit tears down its half-open progress UI.
**Plans**: TBD
**UI hint**: yes

### Phase 31: Frontend Correctness — Captions, Audio, Validation
**Goal**: Make the editor's caption/audio editing actually correct and auditable, and cache-bust media consistently.
**Depends on**: Phase 30
**Requirements**: FE-05, FE-06, FE-07, FE-08
**Success Criteria**:
  1. "Re-derive captions" recomputes segments for the current trim window via real server behavior (or is removed if not delivered) — it no longer silently no-ops.
  2. The editor source video has scrub controls and can be un-muted, so mute/volume edits are auditionable before re-render.
  3. Caption time inputs are validated (numeric, `start<end`, within trim) with an inline error; output media carries a server-provided version so reconcile-rebuilt cards never show stale frames.
**Plans**: TBD
**UI hint**: yes

### Phase 32: Accessibility Pass (WCAG 2.1 AA)
**Goal**: Make the three pages keyboard- and screen-reader-operable and touch-friendly, to WCAG 2.1 AA where feasible.
**Depends on**: Phase 30
**Requirements**: A11Y-01, A11Y-02, A11Y-03, A11Y-04
**Success Criteria**:
  1. Aspect tabs, clip tabs, and modal close are real keyboard-operable buttons with roles/labels; the modal has `role="dialog"`/`aria-modal`, a focus trap, ESC-to-close, and focus return.
  2. Sliders are labeled, progress/log are `aria-live`, and state is text+icon (not color alone); an automated a11y check (e.g. axe via Playwright) passes with no critical violations on each page.
  3. Trim handles meet ≥24px touch targets, wheel-zoom no longer traps page scroll, the index drop enforces video type/size, and the preview CAP is unified across modal/editor/card.
**Plans**: TBD
**UI hint**: yes

### Phase 33: Adopt — Word-level Timing → Cut-snapping
**Goal**: Put the already-persisted per-word timings to work — snap clip and trim boundaries to word edges, with a clean fallback when word timing is missing or poor.
**Depends on**: Phase 28 (validation), Phase 26 (manifest safety)
**Requirements**: WORD-01
**Success Criteria**:
  1. Selection boundary-snapping and editor trim snapping prefer `transcript.json` `words[]` boundaries over segment boundaries when available.
  2. When `words[]` is absent or visibly unreliable, the code falls back to the existing segment-level snap (no regression on a word-timing-poor transcript).
  3. A test asserts word-boundary snapping on a fixture transcript with known word times; verified live on EnlayeParis.mp4.
**Plans**: TBD
**UI hint**: yes
**Research flag**: validate whisper.cpp base.en word-timing accuracy on the test video before relying on it; budget a fallback if drift is large.

### Phase 34: Adopt — Word-level Karaoke Captions (hyperframes)
**Goal**: Finish the already-wired hyperframes path into a reliable word-highlight (karaoke) caption mode driven by `words[]`, keeping the Pillow PNG path as an automatic fallback.
**Depends on**: Phase 33 (word timings), existing `captions.py` hyperframes scaffolding
**Requirements**: CAPS-01, CAPS-02
**Success Criteria**:
  1. A karaoke caption mode renders word-by-word highlighting via the hyperframes overlay, composited correctly over the cropped clip in all three aspects.
  2. The hyperframes runtime is provisioned (Chrome/template) by setup or documented vendoring; on any hyperframes failure the render transparently falls back to PNG overlay captions (existing guarantee preserved).
  3. The mode is selectable (run options / editor) and gated; a real EnlayeParis clip renders karaoke captions, ffprobe-validated; PNG fallback still works when hyperframes is forced off.
**Plans**: TBD
**UI hint**: yes
**Research flag**: confirm the installed hyperframes player `onFrame`/word-highlight contract against the vendored version; Chrome provisioning is the freshest unknown.

### Phase 35: Exhaustive Playwright E2E Suite
**Goal**: The capstone test pass — automate every interaction, edge case, and error state enumerated in discovery across all three pages, plus one real short render to prove the live pipeline.
**Depends on**: Phases 29–34 (app hardened + features in)
**Requirements**: E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06
**Success Criteria**:
  1. Playwright specs pass for: index (upload/drag/library), job preview (tabs/zoom/X/Y/slack/reset/copy/Run), progress+clips (bars/log/reconcile/tabs/download/done+error), Quick-crop modal (seed/tabs/scroll-zoom/drag-pan/re-render/refresh/error), and the editor (reframe all 3 input methods/magnifier/trim+snap/playhead/captions/audio/apply/flow pill/resume).
  2. Edge/error specs pass: zero dims, missing captions, invalid caption/trim input, 404 job (polling stops with a surface).
  3. At least one spec runs a real short render end-to-end and asserts valid outputs; the whole suite runs in CI (real-render spec may be marked slow/optional in CI but must pass locally).
**Plans**: TBD
**UI hint**: yes

### Phase 36: Final Integration Verification & Docs
**Goal**: Prove the whole product works end to end on a real run, document the improvements and criteria applied, and pass the milestone audit.
**Depends on**: Phase 35
**Requirements**: DONE-01
**Success Criteria**:
  1. A full real run (upload → transcribe → select → render → edit → re-render → download) completes with valid outputs in all three aspects (ffprobe-verified).
  2. README + BENCHMARKS reflect v6 (new test/lint/CI commands, karaoke caption mode, reliability notes); the applied "better" criteria and what changed under each are documented; `DeepAgentLLMtxt.md` empty-state noted.
  3. Full `pytest` + Playwright suites green; no known broken functionality; `/gsd-audit-milestone` is clean.
**Plans**: TBD
**UI hint**: no

## v6 Coverage

All 41 v6 requirements mapped to exactly one phase. No orphans, no duplicates.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 23. Test Harness & CI | QA-01, QA-02, QA-03, QA-04, QA-05 | 5 |
| 24. Backend Unit Coverage | QA-06, QA-07, QA-08, QA-09, QA-10, QA-11 | 6 |
| 25. HTTP API Integration | API-01, API-02, API-03, API-04, API-05 | 5 |
| 26. Atomic Manifests + Locking | REL-01, REL-02 | 2 |
| 27. Upload + State + Lifecycle | REL-03, REL-04, REL-05 | 3 |
| 28. Validation & Hardening | VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06 | 6 |
| 29. Shared Crop Math + Parity | CROP-01, CROP-02 | 2 |
| 30. FE Robustness | FE-01, FE-02, FE-03, FE-04 | 4 |
| 31. FE Correctness | FE-05, FE-06, FE-07, FE-08 | 4 |
| 32. Accessibility | A11Y-01, A11Y-02, A11Y-03, A11Y-04 | 4 |
| 33. Word-level Cut-snapping | WORD-01 | 1 |
| 34. Karaoke Captions | CAPS-01, CAPS-02 | 2 |
| 35. Playwright E2E Suite | E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06 | 6 |
| 36. Final Verification & Docs | DONE-01 | 1 |

**Total: 41/41 mapped ✓**

---
*Roadmap created: 2026-06-29 — granularity: coarse, 4 phases, sequential numbering*
*Updated: 2026-06-30 — v3 milestone appended (Phases 9–12: per-aspect zoom/crop + clip editor + progress bars); 15/15 v3 requirements mapped*
*Updated: 2026-06-30 — v5 milestone appended (Phases 17–19: background re-render + live progress, direct-manipulation framing + magnifier, flow polish); 7/7 v5 requirements mapped*
*Updated: 2026-06-30 — v5.1 milestone appended (Phases 20–22: poll-in-place hardening, Quick-crop parity + live progress/logs, direct manipulation); 5/5 v5.1 requirements mapped; recorded retroactively (all shipped)*
*Updated: 2026-06-30 — v6 milestone appended (Phases 23–36: full quality pass — test harness/CI, backend+API coverage, reliability + validation hardening, shared crop math, FE robustness/correctness/a11y, word-timing + karaoke captions, exhaustive Playwright E2E, final verification); 41/41 v6 requirements mapped*
