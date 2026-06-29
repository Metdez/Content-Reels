# Pitfalls Research

**Domain:** Local-first AI video clipper (long video → short captioned LinkedIn clips) on macOS, Claude-driven headless via subscription
**Researched:** 2026-06-29
**Confidence:** HIGH (whisper.cpp, ffmpeg, Claude headless mechanics verified) / MEDIUM (Claude subscription limits — a moving target)

> Phase names below are inferred from the natural pipeline (the roadmap doesn't exist yet):
> **P1 Transcription** · **P2 Clip Selection (Claude headless)** · **P3 Video Rendering (ffmpeg)** · **P4 UI + Jobs/Storage**.
> Map to real phase numbers when the roadmap is built.

---

## Critical Pitfalls

### Pitfall 1: Headless Claude usage silently burns your subscription's shared limit

**What goes wrong:**
You assume `claude -p` runs on a free/separate automation budget. It does not. As of June 2026, Anthropic **paused** the planned separate Agent-SDK/`claude -p` credit pool — headless calls draw from the **same** 5-hour and weekly limits as your interactive Claude Code, Claude Desktop, and claude.ai usage. A few long-transcript runs during a workday can exhaust the 5-hour window mid-task, and the agent that's clipping your video starves the agent you're coding with (and vice versa).

**Why it happens:**
Search results and blog posts from early 2026 describe a "separate credit pool" — but that change was reverted on June 15, 2026. Easy to build against the wrong mental model. Also, transcripts are large (a 60-min talk ≈ 8–12k words ≈ ~15–25k input tokens) and you'll re-run on every iteration.

**How to avoid:**
- Treat Claude calls as a **scarce, metered resource**: one call per video for selection, not per-clip or per-retry loops.
- **Compress the input**: send Claude a downsampled transcript (timestamps every N seconds or per sentence, not per word). Word-level timing stays local for caption rendering.
- Cache Claude's selection output keyed by transcript hash so re-runs of later phases (rendering) never re-invoke Claude.
- Use `--output-format json` and read `total_cost_usd`/`num_turns` to log spend per run.
- Pick the cheapest model that's adequate for selection (Sonnet, not Opus) to preserve the weekly Sonnet-vs-all-models split.

**Warning signs:**
"Approaching usage limit" notices appearing during normal coding; clip jobs failing late in the day; one long video consuming a noticeable chunk of the 5-hour window.

**Phase to address:** P2 (Clip Selection)

---

### Pitfall 2: Transcript exceeds context / gets silently truncated → Claude picks from only the first half

**What goes wrong:**
A long video's full word-level transcript is large. If you paste it raw into `claude -p`, you risk truncation or degraded "lost-in-the-middle" attention — Claude returns clips clustered in the opening minutes and ignores the back half. It looks like it worked (valid clips returned) but coverage is broken.

**Why it happens:**
Word-level JSON is verbose (each word + start + end). Devs send the densest representation they have instead of the leanest one Claude needs.

**How to avoid:**
- Send a **sentence- or segment-level** transcript with coarse timestamps (`[mm:ss] text`), not word-level. This cuts tokens 5–10x.
- For very long videos, **chunk by time** (e.g. 15-min windows), ask Claude for candidates per chunk, then a second cheap pass to rank/dedupe — but only if a single pass actually overflows; don't pre-build chunking you don't need.
- Tell Claude the total duration and ask it to return candidates **distributed across the whole timeline**; reject output where all picks fall in one quartile.

**Warning signs:**
All suggested clips fall in the first N minutes; clip start times never exceed ~50% of video length.

**Phase to address:** P2 (Clip Selection)

---

### Pitfall 3: Claude returns prose / malformed / hallucinated timestamps instead of usable ranges

**What goes wrong:**
LLMs love to wrap answers in commentary ("Here are some great clips!"), invent timestamps that don't exist in the transcript, return `00:73:00`, or give ranges where end < start. Downstream ffmpeg then cuts garbage or crashes.

**Why it happens:**
No output contract, no validation. Non-determinism means a prompt that worked yesterday returns markdown today.

**How to avoid:**
- Demand **strict JSON** (an array of `{start_s, end_s, reason}` in **seconds as floats**, not `mm:ss` strings — avoids parse ambiguity). Provide a one-shot example in the prompt.
- Parse with `--output-format json` then `JSON.parse` the `result`; on parse failure, do **one** repair retry, then fail loudly.
- **Validate every range against reality**: `0 <= start < end <= video_duration`, end-start within allowed clip length, start/end snap to the nearest transcript word boundary (Claude's seconds are approximate — re-anchor to the transcript's actual word times). Drop any clip that fails.
- Keep `--max-turns 1` / disable tools for the selection call — you want a pure text completion, not an agent that wanders.

**Warning signs:**
JSON.parse throws intermittently; timestamps with no matching transcript word; clips longer than the source or with negative duration.

**Phase to address:** P2 (Clip Selection)

---

### Pitfall 4: Mid-sentence cuts — clips start/end on a half-spoken word

**What goes wrong:**
The single most common "this feels amateur" failure. Claude (or a naive splitter) picks `start_s=42.0`, but a word is being spoken at 42.0. The clip opens on "...ortant thing is" and dies on "so what we—". Unwatchable for LinkedIn.

**Why it happens:**
Claude reasons over text meaning, not audio boundaries; its second-marks are approximate. ffmpeg cuts exactly where told. The two are never reconciled.

**How to avoid:**
- **Snap every cut to the nearest silence/sentence boundary** using the local word-level timestamps: move `start` back to the start of the sentence it falls in, `end` forward to the end of the last full sentence. Add a small pre-roll (~0.2–0.4s) so the first word isn't clipped.
- Treat Claude's timestamps as *intent*, the transcript word times as *ground truth*.
- Prefer ending on punctuation (`.`, `!`, `?`) where the transcript has it.

**Warning signs:**
First/last word of a clip is cut off on playback; audible glottal clip at the start; reviewer keeps rejecting clips for "starts weird."

**Phase to address:** P2→P3 boundary (snapping logic sits between selection and rendering)

---

### Pitfall 5: 9:16 center-crop slices the speaker out of frame

**What goes wrong:**
`crop=ih*9/16:ih` takes the **center** column of a 16:9 frame. If the speaker stands on the left third (common in webinars/talks with slides on the right), the vertical crop captures the empty slide area and decapitates the speaker. The 1:1 crop has the same problem, milder.

**Why it happens:**
Static center-crop is the copy-paste ffmpeg recipe everywhere. It assumes the subject is dead-center; real talks rarely are.

**How to avoid:**
- For v1 (yolo): make the **crop x-offset a per-video parameter** the user can nudge in the UI (left/center/right), with center as default. One slider beats a face-tracking pipeline you don't have time to build. `# ponytail: manual crop offset; add face-detect auto-reframe only if manual proves annoying`.
- Render a quick thumbnail/preview of the crop region **before** committing the full re-encode so the user sees decapitation early.
- Defer auto-reframing (face/active-speaker detection, e.g. what video-use *might* offer) to post-v1 — verify those repos can even do it before depending on them (PROJECT.md flags both as unverified).

**Warning signs:**
Speaker's head cropped at the eyes/missing; vertical clip shows mostly slide/background; reviewer rejects for framing.

**Phase to address:** P3 (Rendering)

---

### Pitfall 6: ffmpeg input-seek (`-ss` before `-i`) produces black/garbled first frames and early starts

**What goes wrong:**
The fast recipe `ffmpeg -ss 42 -i in.mp4 -t 15 -c copy out.mp4` snaps to the nearest **keyframe** before 42s, so the clip starts seconds early, AND with `-c copy` from a non-keyframe the opening frames reference data outside the clip → black screen or smeared garbage for the first 1–2 seconds.

**Why it happens:**
`-c copy` + input seeking is the "fast trim" recipe people find first. It's correct for keyframe-aligned lossless trims, wrong for arbitrary frame-accurate clips.

**How to avoid:**
- This app **must re-encode anyway** (cropping + caption burn-in make `-c copy` impossible), so use **output seeking with re-encode**: `ffmpeg -ss <start> -i in.mp4 -t <dur> -vf "crop=...,subtitles=...,scale=..." -c:v libx264 -c:a aac out.mp4` (or `-ss` after `-i`). Frame-accurate, no black frames.
- Combine crop + subtitles + scale in **one filtergraph, one encode pass** — don't write an intermediate file per step (3 aspect ratios × N clips × multiple passes = a disk and time blowup).

**Warning signs:**
Black or smeared opening frames; clip starts noticeably before the chosen moment; audio/video desync at clip head.

**Phase to address:** P3 (Rendering)

---

### Pitfall 7: Burned-in captions are illegible or mispositioned

**What goes wrong:**
Captions are the whole point (LinkedIn autoplays muted), yet defaults produce thin white text that vanishes over light backgrounds, sits behind the phone UI safe-area, runs off the edge in 9:16, or flashes one word at a time too fast to read.

**Why it happens:**
ffmpeg's default subtitle styling is tiny and unstyled. ASS `force_style` is fiddly, and word-level (`-ml 1`) captions burn one word per line by default — strobing.

**How to avoid:**
- Use **ASS with `force_style`**: bold, large font, white text + black outline/box (`BorderStyle=3`, `Outline`, `Shadow`), high `MarginV` so text sits in the lower-middle, **inside the 9:16 safe area** (keep ~10–15% margin from top/bottom for LinkedIn UI).
- Group captions into **short phrases (2–5 words)**, not one word at a time — derive phrase grouping from the word timestamps; `-ml 1` alone gives a strobe effect.
- Re-generate caption styling **per aspect ratio** (font size and wrap differ between 9:16, 1:1, 16:9). The same .ass won't look right in all three.
- Eyeball one rendered clip per ratio before declaring captions "done."

**Warning signs:**
Text unreadable over bright frames; captions clipped at frame edge; one-word strobe; captions overlapping LinkedIn's bottom UI in the feed.

**Phase to address:** P3 (Rendering)

---

### Pitfall 8: Whisper hallucinates on silence and word timestamps drift

**What goes wrong:**
Whisper invents text ("Thanks for watching", "[music]") during silent/low-speech stretches and can loop on silence. Separately, even correct words carry DTW timestamp drift of ~100–400ms. Both feed bad data downstream: phantom captions, and cuts that land slightly off the word.

**Why it happens:**
Known Whisper training-data artifact; word timing comes from cross-attention alignment, which is inherently approximate and model-dependent.

**How to avoid:**
- Run **VAD** (whisper.cpp supports a VAD model) or trim long silences before/within transcription to suppress hallucinations.
- Don't trust word times to the millisecond — when snapping cuts (Pitfall 4), add small pre/post padding to absorb drift.
- Sanity-check transcript: flag segments with repeated identical phrases or text during near-zero audio energy.
- Choose model deliberately: `small`/`medium` are usually the sweet spot for talks on a Mac; `tiny`/`base` drift and mis-transcribe more; `large` is slow. Use Core ML/Metal on macOS for speed.

**Warning signs:**
"Thank you for watching" / "[Music]" in a talk transcript; repeated lines; captions appearing during silence; cuts consistently a few hundred ms off.

**Phase to address:** P1 (Transcription)

---

### Pitfall 9: Long-running local jobs with no progress, no recovery → looks frozen, loses work on crash

**What goes wrong:**
Transcribing 60 min + Claude call + re-encoding 3 ratios × several clips is minutes of work. With a naive "click upload, wait" UI, the user can't tell if it's working or hung, a crash mid-render loses everything, and re-running redoes transcription (the expensive part) from scratch.

**Why it happens:**
Solo yolo builds wire the whole pipeline as one synchronous request. No staging, no progress, no idempotency.

**How to avoid:**
- **Stage the pipeline with persisted intermediate artifacts**: save transcript JSON, then Claude's selection JSON, then per-clip render status — each to local disk keyed by video hash. A crash resumes from the last completed stage; never re-transcribe needlessly.
- Stream **progress** to the UI: at minimum per-stage status (transcribing / selecting / rendering clip 2 of 6). whisper.cpp and ffmpeg both emit progress to stderr — parse and forward it.
- Render clips **incrementally and show partial results** — let the user review/download finished clips while others render.
- Make each render idempotent: if `clip_3_9x16.mp4` exists, skip it.

**Warning signs:**
UI spinner with no detail for minutes; killing the app loses all progress; re-uploading the same video re-runs transcription.

**Phase to address:** P4 (UI + Jobs/Storage); staged-artifact design touches P1–P3

---

### Pitfall 10: Boring / wrong-length clip picks (quality of selection, not mechanics)

**What goes wrong:**
The pipeline runs flawlessly and produces clips nobody would post — generic intros, throat-clearing, a 90s ramble with no hook, or 8s fragments with no payoff. Mechanically "done," substantively useless.

**Why it happens:**
The selection prompt asks for "good clips" without defining what makes a LinkedIn clip work, and without length constraints tied to the platform.

**How to avoid:**
- Engineer the selection prompt with **explicit criteria**: self-contained idea, a hook in the first ~3s, a payoff/insight, no unresolved references ("as I said earlier"), strong standalone open and close. Give 1–2 examples of good vs bad.
- Constrain **length to 15–90s** (per PROJECT.md) and ask Claude to justify each pick (`reason` field) so you can audit selection quality.
- Always keep a **human-in-the-loop review step** (it's already a requirement) — v1 success is "Claude surfaces good candidates," not "Claude auto-posts." Over-rejection by the reviewer is your signal to tune the prompt.
- Ask for **more candidates than needed** (e.g. 8) and let the user pick — cheap insurance against a few weak picks.

**Warning signs:**
Reviewer rejects most suggestions; clips lack a hook; clips reference off-screen context; clip lengths cluster at the min/max bound.

**Phase to address:** P2 (Clip Selection) — prompt engineering; verified at P4 review UI

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Static center-crop for 9:16, no reframing | Ships in one ffmpeg line | Decapitates off-center speakers | v1 — but expose a manual x-offset slider |
| Single synchronous pipeline, no staging | Simplest to wire | Crash = total loss; re-transcribes every run | Never for transcription stage; OK to defer fancy job queue |
| One Claude call, no output validation | Less code | Garbage timestamps crash ffmpeg | Never — validation is cheap and mandatory |
| Word-by-word (`-ml 1`) captions burned as-is | Direct from whisper | Strobing, unreadable | Never ship; group into phrases |
| Skip VAD on transcription | Fewer moving parts | Hallucinated captions during silence | OK for clean studio audio; risky for webinars |
| Re-render all 3 ratios on every run | Simple | Wasted minutes/CPU | Never — make renders idempotent (skip existing files) |
| Send full word-level transcript to Claude | No preprocessing | Token blowup, lost-in-middle, limit burn | Never — downsample to sentence level |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Claude Code headless | Assuming separate/free automation credits | Same shared subscription pool (June 2026); meter every call, one call per video |
| Claude Code headless | Parsing free-text output | `--output-format json`, parse `result`, validate strictly, one repair retry |
| Claude Code headless | Letting it run as an agent w/ tools | `--max-turns 1`, tools off — it's a pure completion for selection |
| whisper.cpp | Trusting word times to the ms for cuts | Treat as ~±300ms; snap to sentence + pad |
| whisper.cpp (macOS) | CPU-only build | Build with Metal/Core ML for usable speed on long video |
| ffmpeg | `-c copy` + input seek for arbitrary cuts | Re-encode + output seek (required anyway for crop/captions) |
| ffmpeg | Crop, then re-open to add subs, then re-open to scale | One filtergraph, one encode pass |
| video-use / hyperframes | Depending on them before verifying they edit video | PROJECT.md flags both UNVERIFIED — confirm role before the roadmap locks; ffmpeg likely does the real work |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-transcribing on every run | Each job takes minutes longer than needed | Cache transcript by video hash | Immediately, on the 2nd run of any video |
| Multi-pass per-clip encoding (separate crop/sub/scale files) | Disk fills, jobs crawl | Single filtergraph per output | Noticeable at ~5+ clips × 3 ratios |
| Claude call per clip / per retry loop | Subscription limit hits mid-day | One selection call per video, cached | Within a few videos in a session |
| Full word-level transcript to Claude | Slow, truncated, expensive | Sentence-level downsample | On any video > ~20–30 min |
| Encoding 3 ratios sequentially for many clips | Long total wall-clock | Parallelize ffmpeg across CPU cores; show partial results | Long videos with many clips |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Localhost UI binds 0.0.0.0 | Source video/transcripts exposed on LAN — breaks the "nothing leaves the machine" core value | Bind 127.0.0.1 only |
| Passing user file paths straight to ffmpeg shell string | Command injection / path traversal via crafted filename | Pass args as array (no shell), validate/normalize paths |
| Logging Claude prompt+transcript to a shared/cloud-synced dir | Private talk content leaks off-machine | Keep all artifacts in a local, non-synced project dir |
| Trusting Claude output as a file path / command | A hallucinated field used unchecked | Only consume validated numeric ranges + reason text; never eval its output |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Spinner with no stage/progress | Can't tell hung from working; kills the job | Per-stage progress (transcribe/select/render i of N) |
| No preview before full render | Discovers bad crop/captions after minutes of encode | Cheap thumbnail/preview of crop + caption per ratio first |
| Auto-pick clips, no review | Posts weak clips; erodes trust | Human-in-the-loop review (already required) — surface 6–8 candidates |
| All-or-nothing output | Waits for last clip to use the first | Stream finished clips into the review grid as they render |
| One blob of all ratios | Hard to grab the one needed | Per-clip, per-ratio download, labeled |

## "Looks Done But Isn't" Checklist

- [ ] **Clip selection:** Validate timestamps are real (within duration, end>start, snapped to words) — not just that JSON parsed
- [ ] **Cuts:** Play first/last second of each clip — verify no mid-word start/end and no black/garbled opening frame
- [ ] **9:16 crop:** Confirm the speaker (not the slide/background) is in frame on an off-center source
- [ ] **Captions:** Check legibility over a bright frame and that text clears the LinkedIn safe-area in 9:16
- [ ] **Captions:** Confirm phrase grouping, not one-word strobe
- [ ] **Transcript:** Scan for silence hallucinations ("Thanks for watching", repeated lines)
- [ ] **Jobs:** Kill the app mid-render — confirm it resumes from last stage, doesn't re-transcribe
- [ ] **Usage:** Confirm a full video run's Claude spend is logged and acceptable against subscription limits
- [ ] **Privacy:** Confirm server binds 127.0.0.1 and no artifacts land in a cloud-synced folder

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Subscription limit exhausted mid-day | LOW | Cache selection output; wait for 5-hr window reset; downsample transcript to reduce future spend |
| Malformed Claude output | LOW | One JSON-repair retry, then surface raw output to user; tighten prompt + add example |
| Mid-sentence cuts shipped | LOW | Add sentence-snapping + padding; re-render from cached selection (no new Claude call) |
| Speaker cropped out in 9:16 | MEDIUM | Add manual x-offset; re-render affected ratios from cached selection |
| Illegible captions | LOW | Adjust ASS force_style; re-render (cached transcript+selection) |
| Crash lost all work | HIGH (if no staging) / LOW (if staged) | Implement staged artifacts early so recovery is free |
| Transcript hallucinations | MEDIUM | Add VAD, re-transcribe (expensive); filter known artifact phrases as a stopgap |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Subscription limit burn | P2 | One Claude call/video; spend logged from JSON output |
| 2 Context overflow / front-loaded picks | P2 | Picks distributed across full timeline; sentence-level input |
| 3 Malformed/hallucinated timestamps | P2 | Strict JSON + validation rejects bad ranges in tests |
| 4 Mid-sentence cuts | P2→P3 | Manual playback: clean word boundaries on sample clips |
| 5 Speaker cropped out | P3 | Off-center source test clip keeps speaker in 9:16 frame |
| 6 Black/garbled cut frames | P3 | First-second playback shows clean frame, accurate start |
| 7 Caption legibility | P3 | Legibility check over bright frame + safe-area, per ratio |
| 8 Whisper hallucination/drift | P1 | Silence test clip yields no phantom captions; timing within tolerance |
| 9 Long-job UX / crash recovery | P4 (design touches P1–P3) | Kill-and-resume test skips completed stages |
| 10 Boring/wrong-length picks | P2 (verified P4) | Reviewer acceptance rate on real video; lengths within 15–90s |

## Sources

- [Run Claude Code programmatically — Claude Code Docs](https://code.claude.com/docs/en/headless) — HIGH
- [Use Claude Code with your Pro or Max plan — Claude Help Center](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan) — MEDIUM
- [Use the Claude Agent SDK with your Claude plan — Claude Help Center](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) — MEDIUM
- [Anthropic splits billing again: Agent SDK gets separate credit pools — The New Stack](https://thenewstack.io/anthropic-agent-sdk-credits/) and [Claude Agent SDK separate credit pool (paused) — Start Debugging](https://startdebugging.net/2026/06/claude-agent-sdk-separate-credit-pool-june-15/) — MEDIUM (June 2026 pause confirmed)
- [whisper.cpp — GitHub (ggml-org)](https://github.com/ggml-org/whisper.cpp) and [CrisperWhisper: Accurate Timestamps (arXiv 2408.16589)](https://arxiv.org/html/2408.16589v1) — HIGH (word timing, DTW drift, silence hallucination)
- [FFmpeg -ss input vs output seeking — DEV / lossless-cut PR #13](https://github.com/mifi/lossless-cut/pull/13) and [How to extract clips with ffmpeg — Mux](https://www.mux.com/articles/clip-sections-of-a-video-with-ffmpeg) — HIGH (keyframe/black-frame cut accuracy)
- [Crop 16:9 to 9:16 with ffmpeg — vgmoose.dev](https://vgmoose.dev/blog/how-to-crop-landscape-169-videos-to-vertical-916-using-ffmpeg-for-youtube-shorts-or-tiktok-6898118583/) — HIGH (center-crop pitfall)
- Personal/expert knowledge: ffmpeg ASS force_style, single-filtergraph encoding, staged-artifact job design — HIGH

---
*Pitfalls research for: local-first AI video clipper (whisper.cpp + ffmpeg + headless Claude)*
*Researched: 2026-06-29*
