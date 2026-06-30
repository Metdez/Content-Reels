# Content Machine — LinkedIn Video Clipper

## What This Is

A local-first webapp that turns a long video (talk, webinar, podcast) into short, post-ready LinkedIn clips. You upload a video; it transcribes the audio locally with whisper.cpp; Claude — driven locally through the existing Claude Code subscription — reads the transcript and picks the most clip-worthy moments; each moment is cut into 9:16, 1:1, and 16:9 versions with burned-in captions; transcripts and clips are stored locally. Built first for the author (a GTM/deployed-engineer making LinkedIn content), plausibly a team tool later.

## Core Value

Drop in one video and get back several genuinely good, caption-burned clips in multiple aspect ratios — without uploading the source anywhere or paying per-token API costs.

## Current Milestone: v5.1 — Quick-Crop Parity & Render Visibility

**Status:** Complete (shipped 2026-06-30) — recorded retroactively. Continues v5's editing-UX work.

**Goal:** Bring the job-page **Quick-crop** modal to full clip-editor parity and make re-render state visible everywhere it was previously a frozen, silent wait.

**Target features (all delivered):**
- Quick-crop framing parity: the Quick-crop modal gains zoom + Position-Y (alongside X), per-aspect framing, and a live WYSIWYG output-preview canvas — reusing the same crop math (`computeCrop`/`drawBox`/`drawOut`) as the full editor and the pre-run preview.
- Non-blocking Quick-crop re-render: the modal posts per-aspect transforms to the existing non-blocking `/edit` endpoint and polls `/rerender-status` instead of the old blocking `/reframe`, so the UI stays interactive.
- Render visibility in the modal: a progress bar + %, per-aspect queued/rendering/done/error rows, and a live tail of `/api/job/{id}/log` — the user always sees what's happening during the long render.
- Direct-manipulation in Quick-crop: scroll-wheel zooms and drag pans the preview (mirrors the full editor), with the sliders kept as a synced fallback.
- Poll hardening: editor and job-page polls update in place so finished `<video>` elements stop re-buffering from zero (a major source of "rendering takes forever").

**Key context:** Pure frontend — no backend changes; reused the v5 `/edit` + `/rerender-status` + `/log` infrastructure. The Quick-crop modal was the old pre-v5 path (X-offset only, blocking `/reframe`, zero feedback), which is what the user actually experienced as "the edit feature is just not working." Output paths are stable (only file content changes on re-render), so the card refresh is a shared-token cache-bust, NOT a reconcile-sig clear (which would rebuild an un-busted `<video>`). All verified live on Windows with real NVENC via Playwright; 58 tests pass.

### Previous milestone

- **v5 — Editing UX Revamp (Phases 17–19):** Shipped. Background re-render + live editor progress + queue, direct-manipulation framing + magnifier, edit-flow state pill + readable errors. (EDITUX-01…07)

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
| v5 editor re-render runs on a background thread + editor polls `job.json` render progress (reuse the P11 progress mechanism), instead of the synchronous blocking call | Synchronous `rerender_one` froze the editor with no feedback; a background thread + polling makes it non-blockable and legible without new infra | ✓ Shipped (v5 P17) |
| v5 framing = direct manipulation (scroll-zoom + drag-pan) on the live preview, keeping sliders as fallback, with one shared crop-math definition | Sliders are fiddly; direct manipulation is the expected video-editor UX. JS↔Python crop-math divergence is the risk — gated by pixel-parity | ✓ Shipped (v5 P18; extended to Quick-crop in v5.1 P22) |
| v5 edit re-renders queue (single in-flight, next change runs after) rather than running concurrently | "Must not break" → one render at a time avoids clobbering partial outputs / racing the manifest; the user never loses an edit | ✓ Shipped (v5 P17) |
| v5.1 Quick-crop reuses the `/edit` + `/rerender-status` pipeline rather than the old blocking `/reframe`; card refresh is a shared-token cache-bust, not a reconcile-sig clear | Reuses proven v5 infra (no backend change); paths are stable so clearing the sig would rebuild an un-busted `<video>` and undo the reload | ✓ Shipped (v5.1 P21) |

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
*Last updated: 2026-06-30 — milestone v5.1 recorded (Quick-crop parity & render visibility: zoom+Y+live preview, non-blocking render with progress bar + per-aspect status + live log, scroll/drag direct manipulation, poll-in-place hardening). Shipped retroactively; v5 complete.*
