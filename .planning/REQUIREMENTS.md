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

---
*Requirements defined: 2026-06-29*
*Last updated: 2026-06-30 — v3 traceability confirmed against ROADMAP (15/15 → Phases 9–12)*
