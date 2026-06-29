# Phase 1: Pipeline Spine — Ingest + Transcribe - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss); decisions pre-locked from research + PROJECT.md

<domain>
## Phase Boundary

A command-line entry point that takes one local video file and produces staged artifacts under `data/<job_id>/`: a copy/reference to the `source`, extracted `audio.wav` (16kHz mono), and a clean timestamped `transcript.json`. This de-risks the whisper.cpp Apple-Silicon build and establishes the staged-artifact + `job.json` layout that every later stage and crash-recovery path depends on. No clip selection, no rendering, no web UI in this phase.

</domain>

<decisions>
## Implementation Decisions

### Language & Project Shape
- Python 3.11+ as the implementation language for the whole project (pipeline shells out to whisper.cpp, ffmpeg, and `claude -p`; FastAPI gives an easy localhost UI in Phase 4). Node is an acceptable equivalent but Python is chosen for consistency.
- A `typer`-based CLI is the Phase 1 surface (e.g. `content-machine ingest <video>`).
- Local-first: nothing leaves the machine. No network calls in this phase except none.

### Storage Layout (load-bearing — later phases depend on it)
- Per-job directory: `data/<job_id>/` where `job_id` is derived from the source video content hash (sha256 of file bytes, truncated) so re-runs are idempotent and cache-keyed.
- Files: `source` (original path reference or copy), `audio.wav`, `transcript.json`, and `job.json` (the job state/manifest: stage statuses, source path, hash, timestamps, tool versions).
- `job.json` tracks per-stage completion so a later crash resumes from the last completed stage and never re-transcribes.

### Transcription
- Use whisper.cpp built with Metal acceleration on Apple Silicon. Vendor it as a git submodule/clone of `github.com/ggml-org/whisper.cpp` and build locally; the app invokes its CLI (`whisper-cli`/`main`) as a subprocess.
- Default model: `base` or `small` (`ggml-small.bin`) — deliberate accuracy/speed tradeoff for a Mac; make the model configurable. Auto-download the model on first run if missing.
- Audio extraction via ffmpeg to 16kHz mono WAV (whisper.cpp's required input format).
- Output `transcript.json` = segment-level text with timestamps, plus word-level timing where whisper.cpp provides it (`--output-json-full` / word timestamps). Treat word timing as approximate (±~300ms drift) — downstream snapping handles precision.

### Quality / VAD
- Enable VAD (whisper.cpp built-in VAD or a silence pre-filter) so silent/empty audio does NOT emit phantom text ("Thanks for watching", "you", etc.). Verify with a deliberately-silent test clip.

### Caching / Idempotency
- Keyed by source video content hash: if `data/<job_id>/transcript.json` already exists and matches, reuse it instead of re-transcribing.

### Claude's Discretion
- Exact CLI command/flag names, internal module layout, choice of hashing length, ffmpeg invocation details, and whether `source` is copied vs referenced — at Claude's discretion, consistent with the above.

</decisions>

<code_context>
## Existing Code Insights

Greenfield — no existing application code. Repos available to vendor: `github.com/ggml-org/whisper.cpp` (build locally). `ffmpeg` expected on PATH (install via Homebrew if missing — surface a clear error/setup step). Pattern reference (do not depend on): `github.com/browser-use/video-use` for transcript→edit shape.

</code_context>

<specifics>
## Specific Ideas

- A known-content test video should be used to assert transcript correctness; a silent clip to assert VAD suppression.
- Tool versions (whisper.cpp commit, model name, ffmpeg version) recorded in `job.json` for reproducibility.

</specifics>

<deferred>
## Deferred Ideas

- Word-level karaoke caption alignment (WhisperX-style forced alignment) — deferred to v1.x (CAPS-01).
- Clip selection, rendering, and UI — later phases.

</deferred>
