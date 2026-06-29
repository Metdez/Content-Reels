# Feature Research

**Domain:** Local-first AI video-clipping / short-form repurposing tool (long video → LinkedIn clips)
**Researched:** 2026-06-29
**Confidence:** HIGH (competitor features, LinkedIn norms, caption/reframe tech all corroborated across multiple independent sources + a directly comparable open-source pipeline)

## TL;DR for the roadmap

- The standard local pipeline is **proven and well-trodden**: transcribe (whisper) → LLM ranks "best moments" from transcript → cut on word boundaries with ffmpeg → reframe to vertical → burn captions. `SamurAIGPT/AI-Youtube-Shorts-Generator` is an open-source Opus Clip clone with this exact architecture; treat it as a reference, not a dependency.
- **`video-use` (one of the three named repos) is a real, directly-relevant LLM video editor** — it transcribes, cuts on word boundaries, and burns subtitles. It overlaps the editing role and partially overlaps the LLM-selection role. This RESOLVES the PROJECT.md "verify first" flag for video-use. (whisper.cpp confirmed-good; hyperframes still unverified for the editing role and is likely an anti-dependency — see Anti-Features.)
- **The one genuinely hard feature is speaker-aware auto-reframe** (keep the speaker in frame for 9:16). It needs face/active-speaker detection, NOT plain ffmpeg. Everything else is ffmpeg + LLM + whisper. **Recommend a static/center crop for v1** and defer smart reframe.
- **Word-level caption timing is the quality lever most likely to bite.** Vanilla whisper.cpp word timestamps are weak; plan for forced alignment (WhisperX-style) or accept segment-level captions in v1.

## Feature Landscape

### Table Stakes (Users Expect These)

If the tool ships without these, it doesn't feel like a clipper.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Upload local video → get clips back | The core loop | LOW | Already the v1 spine in PROJECT.md |
| Local timestamped transcription | Everything downstream keys off transcript timing | LOW–MED | whisper.cpp confirmed good. Segment timestamps are easy; **word-level is the hard part** (see Differentiators / Pitfalls) |
| LLM picks "best moments" automatically | This is the product — nobody wants to scrub a 1hr video | MED | LLM (Claude Code headless per PROJECT.md) reads transcript, returns ranked segments w/ start/end + reason |
| Cut clips on clean boundaries (no mid-sentence cuts) | A clip that starts mid-word looks broken | LOW–MED | **Constrain start/end to transcript word boundaries.** Cheap, huge quality win. Single biggest "feels professional" lever |
| Burned-in captions | Silent autoplay on LinkedIn means no captions = no watch time. Universal expectation | MED | ffmpeg `subtitles` filter with ASS `force_style`. Burned-in (not sidecar SRT) is the norm for feed video |
| 9:16 vertical output | 9:16 native gets materially more LinkedIn organic reach than landscape | LOW (static crop) / HIGH (smart) | Static center/letterbox crop is LOW. Keeping the speaker framed is HIGH — see auto-reframe |
| Multiple aspect ratios (9:16, 1:1, 16:9) | PROJECT.md requirement; covers mobile feed / square / desktop | LOW | Same source clip, three ffmpeg crop/pad passes. Cheap once cut points exist |
| Review clips in UI before download | Users won't trust raw AI picks; they cherry-pick | LOW–MED | Localhost UI: list clips, preview, pick, download. Already in PROJECT.md |
| Local storage browsable by source video | "Where are my clips" — basic library hygiene | LOW | Filesystem + light index; no DB needed for single user |
| Clip length in the 15–90s range | LinkedIn sweet spot; longer clips just won't perform | LOW | Encode as a constraint in the LLM prompt + a hard max in code |

### Differentiators (Competitive Advantage)

