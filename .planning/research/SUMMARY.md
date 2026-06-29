# Project Research Summary

**Project:** Content Machine — LinkedIn Video Clipper
**Domain:** Local-first AI media pipeline (long video → short captioned LinkedIn clips), macOS, single user
**Researched:** 2026-06-29
**Confidence:** HIGH on stack/architecture/features; MEDIUM on the Claude-subscription path (ToS gray area, accepted as a locked risk)

## Executive Summary

This is a **linear, single-user batch pipeline**, not a distributed system: one Mac, one video at a time, four ordered stages — ingest → transcribe → select → render — with the local filesystem as the only database. Experts build this exact shape (`SamurAIGPT/AI-Youtube-Shorts-Generator` and `browser-use/video-use` are open-source references): transcribe with Whisper, let an LLM rank "best moments" from the transcript, snap cuts to word boundaries, cut/reframe with ffmpeg, and burn in captions. The research strongly converges: **ffmpeg does 100% of the actual editing** (cut, crop to 9:16/1:1/16:9, caption burn-in), whisper.cpp does local transcription, and the LLM only reads text and returns a clip list.

The user has **locked the engine**: whisper.cpp (transcription) + ffmpeg (cut/crop/assemble) + **hyperframes for animated captions in v1** (composited as transparent overlay MP4s over ffmpeg-cut clips). `video-use` is **dropped as a dependency** — kept only as a transcript→EDL pattern reference. Clip selection runs through **`claude -p` subscription headless ONLY** (non-bare, OAuth/keychain — `--bare` requires an API key and is forbidden), with **no API-key fallback in v1**. This is an accepted risk: scripted access draws on the shared 5-hour/weekly subscription limits and sits in a ToS gray area with ban precedent. The mitigation is **caching selection results per transcript hash** so Claude is invoked at most once per video and never on re-render.

The biggest quality risks are not architectural — they are in the seams. **Clip selection quality** lives or dies on the prompt (explicit virality criteria, self-contained segments, 15–90s length). **Mid-sentence cuts** are the #1 "amateur" failure: Claude's seconds are *intent*, the whisper word times are *ground truth* — snap every cut to a sentence/silence boundary. The user has deliberately deferred the two CV-heavy items: **v1 reframe is center-crop + a manual x-offset slider** (no speaker-tracking), and **captions are segment-level** (no word-level karaoke / forced alignment). Both are correct lazy defaults that ship and avoid the only features that break the simple stack.

## Key Findings

### Recommended Stack

The technical core is unambiguous and HIGH confidence. Everything heavy is a mature CLI invoked via subprocess — don't wrap in maintained library bindings. Backend language is open (Python+FastAPI recommended for video-use pattern reuse; Node+Hono fine); architecture is identical either way. See `.planning/research/STACK.md`.

**Core technologies:**
- **whisper.cpp** (v1.9.1): local STT with word-level timestamps — fully offline, Metal/Core ML accelerated on Apple Silicon, emits JSON/SRT/VTT directly via CLI.
- **ffmpeg** (7.x, `--enable-libass`): the real editing engine — cut, crop to 9:16/1:1/16:9, scale, burn captions. Use raw subprocess, not fluent-ffmpeg/MoviePy.
- **Claude Code CLI `claude -p`** (non-bare, `--output-format json --json-schema`): clip-selection brain on the subscription. **No API-key path in v1 (locked).**
- **hyperframes**: renders animated captions as transparent overlay MP4s, composited over cropped clips via ffmpeg. **In v1 (locked, user override of STACK.md, which had deferred it).**
- **Local filesystem** (`data/<job_id>/`): the only "database." SQLite optional later for cross-job search.

### Expected Features

See `.planning/research/FEATURES.md`. The standard pipeline is proven; the moat is local-first / zero-upload / no per-token cost.

**Must have (table stakes):**
- Upload local video → get clips back (the core loop)
- Local timestamped transcription
- LLM picks "best moments" with start/end + score + 1-line reason
- Cut on clean boundaries (no mid-sentence cuts) — biggest cheap quality win
- Burned-in captions (silent autoplay = no captions, no watch time)
- 9:16 / 1:1 / 16:9 output (static crop)
- Review/cherry-pick UI; local library browsable by source; 15–90s length enforced

**Should have (competitive):**
- Virality score (0–99) + rationale per clip — nearly free, high perceived value
- Auto-generated hook/title per clip — final per-clip pass
- Animated captions via hyperframes — in v1 per user decision (segment-level timing, not word-level karaoke)

