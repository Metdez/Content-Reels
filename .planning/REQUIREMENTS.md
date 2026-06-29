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

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Cloud upload of source video or clips | Local-first is a core value |
| AI avatars / generated footage | This clips existing video, not synthesizes it |
| Multi-user, accounts, hosting | Single local user for v1 |
| API key as the default selection path | Author chose subscription headless; API key is a deferred fallback only |
| video-use as a dependency | Breaks local-first (ElevenLabs cloud); used only as a pattern reference |

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

---
*Requirements defined: 2026-06-29*
*Last updated: 2026-06-29 after initial definition*
