# Architecture Research

**Domain:** Local-first AI media pipeline (long video → short captioned clips), macOS, single user
**Researched:** 2026-06-29
**Confidence:** HIGH (pipeline shape, Claude invocation, ffmpeg role), MEDIUM (third-party repo fit)

## Headline Findings (read first)

1. **This is a linear batch pipeline, not a distributed system.** Single user, single machine, one video at a time. The "architecture" is a job queue of stages, not microservices. Do not build for scale that will never exist.

2. **The Claude subscription constraint dictates one specific invocation mode.** `claude -p --bare` *requires* `ANTHROPIC_API_KEY` (it skips the keychain). To use the **subscription** (the hard constraint from PROJECT.md), you must call **default, non-bare** `claude -p`, which reads the OAuth credentials written by `claude login`. This is the single load-bearing architectural decision. Clip selection = `transcript → claude -p --output-format json --json-schema → clip list`.

3. **ffmpeg does 100% of the actual editing.** Cut, crop, reframe to 9:16/1:1/16:9, and burn captions are all native ffmpeg operations. No editing library is needed.

4. **Two of the three named repos do not fit and should be dropped.** `video-use` is a cloud-transcription (ElevenLabs) montage editor producing one `final.mp4` — wrong output shape *and* breaks local-first. `hyperframes` renders *synthetic* HTML→video — it does not clip existing footage. Keep `whisper.cpp`; drop the other two. (This must be confirmed with the user before the roadmap locks, per PROJECT.md constraint.)

## Standard Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                    Localhost Web UI (browser)                        │
│   Upload form  →  Job list / progress  →  Clip review + Download     │
└───────────────────────────────┬──────────────────────────────────-─┘
                    HTTP + SSE (progress) │  static file serving (clips)
┌───────────────────────────────┴──────────────────────────────────-─┐
│                      Backend HTTP server (one process)               │
│   - Accepts upload, creates job, returns job_id                      │
│   - Streams stage progress over SSE                                  │
│   - Serves transcripts/clips/thumbnails as static files             │
│                              │                                        │
│   ┌──────────────────────────┴───────────────────────────────────┐  │
│   │            In-process Job Runner (one worker, serial)          │  │
│   │  Stage 1 INGEST   → probe, extract audio (ffmpeg)              │  │
│   │  Stage 2 TRANSCRIBE → whisper.cpp → word-level JSON           │  │
│   │  Stage 3 SELECT   → claude -p (subscription) → clip list      │  │
│   │  Stage 4 RENDER   → ffmpeg ×(N clips × 3 ratios) + captions   │  │
│   └────────────────────────────────────────────────────────────-─┘  │
└───────────────────────────────┬──────────────────────────────────-─┘
                                 │ read / write
