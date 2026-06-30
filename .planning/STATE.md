---
gsd_state_version: 1.0
milestone: v5
milestone_name: — Editing UX Revamp
status: planning
last_updated: "2026-06-30T12:40:07.694Z"
last_activity: 2026-06-30
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

**Core value:** Drop in one video and get back several genuinely good, caption-burned clips in 9:16/1:1/16:9 — locally, no cloud, no per-token API cost.
**Current focus:** Milestone v5 — Editing UX Revamp (background re-render + live progress, direct-manipulation framing, flow polish). Phases 17–19. v1.0–v4 complete and verified live.

## Current Position

Phase: 17 of 19 complete
Plan: —
Status: Phase 17 (Background Re-render + Live Editor Progress) built + verified live in the browser on EnlayeParis.mp4 (clip 1). Next: Phase 18 (direct-manipulation framing + magnifier).
Last activity: 2026-06-30 — Phase 17 complete (EDITUX-01..04)

### Verified live (v5, Windows 11, real ffmpeg/NVENC + browser)

- P17 background re-render: `save_clip_edit` now enqueues onto a per-clip worker thread (`_RERENDER` tracker + `_enqueue_rerender` + `_rerender_worker`) and returns immediately — the editor never blocks. New `GET /clip/{idx}/rerender-status` exposes per-aspect state; `editor.html` polls it (600ms), shows an overall bar + per-aspect cards (queued/rendering/done/error) and drops each rendered output `<video>` in place as its ratio finishes. Aspects encode serially (1 NVENC engine): one "rendering", rest "queued", promoted on each completion. An edit made mid-render queues (single in-flight + 1 pending slot) and runs after — verified live: all-3 render showed `9:16 rendering · 1:1,16:9 queued` → progressed one-by-one; a second edit fired mid-flight set `queued:true` and ran after gen-1, nothing lost. `rerender_one` gained an `on_aspect_done` passthrough. 56 tests pass (+queue regression test).

### Verified live (v4, Windows 11, RTX 5060 + real binaries + ffprobe)

- P13 hwaccel core: select_encoder() probes encoders once + caches; picks nvenc on this machine; build_render_cmd emits the GPU tail on all paths; a real 9:16 render = valid 1080×1920 h264 + aac + faststart; CM_FORCE_CPU=1 → x264 parity; _run_encode auto-retries on libx264 if a GPU encode fails (unit-tested). 60s clip: NVENC 7.85s vs x264 10.68s = 1.36×.
- P14 Windows enablement: setup.ps1 pins NVENC-capable ffmpeg 7.1 (master needs driver ≥610; 591.74 only has the older API — 7.1 NVENC verified) + self-migrates an old build. scripts/benchmark.py times GPU-vs-CPU render + ffprobe-validates + times CPU transcribe. **CUDA whisper DROPPED (data): prebuilt cuBLAS 12.4 is ~40× slower than CPU on Blackwell — Windows transcribe stays CPU BLAS (~9× realtime); ACCEL-02/SAFE-02 deferred.**
- P15 macOS tuning: videotoolbox profile + Metal whisper; probe+fallback unit-tested with a stubbed Mac (picks h264_videotoolbox on darwin, falls back to x264 if absent) — untestable Mac path can't break.
- P16 branch split: windows-optimized + mac-optimized forked off the shared core (differ only in the README platform banner), each one-command quickstart, both pushed to github.com/Metdez/Content-Reels.

### Also fixed this session (regressions, verified live in-browser)

- Run crash (`transcript.json not found`): transcribe() re-derived a content-hash job id and wrote the transcript to the wrong dir while the pipeline ran under the per-upload nonce id — threaded the running Job into transcribe(). Verified: Run completes end-to-end, all 3 ratios render.
- Preview flashing: drawOut() sized the frame from its own mutated width (oscillated at the height cap) — size from the stable parent column. Verified: frame steady at 315px across 40 frames, canvas live.

### Verified live (v3, Windows 11, real binaries + browser + ffprobe)

- P9 transform model: compute_crop gains zoom + x/y pan; back-compat (8 prior render tests unchanged); 6 new unit tests. JS mirror is pixel-accurate (9:16 zoom2 → 202×360px).
- P10 pre-run preview: per-aspect zoom/pan with live WYSIWYG output frame; copy-to-all; slack-aware slider disable; transforms persist to run_params. Browser-verified pixel-parity with the renderer.
- P11 progress: weighted master bar + per-section bars; whisper-% transcribe; render per-aspect-per-clip counts; indeterminate select; screenshotted at 4 states (transcribe 35%, select indeterminate, render 2/6=67%, complete 100%).
- P12 clip editor: /job/{id}/clip/{idx}/edit — trim (snap-to-sentence), per-aspect reframe (+copy-to-all), caption text/timing edit + toggle, audio mute/volume; non-destructive edit.json; per-aspect re-render. EnlayeParis clip 1 trimmed 21.74s→13.78s across all 3 ratios (all aac, vol 0.8), mute drops audio stream, captions auto-re-derive, edit.json round-trips.

