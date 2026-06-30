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

---
*Requirements defined: 2026-06-29*
*Last updated: 2026-06-30 — v5 requirements added (7 reqs, EDITUX → Phases 17–19)*
