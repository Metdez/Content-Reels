---
gsd_state_version: '1.0'
status: planning
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

**Core value:** Drop in one video and get back several genuinely good, caption-burned clips in 9:16/1:1/16:9 — locally, no cloud, no per-token API cost.
**Current focus:** Phase 1 — Pipeline Spine (ingest + transcribe)

## Current Position

Phase: 1 of 4 (Pipeline Spine — Ingest + Transcribe)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-06-29 — ROADMAP.md created (4 phases, coarse), 20/20 requirements mapped

Progress: [░░░░░░░░░░] 0%

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