### v3 phase map (Phases 9–12)

- P9 Per-Aspect Transform Model + Crop Math — replace scalar `x_offset` with `{zoom, x, y}` per aspect in `render.compute_crop`; back-compat shim for old `x_offset` runs; unit tests (ZOOM-01/02/03)
- P10 Pre-Run Preview Upgrade — per-aspect zoom + x/y pan controls with live CSS preview mirroring the Python crop math; transforms become run defaults (ZOOM-04/05). Depends on P9.
- P11 Progress System — real transcribe % (whisper-cli) + render per-aspect-per-clip counts; weighted master + per-section bars; clips surface as they finish; Playwright-verified (PROG-01/02/03/04). Orthogonal to P9/P10.
- P12 Focused Clip Editor — `/job/{id}/clip/{idx}/edit`: trim (snap-to-sentence), per-aspect reframe (+copy-to-all), caption text/timing + toggle, audio keep/mute/volume; non-destructive `edit.json`; per-aspect re-render (EDIT-01..06). Depends on P9 + P10.

### Verified live (v2, Windows 11, real binaries + browser)

- P5 Windows port: transcribe(whisper-cli.exe) + select(claude.CMD) + render(ffmpeg) end-to-end; 28 tests pass
- P6 crop preview: upload stages → preview crop box+slider (matches compute_crop) → Run propagates x_offset
- P7 UI: studio redesign, stage stepper, clean live log (UTF-8)
- P8 audio+captions+reframe: 18/18 outputs have aac audio; uniform captions fit 9:16/1:1/16:9; reframe re-renders left/right with audio intact
- Full EnlayeParis.mp4: 6 clips selected with strong hooks, all 3 ratios each, thumbnails in review grid

### How to run

- `bash scripts/setup.sh` (one-time), then `content-machine serve` → http://127.0.0.1:8000
- CLI: `content-machine ingest <video>` → `select <job_id>` → `render <job_id>`

### Verified live

- P1 transcription correct on known-content video + VAD on silence + caching
- P2 `claude -p` selection (subscription) returns boundary-snapped clips + caching
- P3 3 aspect ratios + visible captions + thumbnails
- P4 web upload→progress→review→reframe→download

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v3 framing model: replace the single scalar `run_params.x_offset` with a per-aspect transform `{zoom≥1, x∈[-1,1], y∈[-1,1]}`; each clip can override per aspect. Back-compat shim maps old `x_offset` → `{zoom:1, x:x_offset, y:0}` so v2 jobs/manifests keep rendering. (Phase 9)
- v3 live preview: the browser CSS-transform preview and the ffmpeg crop must share ONE crop-math definition (mirror/expose `render.compute_crop`) — divergence is the main risk, gated by a pixel-parity criterion. (Phases 10, 12)
- v3 editor scope: focused per-clip tool (trim, reframe, captions, audio) with non-destructive `edit.json` and per-aspect re-render — explicitly NOT a multi-track NLE (out of scope by decision). (Phase 12)
- v3 progress: drive the transcribe bar off real whisper-cli stderr %, render bar off deterministic `len(clips)×len(aspects)`; reuse polling-over-`job.json` (`update_stage`) before reaching for SSE. (Phase 11)
- Engine locked: whisper.cpp (transcribe) + ffmpeg (cut/crop/assemble) + Pillow PNG / hyperframes (captions). video-use is a pattern reference only, not a dependency.
- Clip selection = non-bare `claude -p` on the subscription only — no API-key fallback. Cached by transcript hash.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 9: `x_offset` back-compat shim is load-bearing — live v2 jobs carry scalar `x_offset` in `render.json` run_params; `compute_crop`'s `(crop_w, crop_h, x, y)` return signature must stay stable so `crop_scale_filter`/`build_render_cmd` keep working.
- Phase 10/12: JS↔Python crop-math divergence is the recurring risk — share one definition, verify pixel parity on EnlayeParis.mp4.
- Phase 11: whisper-cli stderr progress format needs a quick parse spike before planning.
- Phase 12: per-aspect dirty-tracking ("only changed aspects re-encode") and the `edit.json` schema are the load-bearing unknowns — worth a short spike/`--research-phase`.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Reframe | REFRAME-01 speaker-aware auto-reframe (CV/active-speaker) | Deferred (v2 backlog) | v1 |
| Captions | CAPS-01 word-level karaoke (forced alignment) | Deferred (v2 backlog) | v1 |
| Distribution | DIST-01/02/03 API-key fallback, LinkedIn publish, batch queue | Deferred | v1 |

## Session Continuity

Last session: 2026-06-30
Stopped at: v3 ROADMAP.md appended (Phases 9–12); REQUIREMENTS.md v3 traceability confirmed (15/15 → P9–P12); STATE.md total_phases set to 4
Resume file: None — next is `/gsd-plan-phase 9`
