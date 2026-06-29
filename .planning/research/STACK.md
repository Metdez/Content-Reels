# Stack Research

**Domain:** Local-first AI video-clipping desktop/web tool (long video → short captioned LinkedIn clips) on macOS
**Researched:** 2026-06-29
**Confidence:** HIGH on the technical stack (whisper.cpp + ffmpeg are unambiguous); MEDIUM-LOW on the "headless Claude via subscription" constraint (real ToS risk — see below).

---

## TL;DR for the roadmap

- **Transcription:** whisper.cpp — confirmed FIT. Keep it.
- **Cutting / cropping / reframing / caption burn-in:** **ffmpeg is the real engine.** Build directly on it. The user's two suspect repos do not do this job.
- **video-use:** PARTIAL-FIT. It is genuinely a transcript-driven AI video editor (much closer to this project than "video understanding for agents"), but it transcribes via **ElevenLabs cloud** (breaks local-first) and targets a single long-form `final.mp4`, not multi-aspect short clips. Use it as a **design reference**, not a dependency.
- **hyperframes:** WRONG-FIT for the core editing job. It is an HTML/CSS→MP4 motion-graphics renderer. Optional, later, only if you want fancy animated caption overlays. Not needed for v1.
- **Headless Claude via the Claude Code subscription:** technically works (`claude -p`), **but Anthropic's Consumer Terms prohibit scripted/automated access except via an API key.** This constraint carries account-ban risk and should be renegotiated with the user before the roadmap locks. See the dedicated section.

---

## CRITICAL: Repo verification verdicts

### 1. `ggml-org/whisper.cpp` — VERDICT: ✅ FITS

**What it actually is (verified from repo):** C/C++ port of OpenAI Whisper for efficient local inference. **v1.9.1** (stable, June 2026).

| Role assumption | Reality | Verdict |
|---|---|---|
| Local transcription | Exactly that. Runs fully offline. | ✅ |
| macOS build | CMake; Apple Silicon path via ARM NEON, Accelerate, **Metal** (GPU), and **Core ML** (`-DWHISPER_COREML=1` → Apple Neural Engine, >3x faster than CPU). | ✅ |
| Bindings | CLI (`whisper-cli`) is primary. Official bindings include Python, JS/React Native, Go, Rust, Ruby, Swift/Obj-C, .NET, Java. | ✅ |
| Timestamps for captions | Segment timestamps + **word-level timestamps** (`-ml 1` / max-line control), SRT/VTT output. Sufficient to drive both clip-selection timing and caption burn-in. | ✅ |

**Recommendation:** Use the **CLI** (`whisper-cli`), shelled out from your app, with the `large-v3-turbo` or `medium` model + Core ML encoder. Do not bother with a language binding for v1 — the CLI emits SRT/VTT/JSON directly, which is all you need. (Lazy path: one subprocess call, parse the JSON.)

---

### 2. `browser-use/video-use` — VERDICT: ⚠️ PARTIAL-FIT (use as reference, not dependency)

**The user's suspicion was wrong in an interesting way.** It is NOT generic "video understanding for agents." It is a **CLI tool that lets an AI agent (Claude Code, Codex, etc.) edit video by reading transcripts instead of watching frames** — which is *architecturally almost exactly this project*.

**What it actually does (verified from README):**
- Drop raw footage in a folder → chat with Claude Code → get `final.mp4` back.
- Transcribes audio to **word-level timestamps**, the agent reads the transcript ("12KB text + a handful of PNGs," not frame-dumping), produces an **edit decision list (EDL)**, then renders via ffmpeg.
- Capabilities: filler-word/dead-space removal, color grading, audio fades, **subtitle burn-in**, animation overlays (via HyperFrames / Remotion / Manim / PIL). Python (`uv sync` / `pip install -e .`). Depends on **ffmpeg** (required) + yt-dlp (optional).

**Why it's only PARTIAL-FIT:**
| Gap | Detail | Impact |
|---|---|---|
| Cloud transcription | Uses **ElevenLabs Scribe** (cloud API key). | ❌ Breaks the local-first core value. whisper.cpp is the replacement. |
| Wrong output shape | Targets one cleaned-up long-form `final.mp4`. | This project wants *several short 15–90s clips in 3 aspect ratios*. Different goal. |
| No multi-aspect reframing | No documented 9:16 / 1:1 / 16:9 cropping or reframing. | The defining feature here is missing. |
| Heavier model | Full agent-driven editing pipeline. | More than v1 needs. |

**Recommendation:** Do **not** adopt as a runtime dependency. **Mine it for design patterns** — specifically its transcript-as-EDL approach (give Claude word-level transcript text, get back a structured list of {start, end, reason}). That is precisely the clip-selection contract this project needs. Reimplementing that contract yourself is ~50 lines and avoids inheriting its cloud-transcription and long-form assumptions.