**Defer (v2+):**
- Word-level / karaoke captions (needs forced alignment — explicitly deferred)
- Speaker-aware auto-reframe (needs CV — explicitly deferred; manual x-offset is the v1 substitute)
- Multi-speaker diarization, LinkedIn auto-publish, cloud anything

### Architecture Approach

A staged pipeline with a single serial worker. Each stage writes its artifact to `data/<job_id>/` and updates `job.json`; any stage can re-run from its predecessor's artifact, so a render crash never forces re-transcription. Subprocess-per-tool with progress parsed from stderr. Progress to the UI via polling (lazy default) or SSE. See `.planning/research/ARCHITECTURE.md`.

**Major components:**
1. **Ingest** — ffprobe + extract 16kHz mono WAV.
2. **Transcribe** — whisper.cpp → `transcript.json` (segment + word timings).
3. **Select** — non-bare `claude -p` → `clips.json` `[{start,end,title,score,reason}]`, cached by transcript hash.
4. **Render** — ffmpeg cut + center-crop (manual x-offset) + caption burn (+ hyperframes overlay) per clip × 3 ratios + thumbnail.
5. **Server/UI + job runner** — one process: upload → progress → review grid → download.

### Critical Pitfalls

Top items from `.planning/research/PITFALLS.md`:

1. **Subscription limit burn** — `claude -p` draws on the shared 5-hr/weekly pool (separate credit pool paused June 2026). Avoid: one call per video, sentence-level (not word-level) transcript input, cache by transcript hash, log `total_cost_usd`.
2. **Mid-sentence cuts** — Claude's seconds are approximate. Avoid: snap start/end to sentence/silence boundaries from local word times, add ~0.2–0.4s pre-roll. (Locked user constraint.)
3. **Malformed/hallucinated timestamps** — Avoid: strict JSON schema, validate `0 ≤ start < end ≤ duration` and clip-length, one repair retry then fail loud, `--max-turns 1` tools off.
4. **Center-crop slices the speaker out** — Avoid: manual x-offset slider (locked v1 choice) + crop-region preview thumbnail before full encode.
5. **ffmpeg input-seek black frames / multi-pass blowup** — Avoid: output-seek + re-encode (required anyway for crop+captions), one filtergraph per output, idempotent renders (skip existing files).
6. **Whisper silence hallucination + ~±300ms drift** — Avoid: VAD, padding on snaps, sanity-check repeated phrases; pick small/medium model.

## Implications for Roadmap

The pipeline's dependency chain *is* the build order. Build CLI-first; the UI is a thin wrapper over a pipeline that already works headlessly, so every real risk (whisper build, subscription auth, ffmpeg reframing, caption styling) is solved before any HTTP code exists.

### Phase 1: Pipeline spine — ingest + transcribe (CLI, no UI)
**Rationale:** Everything downstream keys off transcript timing; this de-risks the whisper.cpp Metal build first.
**Delivers:** Drop a video on the CLI → `data/<job_id>/` with `audio.wav` + word-level `transcript.json`.
**Uses:** whisper.cpp (Metal/Core ML), ffmpeg audio extraction.
**Avoids:** Pitfall 8 (whisper hallucination/drift — VAD, model choice); establishes staged-artifact layout (Pitfall 9).

### Phase 2: Clip selection via Claude (subscription, cached)
**Rationale:** Needs a transcript; this is where the product lives or dies and where the locked subscription risk concentrates.
**Delivers:** `select` stage — non-bare `claude -p` + json-schema → `clips.json` with 15–90s windows, score, hook, reason. Cache by transcript hash.
**Implements:** Select component; the swappable `select_clips()` seam (even with no v1 fallback, keep the seam).
**Avoids:** Pitfalls 1 (one cached call/video, sentence-level input), 2 (timeline-distributed picks), 3 (strict JSON + validation), 10 (criteria-driven prompt).

### Phase 3: Render — cut + center-crop + captions
**Rationale:** Needs source + timing (P1) and clip list (P2).
**Delivers:** Each clip → 9:16/1:1/16:9 with snapped boundaries, segment-level burned captions, hyperframes animated-caption overlay composited via ffmpeg, + thumbnail.
**Uses:** ffmpeg (output-seek re-encode, single filtergraph), hyperframes.
**Avoids:** Pitfalls 4 (manual x-offset + preview), 5/6 (output-seek, idempotent, one pass), 7 (ASS force_style legibility per ratio); boundary-snap straddles P2→P3.

