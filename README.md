# 🎬 Content Machine

Local-first LinkedIn video clipper. Drop in a long video (talk, webinar, podcast) →
it transcribes locally, Claude picks the best clip-worthy moments, and each is cut
into **9:16, 1:1, and 16:9** with captions. Nothing leaves your machine; clip
selection runs on your **Claude Code subscription** (no API key, no per-token cost).

Runs on **macOS / Apple Silicon** and **Windows 11**.

```
upload ─▶ preview & frame each ratio (zoom/pan) ─▶ transcribe ─▶ select (claude -p) ─▶ render (ffmpeg)
   ─▶ live master + per-stage progress ─▶ review ─▶ edit clip (trim · reframe · captions · audio) ─▶ download
                                              all local · data/<job_id>/
```

**Per-aspect framing** — set an independent zoom + x/y pan for 9:16, 1:1, and 16:9,
previewed live (WYSIWYG, no render) before the run and editable per clip after.
**Clip editor** (`/job/<id>/clip/<n>/edit`) — trim with snap-to-sentence, reframe
per ratio, edit caption text/timing, mute/adjust audio; saved non-destructively to
`edit.json` and re-rendered per aspect (only changed ratios re-encode).
**Honest progress** — a weighted master bar plus per-stage bars (live whisper %
and per-clip render counts); clips appear in the grid as each finishes.
**GPU-accelerated, never fragile** — rendering uses your GPU's hardware H.264
encoder (NVENC on Windows, VideoToolbox on Mac) when it's usable, and silently
falls back to CPU `libx264` if it isn't — so it's faster where it can be and
**never breaks**. See [Hardware acceleration](#-hardware-acceleration).

## Quick start

### Windows (no package manager needed)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # vendors static ffmpeg + prebuilt whisper.cpp + model + venv
.venv\Scripts\python.exe -m content_machine.cli serve        # http://127.0.0.1:8000
```

`setup.ps1` downloads a **pinned, NVENC-capable ffmpeg 7.1** build and the prebuilt
`whisper-blas-bin-x64` release into `vendor/` (gitignored) — no Homebrew, cmake, or
compiler required. (ffmpeg is pinned to 7.1 because bleeding-edge builds need NVIDIA
driver ≥610 for NVENC; 7.1's NVENC works on current drivers. If NVENC can't init, the
app just uses CPU x264.) Needs **Claude Code logged in** (`claude login`) for selection.

### macOS / Apple Silicon

```bash
bash scripts/setup.sh          # ffmpeg + cmake, build whisper.cpp (Metal), model, venv
source .venv/bin/activate

# CLI
content-machine ingest path/to/talk.mp4      # -> transcript
content-machine select <job_id>              # -> clips.json (via claude -p)
content-machine render <job_id>              # -> 9:16 / 1:1 / 16:9 + captions

# or the web UI (upload → review → download)
content-machine serve                        # http://127.0.0.1:8000
```

Prereqs: macOS, Homebrew, Python ≥3.11, and **Claude Code logged in** (`claude login`) —
the selection step shells out to `claude -p` using your subscription.

## How it works

| Stage | Tool | Output |
|-------|------|--------|
| Transcribe | **whisper.cpp** (Metal), 16kHz mono via ffmpeg; silence-VAD drops hallucinations | `data/<job>/transcript.json` |
| Select | **`claude -p`** (subscription, non-bare) returns segment-index ranges → clips snap to sentence boundaries; cached by transcript hash | `data/<job>/clips.json` |
| Render | **ffmpeg** cut (accurate re-encode) + center-crop reframe (+x-offset) + captions | `data/<job>/clips/clipNN/{9x16,1x1,16x9}.mp4` |
| Captions | Pillow PNG strips composited via ffmpeg `overlay` (default); **hyperframes** animated overlay optional | burned into clips |
| Storage / library | filesystem: `data/<job_id>/` + `job.json` manifest | browsable in the UI |

Everything is staged and cached: re-running reuses the transcript/selection and only
re-renders, and a crash resumes from the last completed stage.

## ⚡ Hardware acceleration

The render's H.264 **encode** is offloaded to your GPU when possible; decode and the
crop/scale/caption filters stay on the CPU (mixing GPU decode with CPU filters is
fragile, so we don't). At startup the app **probes** the GPU encoder once and caches
the verdict; if it can't init, or fails mid-encode, it transparently re-runs that
encode on `libx264` — **an output is never missing or corrupt.** So this is purely
additive: faster where the GPU helps, identical to before where it doesn't.

| Platform | Encoder | Transcribe |
|----------|---------|-----------|
| **Windows** (NVIDIA) | `h264_nvenc` (NVENC) — needs the pinned ffmpeg 7.1 | CPU whisper (BLAS) — fast (~9× realtime) |
| **macOS** (Apple Silicon) | `h264_videotoolbox` | whisper.cpp **Metal** (GPU) |
| no usable GPU | `libx264` (CPU) | CPU whisper |

Measured numbers and the reasoning behind these choices (including why Windows GPU
*transcription* is intentionally **not** used on Blackwell GPUs) are in
[`BENCHMARKS.md`](BENCHMARKS.md). Run your own:

```
python scripts/benchmark.py EnlayeParis.mp4 --seconds 30
```

Force CPU encoding (A/B test, or if you suspect a GPU issue): set `CM_FORCE_CPU=1`.

## Layout

```
content_machine/   config, jobs, transcribe, select, render, captions, app (FastAPI), cli
  templates/       index.html, job.html
scripts/setup.{sh,ps1}  one-shot local setup (macOS / Windows)
content_machine/hwaccel.py  GPU encoder probe + profile + CPU fallback
scripts/benchmark.py    GPU-vs-CPU render benchmark + ffprobe validation
tests/             pytest (55 tests, no network)
vendor/whisper.cpp built locally by setup.sh (gitignored)
data/              your videos, transcripts, clips (gitignored, local-only)
.planning/         GSD planning + research + per-phase plans/summaries
```

## Known constraints & decisions

- **Subscription headless (`claude -p`)** is the only selection path by design. It draws
  from your normal 5-hour/weekly Claude limits and Anthropic's consumer terms restrict
  scripted access — accepted risk, mitigated by caching one call per transcript. To switch
  to an API key later, the selection call is isolated in `select.run_claude`.
- **This Mac's Homebrew ffmpeg is a stripped build** (no libass/drawtext) — so captions
  are rendered as PNG overlays, not burned text. Works with any ffmpeg.
- **Word-level karaoke captions** ship as the `karaoke` caption mode (word-by-word
  highlight driven by whisper's per-word timings) via the PNG-overlay pipeline — works
  with any ffmpeg. The richer **hyperframes** animated path is wired + gated behind the
  same mode but needs Node ≥22 + a headless Chrome; on any machine without them (or any
  failure) it falls back automatically to PNG-karaoke. Note: PNG-karaoke composites one
  overlay per word, so it's slower to encode on long/wordy clips — it's opt-in; the default
  `overlay` (per-phrase) captions are fast.
- **Reframe** is a manual per-aspect transform — independent zoom + x/y pan for
  each ratio, set live before the run and per clip in the editor (no CV needed). The editor
  trim snaps to **word boundaries** from whisper's word timings. Speaker-tracking
  auto-reframe is still deferred (needs CV; see `.planning/REQUIREMENTS.md`).
- **`DeepAgentLLMtxt.md`** (referenced from CLAUDE.md) is currently empty (0 bytes) — left
  in place; nothing actionable until content is added.

## Logs

Every run is logged to the codebase so nothing is a black box:

- `logs/content_machine.log` — rotating app-wide log (all jobs, requests, errors).
- `logs/jobs/<job_id>.log` — one file per job; the **job page shows this live** under
  "📜 Live log" so you can watch transcribe → select → render progress and see the
  exact error if a stage fails.

```bash
tail -f logs/content_machine.log        # follow everything
tail -f logs/jobs/<job_id>.log          # follow one job
```

## Tests

```bash
make test                              # unit + HTTP (pytest, with coverage)
make lint                              # ruff
pytest -m "e2e and not slow"           # Playwright UI E2E (needs: pip install pytest-playwright; playwright install chromium)
make e2e-seed                          # seed a real fixture job for manual/Playwright QA
```

- **~211 unit/HTTP tests** (pytest, ~92% line coverage) + **34 Playwright UI E2E specs** +
  a JS↔Python crop-math parity test (Node) + a real-ffmpeg render E2E.
- CI (`.github/workflows/test.yml`) runs ruff + the unit suite, and a separate job for the
  Playwright E2E suite.

Built with GSD. See `.planning/` for the roadmap, research, and per-phase plans/summaries
(milestone **v6 — Full Quality Pass** hardened reliability, added the test suites + CI,
the accessibility pass, word-snapping, and karaoke captions).