┌───────────────────────────────┴──────────────────────────────────-─┐
│                  Local filesystem (the only "database")             │
│   data/<job_id>/  source.mp4  audio.wav  transcript.json            │
│                   clips.json  clips/*.mp4  thumbs/*.jpg  job.json    │
└───────────────────────────────────────────────────────────────────-┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Web UI** | Upload, show job/stage progress, review clips, download | Plain HTML + a little JS, or one small SPA. No framework needed for v1. |
| **HTTP server** | One endpoint to upload+enqueue, one SSE endpoint for progress, static serving of `data/` | FastAPI (Python) or Express/Fastify (Node) — one file |
| **Job runner** | Run the 4 stages serially per job; write status + progress to `job.json`; emit SSE events | A background task/thread in the same process; a simple in-memory queue |
| **Ingest** | Validate file, `ffprobe` duration/streams, extract 16kHz mono WAV for whisper | `ffmpeg`/`ffprobe` subprocess |
| **Transcribe** | Audio → timestamped (word-level) transcript | `whisper.cpp` subprocess, `-oj` JSON output, Metal on by default on Apple Silicon |
| **Select (Claude)** | Transcript → list of `{start, end, title, reason}` clip specs | `claude -p` non-bare subprocess, `--output-format json --json-schema`, transcript piped/passed as file |
| **Render** | For each clip × {9:16, 1:1, 16:9}: cut, crop/reframe, burn captions, write thumbnail | `ffmpeg` subprocess (`trim`/`-ss -to`, `crop`, `subtitles`/`ass` filter) |
| **Storage** | Canonical job state + all artifacts on disk under `data/<job_id>/` | Plain files; `job.json` is the source of truth |

## Recommended Project Structure

Python is the recommended backend (rationale below). Node is a fine alternative; the shape is identical.

```
content-machine/
├── app/
│   ├── server.py          # HTTP routes: POST /jobs, GET /jobs/:id, GET /jobs/:id/events (SSE), static
│   ├── jobs.py            # Job model, in-memory queue, status persistence to job.json
│   ├── pipeline/
│   │   ├── ingest.py      # ffprobe + extract audio.wav
│   │   ├── transcribe.py  # whisper.cpp wrapper → transcript.json
│   │   ├── select.py      # claude -p wrapper → clips.json
│   │   └── render.py      # ffmpeg cut/crop/caption per clip per ratio
│   ├── ffmpeg.py          # thin subprocess helpers (run, probe, progress parse)
│   └── captions.py        # transcript.json → .ass/.srt for a given clip window
├── web/
│   ├── index.html         # upload → job list
│   └── review.html        # clip grid, preview, download buttons
├── data/                  # all jobs live here (gitignored)
│   └── <job_id>/ ...
├── bin/                   # whisper.cpp binary + model (or symlink), checked location
└── pyproject.toml
```

### Structure Rationale

- **`pipeline/` = one file per stage.** Each stage is a pure-ish function `(job_dir) -> writes artifact, returns next input`. This is what makes the build order map cleanly onto phases — each file is testable in isolation with a fixture video.
- **`ffmpeg.py` centralizes all subprocess calls.** One place to parse `-progress` output for percent-done, one place to handle errors. (ponytail: avoids repeating subprocess boilerplate in ingest/render.)
- **`data/<job_id>/` is the database.** No SQLite needed for v1 — there is one user and a handful of jobs. `job.json` holds status; the directory listing *is* the job list. Add SQLite only if/when you want search across many jobs.
- **`web/` is static.** Served by the same backend. No build step, no bundler for v1.

## Architectural Patterns

### Pattern 1: Staged pipeline with a single serial worker

**What:** Jobs run through 4 ordered stages. One worker processes one job at a time. Each stage writes its artifact to `data/<job_id>/` and updates `job.json` (`stage`, `percent`, `status`).
**When to use:** Single-user local tools where total throughput doesn't matter but observability does.
**Trade-offs:** No parallelism across jobs (fine — one user). Huge simplicity win: any stage can be re-run from its predecessor's artifact, so a crash in RENDER doesn't force re-transcription.

**Example:**
```python
STAGES = [ingest, transcribe, select, render]

def run_job(job):
    for stage in STAGES:
        update_job(job, stage=stage.__name__, status="running")
        stage(job.dir)              # writes its artifact under job.dir
    update_job(job, status="done")
```

### Pattern 2: Subprocess-per-tool with progress parsing

**What:** whisper.cpp, ffmpeg, and Claude are all external processes invoked via subprocess. Long stages (transcribe, render) parse the tool's own progress output to update `percent`.
**When to use:** Whenever the heavy lifting is a mature CLI — don't wrap it in a library binding you'll have to maintain.
**Trade-offs:** You manage processes (timeouts, non-zero exit, stderr). In exchange you get the fastest, best-supported implementation for free, and ffmpeg/whisper.cpp updates are just a binary swap.

**Example (Claude selection — the constraint-critical call):**
```python
# NON-bare so it uses the subscription (keychain OAuth), NOT an API key.
proc = subprocess.run(
    ["claude", "-p", SELECT_PROMPT,
     "--output-format", "json",
     "--json-schema", CLIP_SCHEMA,        # enforces [{start,end,title,reason}]
     "--allowedTools", ""],               # transcript is in the prompt; no tools needed
    input=transcript_text, capture_output=True, text=True, timeout=300,
)
clips = json.loads(proc.stdout)["structured_output"]["clips"]
```

### Pattern 3: Server-Sent Events for progress (not polling, not WebSocket)

**What:** The UI opens `GET /jobs/:id/events`; the server pushes `{stage, percent}` as the job runs. One-directional, text, auto-reconnect, native `EventSource` in the browser.
**When to use:** Progress streams from server → browser with no client→server channel needed. Exactly this case.
**Trade-offs:** SSE is simpler than WebSocket and needs no extra dependency. Polling `GET /jobs/:id` every 2s is an even lazier fallback that is totally acceptable for v1 if SSE adds friction. (ponytail: start with polling, upgrade to SSE only if the progress bar feels laggy.)

## Data Flow

### Request Flow

```
[User picks file, clicks Upload]
        ↓  POST /jobs (multipart)
[server.py] saves source.mp4 → creates data/<job_id>/ → enqueues job → returns job_id
        ↓
[UI] opens EventSource /jobs/<job_id>/events  (or polls /jobs/<job_id>)
        ↓
[job runner]  ingest → transcribe → select → render   (each emits stage+percent)
        ↓
[UI] on status=done → GET /jobs/<job_id> → renders clip grid from clips.json
        ↓  user clicks Download on a clip/ratio
[server.py] serves data/<job_id>/clips/<clip>_<ratio>.mp4 (static)
```

### Stage Data Flow (artifact handoff)

```
source.mp4 ──ingest──▶ audio.wav, meta(duration,fps,resolution)
audio.wav  ──transcribe(whisper.cpp)──▶ transcript.json  (segments + word timings)
transcript.json ──select(claude -p)──▶ clips.json  [{id,start,end,title,reason}]
clips.json + source.mp4 + transcript.json ──render(ffmpeg)──▶
        clips/<id>_9x16.mp4, <id>_1x1.mp4, <id>_16x9.mp4, thumbs/<id>.jpg
```

### Key Data Flows

1. **Captions are derived per-clip, not global.** RENDER slices `transcript.json` to each clip's `[start,end]` window, rebases timestamps to zero, writes a temporary `.ass`/`.srt`, and burns it with ffmpeg's `subtitles`/`ass` filter. `.ass` is preferred over `.srt` because it allows the large, centered, high-contrast styling LinkedIn silent-autoplay clips need.
2. **Reframing is a crop, not a letterbox.** 9:16 and 1:1 from a 16:9 source = `crop` filter (center crop, or a fixed framing). v1: center crop. (PITFALLS will cover speaker-tracking as a deliberate non-goal for v1.)
3. **`job.json` is written after every stage**, so a restart shows correct state and any stage can resume from the prior artifact.

## Suggested Build Order (maps to COARSE phases)

The pipeline's dependency chain *is* the build order. Each phase ends with something runnable.

| Phase | Name | Delivers | Depends on | Quality gate |
|-------|------|----------|------------|--------------|
| **1** | **Pipeline spine (CLI, no UI)** | `ingest → transcribe` working from the command line: drop a video, get `transcript.json`. whisper.cpp built with Metal, ffmpeg audio extraction, `data/<job_id>/` layout established. | — | Run on a real video, get correct word-level transcript |
| **2** | **Clip selection via Claude (subscription)** | `select` stage: transcript → `clips.json` using **non-bare** `claude -p` + json-schema. Prompt that returns 15–90s clip windows with titles/reasons. | P1 (needs transcript) | `clips.json` with sane, on-topic segments from real transcript |
| **3** | **Render: cut + reframe + captions** | `render` stage: each clip → 9:16, 1:1, 16:9 with burned `.ass` captions + thumbnail. ffmpeg crop/trim/subtitles. | P1 (source+timing), P2 (clip list) | Watchable, correctly-captioned clips in all 3 ratios on disk |
| **4** | **Localhost UI + job runner** | Backend HTTP server wraps the pipeline: upload → progress (poll or SSE) → review grid → download. Serial job runner + `job.json` status. | P1–P3 (wraps the whole pipeline) | End-to-end: upload in browser, watch progress, download chosen clips |

**Why this order:** Each stage consumes the previous stage's artifact, so you cannot build SELECT without a transcript or RENDER without a clip list. Building the UI **last** is deliberate — the UI is a thin wrapper over a pipeline that already works headlessly, which means every hard problem (whisper build, subscription auth, ffmpeg reframing) is solved and tested via CLI before any HTTP code exists. (If you prefer a visible win sooner, P1 and P4-lite can be merged: a one-button upload that just shows the transcript. But the dependency math favors CLI-first.)

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user (v1) | Exactly as above. Serial worker, files on disk, no DB. |
| Small team (later) | Add SQLite for cross-job search; keep files on disk. Add a real queue (e.g. a second worker) only if multiple people submit at once. Move Claude auth to per-user. |
| "Hosted" (out of scope) | Would break local-first (source video would leave the machine). Explicitly a non-goal. |

### Scaling Priorities

1. **First bottleneck: RENDER (CPU-bound ffmpeg, N clips × 3 ratios).** Fix by rendering ratios for a clip in parallel (3 ffmpeg procs) before adding any cross-job concurrency.
2. **Second bottleneck: TRANSCRIBE on long videos.** Fix with a larger whisper model only if accuracy demands it; Metal + base/small is usually enough. Core ML (ANE) gives 2–3x on small/base/medium if needed.

## Anti-Patterns

### Anti-Pattern 1: Using `claude -p --bare` for clip selection

**What people do:** Reach for `--bare` because docs call it the recommended scripted mode.
**Why it's wrong:** `--bare` skips OAuth/keychain and **requires `ANTHROPIC_API_KEY`** — i.e. metered API billing, violating the core subscription constraint.
**Do this instead:** Use default (non-bare) `claude -p`, which uses the `claude login` subscription credentials. Accept that it loads local context; pin behavior with `--append-system-prompt` and `--json-schema`.

### Anti-Pattern 2: Adopting a heavy editing library / the named repos

**What people do:** Wire in `video-use` or `hyperframes` because they were listed.
**Why it's wrong:** `video-use` forces ElevenLabs (cloud) and emits one montage `final.mp4` — wrong output and breaks local-first. `hyperframes` renders synthetic video, not clips of existing footage. Both add large dependencies for capability ffmpeg already has.
**Do this instead:** ffmpeg directly for cut/crop/caption; whisper.cpp for transcription. Confirm dropping the two repos with the user before locking the roadmap.

### Anti-Pattern 3: A database / message broker for one user

**What people do:** Stand up Postgres + Redis + Celery for "the job queue."
**Why it's wrong:** One user, one machine, one job at a time. That stack is pure operational overhead.
**Do this instead:** `data/<job_id>/job.json` as state, an in-process background task as the worker. Add SQLite only when cross-job search is actually wanted.

### Anti-Pattern 4: Building the UI first

**What people do:** Start with the upload page and stub the pipeline.
**Why it's wrong:** Every genuine risk (whisper build on macOS, subscription auth, ffmpeg reframing, caption styling) lives in the pipeline, not the UI. UI-first defers all risk.
**Do this instead:** Make the pipeline correct headlessly (P1–P3), then wrap it (P4).

## Integration Points

### External Tools (all local subprocesses)

| Tool | Integration Pattern | Notes |
|------|---------------------|-------|
| whisper.cpp | subprocess, `-oj` JSON output, `--max-len 1` for word timings | Build with Metal (default on Apple Silicon); ship binary + model under `bin/` |
| ffmpeg / ffprobe | subprocess; parse `-progress pipe:` for percent | Native `crop`, `subtitles`/`ass`, `-ss/-to`. The only editing dependency. |
| Claude Code CLI | subprocess `claude -p`, **non-bare**, `--output-format json --json-schema` | Uses subscription via keychain; assumes `claude login` done once. Returns `total_cost_usd` for visibility (subscription usage). |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Server ↔ Job runner | In-process function call + shared `job.json` | Runner is a background task; server reads status from disk/memory |
| Job runner ↔ Stages | Direct call; artifacts on disk | Each stage idempotent given its input artifact |
| Server ↔ UI | HTTP (upload, status, static) + SSE or polling (progress) | No client→server channel needed beyond upload |

## Open Questions for Roadmap

- **Confirm dropping `video-use` and `hyperframes` with the user** (PROJECT.md holds this constraint pending research — this research says drop both). Roadmap should not assume them.
- **Backend language:** Python (recommended — whisper.cpp/ffmpeg orchestration, easy subprocess, FastAPI SSE) vs Node. Decided in STACK.md, not here; architecture is identical either way.
- **Reframing intelligence:** v1 = center crop. Speaker-aware crop (face/active-speaker tracking) is a clear future differentiator but a deliberate v1 non-goal.

## Sources

- Claude Code headless docs — https://code.claude.com/docs/en/headless (HIGH; `--bare` requires `ANTHROPIC_API_KEY`, default `-p` uses login/subscription; `--output-format json`, `--json-schema`, `--append-system-prompt`, `--allowedTools`)
- whisper.cpp — https://github.com/ggml-org/whisper.cpp (HIGH; JSON/SRT/VTT output, word-level timestamps via `--max-len`, Metal default on Apple Silicon, Core ML optional)
- browser-use/video-use — https://github.com/browser-use/video-use (MEDIUM; ElevenLabs cloud transcription, montage `final.mp4` output — poor fit)
- heygen-com/hyperframes — https://github.com/heygen-com/hyperframes (MEDIUM; HTML→MP4 synthetic renderer, not a clip editor — no fit)
- ffmpeg filters (`crop`, `subtitles`/`ass`, `-ss/-to`, `-progress`) — standard, mature (HIGH)

---
*Architecture research for: local-first AI video-clipping pipeline (macOS)*
*Researched: 2026-06-29*