---

### 3. `heygen-com/hyperframes` — VERDICT: ❌ WRONG-FIT for core editing (optional, later, for animated captions only)

**What it actually is (verified from README):** "An open-source framework for turning HTML, CSS, media, and seekable animations into deterministic MP4 videos." Inputs: HTML files with `data-start`/`data-duration` timing attrs, GSAP/Lottie/Three.js/CSS/WebGL animations. Outputs: deterministic MP4s and **transparent overlay videos** (motion graphics). Use cases: AI-agent-authored motion graphics, animated charts, social-clip *graphics*.

**Why WRONG-FIT for this project's stated role:** It does not cut, it does not crop, it does not reframe a source video, and it does not do speech-driven editing. It *generates* motion-graphic video from HTML — the opposite direction from "slice an existing recording." Using it to cut/crop a webinar would be like using a chart library to trim an MP4.

**The only legit role:** If, in a *later* milestone, you want fancier captions than ffmpeg's `ass` burn-in (e.g. animated word-by-word "karaoke" captions, kinetic typography, branded lower-thirds), HyperFrames can render those as **transparent overlay MP4s** that you then composite over the cropped clip with ffmpeg. That is a polish feature, not v1.

**Correct tool for the role the user assumed (cutting/cropping/reframing/caption burn-in): ffmpeg.** See below.

---

### 4. Headless Claude via the Claude Code subscription — VERDICT: ⚠️ WORKS BUT TOS-RISKY; renegotiate the constraint

**How it works technically (verified from official docs, code.claude.com/docs/en/headless):**
- `claude -p "<prompt>"` runs the full agent loop non-interactively and exits. Add `--output-format json` (with optional `--json-schema`) to get structured output — ideal for returning a clip list. `--bare` skips auto-discovery for deterministic scripted runs.
- The docs now explicitly frame `claude -p` as **"the Agent SDK via the CLI."** The CLI and the Agent SDK (Python/TS) are the same engine.
- For clip selection you'd call something like:
  ```bash
  whisper-cli -oj audio.wav            # local transcript → JSON
  claude -p "Pick the best 15-90s clips from this transcript" \
    --output-format json \
    --json-schema '{"type":"object","properties":{"clips":{"type":"array","items":{"type":"object","properties":{"start":{"type":"number"},"end":{"type":"number"},"reason":{"type":"string"}}}}}}' \
    < transcript.json | jq '.structured_output.clips'
  ```

**The constraint problem (verified — this is the load-bearing risk):**
- Anthropic's **Consumer Terms** prohibit accessing the service "through automated or non-human means, whether through a bot, script, or otherwise" **except via an Anthropic API Key.** (GitHub issue anthropics/claude-code#36324; users have reported **account bans** for scripted `-p` use on subscriptions.)
- The June 2026 plan to give subscriptions a separate "Agent SDK monthly credit" (so scripted use would be sanctioned) was **paused**. Per Anthropic's support page: *"For now, nothing has changed: Claude Agent SDK, `claude -p`, and third-party app usage still draw from your subscription's usage limits."* So today it draws on the subscription — but the ToS-vs-automation conflict is unresolved and unwarned-in-docs.

**What this means for the project:**
- The "subscription, not metered API key" constraint is **technically satisfiable** today and **will not bill per token** — it draws on subscription usage limits.
- But it sits in a **ToS gray area with real ban precedent** for scripted use. For a single-user local tool invoked interactively-ish (you click a button, one `claude -p` fires), risk is lower than always-on automation — but it is non-zero, and Anthropic's own engineers point to API keys as the sanctioned path.

