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

- [ ] **Phase 5: Windows Cross-Platform Port** - App runs end-to-end on Windows: vendored ffmpeg/ffprobe + prebuilt `whisper-cli.exe` + model, OS-agnostic binary/font resolution, `setup.ps1`
- [ ] **Phase 6: Interactive Crop Preview Before Run** - Upload no longer auto-starts; a preview page shows the source video with a draggable crop-box overlay (9:16/1:1) and a Run button that starts the pipeline with the chosen offset
- [ ] **Phase 7: UI Polish + Live Logs** - Cleaner, more legible index + job pages; clear stage progress; readable live log panel
- [ ] **Phase 8: Render Audio + Caption Fit + Review Reframe** - Every rendered clip keeps its audio in all 3 ratios and after re-frame; captions fit + sit in the safe area in 9:16/1:1/16:9; review-time crop slider (live box + re-render) works reliably

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

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Spine — Ingest + Transcribe | 0/TBD | Not started | - |
| 2. Clip Selection via Claude | 0/TBD | Not started | - |
| 3. Render — Cut, Reframe, Captions | 0/TBD | Not started | - |
| 4. Localhost UI + Job Runner | 0/TBD | Not started | - |

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

## Research Flags (carry into planning)

- **Phase 2:** The non-bare `claude -p` subscription invocation contract (OAuth/keychain behavior, `--json-schema` stability across versions, structured-output parsing) and the selection prompt design are load-bearing unknowns. Worth `--research-phase`.
- **Phase 3:** hyperframes integration is the freshest unknown — authoring segment-timed transparent caption overlays and compositing them over an ffmpeg-cropped clip per aspect ratio is under-researched. Flag for research; ffmpeg ASS captions are the proven fallback.
- **Phases 1 & 4:** standard patterns (whisper.cpp CLI + ffmpeg audio extraction; localhost upload→progress→download) — skip `--research-phase`.

---
*Roadmap created: 2026-06-29 — granularity: coarse, 4 phases, sequential numbering*