Where this tool can punch above a generic clipper. Align with PROJECT.md core value (local, no per-token cost, no upload).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Local-first, zero upload, zero per-token cost** | The whole pitch. Opus/Vizard/Klap all upload your source to their cloud and meter you | (inherent) | This is the moat vs SaaS. Not a feature to build so much as a constraint to protect |
| **Virality/quality score per clip** | Opus Clip's signature feature. Lets the user triage which clips to post | LOW (it's a prompt) | Have the LLM emit a 0–100 score + a 1-line rationale per clip. Nearly free since the LLM is already reading the transcript. **High perceived value for almost no cost** |
| **Auto-generated hook / punchy title per clip** | First-second attention is everything; a 3–7 word hook overlay drives watch time | LOW | Generate as a *final* pass, on the chosen clip's transcript only, so it reflects what the clip actually is |
| **Karaoke / word-highlight captions** | The TikTok/Reels look that outperforms static captions; signals "modern" | MED–HIGH | Requires reliable **word-level** timestamps (forced alignment). ASS karaoke tags via ffmpeg. Gate on caption-timing quality being solved first |
| **Speaker-aware auto-reframe (keep speaker in 9:16 frame)** | The quality gap between good and bad vertical clips. Vizard/Opus compete here | HIGH | **NOT plain ffmpeg.** Needs face detection + active-speaker detection (OpenCV / MediaPipe AutoFlip / YOLO+tracking). Strong differentiator but the riskiest item — defer past v1 |
| Caption style presets (font, position, brand color) | Consistent personal-brand look across clips | LOW | ffmpeg `force_style`. A few hardcoded presets is enough for v1.x |
| LLM reasoning shown in review UI | "Why did it pick this?" builds trust in the AI picks | LOW | Just surface the score + rationale the LLM already returns |

### Anti-Features (Commonly Requested, Often Problematic)