**Recommendation (prescriptive):**
1. **Build the clip-selection layer behind a one-function seam** (`select_clips(transcript) -> [{start,end,reason}]`) so the backend is swappable.
2. **Default implementation:** `claude -p --output-format json` against the subscription (meets the stated constraint, zero per-token cost).
3. **Flag to the user before roadmap lock:** the ToS risk + ban precedent. Offer the API-key path (Agent SDK with `ANTHROPIC_API_KEY`) as the sanctioned alternative — clip selection on a transcript is a tiny prompt (cents per video), so the "avoid per-token cost" motivation is weak here. The seam makes switching trivial.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|---|---|---|---|
| **whisper.cpp** | v1.9.1 | Local speech-to-text with word-level timestamps | Confirmed FIT. Fully offline, Core ML + Metal accelerated on Apple Silicon, emits SRT/VTT/JSON directly. The standard local Whisper runtime. |
| **ffmpeg** | 7.x (`brew install ffmpeg`, ensure `--enable-libass`) | Cut, crop, reframe to 9:16/1:1/16:9, scale, burn-in captions | The actual editing engine. Every credible local clipping pipeline (incl. video-use) renders through it. Native, scriptable, no per-clip cost. |
| **Claude Code CLI** (`claude -p`) / Agent SDK | latest (2.1.x) | Clip-selection brain — reads transcript, returns structured clip list | Same engine as interactive Claude Code; `--output-format json --json-schema` gives a typed clip list. **See ToS caveat above — wrap behind a seam.** |
| **Node.js + a minimal server (Hono or Express)** OR **Python + FastAPI** | Node 22 LTS / Python 3.12 | Localhost web UI + orchestration (upload → transcribe → select → render → review) | Pick the language you'll subprocess from most comfortably. Both shell out to whisper-cli/ffmpeg/claude the same way. **Recommend Python+FastAPI** if you want to stay close to video-use patterns; **Node+Hono** if you prefer one language for UI+server. |
| **SQLite** | 3.x (built into both runtimes) | Local storage for transcripts, clip metadata, source-video index | Zero-config, single file, perfect for single-user local-first. No server. Files (videos/clips) on disk, metadata in SQLite. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| **fluent-ffmpeg** (Node) or direct `subprocess` (Python) | — | Programmatic ffmpeg invocation | If on Node and you want a wrapper. Honestly, raw `child_process`/`subprocess` with a string command is simpler and avoids a stale dependency — fluent-ffmpeg is loosely maintained. **Prefer raw subprocess.** |
| **yt-dlp** | latest | Optional: pull a source video from a URL | Only if you later want URL ingestion. Out of scope for v1 (local files only). |
| **HyperFrames** | latest | Optional animated/branded caption overlays as transparent MP4s | LATER polish only. Composite over cropped clips via ffmpeg. Not v1. |

### Development Tools

| Tool | Purpose | Notes |
|---|---|---|
| **Homebrew** | Install ffmpeg, cmake | `brew install ffmpeg cmake` — confirm `ffmpeg -filters | grep libass`. |
| **jq** | Parse `claude -p` / whisper JSON in shell | `brew install jq`. Useful for the clip-selection seam. |
| **Core ML model conversion** | Build the whisper Core ML encoder | whisper.cpp ships `generate-coreml-model.sh`; run once per model for ANE acceleration. |

---

## Installation

```bash
# System tools (macOS)
brew install ffmpeg cmake jq
ffmpeg -filters | grep -i libass   # verify subtitle burn-in support

# whisper.cpp (local transcription)
git clone https://github.com/ggml-org/whisper.cpp
cd whisper.cpp
cmake -B build -DWHISPER_COREML=1
cmake --build build -j --config Release
sh ./models/download-ggml-model.sh large-v3-turbo
sh ./models/generate-coreml-model.sh large-v3-turbo   # ANE acceleration

# Claude Code CLI (clip-selection brain) — already installed for this user
claude --version

# App runtime — choose ONE:
# Python path (recommended, closest to video-use patterns):
#   uv init && uv add fastapi uvicorn
# Node path (one language for UI + server):
#   npm install hono @hono/node-server better-sqlite3
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|---|---|---|
| whisper.cpp (CLI) | `faster-whisper` (CTranslate2, Python) | If you're firmly Python and want a clean Python API over CLI parsing. Comparable accuracy; slightly easier integration but no Core ML/ANE path. whisper.cpp wins on Apple Silicon speed. |
| whisper.cpp | OpenAI Whisper API / Deepgram / ElevenLabs Scribe | Never — all cloud, break local-first. (This is video-use's weakness.) |
| ffmpeg (raw subprocess) | video-use as a dependency | Don't. Adopt its *pattern* (transcript→EDL), not the package — it brings cloud transcription and long-form-only output. |
| ffmpeg | MoviePy / Remotion / HyperFrames | MoviePy is a thin, slow ffmpeg wrapper. Remotion/HyperFrames are for *generating* graphics, not slicing recordings. ffmpeg directly is faster and the right primitive. |
| `claude -p` subscription | Agent SDK + `ANTHROPIC_API_KEY` | When you want ToS-sanctioned automation. Cost is trivial for transcript-only prompts (cents/video). **Recommend offering this given the ban risk.** |
| SQLite | Postgres / files-only | Postgres is overkill for single-user local. Files-only (JSON sidecars) works but SQLite gives you "browse clips by source video" queries for free. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|---|---|---|
| **hyperframes for cutting/cropping** | It renders HTML→MP4 motion graphics; it cannot slice or reframe a source recording. | ffmpeg |
| **video-use as a runtime dependency** | Cloud (ElevenLabs) transcription breaks local-first; outputs one long-form file, not multi-aspect short clips. | whisper.cpp + ffmpeg, reusing video-use's transcript→EDL *pattern* |
| **ElevenLabs Scribe / any cloud STT** | Sends audio off the machine — violates the core local-first constraint. | whisper.cpp |
| **fluent-ffmpeg / MoviePy as the core editor** | Wrappers that lag ffmpeg features and add a maintenance dependency for what is a one-line command string. | raw `subprocess`/`child_process` calls to ffmpeg |
| **Metered Anthropic API as the *default*** | Contradicts the stated constraint (though it's the ToS-clean fallback). | `claude -p` behind a swappable seam, with API key as opt-in |
| **A heavy frontend framework (Next.js, etc.)** | Single-user localhost upload→review→download UI doesn't need SSR/routing/build complexity. | Plain HTML + a tiny server (Hono/FastAPI), or Vite + vanilla/React if you want components |

---

## Stack Patterns by Variant

**If you stay Python (recommended for pattern reuse from video-use):**
- FastAPI + Uvicorn server, `subprocess` to whisper-cli/ffmpeg/claude, SQLite via stdlib `sqlite3`.
- Because video-use's transcript→EDL logic is Python and worth reading alongside.

**If you want one language end-to-end:**
- Node 22 + Hono + `better-sqlite3`, `child_process.execFile` for the three external tools, a Vite SPA or plain HTML for the UI.
- Because the UI and orchestration share a language; no Python toolchain.

**If the ToS risk is unacceptable to the user:**
- Swap the clip-selection seam to Agent SDK + `ANTHROPIC_API_KEY`. Everything else unchanged. Cost ≈ cents/video.

---

## The actual editing pipeline (ffmpeg, since this is the real engine)

For each selected clip `{start, end}`, render 3 aspect ratios with burned-in captions:

```bash
# 9:16 vertical (center-crop from 16:9 source, then scale)
ffmpeg -ss $START -to $END -i source.mp4 \
  -vf "crop=ih*9/16:ih,scale=1080:1920,subtitles=clip.ass" \
  -c:a aac clip_9x16.mp4

