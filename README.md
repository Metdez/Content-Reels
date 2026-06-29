# 🎬 Content Machine

Local-first LinkedIn video clipper. Drop in a long video (talk, webinar, podcast) →
it transcribes locally, Claude picks the best clip-worthy moments, and each is cut
into **9:16, 1:1, and 16:9** with captions. Nothing leaves your machine; clip
selection runs on your **Claude Code subscription** (no API key, no per-token cost).

Built on macOS / Apple Silicon.

```
upload ─▶ transcribe (whisper.cpp) ─▶ select (claude -p) ─▶ render (ffmpeg) ─▶ review & download
                                  all local · data/<job_id>/
```

## Quick start

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

## Layout

```
content_machine/   config, jobs, transcribe, select, render, captions, app (FastAPI), cli
  templates/       index.html, job.html
scripts/setup.sh   one-shot local setup
tests/             pytest (27 tests, no network)
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
- **hyperframes captions** are wired (`--captions hyperframes`) but need a properly
  scaffolded composition to fully animate; the default overlay captions are the reliable path.
- **Reframe** is center-crop + manual x-offset. Speaker-tracking auto-reframe and
  word-level karaoke captions are deferred (see `.planning/REQUIREMENTS.md` v2).

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
make test        # or ./.venv/bin/pytest -q
```

Built with GSD. See `.planning/` for the roadmap, research, and per-phase plans/summaries.
