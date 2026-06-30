# Requirements: Content Machine — LinkedIn Video Clipper

**Defined:** 2026-06-29
**Core Value:** Drop in one video and get back several genuinely good, caption-burned clips in multiple aspect ratios — locally, no cloud, no per-token API cost.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ingest & Transcription

- [ ] **INGEST-01**: User can provide a local video file (mp4/mov and common formats) as input
- [ ] **INGEST-02**: System extracts audio and transcribes locally with whisper.cpp (Metal-accelerated)
- [ ] **INGEST-03**: System produces a timestamped transcript (segment-level, with word timing where available) saved locally as JSON
- [ ] **INGEST-04**: Transcription filters silence/hallucination artifacts (VAD) so empty audio doesn't produce phantom text

### Clip Selection

- [ ] **SELECT-01**: System sends the transcript to `claude -p` (subscription headless, non-bare) and receives a structured list of clip candidates (start, end, title, rationale, score)
- [ ] **SELECT-02**: Selection prompt enforces a rubric (hook strength, self-contained value, target length window for LinkedIn)
- [ ] **SELECT-03**: Clip boundaries snap to sentence/silence boundaries so clips never start or end mid-sentence
- [ ] **SELECT-04**: Selection results are cached by transcript hash to conserve subscription limits (re-runs don't re-spend)
- [ ] **SELECT-05**: Claude output is validated against a schema; long transcripts that exceed context are chunked/two-passed without failing

### Rendering & Output

- [ ] **RENDER-01**: System cuts each selected segment from the source via ffmpeg re-encode with accurate seek (no black/garbled lead frames)
- [ ] **RENDER-02**: Each clip is produced in 9:16, 1:1, and 16:9 (center crop with an adjustable horizontal offset)
- [ ] **RENDER-03**: Captions are generated from transcript timing (segment-level) for each clip
- [ ] **RENDER-04**: Animated captions are rendered via hyperframes and composited over the clip
- [ ] **RENDER-05**: Rendered clips and thumbnails are saved locally, organized under their source video

### UI & Storage

- [ ] **UI-01**: A localhost web UI lets the user upload a video and start a clipping job
- [ ] **UI-02**: The UI shows job progress through pipeline stages (transcribe → select → render) for long-running jobs
- [ ] **UI-03**: The user can review suggested clips (preview, title, score, rationale) before downloading
- [ ] **UI-04**: The user can adjust per-clip crop offset and re-render that clip
- [ ] **UI-05**: The user can download selected clips (per aspect ratio)
- [ ] **UI-06**: All transcripts and clips persist in a local library browsable by source video (SQLite metadata + files on disk)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Smart Reframe

- **REFRAME-01**: Speaker-aware auto-reframe (face/active-speaker tracking) for off-center subjects in 9:16

### Captions+

- **CAPS-01**: Word-level karaoke captions via forced alignment (WhisperX-style)

### Resilience / Distribution

- **DIST-01**: Optional Anthropic API-key fallback for clip selection (swap behind the same seam)
- **DIST-02**: Direct LinkedIn publishing / scheduling
- **DIST-03**: Batch/queued processing of multiple videos

## v3 Requirements

Active milestone — Per-aspect zoom/crop + focused clip editor + progress bars. Phases 9–12.

### Reframe & Zoom

- [x] **ZOOM-01**: User can set an independent zoom level (≥1.0, where 1.0 = max-fit crop) for each aspect ratio of a clip
- [x] **ZOOM-02**: User can pan the crop window horizontally and vertically (x, y ∈ [-1,1]) within the slack that the aspect + zoom create
- [x] **ZOOM-03**: Each aspect ratio carries its own `{zoom, x, y}` transform; transforms are set as run-wide defaults pre-run and can be overridden per clip
- [x] **ZOOM-04**: Zoom/pan changes preview live in the browser via CSS transform, deferring the ffmpeg render until the user commits
- [x] **ZOOM-05**: The pre-run preview lets the user dial in per-aspect zoom/pan that become the job's default framing

### Clip Editor

- [x] **EDIT-01**: User can open a focused full-screen editor for any rendered clip at `/job/{id}/clip/{idx}/edit` and return to the grid with edits reflected
- [x] **EDIT-02**: User can trim a clip's in/out points on a scrubber, with snap-to-sentence using word timings
- [x] **EDIT-03**: User can reframe per aspect (zoom/pan) inside the editor, including a "copy this framing to all aspects" action
- [x] **EDIT-04**: User can edit caption text and per-segment timing, and toggle captions on/off
- [x] **EDIT-05**: User can keep, mute, or set the volume of a clip's audio
- [x] **EDIT-06**: Edits are stored non-destructively in a per-clip `edit.json`; re-render applies them per aspect (only the changed aspects re-encode)

### Progress

- [x] **PROG-01**: The job page shows a per-section progress bar for transcribe (driven by whisper-cli output %), select, and render (per-aspect-per-clip counts)
- [x] **PROG-02**: A master progress bar shows weighted overall completion across all stages
- [x] **PROG-03**: Each clip/aspect appears in the review grid the moment it finishes rendering, not only at the end
- [x] **PROG-04**: Progress bars are visually verified to look good (Playwright screenshots at multiple progress states)

## v4 Requirements

Active milestone — Cross-Platform Hardware Acceleration (GPU encode + GPU transcribe, probe + fallback). Phases 13–16.

### GPU Acceleration

- [ ] **ACCEL-01**: Video encode is offloaded to the GPU when a usable encoder is detected (NVENC on Windows, VideoToolbox on Mac) — encode-only (CPU decode + CPU filters), with the three aspect ratios encoded serially; rendered clips remain valid in 9:16/1:1/16:9
- [~] **ACCEL-02** *(deferred → Out of Scope, data-driven)*: Windows GPU transcription was attempted via the only prebuilt CUDA whisper (cuBLAS 12.4); it DETECTS the RTX 5060 but has no native Blackwell (sm_120) kernels and runs ~40× slower than CPU (48 s for 8 s audio; hangs with flash-attn). Transcription stays on the fast CPU BLAS build (~9× realtime). Native Blackwell whisper needs a from-source CUDA 12.8+ build — deferred (see BENCHMARKS.md).
- [ ] **ACCEL-03**: On macOS, encode uses VideoToolbox and transcription uses Metal as the platform-tuned defaults

### Reliability & Fallback

- [ ] **SAFE-01**: Any GPU encode failure (encoder init or mid-encode error) transparently falls back to CPU `libx264` so the output file is never missing or corrupt, with audio stream and `+faststart` intact
- [~] **SAFE-02** *(moot — no GPU whisper shipped)*: With Windows transcription on CPU by decision (ACCEL-02 deferred), there is no GPU-whisper path to fall back from — the CPU BLAS build is the only path, which is the safe state this requirement aimed at.
- [ ] **SAFE-03**: On hardware with no usable GPU, the pipeline runs exactly as before on CPU with no new errors — the GPU path is purely additive, and with GPU disabled the x264 output matches today's behavior

### Benchmark & Validation

- [ ] **BENCH-01**: A benchmark script reports render and transcribe wall-time for CPU vs GPU on a known input and records the before/after deltas
- [ ] **BENCH-02**: The benchmark validates every output with ffprobe (codec, dimensions, audio stream present, not corrupt), confirming GPU and CPU outputs are equivalently valid

### Platform Packaging

- [ ] **PLAT-01**: Windows setup idempotently vendors the driver-compatible pinned ffmpeg (NVENC-capable on the installed driver) and the CUDA whisper build
- [ ] **PLAT-02**: macOS setup idempotently provides VideoToolbox-capable ffmpeg + a Metal whisper build
- [ ] **PLAT-03**: `windows-optimized` and `mac-optimized` branches exist off the shared auto-detecting core (differing only in defaults/setup/README) and are pushed to GitHub
- [ ] **PLAT-04**: Each platform branch ships a dead-simple README: one-command setup and one-command run for that platform

## v5 Requirements

Active milestone — Editing UX Revamp (background re-render + live progress, direct-manipulation framing + magnifier, flow polish). Phases 17–19.

### Responsive Re-render

- [x] **EDITUX-01**: When the user clicks "Apply & re-render" in the clip editor, the re-render runs in the background and the page stays fully interactive (no frozen request, no disabled-everything spinner) — the user can scrub, switch aspects, and adjust framing while it runs
- [x] **EDITUX-02**: The editor shows a live progress indicator while a re-render runs — overall plus per-aspect state (queued / rendering / done / error) — driven by a per-clip re-render tracker polled by the editor
- [x] **EDITUX-03**: Each re-rendered aspect's preview/thumbnail updates in place the moment that ratio finishes, not only when all ratios are done
- [x] **EDITUX-04**: If the user changes framing/trim/captions again while a render is in flight, the new render is queued and runs after the current one — no lost edits, never blocked

### Direct-Manipulation Framing

- [x] **EDITUX-05**: The user can zoom the crop framing with the scroll-wheel and pan it by dragging, directly on each aspect's live preview; the result mirrors `render.compute_crop` exactly (pixel-parity) and the existing sliders stay as a fallback
- [x] **EDITUX-06**: The user can magnify the preview canvas itself (an inspect zoom) to see fine detail while framing, without changing the clip's output framing

### Flow Clarity

- [x] **EDITUX-07**: The edit→crop flow has clear, always-visible states (idle / unsaved changes / rendering / done / error) so the user is never left guessing whether a render is still running, and errors surface a readable message instead of a silent hang

## v5.1 Requirements

Quick-Crop Parity & Render Visibility — bring the job-page Quick-crop modal to full editor parity and make re-render legible. Phases 20–22. Pure frontend; reuses the v5 `/edit` + `/rerender-status` + `/log` pipeline. Shipped 2026-06-30.

### Quick-Crop Framing Parity

- [x] **EDITUX-08**: The Quick-crop modal lets the user set per-aspect zoom and Position-Y (in addition to Position-X) with a live WYSIWYG output preview, using the same crop math as the full editor (no X-offset-only limitation)
- [x] **EDITUX-09**: The Quick-crop modal can pan/zoom the preview by direct manipulation — scroll-wheel zooms, dragging pans — with the sliders kept as a synced fallback (mirrors the full editor's behavior)

### Quick-Crop Render Visibility

- [x] **EDITUX-10**: Quick-crop re-render is non-blocking (posts to `/edit`, polls `/rerender-status`) and shows a progress bar with overall % plus per-aspect queued/rendering/done/error rows — never a frozen "Re-rendering…" button
- [x] **EDITUX-11**: The Quick-crop modal streams a live log tail (`/api/job/{id}/log`) during the render so the user can see what's happening at every breakpoint
- [x] **EDITUX-12**: On completion the clip card and every ratio tab refresh in place to show the new render immediately (shared-token cache-bust on stable paths), and finished `<video>` elements stop re-buffering from zero (editor + job-page polls update in place)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Cloud upload of source video or clips | Local-first is a core value |
| AI avatars / generated footage | This clips existing video, not synthesizes it |
| Multi-user, accounts, hosting | Single local user for v1 |
| API key as the default selection path | Author chose subscription headless; API key is a deferred fallback only |
| video-use as a dependency | Breaks local-first (ElevenLabs cloud); used only as a pattern reference |
| Full multi-track timeline NLE (splice/reorder/transitions) | v3 editor is a focused per-clip tool; a real NLE is unreliable on a local ffmpeg pipeline and overkill for short vertical clips |
| GPU-accelerated DECODE (`-hwaccel cuda/videotoolbox`) | Mixing hw-decode with the CPU crop/scale/overlay filtergraph causes format-conversion breakage; decode of short clips isn't the bottleneck — v4 is encode-only by decision |
| Parallel multi-clip / multi-aspect GPU encoding | The RTX 5060 has a single NVENC engine (parallel ≈ no gain) and adds concurrency risk to the job runner; "must not break" → encode serially |
| AV1 / HEVC output as default | h264 is the safe, universally-compatible social format; AV1/HEVC compatibility is inconsistent across platforms |
| NVIDIA driver upgrade to unlock newer ffmpeg | Pinning a driver-compatible ffmpeg avoids a risky driver change; the latest ffmpeg's NVENC needs driver ≥610 vs the installed 591.74 |
| GPU transcription on Windows (CUDA whisper) | The only prebuilt CUDA whisper (cuBLAS 12.4) has no native Blackwell/sm_120 kernels → ~40× slower than CPU on the RTX 5060. Native support needs a from-source CUDA 12.8+ build (toolkit install), against "dead-simple setup". CPU BLAS is already ~9× realtime. Deferred (ACCEL-02) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 1 | Pending |
| INGEST-02 | Phase 1 | Pending |
| INGEST-03 | Phase 1 | Pending |
| INGEST-04 | Phase 1 | Pending |
| SELECT-01 | Phase 2 | Pending |
| SELECT-02 | Phase 2 | Pending |
| SELECT-03 | Phase 2 | Pending |
| SELECT-04 | Phase 2 | Pending |
| SELECT-05 | Phase 2 | Pending |
| RENDER-01 | Phase 3 | Pending |
| RENDER-02 | Phase 3 | Pending |
| RENDER-03 | Phase 3 | Pending |
| RENDER-04 | Phase 3 | Pending |
| RENDER-05 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |
| UI-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

### v3 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ZOOM-01 | Phase 9 | Done |
| ZOOM-02 | Phase 9 | Done |
| ZOOM-03 | Phase 9 | Done |
| ZOOM-04 | Phase 10 | Done |
| ZOOM-05 | Phase 10 | Done |
| PROG-01 | Phase 11 | Done |
| PROG-02 | Phase 11 | Done |
| PROG-03 | Phase 11 | Done |
| PROG-04 | Phase 11 | Done |
| EDIT-01 | Phase 12 | Done |
| EDIT-02 | Phase 12 | Done |
| EDIT-03 | Phase 12 | Done |
| EDIT-04 | Phase 12 | Done |
| EDIT-05 | Phase 12 | Done |
| EDIT-06 | Phase 12 | Done |

**v3 Coverage:**
- v3 requirements: 15 total
- Mapped to phases: 15 (Phase 9: 3 · Phase 10: 2 · Phase 11: 4 · Phase 12: 6)
- Unmapped: 0 ✓

### v4 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ACCEL-01 | Phase 13 | Done |
| SAFE-01 | Phase 13 | Done |
| SAFE-03 | Phase 13 | Done |
| ACCEL-02 | Phase 14 | Deferred (Blackwell — see BENCHMARKS.md) |
| SAFE-02 | Phase 14 | Moot (no GPU whisper) |
| BENCH-01 | Phase 14 | Done |
| BENCH-02 | Phase 14 | Done |
| PLAT-01 | Phase 14 | Done (ffmpeg 7.1 pin; whisper stays CPU) |
| ACCEL-03 | Phase 15 | Done (VideoToolbox+Metal defaults; probe/fallback unit-tested) |
| PLAT-02 | Phase 15 | Done (Homebrew ffmpeg VideoToolbox + Metal whisper) |
| PLAT-03 | Phase 16 | Done (windows-optimized + mac-optimized pushed) |
| PLAT-04 | Phase 16 | Done (per-branch quickstart README) |

**v4 Coverage:**
- v4 requirements: 12 total
- Mapped to phases: 12 (Phase 13: 3 · Phase 14: 5 · Phase 15: 2 · Phase 16: 2)
- Delivered: 10 Done · 2 Deferred (ACCEL-02/SAFE-02 — CUDA whisper not viable on Blackwell, see BENCHMARKS.md)
- Unmapped: 0 ✓

### v5 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EDITUX-01 | Phase 17 | Done |
| EDITUX-02 | Phase 17 | Done |
| EDITUX-03 | Phase 17 | Done |
| EDITUX-04 | Phase 17 | Done |
| EDITUX-05 | Phase 18 | Done |
| EDITUX-06 | Phase 18 | Done |
| EDITUX-07 | Phase 19 | Done |

**v5 Coverage:**
- v5 requirements: 7 total
- Mapped to phases: 7 (Phase 17: 4 · Phase 18: 2 · Phase 19: 1)
- Delivered: 7 Done ✓
- Unmapped: 0 ✓

### v5.1 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EDITUX-08 | Phase 21 | Done |
| EDITUX-09 | Phase 22 | Done |
| EDITUX-10 | Phase 21 | Done |
| EDITUX-11 | Phase 21 | Done |
| EDITUX-12 | Phase 20 | Done |

**v5.1 Coverage:**
- v5.1 requirements: 5 total
- Mapped to phases: 5 (Phase 20: 1 · Phase 21: 3 · Phase 22: 1)
- Delivered: 5 Done ✓
- Unmapped: 0 ✓

## v6 Requirements

Milestone v6 — Full Quality Pass: Test, Harden, Improve, Adopt (Phases 23–36). Derived from `.planning/v6-DISCOVERY.md`. Fix requirements are regression-first.

### Test foundation & coverage
- [ ] **QA-01**: The test suite reports line coverage (pytest-cov) with a recorded baseline.
- [ ] **QA-02**: A reusable Starlette `TestClient` fixture exists for exercising endpoints at the request boundary.
- [ ] **QA-03**: A Playwright harness can drive the running app against a seeded job fixture (no multi-minute render required).
- [ ] **QA-04**: `ruff` lint is configured and passes on `content_machine/` and `tests/`.
- [ ] **QA-05**: A CI workflow runs the test suite (and lint) on push.
- [ ] **QA-06**: `config.py` binary/model resolution + `require_tool` error paths are unit-tested.
- [ ] **QA-07**: `cli.py` commands (`ingest`/`select`/`render`/`serve`) are smoke-tested via Typer's runner.
- [ ] **QA-08**: `logging_setup.py` `stream_run`/`run`/`tail`/`job_log` are unit-tested with a real trivial subprocess.
- [ ] **QA-09**: Render orchestration (`render_clip`/`render_job`/`rerender_one`) is tested with the encode layer stubbed.
- [ ] **QA-10**: Captions (`fit_caption`, hyperframes-gated composition path) are unit-tested.
- [ ] **QA-11**: `select.run_claude` failure handling and transcribe binary-layer parsing are tested (gated/skipped if binaries absent).

### HTTP API integration
- [ ] **API-01**: `/upload` is tested for valid video (303 + manifest) and rejection of missing file, bad extension, dotfile, and path-traversal names.
- [ ] **API-02**: `/api/job/{id}/run` is tested for start (ok), re-run (409), unknown job (404), and missing source (400).
- [ ] **API-03**: `/api/job/{id}`, `/log`, and `/clip/{idx}` GET are tested including unknown-job/unknown-idx (404) and the `lines` param.
- [ ] **API-04**: `/clip/{idx}/edit` (too-short trim → 400; valid → queued) and `/rerender-status` are tested.
- [ ] **API-05**: `/download/{id}/{idx}/{aspect}` (200 + 404 on missing aspect), `/media` scoping, and the legacy `/reframe` route are tested.

### Backend reliability
- [ ] **REL-01**: `job.json`/`render.json` writes are atomic (temp-file + `os.replace`) and guarded by a per-job lock; a poll during high-frequency progress writes never reads truncated JSON.
- [ ] **REL-02**: Two clips of one job re-rendering concurrently both persist their `render.json` entries (no lost update).
- [ ] **REL-03**: `/upload` no longer blocks the event loop (hashing/copy off the async path); concurrent progress polls stay responsive during a large upload.
- [ ] **REL-04**: In-flight pipeline errors persist to the manifest and survive a restart; `_RERENDER` reconciles from disk on startup; shutdown stops background work cleanly.
- [ ] **REL-05**: Concurrent renders are capped (semaphore/queue) so simultaneous jobs don't exhaust GPU encode sessions.

### Input validation & hardening
- [ ] **VAL-01**: Trim edits clamp `start≥0` and `end≤duration`; `zoom` has an enforced upper bound.
- [ ] **VAL-02**: `claude -p` selection retries transient failures with backoff and a transcript-scaled timeout; one bad chunk doesn't fail the whole selection.
- [ ] **VAL-03**: Concurrent same-name uploads no longer collide on the staging path.
- [ ] **VAL-04**: A fully-silent / empty-transcript video surfaces the friendly "no clip-worthy moments" message, not a raw exception.
- [ ] **VAL-05**: `/media` no longer serves manifests/transcripts/audio (scoped to media output types) for defense-in-depth.
- [ ] **VAL-06**: `require_tool` hint strings are platform-correct (no `brew install` on Windows).

### Shared crop math
- [ ] **CROP-01**: `computeCrop`/`drawBox`/`drawOut` live in one shared JS module imported by both templates, and use server `source_dims` (not the video element's intrinsic dims).
- [ ] **CROP-02**: A golden-vector parity test asserts the JS crop math matches Python `render.compute_crop` exactly, and runs in CI.

### Frontend robustness & correctness
- [ ] **FE-01**: Polling/edit failures surface a readable "connection lost / retrying" state; polling stops on 404 with a retry cap instead of looping forever.
- [ ] **FE-02**: The pre-run Run error uses an inline surface, not a blocking `alert()`.
- [ ] **FE-03**: Dirty markers are cleared only after the edit POST is confirmed, so a failed apply can be retried without re-nudging.
- [ ] **FE-04**: The editor boots safely when `captions`/`audio`/`transforms` are missing (real error state, no stuck "Loading editor…"); a failed modal edit cleans up its half-open progress UI.
- [ ] **FE-05**: "Re-derive captions" actually recomputes caption segments for the current trim window (real server behavior), or is removed if not delivered.
- [ ] **FE-06**: The editor source video has scrub controls and can be un-muted so audio edits are auditionable.
- [ ] **FE-07**: Caption time inputs are validated (numeric, `start<end`, within trim) with inline error.
- [ ] **FE-08**: Output media is cache-busted consistently (server-provided version), so reconcile-rebuilt cards never show stale media.

### Accessibility (WCAG 2.1 AA where feasible)
- [ ] **A11Y-01**: Aspect tabs, clip tabs, and the modal close are real keyboard-operable `<button>`s with roles/labels.
- [ ] **A11Y-02**: The Quick-crop modal has `role="dialog"`/`aria-modal`, a focus trap, ESC-to-close, and focus return.
- [ ] **A11Y-03**: Sliders are labeled, progress/log regions are `aria-live`, and status is conveyed by text+icon, not color alone.
- [ ] **A11Y-04**: Touch targets meet ≥24px (trim handles), wheel-zoom no longer traps page scroll, drop enforces video type/size, and preview CAP is unified across surfaces.

### Repo-feature adoption
- [ ] **WORD-01**: Selection and editor trim snap to word boundaries using the already-emitted `transcript.json` `words[]` (with segment-level fallback when word timing is absent/poor).
- [ ] **CAPS-01**: Word-level karaoke captions render via the hyperframes overlay path, driven by `words[]`.
- [ ] **CAPS-02**: The hyperframes caption path is provisioned (Chrome/template) and gated behind a caption mode, with the Pillow PNG path intact as an automatic fallback.

### Exhaustive E2E + final verification
- [ ] **E2E-01**: Playwright covers `index.html` — upload enable/disable, drag/drop, size formatting, library pills, submit.
- [ ] **E2E-02**: Playwright covers the job preview state — aspect tabs, zoom/X/Y, slack-disable, reset, copy-to-all, Run.
- [ ] **E2E-03**: Playwright covers progress + clips — master/step bars, log autoscroll, reconcile-in-place, clip tabs, downloads, done/error.
- [ ] **E2E-04**: Playwright covers the Quick-crop modal — open/seed, tabs, scroll-zoom, drag-pan, re-render lifecycle, card refresh, error state.
- [ ] **E2E-05**: Playwright covers the editor — reframe (slider+scroll+drag), magnifier, trim+snap, playhead/preview, captions, audio, apply, flow pill, resume.
- [ ] **E2E-06**: Playwright covers edge/error states (zero dims, missing captions, invalid inputs, 404 job).
- [ ] **DONE-01**: A full real run (upload→render→edit→re-render→download) passes end to end; README/BENCHMARKS updated; applied improvement criteria documented; milestone audit clean.

### v6 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| QA-01, QA-02, QA-03, QA-04, QA-05 | Phase 23 | Pending |
| QA-06, QA-07, QA-08, QA-09, QA-10, QA-11 | Phase 24 | Pending |
| API-01, API-02, API-03, API-04, API-05 | Phase 25 | Pending |
| REL-01, REL-02 | Phase 26 | Pending |
| REL-03, REL-04, REL-05 | Phase 27 | Pending |
| VAL-01, VAL-02, VAL-03, VAL-04, VAL-05, VAL-06 | Phase 28 | Pending |
| CROP-01, CROP-02 | Phase 29 | Pending |
| FE-01, FE-02, FE-03, FE-04 | Phase 30 | Pending |
| FE-05, FE-06, FE-07, FE-08 | Phase 31 | Pending |
| A11Y-01, A11Y-02, A11Y-03, A11Y-04 | Phase 32 | Pending |
| WORD-01 | Phase 33 | Pending |
| CAPS-01, CAPS-02 | Phase 34 | Pending |
| E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06 | Phase 35 | Pending |
| DONE-01 | Phase 36 | Pending |

**v6 Coverage:**
- v6 requirements: 41 total
- Mapped to phases: 41 (every requirement → exactly one phase)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-29*
*Last updated: 2026-06-30 — v6 requirements added (41 reqs, QA/API/REL/VAL/CROP/FE/A11Y/WORD/CAPS/E2E/DONE → Phases 23–36)*
