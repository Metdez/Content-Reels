---
gsd_state_version: '1.0'
status: complete
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

**Core value:** Drop in one video and get back several genuinely good, caption-burned clips in 9:16/1:1/16:9 — locally, no cloud, no per-token API cost.
**Current focus:** v1.0 COMPLETE — all 4 phases built, verified live, committed.

## Current Position

Phase: 4 of 4 complete (milestone v1.0 delivered)
Status: Complete — end-to-end pipeline verified on real binaries
Last activity: 2026-06-29 — Phases 1-4 built + verified; 27 tests pass; full upload→transcribe→select→render→download flow proven live

Progress: [██████████] 100%

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
