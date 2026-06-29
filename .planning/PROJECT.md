# Content Machine — LinkedIn Video Clipper

## What This Is

A local-first webapp that turns a long video (talk, webinar, podcast) into short, post-ready LinkedIn clips. You upload a video; it transcribes the audio locally with whisper.cpp; Claude — driven locally through the existing Claude Code subscription — reads the transcript and picks the most clip-worthy moments; each moment is cut into 9:16, 1:1, and 16:9 versions with burned-in captions; transcripts and clips are stored locally. Built first for the author (a GTM/deployed-engineer making LinkedIn content), plausibly a team tool later.

## Core Value

Drop in one video and get back several genuinely good, caption-burned clips in multiple aspect ratios — without uploading the source anywhere or paying per-token API costs.

## Requirements

### Validated

(None yet — ship to validate)

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

## Context

- **Driver:** The author already uses Claude via the Claude Code subscription for knowledge work and internal tools; wants the same "my subscription does the work locally" model applied to LinkedIn content production.
- **Clip-selection engine:** Claude is invoked locally/headless (Claude Code CLI or Agent SDK) rather than via a paid API key — this is the "like I'm doing now" requirement.
- **Stated repos to leverage:**
  - `github.com/ggml-org/whisper.cpp` — local speech-to-text. Strong fit for transcription (confirmed-by-reputation; verify build/bindings).
  - `github.com/browser-use/video-use` — purpose UNVERIFIED. Suspected to be video understanding for AI agents, not a clip editor. **Verify first.**
  - `github.com/heygen-com/hyperframes` — purpose UNVERIFIED. Suspected frame/render library, not a clip editor. **Verify first.**
- **Likely real editing tool:** ffmpeg almost certainly does the actual cutting, cropping, aspect-ratio reframing, and caption burn-in. Whether video-use/hyperframes add value on top is the open question.
- **Typical input:** medium-to-long single-speaker or interview video; output is several 15–90s clips.

## Constraints

- **Tech / local-first**: Everything runs on the author's Mac (darwin) — no source video leaves the machine. — Privacy + cost control + "runs locally" is the whole point.
- **Tech / clip-selection**: Clip selection must run through the Claude Code subscription (headless), not a metered API key. — Avoid per-token cost; matches author's existing workflow.
- **Dependencies (stated)**: User has asked to use all three named repos (whisper.cpp, video-use, hyperframes). — Stated requirement. **Held pending research verification** — if video-use/hyperframes cannot do clip editing, this constraint will be renegotiated with the user before the roadmap is locked.
- **Platform**: macOS, local toolchain (ffmpeg, Node/Python as needed). — Author's environment.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Clip-selection brain = Claude Code locally (headless), not API key | Reuse existing subscription, no per-token cost, runs locally | — Pending |
| Outputs = 9:16 + 1:1 + 16:9, all with burned-in captions | Cover LinkedIn mobile/feed/desktop; captions drive silent-autoplay watch time | — Pending |
| v1 surface = minimal localhost UI (upload → review → download) | Smallest path to something usable; storage built in | — Pending |
| Use whisper.cpp + video-use + hyperframes | User requirement | ⚠️ Revisit — two of three repos unverified for the editing role |
| Local-first, no cloud, no LinkedIn auto-post in v1 | Privacy, cost, and scope control | — Pending |

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
*Last updated: 2026-06-29 after initialization*
