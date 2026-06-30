# Content Machine — LinkedIn Video Clipper

## What This Is

A local-first webapp that turns a long video (talk, webinar, podcast) into short, post-ready LinkedIn clips. You upload a video; it transcribes the audio locally with whisper.cpp; Claude — driven locally through the existing Claude Code subscription — reads the transcript and picks the most clip-worthy moments; each moment is cut into 9:16, 1:1, and 16:9 versions with burned-in captions; transcripts and clips are stored locally. Built first for the author (a GTM/deployed-engineer making LinkedIn content), plausibly a team tool later.

## Core Value

Drop in one video and get back several genuinely good, caption-burned clips in multiple aspect ratios — without uploading the source anywhere or paying per-token API costs.

## Current Milestone: v4 — Cross-Platform Hardware Acceleration

**Goal:** Make the two slow stages fast by putting the idle GPU to work — offload video encode to the GPU (NVENC on Windows / VideoToolbox on Mac) and transcription to the GPU (CUDA whisper on Windows; Mac is already Metal) — behind a runtime-probe + automatic CPU fallback so it is structurally impossible to break, shipped as two thin platform-tuned branches off one shared auto-detecting core.

**Target features:**
- `hwaccel.py`: probe each candidate encoder once at startup, cache the verdict, return the best encoder profile (nvenc / videotoolbox / x264) with quality-matched flags; encode-only (CPU decode + CPU filters), aspect ratios encoded serially.
- Encoder fallback wired into `render.py`: every GPU encode transparently re-runs on `libx264` on any failure — an output file is never missing or corrupt; the "always has audio" + faststart guarantees hold.
- GPU transcription: Windows vendors the prebuilt CUDA (cuBLAS) whisper build with auto-fallback to the CPU BLAS build; Mac stays Metal.
- Benchmark/eval harness: measures CPU-vs-GPU wall-time for render and transcribe and validates every output with ffprobe; records before/after numbers proving the speedup and the fallback's validity.
- Two thin platform branches (`windows-optimized`, `mac-optimized`) differing only in defaults/setup/README, each with a dead-simple one-command quickstart; pushed to GitHub.

**Key context:** "Must not break" outranks raw speed. Verified live on the author's machine: the bundled bleeding-edge BtbN master ffmpeg fails NVENC on driver 591.74 (needs ≥610); pinning BtbN ffmpeg 7.1 makes NVENC work with no driver change. Encode-only (no `-hwaccel` decode) and serial GPU sessions are deliberate safety choices. The untestable Mac branch inherits the tested probe+fallback, so worst case it runs CPU exactly like today.

## Requirements

### Validated

- Per-aspect zoom + x/y pan framing, previewed live before render and editable per clip (v3, P9–P10, P12)
- Focused clip editor — trim, reframe, captions, audio — non-destructive `edit.json`, per-aspect re-render (v3, P12)
- Honest master + per-section progress bars with live whisper % and per-clip render counts (v3, P11)

### Active

- [ ] Upload a local video file through a localhost UI
- [ ] Transcribe audio locally with whisper.cpp (timestamped transcript)
- [ ] Use Claude (headless via the Claude Code subscription) to select the best clip-worthy segments from the transcript
- [ ] Cut each selected segment into 9:16, 1:1, and 16:9 aspect ratios
- [ ] Burn captions into clips from the transcript timing
- [ ] Store all transcripts and clips locally, browsable by source video
- [ ] Review suggested clips in the UI and download the ones you want
### Out of Scope

- Direct publishing/scheduling to LinkedIn — v1 produces files; posting is manual (revisit later)
- Cloud upload of source video or clips — local-first is a core value
- Per-token Anthropic API billing as the default path — clip selection runs through the Claude Code subscription
- Multi-user / accounts / hosting — single local user for v1
- AI avatars / generated footage — this clips existing video, not synthesizes it
- Full multi-track timeline NLE (splice/reorder/transitions) — v3 editor is a focused per-clip tool; a real NLE is unreliable on a local ffmpeg pipeline and overkill for short vertical clips

## Context