### Phase 4: Localhost UI + job runner
**Rationale:** Thin wrapper over the working pipeline — built last by design.
**Delivers:** Upload → progress (poll, SSE if laggy) → review grid (score/reason/preview) → per-clip per-ratio download. Serial runner + `job.json`.
**Avoids:** Pitfall 9 (per-stage progress, resume-from-stage, stream finished clips); security (bind 127.0.0.1, args-array not shell, no cloud-synced artifact dir).

### Phase Ordering Rationale

- **Strict artifact dependency:** can't SELECT without a transcript, can't RENDER without a clip list. The chain dictates order.
- **Risk-first:** whisper build, subscription auth, and ffmpeg reframing/captions are all solved headlessly in P1–P3 before any UI exists.
- **Locked constraints map cleanly:** caching (P2), boundary-snapping (P2→P3), manual x-offset + segment captions + hyperframes overlay (P3) all land in their natural phases.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** The `claude -p` non-bare subscription invocation contract (OAuth/keychain behavior, json-schema stability across versions, structured-output parsing) and the selection prompt design are the load-bearing unknowns. Worth `--research-phase`.
- **Phase 3:** **hyperframes integration is the freshest unknown** — how to author segment-timed transparent caption overlays and composite them over an ffmpeg-cropped clip per aspect ratio is not covered in depth by the research (STACK/ARCH treated hyperframes as deferred). Flag for research.

Phases with standard patterns (skip research-phase):
- **Phase 1:** whisper.cpp CLI usage and ffmpeg audio extraction are well-documented.
- **Phase 4:** localhost upload→progress→download is a standard, well-trodden pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | whisper.cpp + ffmpeg verified and unambiguous; hyperframes role is a user decision layered on top (see gap). |
| Features | HIGH | Competitor features, LinkedIn norms, caption/reframe tech corroborated across multiple sources + comparable OSS pipeline. |
| Architecture | HIGH | Pipeline shape, Claude invocation mode, ffmpeg role all verified; identical across backend language choice. |
| Pitfalls | HIGH on whisper/ffmpeg/Claude mechanics; MEDIUM on subscription limits (moving target). |

**Overall confidence:** HIGH on the build path; MEDIUM only on the locked subscription path (accepted risk).

### Gaps to Address

- **hyperframes for v1 captions:** All four research files treated hyperframes as deferred or wrong-fit for v1; the user has overridden this to use it for animated captions. The composite-overlay workflow (segment-timed transparent MP4 → ffmpeg overlay per ratio) is under-researched. **Handle:** dedicated research at Phase 3 planning; if hyperframes proves heavy, ffmpeg ASS captions are the proven fallback (segment-level captions still ship).
- **Subscription ToS / ban risk (accepted, no v1 fallback):** Scripted `claude -p` violates Consumer Terms; ban precedent exists. **Handle:** keep the `select_clips()` seam swappable, invoke at most once per video (cached), log spend; revisit an API-key path only if limits/bans bite.
- **Word-level caption timing (deferred):** vanilla whisper.cpp word timestamps are unreliable; v1 ships segment-level. **Handle:** karaoke captions are a v1.x item gated on forced alignment (WhisperX-style) — out of scope now.

## Sources

### Primary (HIGH confidence)
- github.com/ggml-org/whisper.cpp — Core ML/Metal build, word-level timestamps, JSON/SRT/VTT output
- code.claude.com/docs/en/headless — `claude -p`, non-bare = subscription, `--bare` requires API key, `--output-format json --json-schema`
- ffmpeg crop/scale/subtitles/-progress recipes — 9:16 `crop=ih*9/16:ih`, ASS force_style, output-seek re-encode
- github.com/browser-use/video-use — transcript→EDL pattern (reference only; ElevenLabs cloud + montage output = dropped)
- github.com/heygen-com/hyperframes — HTML→MP4 transparent overlay renderer (used for animated captions in v1)

### Secondary (MEDIUM confidence)
- support.claude.com (15036540, 11145838) — Agent SDK/`claude -p` draws on subscription limits; June 2026 credit-pool pause
- Opus Clip / Vizard / Klap feature & virality-score writeups; SamurAIGPT/AI-Youtube-Shorts-Generator (reference architecture)
- LinkedIn video length/format norms (2026 guides)

### Tertiary (LOW confidence)
- github.com/anthropics/claude-code#36324 — community-reported bans for scripted `-p` on subscriptions (ToS quote verified; ban reports community-sourced)

---
*Research completed: 2026-06-29*
*Ready for roadmap: yes*