# 1:1 square
ffmpeg -ss $START -to $END -i source.mp4 \
  -vf "crop=ih:ih,scale=1080:1080,subtitles=clip.ass" clip_1x1.mp4

# 16:9 (no crop, just trim + captions)
ffmpeg -ss $START -to $END -i source.mp4 \
  -vf "scale=1920:1080,subtitles=clip.ass" clip_16x9.mp4
```

Generate per-clip `.ass`/`.srt` from the whisper word-level timestamps (offset to the clip start). Use `force_style` / ASS `BorderStyle=3` for readable captions on any background. **Note (ponytail):** center-crop is the naive reframe — it works for centered single-speaker talks but will clip off-center subjects. Speaker-tracking auto-reframe (detect face, pan the crop) is a real feature ffmpeg doesn't do natively; flag as a later enhancement (would need OpenCV/face-detection feeding dynamic `crop` x-offsets). For v1, center-crop is the lazy-correct default.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|---|---|---|
| whisper.cpp v1.9.1 | macOS Apple Silicon | Core ML requires Xcode CLT; `-DWHISPER_COREML=1` at build. |
| ffmpeg 7.x | libass | Must be built `--enable-libass` (Homebrew default) for `subtitles=`/`ass=` burn-in. |
| `claude -p --json-schema` | Claude Code ≥ v2.1.x | `--bare` becoming default for `-p` in a future release; pin behavior with explicit flags. |

---

## Sources

- github.com/ggml-org/whisper.cpp (README, v1.9.1) — Core ML/Metal build, bindings, word-level timestamps — **HIGH**
- github.com/browser-use/video-use (README) — actual purpose (transcript-driven AI editor), ElevenLabs cloud STT, ffmpeg dependency, Python — **HIGH**
- github.com/heygen-com/hyperframes (README) — HTML→MP4 motion-graphics renderer, transparent overlays — **HIGH**
- code.claude.com/docs/en/headless (official) — `claude -p`, `--output-format json`, `--json-schema`, `--bare`, "Agent SDK via CLI" — **HIGH**
- support.claude.com/en/articles/15036540 (official) — Agent SDK/`claude -p` draws on subscription limits; June 2026 credit plan paused — **HIGH**
- github.com/anthropics/claude-code#36324 — Consumer Terms prohibit scripted access except via API key; ban precedent for subscription `-p` automation — **MEDIUM** (community-reported bans; ToS quote verified)
- ffmpeg crop/scale/subtitles recipes (multiple) — 9:16 crop `crop=ih*9/16:ih`, libass burn-in, `force_style` — **HIGH**

---
*Stack research for: local-first AI video-clipping tool on macOS*
*Researched: 2026-06-29*