- **Driver:** The author already uses Claude via the Claude Code subscription for knowledge work and internal tools; wants the same "my subscription does the work locally" model applied to LinkedIn content production.
- **Clip-selection engine:** Claude is invoked locally/headless (Claude Code CLI or Agent SDK) rather than via a paid API key — this is the "like I'm doing now" requirement.
- **Repo verdicts (verified in research 2026-06-29):**
  - `github.com/ggml-org/whisper.cpp` — ✅ FITS. Local STT, Metal-accelerated on Apple Silicon, word-level timestamps via CLI. **Keep.**
  - `github.com/browser-use/video-use` — ⚠️ It IS a real transcript-driven AI video editor, but transcribes via ElevenLabs cloud (breaks local-first) and outputs one montage file. **Dropped as a dependency; its transcript→edit pattern is a reference only.**
  - `github.com/heygen-com/hyperframes` — HTML/CSS→MP4 motion-graphics renderer (animated transparent overlays). **Kept for v1 to render animated captions**, composited over ffmpeg-cut clips. Not a clip cutter.
- **Editing engine:** ffmpeg does the cutting, cropping, aspect-ratio reframing, and clip assembly; whisper.cpp timestamps drive caption timing; hyperframes renders the animated caption overlay.
- **Typical input:** medium-to-long single-speaker or interview video; output is several 15–90s clips.

## Constraints

- **Tech / local-first**: Everything runs on the author's Mac (darwin) — no source video leaves the machine. — Privacy + cost control + "runs locally" is the whole point.
- **Tech / clip-selection**: Clip selection runs through the Claude Code subscription headless (`claude -p`), NOT an API key. — Author's explicit choice. **Accepted risk:** headless calls draw from the same 5-hour/weekly subscription limits (the separate credit pool was paused June 2026) and the Consumer Terms restrict scripted access; mitigated by caching selection per transcript hash. No API-key fallback in v1 by decision.
- **Dependencies (final)**: whisper.cpp (transcription) + ffmpeg (cut/crop/assemble) + hyperframes (animated captions). video-use dropped as a dependency (pattern reference only). — Resolved after research verification.
- **Platform**: cross-platform — Windows 11 (author's primary: Ryzen 9 + RTX 5060 Laptop, 16GB) and macOS Apple Silicon (16GB). Local toolchain (vendored ffmpeg + whisper.cpp, Python). — Author works on both; v4 tunes each for its GPU.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Clip-selection brain = `claude -p` subscription headless, no API-key path | Author's choice; reuse subscription | ⚠️ Accepted risk — shared subscription limits + ToS on scripted access; mitigated by caching per transcript hash |
| Outputs = 9:16 + 1:1 + 16:9, all with captions | Cover LinkedIn mobile/feed/desktop; captions drive silent-autoplay watch time | — Pending |
| v1 surface = minimal localhost UI (upload → review → download) | Smallest path to something usable; storage built in | — Pending |
| Engine = whisper.cpp + ffmpeg + hyperframes (captions); video-use dropped to reference | Verified in research: ffmpeg is the real cutter; video-use breaks local-first; hyperframes fits animated captions | ✓ Resolved |
| v1 reframe = center crop + manual x-offset; segment-level captions; snap cuts to sentence boundaries | Research: speaker-tracking needs CV (defer); word-level karaoke needs forced alignment (defer) | — Pending |
| Local-first, no cloud, no LinkedIn auto-post in v1 | Privacy, cost, and scope control | — Pending |
| v4 GPU accel = encode-only offload (NVENC/VideoToolbox) + GPU whisper, behind a startup probe with automatic libx264/CPU fallback | "Must not break" > speed; mixing hw-decode with sw-filters breaks the filtergraph; a probe+fallback makes a missing GPU/driver a non-event | ✓ Resolved (verified on Windows) |
| v4 Windows ffmpeg pinned to BtbN 7.1 (not master) | Master ffmpeg needs NVENC driver ≥610; author's driver is 591.74 — 7.1 NVENC verified working on it, no driver gamble | ✓ Resolved (verified live) |
| v4 ships two thin platform branches off one shared auto-detecting core (not divergent codebases) | The Mac branch can't be tested here; a shared probe+fallback core means worst case = CPU like today, so it can't break | ✓ Resolved |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-30 — milestone v4 started (cross-platform hardware acceleration: GPU encode + GPU transcribe with probe+fallback)*
