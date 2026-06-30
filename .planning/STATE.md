---
gsd_state_version: '1.0'
status: complete
milestone: v2
progress:
  total_phases: 8
  completed_phases: 8
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

**Core value:** Drop in one video and get back several genuinely good, caption-burned clips in 9:16/1:1/16:9 — locally, no cloud, no per-token API cost.
**Current focus:** Milestone v2 — Cross-platform (Windows) + interactive crop preview + UI polish + guaranteed audio. v1.0 (phases 1-4) complete.

## Current Position

Milestone: v2 — Cross-Platform + Interactive Crop Preview (autonomous)
Phase: 8 of 8 complete — milestone delivered
Status: Phases 5-8 built + verified live on Windows via browser. Full EnlayeParis.mp4 (13:39) run end-to-end: upload→preview→run→transcribe→6 clips→18 outputs (all aac audio, correct dims), captions fit all ratios, reframe re-renders with audio.
Last activity: 2026-06-29 — branch feat/windows-port-crop-preview; commits 0889a5c (P5), 4839aef (P6-8)

Progress: [██████████] 100% (8/8 phases)

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

- Engine locked: whisper.cpp (transcribe) + ffmpeg (cut/crop/assemble) + hyperframes (animated captions in v1). video-use is a pattern reference only, not a dependency.
- Clip selection = non-bare `claude -p` on the subscription only — no API-key fallback in v1. Cached by transcript hash. Accepted risk: shared subscription limits + ToS gray area on scripted access.
- v1 reframe = center crop + manual x-offset; captions segment-level; cuts snap to sentence boundaries (CV speaker-tracking and word-level karaoke deferred to v2).
- CLI-first: phases 1–3 are a headless pipeline; phase 4 wraps it in a localhost UI. Local-first: nothing leaves the machine (files on disk + optional SQLite).

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 2: `claude -p` subscription invocation contract + selection prompt are load-bearing unknowns — flag for `--research-phase`. Accepted ToS/ban risk on scripted subscription use; keep `select_clips()` seam swappable, invoke at most once per video, log spend.
- Phase 3: hyperframes overlay-compositing workflow is under-researched — flag for research; ffmpeg ASS burn-in is the proven fallback.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-29 16:33
Stopped at: ROADMAP.md and STATE.md created; requirements traceability confirmed (20/20 → P1-P4)
Resume file: None