Things that look attractive but are wrong for a **local v1**. Documenting to prevent scope creep.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Direct publish/schedule to LinkedIn | "Close the loop" | OAuth, LinkedIn API approval, token mgmt, breaks local-first; already Out of Scope in PROJECT.md | Produce files; post manually |
| Cloud rendering / GPU offload | Faster exports | Defeats the entire local-first / no-upload value prop | Accept slower local ffmpeg; it's a background job |
| AI avatars / B-roll / generated footage | "Make it flashier" | Different product (synthesis, not clipping); Out of Scope in PROJECT.md | Clip the real footage only |
| Rearranging/stitching non-contiguous moments into one clip (Opus's "ReClip") | Opus does it | Adds jump-cut quality problems, complex boundary logic, audible pops; hard to do well | Contiguous segments only in v1 |
| Multi-speaker diarization + per-speaker reframe | Podcasts/interviews | Heavy: diarization + active-speaker switching. Author's typical input is single-speaker (PROJECT.md) | Single subject; static crop v1 |
| Real-time / live clipping | "Instant" | No use case here; input is uploaded files | Batch background job |
| Multi-user accounts / brand kits / approval flows | Vizard's enterprise tier | Single local user (Out of Scope in PROJECT.md) | Single-user filesystem |
| Forcing `hyperframes` into the editing pipeline | It's a named repo | Purpose unverified; suspected frame/render lib, not a clip editor. Adopting it for editing risks a dependency that doesn't fit | ffmpeg (+ optionally video-use) does the editing; renegotiate hyperframes with user if it can't earn its place |
| Building our own video editor / preset filter UI | "Full control" | Descript-class scope; massive | LLM-driven cuts + review/cherry-pick UI only |

## Feature Dependencies

```
Transcription (whisper.cpp)
    └──requires──> Word/segment timestamps
            ├──enables──> LLM best-moment selection (start/end times)
            │       └──requires──> Clean boundary cutting (snap to word boundaries)
            │               └──enables──> ffmpeg cut + multi-aspect export
            │                       └──enables──> Burned-in captions
            │                               └──enhanced-by──> Word-level (karaoke) captions
            │                                       └──requires──> Forced alignment / reliable word timestamps
            └──enables──> Virality score + hook generation (LLM, transcript-only)

Speaker-aware auto-reframe ──enhances──> 9:16 export
        └──requires──> Face detection + active-speaker detection (NOT ffmpeg)

Review/cherry-pick UI ──requires──> clips + scores + rationale produced upstream
Local storage/library ──requires──> clips produced; ──enables──> review UI
```

### Dependency Notes

- **Everything depends on transcript timing quality.** Segment-level timing is enough for cutting and basic captions. **Word-level** timing is the gate for karaoke captions AND for tight boundary snapping. Vanilla whisper.cpp word timestamps are unreliable (the models weren't trained for per-word timestamps); forced alignment (WhisperX/wav2vec2 style) is the known fix. Decide early: ship segment-level captions in v1, or invest in alignment.
- **Clean boundary cutting requires the LLM to return times that snap to transcript word boundaries**, not raw seconds it invents. Cheapest highest-impact quality feature. Implement as: LLM returns approximate start/end → code snaps to nearest word boundary / silence gap.
- **Virality score + hook are nearly free** because the LLM is already reading the transcript. Bundle them into the selection call's structured output.
- **Auto-reframe is the only feature that breaks the "ffmpeg + LLM + whisper" stack.** It needs a CV dependency (OpenCV face tracking, Google AutoFlip/MediaPipe, or YOLO+ByteTrack). This is the flag for the roadmap: isolate it in its own phase, gate it behind a v1 that uses static crop.
- **Multi-aspect export is cheap once cut points exist** — three crop/pad passes over the same trimmed segment.
- **video-use overlap:** video-use already does transcript-driven cutting + subtitle burn-in. The roadmap should explicitly decide whether to *use* video-use as the cut/caption engine or just borrow its approach. It does not do speaker-aware reframe, so that stays a separate build either way.

## MVP Definition

### Launch With (v1)

Ruthlessly minimum — validate "drop in a video, get good clips" with no cloud.

- [ ] Upload local video via localhost UI — the loop
- [ ] Local whisper.cpp transcription (segment-level timestamps OK) — foundation
- [ ] LLM (Claude Code headless) selects top N segments with **start/end + score + 1-line reason** — the product
- [ ] Snap clip boundaries to word/segment boundaries — "feels professional" with tiny effort
- [ ] ffmpeg cut → export 9:16, 1:1, 16:9 with **static center crop** — covers PROJECT.md aspect requirement without the hard CV work
- [ ] Burned-in captions (segment-level, one readable ASS style) — silent-autoplay table stake
- [ ] Enforce 15–90s clip length — LinkedIn norm
- [ ] Review UI: preview clips + score/reason, pick, download — trust + cherry-pick
- [ ] Local storage browsable by source video — library hygiene

### Add After Validation (v1.x)

Trigger: v1 produces clips the author actually posts, but quality/polish gaps show.

- [ ] **Word-level captions (karaoke highlight)** — add once forced alignment is in and basic captions proven. Biggest "looks modern" upgrade
- [ ] Auto-generated hook/title overlay per clip — add when captions pipeline is stable
- [ ] Caption style presets (brand color/font/position) — add when author wants a consistent look
- [ ] Surface full LLM rationale in UI — cheap trust boost

### Future Consideration (v2+)

Defer until the core loop is validated and the static-crop quality ceiling is actually hit.

- [ ] **Speaker-aware auto-reframe** for 9:16 — defer: only CV-heavy, non-ffmpeg feature; static crop is "good enough" for single-speaker talking-head input. Add when static crop visibly fails (speaker walks/moves)
- [ ] Multi-speaker handling (interviews/panels) — defer: PROJECT.md input is mostly single-speaker
- [ ] LinkedIn direct publish — explicitly Out of Scope; revisit only if manual posting becomes the bottleneck

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Upload → clips loop | HIGH | LOW | P1 |
| Local transcription (segment-level) | HIGH | LOW | P1 |
| LLM best-moment selection | HIGH | MEDIUM | P1 |
| Boundary snapping (no mid-sentence cuts) | HIGH | LOW | P1 |
| 9:16/1:1/16:9 static-crop export | HIGH | LOW | P1 |
| Burned-in captions (segment-level) | HIGH | MEDIUM | P1 |
| Virality score + reason | HIGH | LOW | P1 |
| Clip-length enforcement | MEDIUM | LOW | P1 |
| Review/cherry-pick UI | HIGH | MEDIUM | P1 |
| Local library/storage | MEDIUM | LOW | P1 |
| Word-level / karaoke captions | HIGH | HIGH | P2 |
| Hook/title overlay | MEDIUM | LOW | P2 |
| Caption style presets | MEDIUM | LOW | P2 |
| Speaker-aware auto-reframe | HIGH | HIGH | P3 |
| Multi-speaker reframe | MEDIUM | HIGH | P3 |
| LinkedIn auto-publish | LOW (scope) | HIGH | P3 |

## What makes LLM clip-selection actually GOOD (concrete)

The selection prompt/heuristic is where this product lives or dies. Concrete requirements distilled from how Opus Clip and open-source clones do it:

1. **Score on explicit virality signals, not vibes.** Have the LLM evaluate each candidate against named signals: **hook strength** (does the opening 1–3s grab attention?), **flow** (self-contained, logical, satisfying end?), **value** (insight / emotional resonance / takeaway), **quotability** (a punchy line), and emotional peaks / opinion bombs / revelations. Emit a 0–99 score + short rationale. This mirrors Opus Clip's Hook/Flow/Value/Trend rubric.
2. **Self-contained segments.** Each clip must make sense without the surrounding video — a strong open and a clean resolution. Penalize segments that reference unshown context ("as I said earlier...").
3. **Snap to word boundaries.** LLM returns approximate start/end; code snaps to nearest transcript word boundary and, ideally, a nearby silence gap. **Never cut mid-word.** Prefer cutting at sentence boundaries / pauses to avoid audible pops.
4. **Non-overlapping / dedup.** Without a non-overlap constraint you get N variations of the same moment. Collapse overlapping candidates, keep the highest-scoring.
5. **Length window baked in.** Constrain candidates to 15–90s (LinkedIn) in the prompt AND enforce in code.
6. **Two-stage for long input (cheap → expensive).** For 1hr+ video: a cheap topic/segment pass narrows hours to tens of candidates, then an expensive scoring pass ranks the survivors. Chunk long transcripts with overlap (e.g. 20-min windows) so no moment is split across a boundary. (Relevant because Claude Code headless has context limits.)
7. **Hook generated last, per-clip.** Generate the 3–7 word hook/title from ONLY the chosen clip's transcript, as a final pass — so it reflects what the clip is, not what you hoped.
8. **Structured output.** Selection call should return JSON: `[{start, end, score, hook, reason}]` — directly drives cutting, captions, and the review UI.

## Caption styling expectations (concrete)

- **Burned-in, not sidecar.** Feed video autoplays muted; captions must be permanent pixels. Sidecar SRT won't show.
- **Legible on mobile by default.** Default SRT styling is too small / no background. Use large font, high contrast, outline or semi-transparent background box, bottom-or-center placement, generous bottom margin. ffmpeg `subtitles=...:force_style='FontName=...,FontSize=...,Outline=...,BorderStyle=...,MarginV=...'`.
- **Word-highlight (karaoke) is the modern, higher-performing look** — but requires reliable word-level timestamps and ASS karaoke tags. v1 can ship segment-level captions; karaoke is a P2 upgrade gated on forced alignment.
- Use ASS (not plain SRT) for predictable styling control; libx264 + ASS is the reliable burn combo.

## Auto-crop / speaker-framing (concrete — flag for roadmap)

- **Static crop (v1): plain ffmpeg.** Center crop or letterbox/pad to 9:16, 1:1, 16:9. Zero CV dependency. Adequate for centered single-speaker talking-head footage (the author's typical input).
- **Speaker-aware reframe (P3): NOT ffmpeg.** Requires face detection + active-speaker detection + smoothed virtual-camera path. Known options: **Google AutoFlip** (MediaPipe-based, purpose-built for intelligent reframing), OpenCV face tracking + motion smoothing (what the SamurAIGPT clone uses locally), or YOLO-segmentation + ByteTrack approaches. This is the single feature that breaks the otherwise-simple stack — isolate it.
- **Roadmap flag:** v1 must NOT block on reframe quality. Ship static crop; treat smart reframe as its own later phase with its own CV-dependency research.

## Competitor Feature Analysis

| Feature | Opus Clip | Vizard / Klap | Our Approach (local v1) |
|---------|-----------|---------------|-------------------------|
| Best-moment selection | GPT-4-based hook model, ranks 10–30 clips | AI picks strongest moments | Claude Code (headless, local, no per-token cost) scores segments from transcript |
| Virality score | 0–99 (Hook/Flow/Value/Trend) | Score-based ranking | 0–99 + rationale via LLM structured output (P1, cheap) |
| Captions | Auto, animated/word-level | Dynamic auto captions | Burned-in segment-level (v1) → karaoke (v1.x) |
| Auto-reframe | Strong multi-speaker face tracking | Vizard strong; Klap picks largest face | Static crop v1; speaker-aware deferred to P3 |
| Aspect ratios | 9:16/1:1/16:9 | Multiple | 9:16/1:1/16:9 (PROJECT.md) |
| Source handling | Cloud upload, metered | Cloud upload, metered | **Local only, no upload, no metering** (the moat) |
| Publishing | Built-in scheduler | Scheduling/workspaces | Files only; manual post (Out of Scope) |

## Sources

- Opus Clip virality score / hook detection: [help.opus.pro](https://help.opus.pro/docs/article/virality-score), [skywork.ai review](https://skywork.ai/blog/opusclip-review-2025-ai-auto-clipping-virality-score-scheduler/), [aitoolsdevpro guide](https://aitoolsdevpro.com/ai-tools/opus-clip-guide/)
- Vizard / Klap / Descript reframe + captions: [vugola alternatives 2026](https://www.vugolaai.com/blog/best-vizard-alternatives-2026), [vugola best clipping tools 2026](https://www.vugolaai.com/blog/best-ai-video-clipping-tools-2026), [choppity best AI clip makers](https://www.choppity.com/blog/best-ai-clip-maker/)
- LinkedIn video length/format norms: [Visla LinkedIn video 2026](https://www.visla.us/blog/guides/linkedin-video-in-2026-whats-working-and-how-to-make-it/), [OpusClip ideal LinkedIn length](https://www.opus.pro/blog/ideal-linkedin-video-length-format-for-retention), [justpollen specs 2026](https://www.justpollen.com/blog/linkedin-video-guide)
- LLM clip selection / boundary / hook strategy: [LumiClip DEV writeup](https://dev.to/garrywilliamss/how-lumiclip-finds-the-best-moments-in-your-video-and-reframes-them-for-mobile-2hlh), [SamurAIGPT/AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator) (open-source Opus Clip clone, reference architecture)
- video-use purpose (resolves PROJECT.md flag): [video-use SKILL.md](https://github.com/browser-use/video-use/blob/main/SKILL.md)
- Captions / ffmpeg ASS / karaoke: [mpegflow burn captions](https://www.mpegflow.com/recipes/burn-captions-into-video), [samgalope karaoke ffmpeg](https://www.samgalope.dev/2024/11/05/diy-karaoke-videos-with-ffmpeg-and-srt-format-sync-and-style/), [abyssale subtitle appearance](https://www.abyssale.com/blog/how-to-change-the-appearances-of-subtitles-with-ffmpeg)
- Auto-reframe / active-speaker: [Google AutoFlip](https://research.google/blog/autoflip-an-open-source-framework-for-intelligent-video-reframing/), [smart-reframe](https://github.com/gauravzazz/smart-reframe), [auto-vertical-reframe](https://github.com/KazKozDev/auto-vertical-reframe)
- whisper.cpp word timestamps / forced alignment: [whisper.cpp discussion #2307](https://github.com/ggml-org/whisper.cpp/discussions/2307), [WhisperX guide](https://localaimaster.com/blog/whisperx-guide)

---
*Feature research for: local-first AI LinkedIn video clipper*
*Researched: 2026-06-29*
